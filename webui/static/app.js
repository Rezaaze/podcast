(() => {
  "use strict";

  const logOutput = document.getElementById("log-output");
  const logTitle = document.getElementById("log-title");
  const logStep = document.getElementById("log-step");
  let currentEventSource = null;

  // ---------- Akustische Rückmeldung bei Job-Ende ----------
  // AudioContext braucht eine Nutzer-Geste zum Erstellen/Fortsetzen — wird
  // beim ersten Button-Klick synchron initialisiert, damit sie beim späteren
  // "done"-Event (Sekunden bis Minuten danach) garantiert schon läuft.
  let audioCtx = null;
  function ensureAudioContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } else if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
  }

  function playTone(freq, startTime, duration, gain) {
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    osc.frequency.value = freq;
    osc.type = "sine";
    gainNode.gain.setValueAtTime(0, startTime);
    gainNode.gain.linearRampToValueAtTime(gain, startTime + 0.02);
    gainNode.gain.linearRampToValueAtTime(0, startTime + duration);
    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    osc.start(startTime);
    osc.stop(startTime + duration);
  }

  function playChime(success) {
    if (!audioCtx) return;
    const now = audioCtx.currentTime;
    if (success) {
      playTone(880, now, 0.14, 0.18);
      playTone(1318.5, now + 0.13, 0.22, 0.18);
    } else {
      playTone(220, now, 0.28, 0.2);
      playTone(174.6, now + 0.22, 0.32, 0.2);
    }
  }

  // ---------- Tabs ----------
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });

  // ---------- Status polling ----------
  function stateLabel(state) {
    return { ready: "fertig", partial: "teilweise", running: "läuft", missing: "offen" }[state] || state;
  }

  function card(label, value, state) {
    return `<div class="status-card" data-state="${state || 'missing'}">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
    </div>`;
  }

  // ---------- Schritt-Status (welcher Schritt ist dran?) ----------
  // stepStates: Array von "done" | "current" | "upcoming", Reihenfolge = Schrittnummer.
  function applyStepStates(prefix, stepStates) {
    let currentAssigned = false;
    stepStates.forEach((rawState, i) => {
      const n = i + 1;
      const el = document.getElementById(`${prefix}-step-${n}`);
      const badge = document.getElementById(`${prefix}-step-${n}-badge`);
      if (!el || !badge) return;
      let state = rawState;
      if (state === "current") {
        if (currentAssigned) state = "upcoming";
        else currentAssigned = true;
      }
      el.classList.remove("step-done", "step-current", "step-upcoming");
      el.classList.add(`step-${state}`);
      badge.textContent = state === "done" ? "✓" : String(n);
    });
  }

  function pfStepStates(s) {
    const seriesDone = !!s.series_title;
    const episodesDone = (s.episodes || []).length > 0 &&
      s.episodes.every(ep => ep.script_state === "ready" && ep.audio_state === "ready");
    const anthologyDone = s.anthology_state === "ready";
    return [
      seriesDone ? "done" : "current",
      !seriesDone ? "upcoming" : (episodesDone ? "done" : "current"),
      !seriesDone || !episodesDone ? "upcoming" : (anthologyDone ? "done" : "current"),
    ];
  }

  function lolfiStepStates(s) {
    const sceneDone = !!s.current_scene_title;
    const promptsDone = s.latest_prompt_state === "ready";
    const assetsDone = s.video_baseline_ready && s.music_ready;
    const renderDone = s.render_state === "ready";
    return [
      sceneDone ? "done" : "current",
      !sceneDone ? "upcoming" : (promptsDone ? "done" : "current"),
      !sceneDone || !promptsDone ? "upcoming" : (assetsDone ? "done" : "current"),
      !sceneDone || !promptsDone || !assetsDone ? "upcoming" : (renderDone ? "done" : "current"),
    ];
  }

  async function refreshPfStatus() {
    const res = await fetch("/api/status/pf");
    const s = await res.json();
    const container = document.getElementById("pf-status-cards");
    let html = "";
    html += card("Serie", s.series_title || "—", s.series_title ? "ready" : "missing");
    html += card("Episoden", s.episode_count, s.episode_count ? "ready" : "missing");
    (s.episodes || []).forEach(ep => {
      html += card(`Ep. ${ep.index}: ${ep.figure}`, `Skript ${stateLabel(ep.script_state)} · Audio ${stateLabel(ep.audio_state)}`,
        ep.audio_state === "running" ? "running" : (ep.script_state === "ready" && ep.audio_state === "ready" ? "ready" : "partial"));
    });
    html += card("Anthologie", stateLabel(s.anthology_state), s.anthology_state);
    html += card("Archiv", `${s.archive_count} Serie(n)`, s.archive_count ? "ready" : "missing");
    container.innerHTML = html;
    applyStepStates("pf", pfStepStates(s));
  }

  async function refreshLolfiStatus() {
    const res = await fetch("/api/status/lolfi");
    const s = await res.json();
    const container = document.getElementById("lolfi-status-cards");
    let html = "";
    html += card("Szenen", s.scene_count, s.scene_count ? "ready" : "missing");
    html += card("Aktuelle Szene", s.current_scene_title || "—", s.current_scene_title ? "ready" : "missing");
    html += card("Prompt-Set", s.latest_prompt_file ? stateLabel(s.latest_prompt_state) : "offen", s.latest_prompt_state);
    html += card("Loop-Clip", s.video_baseline_ready ? "vorhanden" : "fehlt", s.video_baseline_ready ? "ready" : "missing");
    html += card("Musik", s.music_ready ? "vorhanden" : "fehlt", s.music_ready ? "ready" : "missing");
    html += card("SFX", (s.sfx_baseline_ready || s.sfx_variations_ready) ? "vorhanden" : "fehlt", (s.sfx_baseline_ready || s.sfx_variations_ready) ? "ready" : "missing");
    html += card("Renders", (s.renders || []).length, s.render_state);
    container.innerHTML = html;

    document.getElementById("lolfi-scene-text").textContent = s.current_scene_text || "(keine Szene vorhanden)";

    const list = document.getElementById("lolfi-renders-list");
    list.innerHTML = (s.renders || []).map(r =>
      `<li>${r.name} — ${r.size_mb} MB</li>`
    ).join("") || "<li>(noch keine Renders)</li>";
    applyStepStates("lolfi", lolfiStepStates(s));
  }

  async function refreshTtsStatus() {
    const res = await fetch("/api/status/tts");
    const s = await res.json();
    const el = document.getElementById("tts-inline-status");
    if (!el) return;
    const label = s.listening ? `läuft (Port ${s.port})` : (s.starting ? "startet ..." : "aktuell aus");
    el.textContent = `(${label})`;
    el.className = s.listening ? "tts-tag ready" : (s.starting ? "tts-tag running" : "tts-tag missing");
  }

  function refreshStatus() {
    refreshPfStatus().catch(console.error);
    refreshLolfiStatus().catch(console.error);
    refreshTtsStatus().catch(console.error);
  }
  refreshStatus();
  setInterval(refreshStatus, 4000);

  // ---------- Run buttons ----------
  function collectParams(btn) {
    const params = {};
    for (const attr of btn.attributes) {
      if (attr.name.startsWith("data-param-")) {
        const paramName = attr.name.replace("data-param-", "");
        const el = document.getElementById(attr.value);
        if (el) params[paramName] = el.value;
      }
    }
    return params;
  }

  async function runCommand(commandId, params, btn) {
    logOutput.textContent = "";
    logTitle.textContent = "Log: " + commandId;
    logStep.textContent = "";
    if (btn) btn.disabled = true;

    let res;
    try {
      res = await fetch(`/api/run/${commandId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
    } catch (err) {
      logOutput.textContent += `❌ Netzwerkfehler: ${err}\n`;
      if (btn) btn.disabled = false;
      return;
    }

    const data = await res.json();
    if (!res.ok) {
      logOutput.textContent += `❌ ${data.error || "Fehler beim Start"}\n`;
      if (btn) btn.disabled = false;
      return;
    }

    if (currentEventSource) currentEventSource.close();
    const es = new EventSource(`/api/stream/${data.job_id}`);
    currentEventSource = es;

    es.addEventListener("log", (ev) => {
      const payload = JSON.parse(ev.data);
      logOutput.textContent += payload.line + "\n";
      logOutput.scrollTop = logOutput.scrollHeight;
    });
    es.addEventListener("progress", (ev) => {
      const payload = JSON.parse(ev.data);
      logStep.textContent = `${payload.part || ""}: ${payload.chunks} Chunks`;
    });
    es.addEventListener("step", (ev) => {
      const payload = JSON.parse(ev.data);
      logStep.textContent = `Schritt ${payload.step}: ${payload.label}`;
    });
    es.addEventListener("done", (ev) => {
      const payload = JSON.parse(ev.data);
      logOutput.textContent += `\n${payload.returncode === 0 ? "✅ fertig" : "❌ Fehler (Exit " + payload.returncode + ")"}\n`;
      es.close();
      if (btn) btn.disabled = false;
      playChime(payload.returncode === 0);
      refreshStatus();
      if (payload.returncode === 0 && commandId === "lolfi_generate_prompts") {
        loadLolfiPromptSet().catch(console.error);
      }
    });
    es.onerror = () => {
      if (btn) btn.disabled = false;
    };
  }

  document.querySelectorAll(".run-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      ensureAudioContext();
      runCommand(btn.dataset.command, collectParams(btn), btn);
    });
  });

  // ---------- Folder buttons ----------
  document.querySelectorAll(".folder-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/open-folder/${btn.dataset.key}`, { method: "POST" });
    });
  });

  // ---------- Copy buttons ----------
  document.addEventListener("click", (ev) => {
    if (!ev.target.classList.contains("copy-btn")) return;
    const target = document.getElementById(ev.target.dataset.target);
    if (!target) return;
    navigator.clipboard.writeText(target.textContent).then(() => {
      const original = ev.target.textContent;
      ev.target.textContent = "Kopiert!";
      setTimeout(() => { ev.target.textContent = original; }, 1200);
    });
  });

  // ---------- Copy-paste blocks ----------
  document.getElementById("pf-build-block-btn").addEventListener("click", async () => {
    const topic = document.getElementById("pf-topic").value;
    const episodes = document.getElementById("pf-episodes").value || 3;
    if (!topic.trim()) { alert("Bitte zuerst ein Thema eintragen."); return; }
    const res = await fetch(`/api/blocks/pf/series-prompt?topic=${encodeURIComponent(topic)}&episodes=${episodes}`);
    const data = await res.json();
    document.getElementById("pf-series-block").textContent = data.block || data.error || "";
  });

  document.getElementById("pf-meta-load-btn").addEventListener("click", async () => {
    const res = await fetch("/api/blocks/pf/anthology-meta");
    const data = await res.json();
    document.getElementById("pf-meta-block").textContent = data.anthology_meta || "(noch nicht vorhanden)";
    document.getElementById("pf-upload-index-block").textContent = data.upload_index || "(noch nicht vorhanden)";
  });

  async function loadLolfiPromptSet() {
    const res = await fetch("/api/blocks/lolfi/prompt-set");
    const data = await res.json();
    document.getElementById("lolfi-prompt-source").textContent = data.source_file
      ? `Quelle: ${data.source_file}` : "(noch kein Prompt-Set vorhanden)";
    document.getElementById("lolfi-image-prompt").textContent = data.image_prompt || "";
    document.getElementById("lolfi-image-negative").textContent = data.image_negative_prompt || "";
    document.getElementById("lolfi-kling-prompt").textContent = data.kling_loop_prompt || "";
    document.getElementById("lolfi-kling-negative").textContent = data.kling_negative_prompt || "";
    document.getElementById("lolfi-suno-prompt").textContent = data.suno_prompt || "";
  }

  document.getElementById("lolfi-prompt-load-btn").addEventListener("click", loadLolfiPromptSet);
})();
