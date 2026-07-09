"""Cockpit-WebUI für Podcast-Fabrik + Lolfi. Start: python3 app.py"""

import os

from flask import Flask, Response, jsonify, render_template, request

import folders
import prompt_blocks
import status
import tts_control
from config import COMMANDS
from runner import JobRegistry, ValidationError

app = Flask(__name__)
jobs = JobRegistry()


@app.get("/")
def index():
    return render_template("index.html", commands=COMMANDS)


@app.get("/api/status/pf")
def api_status_pf():
    return jsonify(status.pf_status(jobs))


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
    if not topic.strip():
        return jsonify(error="topic fehlt"), 400
    return jsonify(block=prompt_blocks.build_series_prompt_block(topic, episodes))


@app.get("/api/blocks/lolfi/prompt-set")
def api_prompt_set():
    return jsonify(prompt_blocks.parse_latest_prompt_set())


@app.get("/api/blocks/pf/anthology-meta")
def api_anthology_meta():
    return jsonify(prompt_blocks.read_anthology_meta())


@app.post("/api/open-folder/<key>")
def api_open_folder(key):
    ok = folders.open_folder(key)
    return ("", 204) if ok else ("", 404)


if __name__ == "__main__":
    port = int(os.environ.get("WEBUI_PORT", 5151))
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
