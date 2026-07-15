#!/usr/bin/env python3
"""Lernt aus dem tatsächlichen Verlauf gemieteter Instanzen, statt nur auf
die von Hand gepflegte KNOWN_RELIABLE_MACHINE_IDS-Liste zu vertrauen:
Instanzen, die von rent.sh/race.sh (nur der Sieger)/get_ready_instance.sh
(bevorzugte Maschine) gemietet werden, werden hier per record_created()
protokolliert. Beim nächsten Scriptlauf gleicht reconcile() ab, welche
davon inzwischen verschwunden sind (destroyed -- egal ob automatisch durch
ein Script oder von Hand über die vast.ai-Konsole/Website) und klassifiziert
sie NUR über die verstrichene Zeit seit der Miete:

- FAVORITE_THRESHOLD_SECONDS (10 Min) erreicht/überschritten: die Instanz
  wurde tatsächlich nutzbar (kam zum Rendern) -- ihre Maschine wird
  dauerhaft favorisiert (wie KNOWN_RELIABLE_MACHINE_IDS, aber dynamisch).
- Darunter: die Instanz ist nie brauchbar geworden ('gestartet, aber nie
  eine Rückmeldung') -- ihre Maschine kommt für BLACKLIST_DURATION_SECONDS
  (3 Std.) auf die Blacklist, taucht in dieser Zeit in keiner Angebots-
  suche mehr auf (siehe pick_cheapest_offer.py/race_pick_offers.py).

Race.sh-Verlierer werden bewusst NICHT getrackt: die werden immer sofort
nach dem Rennen gelöscht, unabhängig davon, ob sie brauchbar gewesen
wären -- das wäre kein Zeichen einer kaputten Maschine, nur ein
verlorenes Rennen.

Reconcile ist absichtlich lazy (kein Daemon): läuft am Anfang von
rent.sh/race.sh/get_ready_instance.sh, bevor eine neue Suche startet --
holt dabei genau EINMAL 'vastai show instances-v1 --raw', um zu sehen,
welche getrackten Instanzen noch existieren (auch gestoppte -- nur
tatsächlich GELÖSCHTE fehlen dort komplett)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKED_FILE = os.path.join(SCRIPT_DIR, ".tracked_instances.json")
STATS_FILE = os.path.join(SCRIPT_DIR, ".machine_stats.json")

FAVORITE_THRESHOLD_SECONDS = 600      # 10 Minuten
BLACKLIST_DURATION_SECONDS = 10800    # 3 Stunden


def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _load_tracked():
    return _load(TRACKED_FILE, [])


def _load_stats():
    return _load(STATS_FILE, {})


def _current_instance_ids():
    raw = subprocess.run(["vastai", "show", "instances-v1", "--raw"],
                         capture_output=True, text=True, timeout=30)
    if raw.returncode != 0:
        return None
    try:
        data = json.loads(raw.stdout)
    except json.JSONDecodeError:
        return None
    instances = data.get("instances") or []
    return {i.get("id") for i in instances if i.get("id") is not None}


def _machine_id_for(instance_id):
    raw = subprocess.run(["vastai", "show", "instances-v1", "--raw"],
                         capture_output=True, text=True, timeout=30)
    if raw.returncode != 0:
        return None
    try:
        data = json.loads(raw.stdout)
    except json.JSONDecodeError:
        return None
    instances = data.get("instances") or []
    inst = next((i for i in instances if i.get("id") == instance_id), None)
    return inst.get("machine_id") if inst else None


def record_created(instance_id):
    """Von rent.sh/race.sh (Sieger)/get_ready_instance.sh direkt nach
    erfolgreichem 'vastai create instance' aufgerufen."""
    machine_id = _machine_id_for(instance_id)
    if machine_id is None:
        # Instanz noch nicht in der Liste sichtbar (API-Lag) oder API-Fehler --
        # kein Tracking-Eintrag ohne machine_id, aber kein harter Fehler:
        # der Renter-Workflow selbst darf davon nie blockiert werden.
        print(f"  (Tracking übersprungen: machine_id für Instanz {instance_id} "
              f"nicht ermittelbar.)", file=sys.stderr)
        return
    tracked = _load_tracked()
    tracked.append({
        "instance_id": instance_id,
        "machine_id": machine_id,
        "created_at": time.time(),
    })
    _save(TRACKED_FILE, tracked)


def reconcile():
    """Klassifiziert alle getrackten Instanzen, die inzwischen aus der
    vast.ai-Liste verschwunden sind (destroyed), nach verstrichener Zeit."""
    tracked = _load_tracked()
    if not tracked:
        return
    alive_ids = _current_instance_ids()
    if alive_ids is None:
        # vastai-CLI/API gerade nicht erreichbar -- nichts klassifizieren,
        # beim nächsten Lauf erneut versuchen statt falsch zu urteilen.
        return

    stats = _load_stats()
    still_pending = []
    now = time.time()
    for entry in tracked:
        if entry["instance_id"] in alive_ids:
            still_pending.append(entry)
            continue
        machine_id = str(entry["machine_id"])
        elapsed = now - entry["created_at"]
        record = stats.setdefault(machine_id, {})
        if elapsed >= FAVORITE_THRESHOLD_SECONDS:
            record["favorite"] = True
            record.pop("blacklisted_until", None)
            print(f"  ✓ Maschine {machine_id}: Instanz {entry['instance_id']} lief "
                  f"{elapsed/60:.1f} Min. -- als Favorit vermerkt.", file=sys.stderr)
        else:
            record["blacklisted_until"] = now + BLACKLIST_DURATION_SECONDS
            print(f"  ✗ Maschine {machine_id}: Instanz {entry['instance_id']} verschwand "
                  f"nach nur {elapsed/60:.1f} Min. -- {BLACKLIST_DURATION_SECONDS // 3600}h "
                  f"blacklisted.", file=sys.stderr)

    _save(TRACKED_FILE, still_pending)
    _save(STATS_FILE, stats)


def blacklisted_machine_ids():
    """Menge der aktuell (noch nicht abgelaufen) blacklisteten machine_ids,
    für pick_cheapest_offer.py/race_pick_offers.py."""
    stats = _load_stats()
    now = time.time()
    return {
        int(mid) for mid, rec in stats.items()
        if rec.get("blacklisted_until") and rec["blacklisted_until"] > now
    }


def favorite_machine_ids():
    """Menge der dynamisch gelernten Favoriten, zusätzlich zu
    KNOWN_RELIABLE_MACHINE_IDS."""
    stats = _load_stats()
    return {int(mid) for mid, rec in stats.items() if rec.get("favorite")}


def is_blacklisted(machine_id):
    return int(machine_id) in blacklisted_machine_ids()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Nutzung: machine_stats.py record <instance_id> | reconcile | "
              "is-blacklisted <machine_id>", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "record" and len(sys.argv) == 3:
        record_created(int(sys.argv[2]))
    elif cmd == "reconcile":
        reconcile()
    elif cmd == "is-blacklisted" and len(sys.argv) == 3:
        print("1" if is_blacklisted(int(sys.argv[2])) else "")
    else:
        print("Unbekanntes Kommando.", file=sys.stderr)
        sys.exit(1)
