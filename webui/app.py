"""Cockpit-WebUI für Podcast-Fabrik. Start: python3 app.py"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time

from flask import Flask, Response, jsonify, render_template, request

import folders
import prompt_blocks
import status
import tts_control
import config
from config import COMMANDS, PF_DIR, list_series_slugs, read_latest_slug, write_latest_slug, series_dir_for
# config.py legt PF_DIR auf sys.path — deshalb ist fabrik hier importierbar.
from fabrik.core import config as pf_config  # noqa: E402
from runner import JobRegistry, ValidationError

app = Flask(__name__)
# Templates immer frisch von der Platte lesen (auch ohne debug=True) — sonst
# liefert ein laufender Server nach Template-Änderungen altes HTML zusammen
# mit neuen Static-Dateien aus, und das JS bricht an fehlenden Elementen ab.
app.config["TEMPLATES_AUTO_RELOAD"] = True
jobs = JobRegistry()

# Mehrere Cockpits parallel: die "aktive Serie" darf dann nicht mehr global über
# data/series/LATEST laufen (die Instanzen würden sich gegenseitig umbiegen —
# besonders beim Anlegen, wo eine Schwester-Instanz LATEST überschreibt, bevor
# diese ihren frischen Slug zurückgelesen hat). Zwei Umgebungsvariablen:
#   WEBUI_SERIES=<slug>  -> isoliert UND fest auf diesen (existierenden) Slug
#                           gepinnt; der Umschalter im UI ist gesperrt.
#   WEBUI_ISOLATED=1     -> isoliert, aber nicht gepinnt: für den Fall "Serie
#                           erst hier anlegen und dann weiterarbeiten" (4 leere
#                           Cockpits, jedes legt seine eigene Serie an).
# Isoliert heißt: die aktive Serie lebt pro Prozess im Speicher (_active) und
# diese Instanz schreibt den globalen LATEST NIE. Ohne beide Variablen bleibt
# alles beim alten, LATEST-gestützten Verhalten (Ein-Cockpit-Betrieb).
PINNED_SERIES = os.environ.get("WEBUI_SERIES") or None
ISOLATED = bool(PINNED_SERIES) or os.environ.get("WEBUI_ISOLATED") == "1"
# Aktive Serie DIESER Instanz (nur relevant im isolierten Betrieb; sonst bleibt
# LATEST die Quelle). Startwert: der Pin bzw. der aktuelle LATEST als Hinweis.
_active = {"slug": PINNED_SERIES or read_latest_slug()}


@app.get("/")
def index():
    # Templates bei jedem Seitenaufruf frisch enumerieren — ein neues
    # Template unter templates/ erscheint so ohne Server-Neustart.
    return render_template("index.html", commands=COMMANDS,
                           pf_templates=config.list_templates())


@app.get("/api/status/pf")
def api_status_pf():
    series_slug = request.args.get("series")
    return jsonify(status.pf_status(jobs, series_slug=series_slug))


@app.get("/api/pf/series")
def api_pf_series_list():
    """Alle vorhandenen Serien + welche gerade als Standard (series/LATEST)
    gilt — Grundlage für den Serien-Umschalter in der WebUI."""
    slugs = list_series_slugs()
    series = []
    for slug in slugs:
        data = status._read_json(os.path.join(series_dir_for(slug) or "", config.EPISODES_RELPATH)) or {}
        series.append({
            "slug": slug,
            "title": data.get("series_title", slug),
            "mode": data.get("mode", "narration"),
            "template": data.get("template", "narration"),
            "merge_anthology": data.get("audio", {}).get("merge_anthology", True),
            # Default MUSS DEFAULTS["use_beats"] spiegeln (aktuell True): fehlt
            # der Key in episodes.json, läuft die Beat-Schicht trotzdem, weil
            # build_config() auf den DEFAULT zurückfällt. Ein hart kodiertes
            # False zeigte hier jahrelang eine leere Checkbox für Serien, in
            # denen die Beats sehr wohl liefen (aufgefallen 19.07.2026 bei der
            # Drift-Messung — beide untersuchten Serien hatten BEATS-Dateien,
            # nur eine hatte den Key gesetzt).
            "use_beats": data.get("generation", {}).get(
                "use_beats", pf_config.DEFAULTS["use_beats"]),
        })
    if PINNED_SERIES and series_dir_for(PINNED_SERIES):
        active = PINNED_SERIES
    elif ISOLATED:
        active = _active["slug"]  # per-Instanz-Speicher; kann None sein (noch nichts angelegt)
    else:
        active = read_latest_slug()
    return jsonify(series=series, active=active, pinned=PINNED_SERIES, isolated=ISOLATED)


@app.post("/api/pf/series/active")
def api_pf_series_set_active():
    """Wählt die aktive Serie. Ein-Cockpit-Betrieb (nicht isoliert): schreibt
    series/LATEST, damit auch CLI-Läufe ohne --series dieselbe Serie sehen.
    Isolierter Betrieb (WEBUI_SERIES/WEBUI_ISOLATED): merkt sich die Serie nur
    im Prozess-Speicher und fasst den globalen LATEST NIE an — sonst würden
    parallele Cockpits sich gegenseitig den Default umbiegen. Gepinnt: no-op."""
    body = request.get_json(silent=True) or {}
    slug = body.get("slug", "")
    if not series_dir_for(slug):
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400
    if PINNED_SERIES:
        return ("", 204)  # fest gepinnt — Auswahl unveränderlich
    if ISOLATED:
        _active["slug"] = slug  # nur Prozess-Speicher, kein LATEST-Write
        return ("", 204)
    write_latest_slug(slug)
    return ("", 204)


@app.post("/api/pf/series/settings")
def api_pf_series_settings():
    """Schreibt Einzel-Settings direkt in episodes.json (z.B.
    audio.merge_anthology) — für Optionen, die keinen eigenen CLI-Lauf
    brauchen, nur eine dauerhafte Serien-Einstellung."""
    body = request.get_json(silent=True) or {}
    slug = body.get("slug", "")
    series_dir = series_dir_for(slug)
    if not series_dir:
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400
    episodes_path = os.path.join(series_dir, config.EPISODES_RELPATH)
    with open(episodes_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "merge_anthology" in body:
        data.setdefault("audio", {})["merge_anthology"] = bool(body["merge_anthology"])
    if "use_beats" in body:
        data.setdefault("generation", {})["use_beats"] = bool(body["use_beats"])
    with open(episodes_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return ("", 204)


ASSET_STEMS = ("intro", "outro", "transition")
ASSET_EXTS = (".mp3", ".wav", ".m4a", ".flac")


@app.get("/api/pf/series/assets")
def api_pf_series_assets():
    """Welche optionalen Audio-Assets (intro/outro/transition) die Serie
    gerade hat — podcast_maker.find_audio_asset() liest dieselben Dateien
    aus series/<slug>/assets/ direkt vor dem Merge."""
    slug = request.args.get("series") or read_latest_slug()
    series_dir = series_dir_for(slug)
    if not series_dir:
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400
    assets_dir = os.path.join(series_dir, "assets")
    found = {}
    for stem in ASSET_STEMS:
        found[stem] = next(
            (f"{stem}{ext}" for ext in ASSET_EXTS
             if os.path.exists(os.path.join(assets_dir, f"{stem}{ext}"))),
            None)
    return jsonify(assets=found)


@app.post("/api/pf/series/asset")
def api_pf_series_asset_upload():
    """Lädt intro/outro/transition hoch und ersetzt eine evtl. vorhandene
    Version mit ANDERER Endung — sonst würde find_audio_asset() dank fester
    Endungs-Priorität (.mp3 vor .wav vor ...) weiter die alte Datei
    aufheben, obwohl der Upload eine neue Endung mitbrachte."""
    slug = request.form.get("slug", "")
    stem = request.form.get("stem", "")
    series_dir = series_dir_for(slug)
    if not series_dir:
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400
    if stem not in ASSET_STEMS:
        return jsonify(error=f"Unbekanntes Asset: {stem}"), 400
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Keine Datei hochgeladen"), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ASSET_EXTS:
        return jsonify(error=f"Nicht unterstütztes Format {ext or '(keins)'} "
                             f"— erlaubt: {', '.join(ASSET_EXTS)}"), 400
    assets_dir = os.path.join(series_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    for old_ext in ASSET_EXTS:
        old_path = os.path.join(assets_dir, f"{stem}{old_ext}")
        if os.path.exists(old_path):
            os.remove(old_path)
    file.save(os.path.join(assets_dir, f"{stem}{ext}"))
    return jsonify(filename=f"{stem}{ext}")


@app.delete("/api/pf/series/asset")
def api_pf_series_asset_delete():
    slug = request.args.get("slug", "")
    stem = request.args.get("stem", "")
    series_dir = series_dir_for(slug)
    if not series_dir:
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400
    if stem not in ASSET_STEMS:
        return jsonify(error=f"Unbekanntes Asset: {stem}"), 400
    assets_dir = os.path.join(series_dir, "assets")
    for ext in ASSET_EXTS:
        p = os.path.join(assets_dir, f"{stem}{ext}")
        if os.path.exists(p):
            os.remove(p)
    return ("", 204)


@app.post("/api/pf/series/discard")
def api_pf_series_discard():
    """Verwirft eine FRISCH erzeugte Serie wieder (Review-Schritt nach
    "Serie erstellen"): löscht series/<slug>/ nur, solange dort weder
    Skripte noch Audio liegen — eine Serie mit erarbeitetem Inhalt kann
    hierüber nie verschwinden. Zeigt LATEST danach auf die zuletzt
    geänderte verbleibende Serie."""
    body = request.get_json(silent=True) or {}
    slug = body.get("slug", "")
    series_dir = series_dir_for(slug)
    if not series_dir:
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400

    has_scripts = bool(glob.glob(os.path.join(series_dir, config.SCRIPTS_RELPATH, "*.txt")))
    has_output = any(
        not f.startswith(".") for f in
        (os.listdir(os.path.join(series_dir, config.OUTPUT_RELPATH)) if os.path.isdir(os.path.join(series_dir, config.OUTPUT_RELPATH)) else [])
    )
    if has_scripts or has_output:
        return jsonify(error="Serie hat bereits Skripte oder Audio — Verwerfen nur für "
                             "frisch erzeugte Serien ohne Inhalt erlaubt."), 409

    shutil.rmtree(series_dir)

    if read_latest_slug() == slug:
        remaining = [(s, os.path.getmtime(series_dir_for(s))) for s in list_series_slugs()]
        if remaining:
            write_latest_slug(max(remaining, key=lambda x: x[1])[0])
        else:
            latest_file = os.path.join(PF_DIR, "data", "series", "LATEST")
            if os.path.exists(latest_file):
                os.remove(latest_file)
    return ("", 204)


@app.get("/api/status/tts")
def api_status_tts():
    port = tts_control.get_tts_port()
    running_commands = jobs.snapshot()
    starting = status.any_command_running(
        running_commands, "pf_tts_start", "pf_podcast_maker", "pf_batch")
    listening = tts_control.is_port_listening(port)
    return jsonify(port=port, listening=listening, starting=starting and not listening)


# ---------- Cloud-Server-Pool (vast.ai) ----------
# Server-Scouting-Workflow: "Nächsten Server mieten" läuft als normaler Job
# (pf_cloud_rent -> cloud/rent.sh), die Routen hier liefern die Liste
# (Live-Instanzen + gelerntes Maschinen-Urteil) und nehmen das manuelle
# Urteil entgegen. Favoriten/Verworfene fließen über machine_stats.py
# automatisch in JEDE Offer-Suche ein (pick_cheapest_offer/race_pick_offers).

CLOUD_DIR = os.path.join(PF_DIR, "cloud")
MACHINE_STATS = os.path.join(CLOUD_DIR, "machine_stats.py")


def _machine_stats_cmd(*args, timeout=30):
    # machine_stats.py ist stdlib-only -- der venv-Python des WebUI reicht.
    return subprocess.run([sys.executable, MACHINE_STATS, *args],
                          capture_output=True, text=True, timeout=timeout)


@app.get("/api/cloud/instances")
def api_cloud_instances():
    """Live-Instanzen (vastai) + Maschinen-Stats (Favorit/Blacklist/avoid)
    für die Server-Pool-Ansicht. vastai-Fehler sind kein 500 -- die Ansicht
    zeigt dann nur die gelernten Maschinen."""
    machines = {}
    dump = _machine_stats_cmd("dump")
    if dump.returncode == 0:
        try:
            machines = json.loads(dump.stdout).get("stats", {})
        except json.JSONDecodeError:
            pass

    instances, error = [], None
    if shutil.which("vastai") is None:
        error = "vastai-CLI nicht im PATH des WebUI-Prozesses"
    else:
        try:
            raw = subprocess.run(["vastai", "show", "instances-v1", "--raw"],
                                 capture_output=True, text=True, timeout=30)
            if raw.returncode != 0:
                error = (raw.stderr or raw.stdout or "vastai-Fehler").strip()[:300]
            else:
                for inst in (json.loads(raw.stdout).get("instances") or []):
                    instances.append({
                        "instance_id": inst.get("id"),
                        "machine_id": inst.get("machine_id"),
                        "gpu_name": inst.get("gpu_name"),
                        "geolocation": inst.get("geolocation"),
                        "dph_total": inst.get("dph_total"),
                        "status": inst.get("actual_status") or inst.get("cur_state"),
                        "label": inst.get("label"),
                    })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            error = str(exc)[:300]

    now = time.time()
    machine_rows = {}
    for mid, rec in machines.items():
        machine_rows[str(mid)] = {
            "favorite": bool(rec.get("favorite")),
            "avoid": bool(rec.get("avoid")),
            "manual": bool(rec.get("manual")),
            "blacklisted": bool(rec.get("blacklisted_until") and rec["blacklisted_until"] > now),
        }
    return jsonify(instances=instances, machines=machine_rows, error=error)


@app.post("/api/cloud/machine")
def api_cloud_machine():
    """Manuelles Urteil über eine Maschine: favorite | unfavorite | reject.
    reject kann optional zusätzlich die laufende Instanz destroyen."""
    payload = request.get_json(silent=True) or {}
    machine_id = payload.get("machine_id")
    action = payload.get("action")
    if not machine_id or action not in ("favorite", "unfavorite", "reject"):
        return jsonify(error="machine_id und action (favorite|unfavorite|reject) nötig"), 400

    destroy_error = None
    if action == "reject" and payload.get("instance_id"):
        destroyed = subprocess.run(["vastai", "destroy", "instance", str(payload["instance_id"])],
                                   capture_output=True, text=True, timeout=60)
        if destroyed.returncode != 0:
            destroy_error = (destroyed.stderr or destroyed.stdout or "destroy fehlgeschlagen").strip()[:300]

    result = _machine_stats_cmd(action, str(machine_id))
    if result.returncode != 0:
        return jsonify(error=(result.stderr or "machine_stats fehlgeschlagen").strip()[:300]), 500
    return jsonify(ok=True, destroy_error=destroy_error)


@app.post("/api/run/<command_id>")
def api_run(command_id):
    params = request.get_json(silent=True) or {}
    try:
        job_id = jobs.start(command_id, params)
    except ValidationError as exc:
        message = str(exc)
        status_code = 409 if "läuft bereits" in message else 400
        return jsonify(error=message), status_code
    return jsonify(job_id=job_id)


@app.get("/api/stream/<job_id>")
def api_stream(job_id):
    return Response(jobs.stream(job_id), mimetype="text/event-stream",
                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/jobs")
def api_jobs():
    return jsonify(jobs.snapshot())


@app.post("/api/jobs/<job_id>/kill")
def api_kill(job_id):
    ok = jobs.kill(job_id)
    return ("", 204) if ok else ("", 404)


@app.get("/api/blocks/pf/series-prompt")
def api_series_prompt():
    topic = request.args.get("topic", "")
    template = request.args.get("template", "narration")
    if not topic.strip():
        return jsonify(error="topic fehlt"), 400
    try:
        episodes = int(request.args.get("episodes", 3))
        minutes = float(request.args.get("minutes", 35))
        locations_raw = request.args.get("locations")
        locations = int(locations_raw) if locations_raw else None
    except ValueError:
        return jsonify(error="episodes/minutes/locations müssen Zahlen sein"), 400
    return jsonify(block=prompt_blocks.build_series_prompt_block(
        topic, episodes, template, minutes, locations))


@app.get("/api/blocks/pf/anthology-meta")
def api_anthology_meta():
    return jsonify(prompt_blocks.read_anthology_meta())


@app.get("/api/blocks/pf/character-prompts")
def api_character_prompts():
    return jsonify(prompt_blocks.read_character_prompts(request.args.get("series")))


@app.get("/api/blocks/pf/location-prompts")
def api_location_prompts():
    return jsonify(prompt_blocks.read_location_prompts(request.args.get("series")))


@app.post("/api/open-folder/<key>")
def api_open_folder(key):
    ok = folders.open_folder(key)
    return ("", 204) if ok else ("", 404)


if __name__ == "__main__":
    # PORT: von Tooling/Preview-Harnesses gesetzt (Vorrang, falls vorhanden).
    # WEBUI_PORT: eigener Override für den manuellen Start. Sonst Default 5151.
    port = int(os.environ.get("PORT") or os.environ.get("WEBUI_PORT", 5151))
    if PINNED_SERIES:
        if series_dir_for(PINNED_SERIES):
            print(f"WEBUI_SERIES={PINNED_SERIES}: Cockpit fest auf diese Serie "
                  f"genagelt (LATEST wird von dieser Instanz nicht verändert).")
        else:
            print(f"⚠️  WEBUI_SERIES={PINNED_SERIES}: Serie nicht gefunden unter "
                  f"data/series/ — Pinning ignoriert, Fallback auf LATEST.")
    elif ISOLATED:
        print("WEBUI_ISOLATED=1: aktive Serie pro Instanz (Prozess-Speicher), "
              "globaler LATEST wird nicht verändert — für Parallelbetrieb "
              "mehrerer Cockpits, die je eine eigene Serie anlegen.")
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
