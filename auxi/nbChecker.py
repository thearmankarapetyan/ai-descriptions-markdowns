#!/usr/bin/env python3
"""
nbChecker.py – Combien d’itinéraires restent à formater par l’AI Markdown Tool ?

Critères :
  • status = '1'
  • activités ∈ ALLOWED_ACTIVITIES
  • ai_reformatted_description vide
  • description contenant déjà du Markdown / HTML
"""

from __future__ import annotations

import json
import re
import sys
from argparse import ArgumentParser
from typing import Dict, List, Tuple

import psycopg2.extras

from Databases.ConnectDB import ConnectDB
from Databases.DbParams import postgresql_config

# ---------- paramètres ----------------------------------------------
ALLOWED_ACTIVITIES = {
    "bouldering",
    "via_ferrata",
    "rock_climbing",
    "ice_climbing",
    "mountain_climbing",
    "snow_ice_mixed",
}

_MD_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I | re.M)
    for p in (
        # Markdown « classique »
        r"^\s*#{1,6}\s+\S", r"^\s*>\s+", r"^\s*[*+-]\s+\S", r"^\s*\d+\.\s+\S",
        r"\|.*\|.*\|", r"```", r"\[.+?\]\(.+?\)",
        r"__\S+?__|\*\*\S+?\*\*", r"(?<!\*)\*\w[^*]+\*", r"`[^`]+`",
        # Balises HTML usuelles (votre base en regorge)
        r"<h[1-6][ >]", r"<(ul|ol|li|table|tr|td|th)[ >]",
        r"<p[ >]", r"<br ?/?>", r"<strong[ >]", r"<em[ >]", r"<div[ >]",
    )
)

_RE_MANY_BLANKS = re.compile(r"\n{3,}")


def _normalise(txt: str) -> str:
    txt = txt.replace("\r\n", "\n").replace("\r", "\n").strip()
    return _RE_MANY_BLANKS.sub("\n\n", txt)


def _has_markdown(txt: str) -> bool:
    txt = _normalise(txt)
    return any(p.search(txt) for p in _MD_PATTERNS)


def _activity_matches(raw_val: str | None) -> bool:
    """True si l’activité fait partie du set autorisé."""
    if not raw_val:
        return False
    low = raw_val.lower().strip()
    # JSON list ?
    if low.startswith("["):
        try:
            arr = json.loads(low)
            return any(tok in ALLOWED_ACTIVITIES for tok in arr)
        except Exception:
            pass
    # liste « csv »
    for tok in re.split(r"[;,]", low):
        if tok.strip() in ALLOWED_ACTIVITIES:
            return True
    # valeur simple
    return low in ALLOWED_ACTIVITIES


def _parse_description(blob: str | dict) -> Dict[str, str]:
    if isinstance(blob, dict):
        return {k: str(v) for k, v in blob.items()}
    try:
        js = json.loads(blob or "{}")
        return {k: str(v) for k, v in js.items()} if isinstance(js, dict) else {}
    except json.JSONDecodeError:
        return {}


# ---------- principal ------------------------------------------------
def main(verbose: bool = False) -> None:
    conn = ConnectDB(**postgresql_config).connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id,
                       description,
                       activities::text AS activity_raw,
                       ai_reformatted_description
                  FROM route
                 WHERE status = '1'
                   AND (
                       ai_reformatted_description IS NULL
                    OR ai_reformatted_description::text = '{}'
                    OR ai_reformatted_description::text = ''
                   )
                """
            )
            rows = cur.fetchall()

        pending: List[int] = []

        for row in rows:
            if not _activity_matches(row["activity_raw"]):
                continue

            desc_dict = _parse_description(row["description"])
            if not desc_dict:
                continue

            if any(_has_markdown(txt) for txt in desc_dict.values() if txt.strip()):
                pending.append(row["id"])

        print(f"Routes encore à traiter : {len(pending)}")
        if verbose:
            print("IDs :", ", ".join(map(str, pending)))

    finally:
        conn.close()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="affiche aussi les IDs")
    args = parser.parse_args()
    main(verbose=args.verbose)
