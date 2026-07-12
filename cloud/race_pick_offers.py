#!/usr/bin/env python3
"""Liest 'vastai search offers ... --raw' von stdin und gibt die IDs der
argv[1] guenstigsten Angebote aus (eine ID pro Zeile auf stdout, Diagnose
nach stderr) -- fuer race.sh, das mehrere Instanzen parallel mietet."""
import json
import sys

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
offers = json.load(sys.stdin)
if not offers:
    sys.exit("Keine passenden Angebote gefunden — Filter in race.sh lockern.")

offers = sorted(offers, key=lambda o: o["dph_total"])[:n]
for o in offers:
    print(f"  -> Offer {o['id']}: ${o['dph_total']:.3f}/hr, "
          f"{o.get('geolocation', '?')}, reliability={o.get('reliability2', 0):.2f}",
          file=sys.stderr)
    print(o["id"])
