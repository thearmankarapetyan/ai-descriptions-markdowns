#!/usr/bin/env python3
"""
route_dump_to_file.py – dump every column of one route into a JSON file
────────────────────────────────────────────────────────────────────────
• Output file goes to  /app/data/route_<ID>.json   (or another directory
  if you change OUT_DIR below).
• Existing files are overwritten.
• DB remains untouched.
Usage:
    docker exec ai-markdown-app python3 route_dump_to_file.py 19555
"""

from __future__ import annotations
import json, sys, pathlib, psycopg2.extras
from typing import Any

from Databases.ConnectDB import ConnectDB
from Databases.DbParams  import postgresql_config


# ── where to store the dumps -------------------------------------------------
OUT_DIR = pathlib.Path("/app/data")           # change if you prefer elsewhere
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _coerce(val: Any) -> Any:
    """
    Convert JSON / JSONB text to real JSON so the final output is valid.
    For any non-JSON values just return them unchanged (they will be serialised
    by json.dump later).
    """
    if isinstance(val, str):
        t = val.strip()
        if (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]")):
            try:
                return json.loads(t)
            except Exception:
                pass
    return val


def dump_route(rid: int) -> None:
    conn = ConnectDB(**postgresql_config).connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM route WHERE id = %s", (rid,))
            row = cur.fetchone()

        if not row:
            sys.exit(f"Route {rid} not found.")

        # coerce possible JSON strings so the output is valid JSON
        clean_row = {k: _coerce(v) for k, v in row.items()}

        out_file = OUT_DIR / f"route_{rid}.json"
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(clean_row, f, indent=2, ensure_ascii=False)

        print(f"✅  Dumped route {rid} to {out_file}")

    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("Usage: route_dump_to_file.py <route_id>")
    dump_route(int(sys.argv[1]))
