#!/usr/bin/env python3
# ======================================================================
# AI/AiOps.py
#   · GPT wrapper (AiOps)
#   · AiOpsMarkdownExtended – DB ↔ GPT ↔ DB helper
#       ▸ resume with start_id
#       ▸ per-row commit
#       ▸ fault-tolerant loop
#       ▸ processes ONLY descriptions that already contain Markdown/HTML
#       ▸ **no schema alteration**
# ======================================================================

from __future__ import annotations

import json
import re
import sys
from typing import Dict, Tuple

import psycopg2.extras                         # type: ignore

from AI.ConnectAI         import ConnectAI
from AI.AiParams          import AiParams
from Databases.ConnectDB  import ConnectDB
from Databases.DbParams   import postgresql_config

# ──────────────────────────────────────────────────────────────────────
#  PART A – tiny GPT wrapper
# ---------------------------------------------------------------------


class AiOps:
    """Generate a single Markdown response via GPT-4o."""

    def __init__(self, connector: ConnectAI):
        self.connector = connector

    def generate_response(self, user_input: str) -> str:
        try:
            resp = self.connector.client.responses.create(
                model="gpt-4o-mini",
                instructions=AiParams.SYSTEM_PROMPT,
                input=AiParams.USER_PROMPT_TEMPLATE.format(user_text=user_input),
            )
            return resp.output_text.strip()
        except Exception as exc:                    # pragma: no cover
            print(f"[AiOps] OpenAI error: {exc}", file=sys.stderr)
            return user_input.strip()


# ──────────────────────────────────────────────────────────────────────
#  PART B – bulk DB helper
# ---------------------------------------------------------------------

_LANG_ORDER: Tuple[str, ...] = ("fr", "en", "it", "es", "de", "ca")
_RE_MANY_BLANKS              = re.compile(r"\n{3,}")

# extra patterns and markdown/html patterns from AiOps.py
_EXTRA_PATTERNS = (
    r"(?m)^[ \t]*L#\b",   # classic Camptocamp “L# …” pitch rows
    r"\r",                # stray CR
    r"\n",
)
_MD_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I | re.M)
    for p in (
        # existing rules...
        r"^\s*#{1,6}\s+\S",
        r"^\s*>\s+",
        r"^\s*[*+-]\s+\S",
        r"^\s*\d+\.\s+\S",
        r"```",
        r"\|.*\|.*\|",
        r"\[.+?\]\(.+?\)",
        r"__\S+?__|\*\*\S+?\*\*",
        r"(?<!\*)\*\w[^*]+\*",
        r"`[^`]+`",
        r"^\s*([-_*] ?){3,}\s*$",
        r"<h[1-6][ >]",
        r"<(ul|ol|li)[ >]",
        r"<table[ >]|<tr[ >]|<td[ >]",
        # new rules
        *_EXTRA_PATTERNS,
    )
)


def _normalise(text: str) -> str:
    """CRLF → LF, trim, collapse ≥3 blank lines to exactly 2."""
    txt = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return _RE_MANY_BLANKS.sub("\n\n", txt)


def _has_markdown(txt: str) -> bool:
    """True ⇢ description already contains markup worth sending to GPT."""
    txt = _normalise(txt)
    return any(p.search(txt) for p in _MD_PATTERNS)


