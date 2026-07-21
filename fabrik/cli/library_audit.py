#!/usr/bin/env python3
"""Zeigt Near-Miss-Paare in den serienübergreifenden Asset-Bibliotheken
(Charaktere/Orte/SFX) an, die UNTER der produktiven Fuzzy-Schwelle liegen,
aber ähnlich genug sein könnten, um dieselbe Datei zu verdienen.

Reine Anzeige, KEINE automatische Verschmelzung: Wortmengen-Überlappung kann
einen echten Archetyp-/Konzept-Treffer nicht zuverlässig von zufälliger
Wortüberlappung trennen (Beleg 16.07.2026 — siehe character_library.py::
_archetype_clause: zwei völlig verschiedene Rollen können allein durch eine
geteilte Ethnizitäts-Formulierung in dieselbe Score-Spanne fallen wie ein
echter Archetyp-Treffer). Deshalb entscheidet hier bewusst ein Mensch beim
Lesen der beiden Beschreibungen, nicht ein Schwellenwert.

Verwendung:
  python3 -m fabrik.cli.library_audit characters
  python3 -m fabrik.cli.library_audit locations
  python3 -m fabrik.cli.library_audit sfx --category oneshots
  python3 -m fabrik.cli.library_audit sfx --category ambience
  [--threshold 0.15] [--top 20]

Stdlib-only (wie die *_library.py-Module selbst) — kein .venv nötig.
"""

import argparse

from fabrik.writing import character_library, location_library, sfx_library

# Bewusst weit UNTER den produktiven Schwellen (0.8 Charaktere/Orte, 0.65 SFX)
# — hier soll jeder potenziell interessante Kandidat auftauchen, die
# Bewertung "ist das wirklich dasselbe?" übernimmt der Mensch beim Lesen.
REPORT_THRESHOLD_DEFAULT = 0.15
TOP_DEFAULT = 20


def _pairwise(index, key_fn, sim_fn):
    """index: {hash: entry}. key_fn(entry) -> Vergleichstext, sim_fn(a, b) ->
    Score. Liefert (score, hash_a, entry_a, hash_b, entry_b), absteigend
    sortiert. O(n²) Textvergleiche — bei den bisherigen Bibliotheksgrößen
    (Dutzende bis wenige Hundert Einträge) im Sub-Sekunden-Bereich."""
    items = list(index.items())
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            h1, e1 = items[i]
            h2, e2 = items[j]
            score = sim_fn(key_fn(e1), key_fn(e2))
            if score > 0:
                pairs.append((score, h1, e1, h2, e2))
    pairs.sort(key=lambda p: p[0], reverse=True)
    return pairs


def _print_pairs(pairs, threshold, top, label_a="A", label_b="B"):
    shown = [p for p in pairs if p[0] >= threshold][:top]
    if not shown:
        print(f"  (keine Kandidaten ab Score {threshold} — nichts zu prüfen)")
        return
    for score, h1, e1, h2, e2 in shown:
        print(f"\n  {score:.2f}  {h1}  vs  {h2}")
        print(f"    {label_a}: {e1['description']}")
        print(f"    {label_b}: {e2['description']}")


def audit_characters(threshold, top):
    index = character_library._load_index()
    def key(e):
        return character_library._archetype_clause(e["description"])
    def sim(a, b):
        return character_library._similarity(character_library._tokens(a), character_library._tokens(b))
    print(f"Charakter-Bibliothek: {len(index)} Einträge (Vergleich auf dem Archetyp-Teil vor "
          f"dem ersten ';', Produktiv-Schwelle {character_library.SIMILARITY_THRESHOLD}):")
    _print_pairs(_pairwise(index, key, sim), threshold, top)


def audit_locations(threshold, top):
    index = location_library._load_index()
    def key(e):
        return e["description"]
    def sim(a, b):
        return location_library._similarity(location_library._tokens(a), location_library._tokens(b))
    print(f"Orts-Bibliothek: {len(index)} Einträge (Produktiv-Schwelle "
          f"{location_library.SIMILARITY_THRESHOLD}):")
    _print_pairs(_pairwise(index, key, sim), threshold, top)


def audit_sfx(category, threshold, top):
    index = sfx_library._load_index(category)
    def key(e):
        return e["description"]
    def sim(a, b):
        return sfx_library._similarity(sfx_library._tokens(a), sfx_library._tokens(b))
    prod_threshold = (sfx_library.SFX_REUSE_SIMILARITY_THRESHOLD if category == "oneshots"
                      else "n/a — Fuzzy hier bewusst immer aus, siehe location_ambience.py")
    print(f"SFX-Bibliothek ({category}): {len(index)} Einträge (Produktiv-Schwelle {prod_threshold}):")
    _print_pairs(_pairwise(index, key, sim), threshold, top)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["characters", "locations", "sfx"])
    parser.add_argument("--category", choices=["oneshots", "ambience"], default="oneshots",
                        help="nur für 'sfx': welche Kategorie prüfen (Default: oneshots)")
    parser.add_argument("--threshold", type=float, default=REPORT_THRESHOLD_DEFAULT,
                        help=f"Mindest-Score für die Anzeige (Default {REPORT_THRESHOLD_DEFAULT})")
    parser.add_argument("--top", type=int, default=TOP_DEFAULT,
                        help=f"maximal angezeigte Paare (Default {TOP_DEFAULT})")
    args = parser.parse_args()

    if args.kind == "characters":
        audit_characters(args.threshold, args.top)
    elif args.kind == "locations":
        audit_locations(args.threshold, args.top)
    else:
        audit_sfx(args.category, args.threshold, args.top)

    print("\nHinweis: reine Anzeige, keine automatische Änderung. Hältst du zwei Einträge für "
          "denselben Charakter/Ort/Sound: die Beschreibungen in den betroffenen episodes.json "
          "künftig wortgleich formulieren (dann trifft der exakte Hash beim nächsten Lauf) oder "
          "die Bilddatei/den Sound von Hand unter dem anderen Hash kopieren.")


if __name__ == "__main__":
    main()
