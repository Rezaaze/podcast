#!/usr/bin/env python3
"""Liest 'vastai search offers ... --raw' von stdin und gibt die ID des
guenstigsten Angebots auf stdout aus (Diagnosezeile geht nach stderr,
damit $(...) in rent.sh sauber nur die ID einfaengt)."""
import json
import sys

offers = json.load(sys.stdin)
if not offers:
    sys.exit("Keine passenden Angebote gefunden — Filter in rent.sh lockern.")

best = min(offers, key=lambda o: o["dph_total"])
price = best["dph_total"]
geo = best.get("geolocation", "?")
reliability = best.get("reliability2", 0)
verification = best.get("verification", "?")
print(f"  -> Offer {best['id']}: ${price:.3f}/hr, {geo}, reliability={reliability:.2f}, "
      f"verification={verification}",
      file=sys.stderr)
print(best["id"])
