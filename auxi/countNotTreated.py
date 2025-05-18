#!/usr/bin/env python3
# countNotTreated.py – compte et exporte les routes “Markdown détecté” non reformattées

import os
import re
import json
import sys
import pathlib
import psycopg2
from dotenv import load_dotenv

# ─── Patterns supplémentaires qu’on veut traquer ──────────────────
_EXTRA_PATTERNS = (
    r"(?m)^[ \t]*L#\b",   # lignes “L# …”
    r"\r",                # retours chariot errants
    r"\n",                # nouvelles lignes
)
_EXTRA_RE = [re.compile(p) for p in _EXTRA_PATTERNS]

# activités autorisées
ALLOWED_ACTIVITIES = {
    "bouldering",
    "via_ferrata",
    "rock_climbing",
    "ice_climbing",
    "mountain_climbing",
    "snow_ice_mixed",
}

# où écrire la liste d’IDs
OUT_FILE = pathlib.Path("data/ids_not_treated.txt")


def extract_activities(blob):
    """
    Retourne toujours une liste d’activités.
    • Si blob est déjà une list, on la renvoie.
    • Si c’est une chaîne JSON, on la parse.
    • Sinon, []
    """
    if isinstance(blob, list):
        return blob
    if not blob:
        return []
    if isinstance(blob, str):
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            return []
    return []


def pick_lang(desc_blob):
    """
    Choix multilingue FR > EN > IT. Si ce n’est pas du JSON, retourne le texte brut.
    """
    if not desc_blob:
        return ""
    if isinstance(desc_blob, dict):
        return desc_blob.get("fr") or desc_blob.get("en") or desc_blob.get("it") or ""
    if isinstance(desc_blob, str):
        try:
            d = json.loads(desc_blob)
            if isinstance(d, dict):
                return d.get("fr") or d.get("en") or d.get("it") or ""
        except json.JSONDecodeError:
            return desc_blob
    return ""


def has_extra(text):
    """Renvoie True si l’une des _EXTRA_PATTERNS matche dans le texte."""
    for rx in _EXTRA_RE:
        if rx.search(text):
            return True
    return False


def main():
    load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv("HNAME"),
        user=os.getenv("HUSER"),
        password=os.getenv("HPASSWORD"),
        dbname=os.getenv("HDATABASE"),
        port=os.getenv("HPORT"),
    )
    cur = conn.cursor()

    # on récupère toutes les routes actives
    cur.execute("""
        SELECT id, description, activities, ai_reformatted_description
          FROM route
         WHERE status = '1'
    """)
    rows = cur.fetchall()

    total = 0
    matched = 0
    untreated = 0
    untreated_ids = []

    for rid, desc_blob, acts_blob, reformatted in rows:
        # 1) filtre activités
        acts = extract_activities(acts_blob)
        if not any(a in ALLOWED_ACTIVITIES for a in acts):
            continue

        # 2) description texte
        text = pick_lang(desc_blob).strip()
        if not text:
            continue

        # 3) contient un pattern “extra” ?
        if not has_extra(text):
            continue

        total += 1

        # 4) déjà reformatté ?
        if not reformatted or reformatted in ({}, "{}", "[]", ""):
            untreated += 1
            untreated_ids.append(str(rid))
        else:
            matched += 1

    cur.close()
    conn.close()

    # écriture du fichier
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("\n".join(untreated_ids), encoding="utf-8")

    # rapport
    print(f"Total de descriptions contenant les patterns : {total}")
    print(f"  • déjà traitées           : {matched}")
    print(f"  • non traitées (IDs)     : {untreated} → {OUT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"💥  {exc}", file=sys.stderr)
        sys.exit(1)