class AiOpsMarkdownExtended:
    """
    Re-format `route.description` JSON **only when it already contains
    Markdown / HTML cues**; skips plain-text descriptions to save tokens.

    NOTE  No schema creation / alteration is performed.
    Make sure `ai_reformatted_description` (jsonb) already exists, or adapt
    the UPDATE statement accordingly.
    """

    def __init__(
        self,
        lang_order: Tuple[str, ...] = _LANG_ORDER,
        *,
        start_id: int | None = None,
    ) -> None:
        self.lang_order = lang_order
        self.start_id   = start_id or 1
        self.gpt        = AiOps(ConnectAI())

    @staticmethod
    def _parse_description(blob: str | dict) -> Dict[str, str]:
        if isinstance(blob, dict):
            return {k: str(v) for k, v in blob.items()}
        try:
            js = json.loads(blob or "{}")
            return {k: str(v) for k, v in js.items()} if isinstance(js, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _process_block(self, raw: str, rid: int, lang: str) -> str:
        md = self.gpt.generate_response(raw)
        md = _normalise(md)
        print(f"[Route {rid}·{lang}] {len(raw)} → {len(md)} chars")
        return md

    def produceMarkdownForRoute(
        self,
        route_id: int,
        *,
        dry_run: bool = False,
    ) -> None:
        conn = ConnectDB(**postgresql_config).connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT description FROM route WHERE id = %s", (route_id,))
                row = cur.fetchone()
                if not row:
                    print(f"[Route {route_id}] not found.")
                    return

            raw_desc = self._parse_description(row["description"])
            if not raw_desc:
                print(f"[Route {route_id}] description JSON empty.")
                return

            result_map: Dict[str, str] = {}
            for lang in self.lang_order:
                txt = raw_desc.get(lang, "").strip()
                if not txt or not _has_markdown(txt):
                    continue

                # 1st GPT pass
                md = self._process_block(txt, route_id, lang)

                # if the GPT-ed text still contains an L# marker, retry once
                if re.search(r"\bL#\b", md):
                    print(f"[Route {route_id}·{lang}] L# still present, retrying GPT...")
                    md = self._process_block(txt, route_id, lang)

                result_map[lang] = md

            if not result_map:
                print(f"[Route {route_id}] no markdown detected – skipped.")
                return

            if dry_run:
                preview = json.dumps(result_map, ensure_ascii=False)[:120]
                print(f"[DRY-RUN] {route_id} → {preview} …")
                return

            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE route
                       SET ai_reformatted_description = %s::jsonb
                     WHERE id = %s
                    """,
                    (json.dumps(result_map, ensure_ascii=False), route_id),
                )
                conn.commit()
                print(f"[Route {route_id}] updated.")

        finally:
            conn.close()

    def produceMarkdownInBulk(
        self,
        *,
        skip:  bool       = True,
        limit: int | None = None,
        dry_run: bool     = False,
    ) -> None:
        conn = ConnectDB(**postgresql_config).connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id,
                           description,
                           ai_reformatted_description
                      FROM route
                     WHERE status = '1'
                       AND id >= %s
                     ORDER BY id
                    """,
                    (self.start_id,),
                )
                rows = cur.fetchall()

            processed = updated = failed = 0
            for row in rows:
                if limit is not None and processed >= limit:
                    break
                processed += 1
                rid = row["id"]

                try:
                    if skip and row["ai_reformatted_description"] not in (
                        None, {}, "{}", ""
                    ):
                        continue

                    raw_desc = self._parse_description(row["description"])
                    if not raw_desc:
                        continue

                    result_map: Dict[str, str] = {}
                    for lang in self.lang_order:
                        txt = raw_desc.get(lang, "").strip()
                        if not txt or not _has_markdown(txt):
                            continue

                        # 1st GPT pass
                        md = self._process_block(txt, rid, lang)

                        # retry if still contains L#
                        if re.search(r"\bL#\b", md):
                            print(f"[Bulk] route {rid}·{lang}: L# detected, retrying GPT...")
                            md = self._process_block(txt, rid, lang)

                        result_map[lang] = md

                    if not result_map:
                        continue

                    if dry_run:
                        print(f"[DRY-RUN] id {rid} → {list(result_map)}")
                        continue

                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE route
                               SET ai_reformatted_description = %s::jsonb
                             WHERE id = %s
                            """,
                            (json.dumps(result_map, ensure_ascii=False), rid),
                        )
                        conn.commit()
                        updated += cur.rowcount

                except Exception as exc:
                    conn.rollback()
                    failed += 1
                    print(f"[Bulk] route {rid} failed: {exc}", file=sys.stderr)

            msg = f"[Bulk] processed {processed} — updated {updated}"
            if failed:
                msg += f" — failed {failed}"
            if dry_run:
                msg += " (DRY-RUN)"
            print(msg)

        finally:
            conn.close()
