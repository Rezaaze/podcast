"""Cockpit-WebUI für Podcast-Fabrik + Lolfi. Start: python3 app.py"""

import glob
import json
import os
import shutil

from flask import Flask, Response, jsonify, render_template, request

import folders
import prompt_blocks
import status
import tts_control
from config import COMMANDS, PF_DIR, list_series_slugs, read_latest_slug, write_latest_slug, series_dir_for
from runner import JobRegistry, ValidationError

app = Flask(__name__)
# Templates immer frisch von der Platte lesen (auch ohne debug=True) — sonst
# liefert ein laufender Server nach Template-Änderungen altes HTML zusammen
# mit neuen Static-Dateien aus, und das JS bricht an fehlenden Elementen ab.
app.config["TEMPLATES_AUTO_RELOAD"] = True
jobs = JobRegistry()


@app.get("/")
def index():
    return render_template("index.html", commands=COMMANDS)


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
        data = status._read_json(os.path.join(series_dir_for(slug) or "", "episodes.json")) or {}
        series.append({
            "slug": slug,
            "title": data.get("series_title", slug),
            "mode": data.get("mode", "narration"),
            "template": data.get("template", "narration"),
            "merge_anthology": data.get("audio", {}).get("merge_anthology", True),
            "use_beats": data.get("generation", {}).get("use_beats", False),
        })
    return jsonify(series=series, active=read_latest_slug())


@app.post("/api/pf/series/active")
def api_pf_series_set_active():
    """Setzt series/LATEST — macht die WebUI-Auswahl zum Standard, den auch
    generate_episode.py/podcast_maker.py/batch.py ohne --series verwenden."""
    body = request.get_json(silent=True) or {}
    slug = body.get("slug", "")
    if not series_dir_for(slug):
        return jsonify(error=f"Unbekannte Serie: {slug}"), 400
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
    episodes_path = os.path.join(series_dir, "episodes.json")
    with open(episodes_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "merge_anthology" in body:
        data.setdefault("audio", {})["merge_anthology"] = bool(body["merge_anthology"])
    if "use_beats" in body:
        data.setdefault("generation", {})["use_beats"] = bool(body["use_beats"])
    with open(episodes_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
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

    has_scripts = bool(glob.glob(os.path.join(series_dir, "scripts", "*.txt")))
    has_output = any(
        not f.startswith(".") for f in
        (os.listdir(os.path.join(series_dir, "output")) if os.path.isdir(os.path.join(series_dir, "output")) else [])
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


@app.get("/api/status/lolfi")
def api_status_lolfi():
    return jsonify(status.lolfi_status(jobs))


@app.get("/api/status/tts")
def api_status_tts():
    port = tts_control.get_tts_port()
    running_commands = jobs.snapshot()
    starting = any(
        running_commands.get(cid, {}).get("state") == "running"
        for cid in ("pf_tts_start", "pf_podcast_maker", "pf_batch")
    )
    listening = tts_control.is_port_listening(port)
    return jsonify(port=port, listening=listening, starting=starting and not listening)


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
    episodes = int(request.args.get("episodes", 3))
    template = request.args.get("template", "narration")
    minutes = float(request.args.get("minutes", 35))
    if not topic.strip():
        return jsonify(error="topic fehlt"), 400
    return jsonify(block=prompt_blocks.build_series_prompt_block(topic, episodes, template, minutes))


@app.get("/api/blocks/lolfi/prompt-set")
def api_prompt_set():
    return jsonify(prompt_blocks.parse_latest_prompt_set())


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
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
