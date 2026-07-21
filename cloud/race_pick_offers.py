#!/usr/bin/env python3
"""Liest 'vastai search offers ... --raw' von stdin und gibt die IDs der
argv[1] bevorzugten Angebote aus (eine ID pro Zeile auf stdout, Diagnose
nach stderr) -- fuer race.sh, das mehrere Instanzen parallel mietet.

Wie pick_cheapest_offer.py: erst eine Preisspanne knapp ueber dem
Minimum bilden (nicht stur das billigste Set), darin nach PCIe-
Bandbreite sortieren und einen der bekannt zuverlaessigen Hosts (siehe
Memory 'vastai-reliable-machine' / 'vastai-stamm-instanz') an die erste
Stelle setzen, falls einer vorhanden ist -- das reduziert bei parallelen
race.sh-Laeufen (z.B. fuer mehrere gleichzeitige Cloud-Renders) das
Risiko, auf einem unbekannten Host mit gutem PCIe-Wert aber schlechtem
echten Transfer-Durchsatz zu landen (siehe Maschine 58908)."""
import json
import sys

from machine_stats import blacklisted_machine_ids, favorite_machine_ids

# 55308: zweifach verifiziert (Stamm-Instanz UND eine parallele
# Zweitinstanz auf derselben Maschine) -- Rendern UND Download liefen
# beide Male komplett durch.
# 141151 (Polen): vom User am 15.07. direkt als gut bestätigt.
# NICHT hier eintragen: machine_id 77325
# (Ungarn) -- kurz nach der Miete komplett aus "vastai show instances"
# verschwunden. NICHT mehr hier: machine_id 117811 (Daenemark) -- Rendern
# lief gut, aber der Ergebnis-Download scheiterte beim echten
# Parallel-Renderlauf 2026-07-14 DREIMAL in Folge (haengender Transfer,
# dann zwei Verbindungsabbrueche), am Ende ging eine bereits fertig
# gerenderte Episode verloren, weil die Instanz vor erfolgreichem Download
# geloescht wurde. Siehe Memory 'vastai-stamm-instanz'.
# NICHT MEHR HIER: machine_id 137831 (US, hohe Rechenleistung/Batching-
# Zuverlaessigkeit) -- User will grundsaetzlich nur Ost-/Baltikum-Server
# (Wunsch, nicht Zuverlaessigkeits-Problem). Der 'geolocation in
# [PL,CZ,SK,HU,RO,BG,EE,LV,LT,UA,MD]'-Filter in der Suchanfrage schliesst
# sie ohnehin aus; hier zusaetzlich entfernt, damit sie auch nicht ueber
# einen kuenftig gelockerten Filter wieder hereinrutscht.
KNOWN_RELIABLE_MACHINE_IDS = {55308, 141151}
PRICE_BAND = 1.15

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
offers = json.load(sys.stdin)
if not offers:
    sys.exit("Keine passenden Angebote gefunden — Filter in race.sh lockern.")

blacklisted = blacklisted_machine_ids()
offers = [o for o in offers if o.get("machine_id") not in blacklisted]
if not offers:
    sys.exit("Alle passenden Angebote sind aktuell blacklisted — "
              "cloud/.machine_stats.json prüfen oder abwarten.")

reliable_ids = KNOWN_RELIABLE_MACHINE_IDS | favorite_machine_ids()

min_price = min(o["dph_total"] for o in offers)
candidates = [o for o in offers if o["dph_total"] <= min_price * PRICE_BAND]
candidates.sort(key=lambda o: (o.get("machine_id") not in reliable_ids, -o.get("pcie_bw", 0)))

picked = candidates[:n]
for o in picked:
    tag = " [bekannt zuverlässiger Host]" if o.get("machine_id") in reliable_ids else ""
    print(f"  -> Offer {o['id']}: ${o['dph_total']:.3f}/hr, {o.get('geolocation', '?')}, "
          f"reliability={o.get('reliability2', 0):.2f}, pcie_bw={o.get('pcie_bw', 0):.1f}{tag}",
          file=sys.stderr)
    print(o["id"])
