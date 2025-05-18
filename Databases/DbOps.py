#!/usr/bin/env python3
# ======================================================================
# Databases/DbOps.py  –  Markdown project (DDL-free edition)
#   • CSV helpers
#   • GPT helpers with per-row commit & resume
#   Nothing here creates / alters tables or triggers. The DB schema
#   must already contain   route.ai_reformatted_description JSONB NULL.
# ======================================================================

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from Databases.ConnectDB import ConnectDB
from Databases.DbParams  import postgresql_config
from AI.AiOps            import AiOpsMarkdownExtended


# ────────────────────────────────────────────────────────────────
# 1) CSV helpers
# ----------------------------------------------------------------
def ExportRoutes(csv_filename: str | Path) -> None:
    """COPY the whole `route` table to a CSV file."""
    load_dotenv()
    conn = ConnectDB(**postgresql_config).connect()
    try:
        with conn.cursor() as cur, open(csv_filename, "w", encoding="utf-8",
                                        newline="") as fout:
            cur.copy_expert(
                """
                COPY route
                  TO STDOUT
                  WITH CSV HEADER
                  DELIMITER ';'
                  QUOTE '"'
                  ESCAPE '"'
                  ENCODING 'UTF8'
                """,
                fout,
            )
        print(f"[ExportRoutes] → {csv_filename}")
    finally:
        conn.close()


def produceRoutesMarkdownInBulk(
    csv_path: str | Path,
    *,
    skip: bool = True,                 # skip rows whose column is not NULL
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """
    Import reformatted Markdown from a cleaned CSV   (id ; description).

    * commits after each UPDATE so the job is resumable
    * continues on errors (prints them, never aborts the loop)
    """
    load_dotenv()
    conn = ConnectDB(**postgresql_config).connect()

    processed = updated = failed = 0
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as fin:
            reader = csv.DictReader(fin, delimiter=";")

            for row in reader:
                if limit is not None and processed >= limit:
                    break
                processed += 1

                rid_txt = (row.get("id") or "").strip()
                if not rid_txt.isdigit():
                    continue
                rid = int(rid_txt)

                md_json = (row.get("description") or "").strip()
                if not md_json:
                    continue

                if skip:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT ai_reformatted_description "
                            "FROM route WHERE id = %s",
                            (rid,),
                        )
                        if (cur.fetchone() or [None])[0] is not None:
                            continue

                if dry_run:
                    print(f"[CSV-Bulk][DRY-RUN] would update id {rid}")
                    continue

                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE route
                               SET ai_reformatted_description = %s::jsonb
                             WHERE id = %s
                            """,
                            (md_json, rid),
                        )
                        conn.commit()
                        updated += cur.rowcount
                except Exception as exc:
                    conn.rollback()
                    failed += 1
                    print(f"[CSV-Bulk] id {rid} failed: {exc}", file=sys.stderr)

        if not dry_run:
            msg = f"[CSV-Bulk] processed {processed} — updated {updated}"
            if failed:
                msg += f" — failed {failed}"
            print(msg)

    finally:
        conn.close()


def produceRouteMarkdown(
    route_id: int,
    csv_path: str | Path,
    *,
    dry_run: bool = False,
) -> None:
    """Update exactly one route from the cleaned CSV."""
    load_dotenv()
    conn = ConnectDB(**postgresql_config).connect()

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as fin:
            reader = csv.DictReader(fin, delimiter=";")
            for row in reader:
                if (row.get("id") or "").strip() != str(route_id):
                    continue
                md_json = (row.get("description") or "").strip()

                if dry_run:
                    print(f"[Single][DRY-RUN] would set id {route_id}")
                    return

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE route
                           SET ai_reformatted_description = %s::jsonb
                         WHERE id = %s
                        """,
                        (md_json, route_id),
                    )
                    conn.commit()
                    print(f"[Single] route {route_id} updated.")
                return

        print(f"[Single] id {route_id} not found in CSV.")

    finally:
        conn.close()


# ────────────────────────────────────────────────────────────────
# 2) GPT helpers (unchanged)
# ----------------------------------------------------------------
def gpt_markdown_for_route(route_id: int, *, dry_run: bool = False) -> None:
    AiOpsMarkdownExtended().produceMarkdownForRoute(route_id, dry_run=dry_run)


def gpt_markdown_in_bulk(
    *,
    start_id: int | None = None,
    skip: bool = True,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    AiOpsMarkdownExtended(start_id=start_id).produceMarkdownInBulk(
        skip=skip,
        limit=limit,
        dry_run=dry_run,
    )
