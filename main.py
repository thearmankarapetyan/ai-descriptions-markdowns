#!/usr/bin/env python3
# ======================================================================
# main.py – unified CLI for the Markdown tool-chain (resume & append)
# ======================================================================

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from Databases.DbOps import (
    ExportRoutes,
    produceRoutesMarkdownInBulk,
    produceRouteMarkdown,
    gpt_markdown_for_route,
    gpt_markdown_in_bulk,
)
from MarkdownCleaner import clean_route_csv_with_gpt


def _path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


# ──────────────────────────────────────────────────────────────────────
# Command helpers
# ---------------------------------------------------------------------


def cmd_export(ns):
    ExportRoutes(_path(ns.csv))


def cmd_clean(ns):
    clean_route_csv_with_gpt(
        input_csv=_path(ns.input),
        output_csv=_path(ns.output),
        append=ns.append,
        start_id=ns.start_id,
    )


def cmd_db_bulk(ns):
    produceRoutesMarkdownInBulk(
        csv_path=_path(ns.csv),
        skip=ns.skip,
        limit=ns.limit,
        dry_run=ns.dry_run,
    )


def cmd_db_route(ns):
    produceRouteMarkdown(
        route_id=ns.id,
        csv_path=_path(ns.csv),
        dry_run=ns.dry_run,
    )


def cmd_pipeline(ns):
    export_csv = _path(ns.export_csv)
    ExportRoutes(export_csv)

    cleaned_csv = _path(ns.cleaned_csv)
    clean_route_csv_with_gpt(
        input_csv=export_csv,
        output_csv=cleaned_csv,
        append=ns.append,
        start_id=ns.start_id,
    )

    produceRoutesMarkdownInBulk(
        csv_path=cleaned_csv,
        skip=ns.skip,
        limit=ns.limit,
        dry_run=ns.dry_run,
    )


def cmd_gpt_route(ns):
    gpt_markdown_for_route(ns.id, dry_run=ns.dry_run)


def cmd_gpt_bulk(ns):
    gpt_markdown_in_bulk(
        start_id=ns.start_id,
        skip=ns.skip,
        limit=ns.limit,
        dry_run=ns.dry_run,
    )


# ──────────────────────────────────────────────────────────────────────
# Parser
# ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Markdown tool-chain with resume & append support",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # export ---------------------------------------------------------
    sp = sub.add_parser("export", help="dump route table to CSV")
    sp.add_argument("--csv", default="/app/data/route.csv")
    sp.set_defaults(func=cmd_export)

    # clean ----------------------------------------------------------
    sp = sub.add_parser("clean", help="clean raw CSV with GPT")
    sp.add_argument("--input", default="/app/data/route.csv")
    sp.add_argument("--output", default="/app/data/route_cleaned.csv")
    sp.add_argument("--append", action="store_true")
    sp.add_argument("--start-id", type=int, default=1)
    sp.set_defaults(func=cmd_clean)

    # db-bulk --------------------------------------------------------
    sp = sub.add_parser("db-bulk", help="import entire cleaned CSV")
    sp.add_argument("--csv", default="/app/data/route_cleaned.csv")
    sp.add_argument("--no-skip", dest="skip", action="store_false")
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(skip=True, func=cmd_db_bulk)

    # db-route -------------------------------------------------------
    sp = sub.add_parser("db-route", help="import ONE route from CSV")
    sp.add_argument("id", type=int)
    sp.add_argument("--csv", default="/app/data/route_cleaned.csv")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_db_route)

    # pipeline -------------------------------------------------------
    sp = sub.add_parser("pipeline", help="export → clean → DB import")
    sp.add_argument("--export-csv", default="/app/data/route.csv")
    sp.add_argument("--cleaned-csv", default="/app/data/route_cleaned.csv")
    sp.add_argument("--append", action="store_true")
    sp.add_argument("--start-id", type=int, default=1)
    sp.add_argument("--no-skip", dest="skip", action="store_false")
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(skip=True, func=cmd_pipeline)

    # gpt-route ------------------------------------------------------
    sp = sub.add_parser("gpt-route", help="DB → GPT → DB for ONE route")
    sp.add_argument("id", type=int)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_gpt_route)

    # gpt-bulk -------------------------------------------------------
    sp = sub.add_parser("gpt-bulk", help="DB → GPT → DB for MANY routes")
    sp.add_argument("--start-id", type=int, default=None)
    sp.add_argument("--no-skip", dest="skip", action="store_false")
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(skip=True, func=cmd_gpt_bulk)

    return p


# ──────────────────────────────────────────────────────────────────────
# entry-point
# ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    ns = build_parser().parse_args(argv)
    try:
        ns.func(ns)
    except KeyboardInterrupt:  # pragma: no cover
        print("\n[user cancelled]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
