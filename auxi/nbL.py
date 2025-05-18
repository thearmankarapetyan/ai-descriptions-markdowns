#!/usr/bin/env python3
"""
nbL.py – stats on ai_reformatted_description
────────────────────────────────────────────
• How many rows contain “L#” ?
• How many rows have a non-empty JSON value?
• Write all IDs with “L#” to  /app/data/ids_with_Lsharp.txt
"""

import pathlib, sys, psycopg2.extras
from Databases.ConnectDB import ConnectDB
from Databases.DbParams  import postgresql_config

OUT_FILE = pathlib.Path("data/ids_with_Lsharp.txt")

def main() -> None:
    conn = ConnectDB(**postgresql_config).connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # 1) rows whose JSON (as text) contains  L#
            cur.execute(
                """
                SELECT COUNT(*) AS n
                  FROM route
                 WHERE ai_reformatted_description::text ILIKE '%L#%'
                """
            )
            n_lsharp = cur.fetchone()["n"]

            # 2) rows that are not NULL / {} / []
            cur.execute(
                """
                SELECT COUNT(*) AS n
                  FROM route
                 WHERE ai_reformatted_description IS NOT NULL
                   AND ai_reformatted_description::text NOT IN ('{}','[]')
                """
            )
            n_nonempty = cur.fetchone()["n"]

            # 3) collect IDs with L#
            cur.execute(
                """
                SELECT id
                  FROM route
                 WHERE ai_reformatted_description::text ILIKE '%L#%'
                """
            )
            ids = [str(r["id"]) for r in cur.fetchall()]

        # write the file
        OUT_FILE.write_text("\n".join(ids), encoding="utf-8")
        print(f"🔢  rows with “L#”      : {n_lsharp:,}")
        print(f"🔢  non-empty JSON rows : {n_nonempty:,}")
        print(f"💾  {len(ids):,} id(s) written to {OUT_FILE}")

    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"💥  {exc}", file=sys.stderr)
        sys.exit(1)
