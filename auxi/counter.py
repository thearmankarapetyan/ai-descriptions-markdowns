#!/usr/bin/env python3
# counter.py  — version robuste (None-safe, gros champs CSV, estimation GPT-4o)
"""
Analyse de route.csv pour :
  1) Volume global   : nombre de blocs linguistiques traités
  2) Markdown détecté : proportion contenant déjà du Markdown/HTML
  3) Coût & temps     : estimation à partir du nombre de tokens

Usage :
  python3 counter.py route.csv \
        --cost-per-1000 0.02 \
        --time-per-1000 1.5 \
        [--verbose]
"""

import csv
import json
import re
import sys
from argparse import ArgumentParser

# ─── Augmenter la limite de taille pour les champs CSV volumineux ────
_max = sys.maxsize
while True:
    try:
        csv.field_size_limit(_max)
        break
    except OverflowError:
        _max //= 10

# ─── Motifs Markdown / HTML à détecter ───────────────────────────────
MD_PATTERNS = [
    re.compile(r"`"),                   # backticks inline
    re.compile(r"\|.*\|.*\|"),          # tableau Markdown
    re.compile(r"<[hp]>"),              # <p> ou <h> HTML
    re.compile(r"<(ul|ol|li)[ >]"),     # listes HTML
    re.compile(r"```"),                 # bloc code
    re.compile(r"\[.+?\]\(.+?\)"),      # lien Markdown
]

def has_markdown(text: str) -> bool:
    """Retourne True si l’un des motifs MD_PATTERNS apparaît dans text."""
    for pat in MD_PATTERNS:
        if pat.search(text):
            return True
    return False

def count_tokens(text: str) -> int:
    """Approxime le nombre de tokens en comptant les mots."""
    return len(text.split())

def main():
    p = ArgumentParser(description="Stats Markdown GPT sur route.csv")
    p.add_argument("csvfile", help="chemin vers route.csv")
    p.add_argument(
        "--cost-per-1000", type=float, default=0.02,
        help="coût GPT-4o (€) pour 1000 tokens (input+output)"
    )
    p.add_argument(
        "--time-per-1000", type=float, default=1.5,
        help="temps moyen (s) pour traiter 1000 tokens"
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="afficher le détail tokens/md par bloc"
    )
    args = p.parse_args()

    total_blocks = 0
    markdown_blocks = 0
    total_tokens = 0

    with open(args.csvfile, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            # Récupérer la chaîne JSON ou brut
            blob = (row.get("description") or "").strip()
            if not blob:
                continue
            try:
                desc_map = json.loads(blob)
            except json.JSONDecodeError:
                # pas un JSON → traiter en un seul bloc
                desc_map = {"": blob}

            # Parcourir chaque langue ou texte brut
            for lang, txt in desc_map.items():
                txt = (txt or "").strip()   # protège contre None
                if not txt:
                    continue
                total_blocks += 1
                if has_markdown(txt):
                    markdown_blocks += 1
                tok = count_tokens(txt)
                total_tokens += tok
                if args.verbose:
                    md_flag = "✓" if has_markdown(txt) else "×"
                    print(f"[{lang or 'raw'}] {tok} tok, md={md_flag}")

    if total_blocks == 0:
        print("Aucun bloc pertinent trouvé dans le CSV.")
        sys.exit(1)

    # Calculs finaux
    prop_md = markdown_blocks / total_blocks * 100
    cost_total = total_tokens / 1000 * args.cost_per_1000
    time_total = total_tokens / 1000 * args.time_per_1000
    avg_tokens = total_tokens / total_blocks
    avg_time = time_total / total_blocks

    # Affichage des résultats
    print(f"1) Volume global : {total_blocks} blocs linguistiques traités")
    print(f"2) Markdown détecté : {markdown_blocks}/{total_blocks} "
          f"({prop_md:.1f} %) contenaient déjà du Markdown/HTML")
    print("3) Coût & temps estimés :")
    print(f"   • Tokens totaux    : {total_tokens:,}")
    print(f"   • Coût total       : €{cost_total:.2f} "
          f"(à €{args.cost_per_1000:.3f}/1k tokens)")
    print(f"   • Temps total      : {time_total:.1f}s "
          f"(à {args.time_per_1000:.1f}s/1k tokens)")
    print(f"   • Moyenne / bloc   : {avg_tokens:.0f} tokens, {avg_time:.2f}s")

if __name__ == "__main__":
    main()
