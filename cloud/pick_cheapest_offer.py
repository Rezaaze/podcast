#!/usr/bin/env python3
"""Liest 'vastai search offers ... --raw' von stdin und gibt die ID des
bevorzugten Angebots auf stdout aus (Diagnosezeile geht nach stderr,
damit $(...) in rent.sh sauber nur die ID einfaengt).

Nicht einfach das billigste Angebot: reliability/inet_down/inet_up sagen
nichts ueber die tatsaechliche Rechenleistung/den echten Transfer-Durchsatz
aus (zwei Hosts mit derselben GPU koennen durch limitierte PCIe-Anbindung
unterschiedlich schnell rendern, und gemeldete inet_up/inet_down-Werte
koennen mit dem tatsaechlichen Durchsatz zu einem bestimmten Standort --
z.B. dem Mac in Deutschland -- nichts zu tun haben, siehe Memory
'vastai-stamm-instanz': Maschine 58908 mass sich selbst 1.7-2 Gbit/s,
lieferte real aber nur 5-25 KB/s). Deshalb: erst eine Preisspanne knapp
ueber dem Minimum bilden, darin nach PCIe-Bandbreite (Proxy fuer echte
Rechenleistung) sortieren -- und einen der bekannt zuverlaessigen Hosts
(siehe Memory 'vastai-reliable-machine' / 'vastai-stamm-instanz')
bevorzugen, falls einer davon in der Spanne auftaucht. Das haelt die
Renter-Erfahrung planbar, ohne bei jedem Lauf neu Durchsatz-Roulette zu
spielen."""
import json
import sys

# 137831: hohe Rechenleistung/Batching-Zuverlaessigkeit (US).
# 55308: zweifach verifiziert (Stamm-Instanz UND eine parallele
# Zweitinstanz auf derselben Maschine) -- Rendern UND Download liefen
# beide Male komplett durch. NICHT hier eintragen: machine_id 77325
# (Ungarn) -- kurz nach der Miete komplett aus "vastai show instances"
# verschwunden. NICHT mehr hier: machine_id 117811 (Daenemark) -- Rendern
# lief gut, aber der Ergebnis-Download scheiterte beim echten
# Parallel-Renderlauf 2026-07-14 DREIMAL in Folge (haengender Transfer,
# dann zwei Verbindungsabbrueche), am Ende ging eine bereits fertig
# gerenderte Episode verloren, weil die Instanz vor erfolgreichem Download
# geloescht wurde. Siehe Memory 'vastai-stamm-instanz'.
KNOWN_RELIABLE_MACHINE_IDS = {137831, 55308}
PRICE_BAND = 1.15  # bis zu 15% teurer als das billigste Angebot akzeptieren,
                    # wenn es dafuer schneller (hoehere PCIe-Bandbreite) ist

offers = json.load(sys.stdin)
if not offers:
    sys.exit("Keine passenden Angebote gefunden — Filter in rent.sh lockern.")

min_price = min(o["dph_total"] for o in offers)
candidates = [o for o in offers if o["dph_total"] <= min_price * PRICE_BAND]

reliable = [o for o in candidates if o.get("machine_id") in KNOWN_RELIABLE_MACHINE_IDS]
if reliable:
    best = min(reliable, key=lambda o: o["dph_total"])
else:
    best = max(candidates, key=lambda o: o.get("pcie_bw", 0))

price = best["dph_total"]
geo = best.get("geolocation", "?")
reliability = best.get("reliability2", 0)
verification = best.get("verification", "?")
pcie_bw = best.get("pcie_bw", 0)
dlperf = best.get("dlperf", 0)
tag = " [bekannt zuverlässiger Host]" if best.get("machine_id") in KNOWN_RELIABLE_MACHINE_IDS else ""
print(f"  -> Offer {best['id']}: ${price:.3f}/hr, {geo}, reliability={reliability:.2f}, "
      f"verification={verification}, pcie_bw={pcie_bw:.1f}, dlperf={dlperf:.0f}{tag}",
      file=sys.stderr)
print(best["id"])
