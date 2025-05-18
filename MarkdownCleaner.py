#!/usr/bin/env python3
"""
Create / update route_cleaned.csv:

  • keeps only rows with status='1' and an allowed activity
  • GPT-cleans each language block
  • APPEND mode so previous rows are preserved
  • start_id to resume

Usage example
-------------
docker compose exec ai-markdown-app \
  python3 main.py clean --append --start-id 8665
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Set

from AI.ConnectAI import ConnectAI
from AI.AiOps import AiOps

# ───────────────────────── configuration ──────────────────────────
INPUT_CSV_PATH: str | Path = "/app/data/route.csv"
OUTPUT_CSV_PATH: str | Path = "/app/data/route_cleaned.csv"

LANG_ORDER = ("fr", "en", "it", "es", "de", "ca")

ALLOWED_ACTIVITIES = {
    "bouldering",
    "via_ferrata",
    "rock_climbing",
    "ice_climbing",
    "mountain_climbing",
    "snow_ice_mixed",
}
# ------------------------------------------------------------------

# allow gigantic CSV fields
_max = sys.maxsize
while True:
    try:
        csv.field_size_limit(_max)
        break
    except OverflowError:
        _max //= 10

_RE_MANY_BLANKS = re.compile(r"\n{3,}")


def _normalise(text: str) -> str:
    txt = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return _RE_MANY_BLANKS.sub("\n\n", txt)


def _gpt(ai_ops: AiOps, raw: str) -> str:
    try:
        return _normalise(ai_ops.generate_response(raw))
    except Exception as exc:  # pragma: no cover
        print(f"[MarkdownCleaner] GPT error, keeping raw: {exc}")
        return _normalise(raw)


def _activity_is_allowed(raw_val: str) -> bool:
    if not raw_val:
        return False
    low = raw_val.lower().strip()
    if low.startswith("["):
        try:
            arr = json.loads(low)
            return any(tok in ALLOWED_ACTIVITIES for tok in arr)
        except Exception:
            pass
    for tok in re.split(r"[;,]", low):
        if tok.strip() in ALLOWED_ACTIVITIES:
            return True
    return low in ALLOWED_ACTIVITIES


# ───────────────────────────── main routine ───────────────────────
def clean_route_csv_with_gpt(
    *,
    input_csv: str | Path = INPUT_CSV_PATH,
    output_csv: str | Path = OUTPUT_CSV_PATH,
    append: bool = False,
    start_id: int = 1,
    lang_order=LANG_ORDER,
) -> None:
    connector = ConnectAI()
    ai_ops = AiOps(connector)

    output_csv = Path(output_csv)
    mode = "a" if append else "w"
    file_exists = output_csv.exists() and output_csv.stat().st_size > 0

    # keep track of ids already present when appending
    existing_ids: Set[str] = set()
    if append and file_exists:
        with open(output_csv, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                existing_ids.add((row.get("id") or "").strip())

    with open(input_csv, "r", encoding="utf-8-sig") as fin, open(
        output_csv, mode, encoding="utf-8", newline=""
    ) as fout:
        reader = csv.DictReader(fin, delimiter=";")
        writer = csv.DictWriter(
            fout,
            fieldnames=["id", "description"],
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
        )
        if not append or not file_exists:
            writer.writeheader()

        total = kept = 0
        for row in reader:
            total += 1

            rid = (row.get("\ufeffid") or row.get("id") or "").strip()
            if not rid or int(rid) < start_id or rid in existing_ids:
                continue

            if (row.get("status") or "").strip() != "1":
                continue

            activity_raw = (
                row.get("activity")
                or row.get("activities")
                or row.get("activity_type")
                or ""
            ).strip()
            if not _activity_is_allowed(activity_raw):
                continue

            try:
                src_dict = json.loads(row.get("description") or "{}")
            except json.JSONDecodeError:
                src_dict = {}

            lang_to_md: dict[str, str] = {}
            for lang in lang_order:
                raw_txt = (src_dict.get(lang) or "").strip()
                if raw_txt:
                    lang_to_md[lang] = _gpt(ai_ops, raw_txt)

            if not lang_to_md:
                continue

            kept += 1
            writer.writerow(
                {
                    "id": rid,
                    "description": json.dumps(
                        lang_to_md, ensure_ascii=False, separators=(",", ":")
                    ),
                }
            )

        print(
            f"[MarkdownCleaner] scanned {total} rows – appended {kept} → {output_csv}"
        )


if __name__ == "__main__":
    clean_route_csv_with_gpt()
