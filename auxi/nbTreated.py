#!/usr/bin/env python3
# nbCheckerMarkdown.py
"""
Compte les itinéraires déjà traités par l’AI Markdown Tool.

Critères :
  • status = '1'
  • ai_reformatted_description non NULL et non vide
Affiche :
  - nombre total de routes status='1'
  - nombre et pourcentage de routes traitées
  - nombre total de blocs linguistiques (langues) générés
  - (optionnel) liste des IDs traitées et nb de langues par route

Usage :
  docker compose exec ai-markdown-app \
    python3 nbCheckerMarkdown.py [--verbose]
"""

import sys
from argparse import ArgumentParser

import psycopg2.extras
from Databases.ConnectDB import ConnectDB
from Databases.DbParams import postgresql_config

def main(verbose: bool = False) -> None:
    conn = ConnectDB(**postgresql_config).connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, ai_reformatted_description
                  FROM route
                 WHERE status = '1'
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    total_routes = len(rows)
    treated_routes = 0
    total_blocks = 0
    treated_ids = []

    for row in rows:
        desc = row["ai_reformatted_description"]
        # Vérifier que c'est un dict non vide
        if isinstance(desc, dict) and desc:
            treated_routes += 1
            n_langs = len(desc)
            total_blocks += n_langs
            treated_ids.append((row["id"], n_langs))
            if verbose:
                print(f"[Route {row['id']}] langues traitées : {n_langs}")

    untreated = total_routes - treated_routes
    pct = (treated_routes / total_routes * 100) if total_routes else 0.0

    print(f"Routes status='1' totales   : {total_routes}")
    print(f"Routes déjà traitées        : {treated_routes} ({pct:.1f} %)")
    print(f"Routes non traitées        : {untreated}")
    print(f"Blocs linguistiques générés : {total_blocks}")

    if verbose:
        print("\nDétail des routes traitées :")
        for rid, n in treated_ids:
            print(f"  • id {rid} → {n} langue(s)")

if __name__ == "__main__":
    parser = ArgumentParser(description="Stats AI Markdown Tool")
    parser.add_argument(
        "--verbose", action="store_true",
        help="affiche le détail (IDs et nb de langues par route)"
    )
    args = parser.parse_args()
    main(verbose=args.verbose)
