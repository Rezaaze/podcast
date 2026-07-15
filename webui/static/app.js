(() => {
  "use strict";

  const logOutput = document.getElementById("log-output");
  const logTitle = document.getElementById("log-title");
  const logStep = document.getElementById("log-step");
  const logPanel = document.getElementById("log-panel");
  const logDot = document.getElementById("log-dot");
  const mainEl = document.querySelector("main");
  let currentEventSource = null;

  // ---------- Log-Panel auf-/zuklappen ----------
  // Startet zugeklappt (spart Platz); klappt automatisch auf, sobald ein
  // Kommando läuft, damit Fortschritt/Fehler nicht übersehen werden. Der
  // Punkt in der Kopfzeile zeigt den Status auch im zugeklappten Zustand.
  function setLogOpen(open) {
    logPanel.classList.toggle("collapsed", !open);
    mainEl.classList.toggle("log-open", open);
  }
  document.getElementById("log-toggle").addEventListener("click", () => {
    setLogOpen(logPanel.classList.contains("collapsed"));
  });
  document.getElementById("log-toggle").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      setLogOpen(logPanel.classList.contains("collapsed"));
    }
  });

  // ---------- Job abbrechen ----------
  // Beendet serverseitig die ganze Prozessgruppe (inkl. Kindprozesse von
  // batch.py / generate_episode.py all). Das done-Event mit Exit-Code ≠ 0
  // kommt danach normal über den Stream rein.
  const killBtn = document.getElementById("log-kill");
  let currentJobId = null;
  killBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (!currentJobId) return;
    if (!confirm("Laufenden Job wirklich abbrechen?")) return;
    logOutput.textContent += "\n⏹ Abbruch angefordert ...\n";
    await fetch(`/api/jobs/${currentJobId}/kill`, { method: "POST" });
  });

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

  // ---------- Serien-Umschalter ----------
  // Die Auswahl ist die einzige Quelle der Wahrheit für "welche Serie"
  // während dieser Session: sie wird an /api/status/pf (?series=) UND an
  // jeden pf_*-Kommando-Aufruf (params.series) durchgereicht, UND per
  // /api/pf/series/active sofort als series/LATEST persistiert — damit
  // CLI-Aufrufe außerhalb der WebUI dieselbe Serie als Standard sehen.
  const seriesSelect = document.getElementById("pf-series-select");
  const mergeAnthologyCheckbox = document.getElementById("pf-merge-anthology");
  const useBeatsCheckbox = document.getElementById("pf-use-beats");
  const introFileInput = document.getElementById("pf-intro-file");
  const introCurrentLabel = document.getElementById("pf-intro-current");
  const introUploadBtn = document.getElementById("pf-intro-upload-btn");
  const introRemoveBtn = document.getElementById("pf-intro-remove-btn");
  let seriesList = [];

  function currentSeriesSlug() {
    return seriesSelect.value || null;
  }

  async function loadSeriesList(preferSlug) {
    const res = await fetch("/api/pf/series");
    const data = await res.json();
    const list = data.series || [];
    seriesList = list;
    const want = preferSlug || seriesSelect.value || data.active || (list[0] && list[0].slug);
    seriesSelect.innerHTML = list.length
      ? list.map(s => `<option value="${s.slug}">${s.title} (${s.slug}) — ${s.template}</option>`).join("")
      : `<option value="">(keine Serie vorhanden)</option>`;
    if (want && list.some(s => s.slug === want)) seriesSelect.value = want;
    updateSeriesSelectTitle();
    updateMergeAnthologyCheckbox();
    updateUseBeatsCheckbox();
    updateIntroAsset();
  }

  function updateMergeAnthologyCheckbox() {
    if (!mergeAnthologyCheckbox) return;
    const s = seriesList.find(s => s.slug === seriesSelect.value);
    mergeAnthologyCheckbox.checked = s ? s.merge_anthology !== false : true;
  }

  function updateUseBeatsCheckbox() {
    if (!useBeatsCheckbox) return;
    const s = seriesList.find(s => s.slug === seriesSelect.value);
    useBeatsCheckbox.checked = s ? !!s.use_beats : false;
  }

  async function updateIntroAsset() {
    if (!introCurrentLabel) return;
    const slug = currentSeriesSlug();
    if (!slug) {
      introCurrentLabel.textContent = "";
      if (introRemoveBtn) introRemoveBtn.disabled = true;
      return;
    }
    const res = await fetch(`/api/pf/series/assets?series=${encodeURIComponent(slug)}`);
    const data = await res.json().catch(() => ({}));
    const name = data.assets && data.assets.intro;
    introCurrentLabel.textContent = name ? `aktuell: ${name}` : "kein Intro gesetzt";
    if (introRemoveBtn) introRemoveBtn.disabled = !name;
  }

  if (introUploadBtn) {
    introUploadBtn.addEventListener("click", async () => {
      const slug = currentSeriesSlug();
      const file = introFileInput.files[0];
      if (!slug || !file) return;
      const form = new FormData();
      form.append("slug", slug);
      form.append("stem", "intro");
      form.append("file", file);
      const res = await fetch("/api/pf/series/asset", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "Upload fehlgeschlagen");
        return;
      }
      introFileInput.value = "";
      await updateIntroAsset();
    });
  }

  if (introRemoveBtn) {
    introRemoveBtn.addEventListener("click", async () => {
      const slug = currentSeriesSlug();
      if (!slug) return;
      await fetch(`/api/pf/series/asset?slug=${encodeURIComponent(slug)}&stem=intro`, { method: "DELETE" });
      await updateIntroAsset();
    });
  }

  function updateSeriesSelectTitle() {
    const opt = seriesSelect.options[seriesSelect.selectedIndex];
    seriesSelect.title = opt ? opt.textContent : "";
  }

  async function setActiveSeries(slug) {
    if (!slug) return;
    await fetch("/api/pf/series/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug }),
    });
  }

  // ---------- Review-Schritt nach "Serie erstellen" ----------
  // create_series.py hat series/LATEST bereits auf die neue Serie gesetzt —
  // Konzept anzeigen, bevor teure Skript-/Audio-Generierung startet.
  // "Verwerfen" löscht nur frische Serien ohne Skripte/Audio (Server-Guard).
  const reviewPanel = document.getElementById("pf-series-review");
  const reviewContent = document.getElementById("pf-series-review-content");
  let reviewSlug = null;
  // Aktive Serie VOR dem "Serie erstellen"-Lauf — "Verwerfen" stellt sie
  // wieder her, statt LATEST der mtime-Heuristik des Servers zu überlassen.
  let preCreateSlug = null;

  // Das Orte-Feld wirkt nur bei Templates, deren Creator-Prompt
  // {{LOCATION_COUNT}} kennt (data-locations aus config.list_templates())
  // — bei allen anderen ausblenden.
  const templateSelect = document.getElementById("pf-template");
  const locationsLabel = document.getElementById("pf-locations-label");
  function syncLocationsVisibility() {
    const opt = templateSelect && templateSelect.options[templateSelect.selectedIndex];
    if (locationsLabel) locationsLabel.hidden = !(opt && opt.dataset.locations === "1");
  }
  if (templateSelect) {
    templateSelect.addEventListener("change", syncLocationsVisibility);
    syncLocationsVisibility();
  }

  async function showSeriesReview() {
    const data = await (await fetch("/api/pf/series")).json();
    const slug = data.active;
    if (!slug) return;
    reviewSlug = slug;
    // Dropdown auf die frische Serie stellen, damit Status/Folgeschritte sie zeigen.
    if ([...seriesSelect.options].some(o => o.value === slug)) {
      seriesSelect.value = slug;
      updateSeriesSelectTitle();
      updateMergeAnthologyCheckbox();
      updateUseBeatsCheckbox();
      updateIntroAsset();
    }
    const s = await (await fetch(`/api/status/pf?series=${encodeURIComponent(slug)}`)).json();
    const lines = [
      `Titel:    ${s.series_title || slug}`,
      `Template: ${s.template} (${s.mode})  ·  Sprache: ${s.language || "?"}`,
      `Episoden: ${s.episode_count}`,
      ...(s.episodes || []).map(ep => `  ${ep.index}. ${ep.figure}`),
    ];
    reviewContent.textContent = lines.join("\n");
    reviewPanel.hidden = false;
    refreshPfStatus().catch(console.error);
  }

  document.getElementById("pf-series-keep-btn").addEventListener("click", () => {
    reviewPanel.hidden = true;
    reviewSlug = null;
  });

  document.getElementById("pf-series-discard-btn").addEventListener("click", async () => {
    if (!reviewSlug) { reviewPanel.hidden = true; return; }
    const res = await fetch("/api/pf/series/discard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: reviewSlug }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      reviewContent.textContent = `❌ ${err.error || "Verwerfen fehlgeschlagen"}`;
      return;
    }
    reviewPanel.hidden = true;
    reviewSlug = null;
    seriesSelect.value = "";
    // Zur vorher aktiven Serie zurück (falls sie noch existiert) und das
    // auch nach series/LATEST durchschreiben — der Server hat LATEST beim
    // Discard nur heuristisch (mtime) repointet.
    await loadSeriesList(preCreateSlug || undefined);
    if (preCreateSlug && seriesSelect.value === preCreateSlug) {
      await setActiveSeries(preCreateSlug);
    }
    preCreateSlug = null;
    refreshStatus();
  });

  seriesSelect.addEventListener("change", async () => {
    updateSeriesSelectTitle();
    updateMergeAnthologyCheckbox();
    updateUseBeatsCheckbox();
    updateIntroAsset();
    // Geladene Porträt-Prompts gehören zur vorherigen Serie — leeren.
    document.getElementById("pf-character-blocks").innerHTML = "";
    await setActiveSeries(seriesSelect.value);
    refreshPfStatus().catch(console.error);
  });

  if (mergeAnthologyCheckbox) {
    mergeAnthologyCheckbox.addEventListener("change", async () => {
      const slug = currentSeriesSlug();
      if (!slug) return;
      await fetch("/api/pf/series/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, merge_anthology: mergeAnthologyCheckbox.checked }),
      });
      const s = seriesList.find(s => s.slug === slug);
      if (s) s.merge_anthology = mergeAnthologyCheckbox.checked;
    });
  }

  if (useBeatsCheckbox) {
    useBeatsCheckbox.addEventListener("change", async () => {
      const slug = currentSeriesSlug();
      if (!slug) return;
      await fetch("/api/pf/series/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, use_beats: useBeatsCheckbox.checked }),
      });
      const s = seriesList.find(s => s.slug === slug);
      if (s) s.use_beats = useBeatsCheckbox.checked;
    });
  }

  async function refreshPfStatus() {
    const slug = currentSeriesSlug();
    const res = await fetch("/api/status/pf" + (slug ? `?series=${encodeURIComponent(slug)}` : ""));
    const s = await res.json();
    const container = document.getElementById("pf-status-cards");
    let html = "";
    html += card("Serie", s.series_title ? `${s.series_title} · ${s.template || s.mode}` : "—", s.series_title ? "ready" : "missing");
    html += card("Episoden", s.episode_count, s.episode_count ? "ready" : "missing");
    (s.episodes || []).forEach(ep => {
      html += card(`Ep. ${ep.index}: ${ep.figure}`, `Skript ${stateLabel(ep.script_state)} · Audio ${stateLabel(ep.audio_state)}`,
        ep.audio_state === "running" ? "running" : (ep.script_state === "ready" && ep.audio_state === "ready" ? "ready" : "partial"));
    });
    const failedEps = s.failed_episodes || [];
    if (failedEps.length) {
      html += card("⚠ Vertonung endgültig fehlgeschlagen",
        `${failedEps.join(", ")} — TTS-Server/Log prüfen, dann Vertonung neu starten`, "error");
    }
    html += card("Anthologie", stateLabel(s.anthology_state), s.anthology_state);
    html += card("Cover", s.cover_exists ? "vorhanden" : "offen", s.cover_exists ? "ready" : "missing");
    const chars = s.characters || {};
    if (s.mode === "drama" && chars.roles) {
      html += card("Porträts", `${chars.images}/${chars.roles} Bilder`,
        chars.images >= chars.roles ? "ready" : (chars.images || chars.prompts_ready ? "partial" : "missing"));
    }
    const locs = s.locations || {};
    if (locs.keys) {
      html += card("Szenen-Orte", `${locs.images}/${locs.keys} Bilder`,
        locs.images >= locs.keys ? "ready" : (locs.images || locs.prompts_ready ? "partial" : "missing"));
    }
    const thumbs = s.thumbnails || {};
    if (thumbs.total) {
      html += card("Episoden-Thumbnails", `${thumbs.ready}/${thumbs.total}`,
        thumbs.ready >= thumbs.total ? "ready" : (thumbs.ready ? "partial" : "missing"));
    }
    html += card("Archiv", `${s.archive_count} Serie(n)`, s.archive_count ? "ready" : "missing");
    container.innerHTML = html;
    applyStepStates("pf", pfStepStates(s));

    // Porträt-Schritt nur für Drama-Serien zeigen; Badge spiegelt den
    // Bild-Fortschritt (✓ sobald jede Rolle ihr Bild hat).
    const charStep = document.getElementById("pf-step-characters");
    const isDrama = s.mode === "drama" && (s.characters || {}).roles > 0;
    charStep.hidden = !isDrama;
    if (isDrama) {
      const done = s.characters.images >= s.characters.roles;
      charStep.classList.remove("step-done", "step-current", "step-upcoming");
      charStep.classList.add(done ? "step-done" : "step-current");
      document.getElementById("pf-step-characters-badge").textContent = done ? "✓" : "★";
    }

    // Location-Schritt nur zeigen, wenn die Serie "locations" definiert hat.
    const locStep = document.getElementById("pf-step-locations");
    const hasLocations = (s.locations || {}).keys > 0;
    locStep.hidden = !hasLocations;
    if (hasLocations) {
      const done = s.locations.images >= s.locations.keys;
      locStep.classList.remove("step-done", "step-current", "step-upcoming");
      locStep.classList.add(done ? "step-done" : "step-current");
      document.getElementById("pf-step-locations-badge").textContent = done ? "✓" : "★";
    }

    // Cover-Schritt: immer sichtbar, jede Serie braucht genau ein Cover.
    const coverStep = document.getElementById("pf-step-cover");
    if (coverStep) {
      coverStep.classList.remove("step-done", "step-current", "step-upcoming");
      coverStep.classList.add(s.cover_exists ? "step-done" : "step-current");
      document.getElementById("pf-step-cover-badge").textContent = s.cover_exists ? "✓" : "★";
    }
  }

  // ---------- Charakter-Porträt-Prompts ----------
  async function loadCharacterPrompts() {
    const slug = currentSeriesSlug();
    const res = await fetch("/api/blocks/pf/character-prompts" + (slug ? `?series=${encodeURIComponent(slug)}` : ""));
    const data = await res.json();
    const container = document.getElementById("pf-character-blocks");
    if (!data.prompts_ready) {
      container.innerHTML = `<p class="hint">(Noch keine Prompts generiert — erst „Porträt-Prompts generieren" klicken.)</p>`;
      return;
    }
    container.innerHTML = "";
    data.characters.forEach((c, i) => {
      const block = document.createElement("div");
      block.className = "copy-block";
      const status = c.image
        ? `✅ Bild vorhanden: ${c.image}`
        : `Bild fehlt — speichern als: ${c.target_filename}`;
      block.innerHTML = `
        <label>${c.role} — <span class="hint">${status}</span></label>
        <pre id="pf-char-prompt-${i}"></pre>
        <button class="copy-btn" data-target="pf-char-prompt-${i}">Kopieren</button>`;
      block.querySelector("pre").textContent = c.prompt;
      container.appendChild(block);
    });
  }
  document.getElementById("pf-characters-load-btn").addEventListener("click", () => {
    loadCharacterPrompts().catch(console.error);
  });

  // ---------- Location-Prompts ----------
  async function loadLocationPrompts() {
    const slug = currentSeriesSlug();
    const res = await fetch("/api/blocks/pf/location-prompts" + (slug ? `?series=${encodeURIComponent(slug)}` : ""));
    const data = await res.json();
    const container = document.getElementById("pf-location-blocks");
    if (!data.prompts_ready) {
      container.innerHTML = `<p class="hint">(Noch keine Prompts generiert — erst „Location-Prompts generieren" klicken.)</p>`;
      return;
    }
    container.innerHTML = "";
    data.locations.forEach((loc, i) => {
      const block = document.createElement("div");
      block.className = "copy-block";
      const status = loc.image
        ? `✅ Bild vorhanden: ${loc.image}`
        : `Bild fehlt — speichern als: ${loc.target_filename}`;
      block.innerHTML = `
        <label>${loc.key} — <span class="hint">${status}</span></label>
        <pre id="pf-loc-prompt-${i}"></pre>
        <button class="copy-btn" data-target="pf-loc-prompt-${i}">Kopieren</button>`;
      block.querySelector("pre").textContent = loc.prompt;
      container.appendChild(block);
    });
  }
  document.getElementById("pf-locations-load-btn").addEventListener("click", () => {
    loadLocationPrompts().catch(console.error);
  });

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
    refreshTtsStatus().catch(console.error);
  }
  loadSeriesList().then(refreshStatus).catch(() => refreshStatus());
  setInterval(refreshStatus, 4000);

  // ---------- Run buttons ----------
  // pf_create_series legt eine NEUE Serie an und braucht daher keine
  // Serien-Auswahl; jedes andere pf_*-Kommando wirkt auf die gerade
  // ausgewählte Serie und bekommt sie automatisch als 'series'-Param mit.
  const PF_SERIES_SCOPED_EXCLUDE = new Set(["pf_create_series", "pf_import_story", "pf_cloud_rent"]);

  function collectParams(btn) {
    const params = {};
    for (const attr of btn.attributes) {
      if (attr.name.startsWith("data-param-")) {
        const paramName = attr.name.replace("data-param-", "");
        const el = document.getElementById(attr.value);
        if (el) params[paramName] = el.type === "checkbox" ? el.checked : el.value;
      }
    }
    const commandId = btn.dataset.command;
    if (commandId && commandId.startsWith("pf_") && !PF_SERIES_SCOPED_EXCLUDE.has(commandId)) {
      const slug = currentSeriesSlug();
      if (slug) params.series = slug;
    }
    return params;
  }

  // Hängt das Log-Panel an einen (neuen oder bereits laufenden) Job. Wird
  // sowohl direkt nach dem Start als auch beim Reconnect nach einem
  // Seiten-Reload verwendet — der Server spielt bei jedem subscribe() den
  // kompletten bisherigen Log-Puffer neu ab.
  function attachStream(jobId, commandId, btn) {
    if (currentEventSource) currentEventSource.close();
    currentJobId = jobId;
    logTitle.textContent = "Log: " + commandId;
    logStep.textContent = "";
    logDot.className = "log-dot running";
    killBtn.hidden = false;

    // "Episode 2/5" aus batch.py-Zeilen — wird mit dem Chunk-Fortschritt
    // des Checkpoint-Pollings zu einer Anzeige kombiniert.
    let episodePhase = "";

    const es = new EventSource(`/api/stream/${jobId}`);
    currentEventSource = es;

    es.onopen = () => {
      // Auch bei automatischem SSE-Reconnect kommt der volle Puffer erneut
      // — vorher leeren, sonst verdoppeln sich die Zeilen.
      logOutput.textContent = "";
    };
    es.addEventListener("log", (ev) => {
      const payload = JSON.parse(ev.data);
      logOutput.textContent += payload.line + "\n";
      logOutput.scrollTop = logOutput.scrollHeight;
    });
    es.addEventListener("progress", (ev) => {
      const payload = JSON.parse(ev.data);
      const chunkInfo = `${payload.part || ""}: ${payload.chunks} Chunks`;
      logStep.textContent = episodePhase ? `${episodePhase} · ${chunkInfo}` : chunkInfo;
    });
    es.addEventListener("episode", (ev) => {
      const payload = JSON.parse(ev.data);
      episodePhase = `Episode ${payload.current}/${payload.total}`;
      logStep.textContent = `${episodePhase} — ${payload.name}`;
    });
    es.addEventListener("step", (ev) => {
      const payload = JSON.parse(ev.data);
      logStep.textContent = `Schritt ${payload.step}: ${payload.label}`;
    });
    es.addEventListener("done", (ev) => {
      const payload = JSON.parse(ev.data);
      logOutput.textContent += `\n${payload.returncode === 0 ? "✅ fertig" : "❌ Fehler (Exit " + payload.returncode + ")"}\n`;
      logDot.className = payload.returncode === 0 ? "log-dot done" : "log-dot error";
      es.close();
      currentJobId = null;
      killBtn.hidden = true;
      if (btn) btn.disabled = false;
      playChime(payload.returncode === 0);
      if (payload.returncode === 0 && (commandId === "pf_create_series" || commandId === "pf_import_story")) {
        // Beide legen series/<slug>/ neu an und setzen series/LATEST selbst
        // — Dropdown neu laden und die frische Serie übernehmen.
        loadSeriesList().then(() => {
          refreshStatus();
          if (commandId === "pf_create_series") showSeriesReview().catch(console.error);
        }).catch(console.error);
      } else {
        refreshStatus();
      }
      if (payload.returncode === 0 && commandId === "pf_character_prompts") {
        loadCharacterPrompts().catch(console.error);
      }
      if (commandId === "pf_cloud_rent") {
        // Auch bei Fehlschlag neu laden — eine halb eingerichtete Instanz
        // taucht trotzdem in der vastai-Liste auf und soll sichtbar sein.
        loadCloudPool().catch(console.error);
      }
    });
    es.onerror = () => {
      // EventSource verbindet sich selbst neu (readyState CONNECTING) —
      // nur ein endgültig geschlossener Stream ist ein echter Fehler.
      if (es.readyState === EventSource.CLOSED) {
        logDot.className = "log-dot error";
        killBtn.hidden = true;
        if (btn) btn.disabled = false;
      }
    };
  }

  async function runCommand(commandId, params, btn) {
    logOutput.textContent = "";
    logTitle.textContent = "Log: " + commandId;
    logStep.textContent = "";
    logDot.className = "log-dot running";
    setLogOpen(true);
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
      logDot.className = "log-dot error";
      if (btn) btn.disabled = false;
      return;
    }

    const data = await res.json();
    if (!res.ok) {
      logOutput.textContent += `❌ ${data.error || "Fehler beim Start"}\n`;
      logDot.className = "log-dot error";
      if (btn) btn.disabled = false;
      return;
    }

    attachStream(data.job_id, commandId, btn);
  }

  // ---------- Reconnect nach Seiten-Reload ----------
  // Laufende Jobs überleben einen Reload serverseitig problemlos — hier
  // holen wir uns Log-Stream und Button-Zustand zurück, statt so zu tun,
  // als liefe nichts.
  async function syncRunningJobs({ reattach = false } = {}) {
    let snap;
    try {
      snap = await (await fetch("/api/jobs")).json();
    } catch {
      return;
    }
    const running = Object.entries(snap)
      .filter(([, job]) => job.state === "running")
      .sort((a, b) => b[1].started_at - a[1].started_at);
    const runningIds = new Set(running.map(([cid]) => cid));
    document.querySelectorAll(".run-btn").forEach(b => {
      b.disabled = runningIds.has(b.dataset.command);
    });
    if (reattach && running.length && !currentJobId) {
      const [cid, job] = running[0];
      const btn = document.querySelector(`.run-btn[data-command="${cid}"]`);
      attachStream(job.job_id, cid, btn);
      setLogOpen(true);
    }
  }
  syncRunningJobs({ reattach: true }).catch(console.error);
  setInterval(() => syncRunningJobs().catch(console.error), 4000);

  // ---------- Vertonungs-Ziel Lokal/Cloud ----------
  // Bei "cloud" werden die beiden Vertonen-Buttons auf pf_render_remote
  // (cloud/render_remote.sh) umgeschrieben: pf_batch -> ganze Serie remote,
  // pf_podcast_maker -> --only <datei>. Alles andere bleibt unberührt;
  // pf_render_remote startet KEIN lokales TTS (nicht in AUTO_TTS_COMMANDS).
  const renderTarget = document.getElementById("pf-render-target");
  const cloudStopAfterLabel = document.getElementById("pf-cloud-stop-after-label");
  const cloudLocalMasterLabel = document.getElementById("pf-cloud-local-master-label");
  const cloudHint = document.getElementById("pf-cloud-hint");

  function syncRenderTargetUI() {
    const cloud = renderTarget && renderTarget.value === "cloud";
    if (cloudStopAfterLabel) cloudStopAfterLabel.hidden = !cloud;
    if (cloudLocalMasterLabel) cloudLocalMasterLabel.hidden = !cloud;
    if (cloudHint) cloudHint.hidden = !cloud;
  }
  if (renderTarget) {
    renderTarget.value = localStorage.getItem("pfRenderTarget") || "local";
    renderTarget.addEventListener("change", () => {
      localStorage.setItem("pfRenderTarget", renderTarget.value);
      syncRenderTargetUI();
    });
    syncRenderTargetUI();
  }

  // ---------- Cloud-Server-Pool (Scouting) ----------
  // Liste = Live-Instanzen (vastai) + gelerntes Maschinen-Urteil aus
  // cloud/.machine_stats.json. ★/✗ posten nach /api/cloud/machine; die
  // Urteile fließen über machine_stats.py in jede künftige Offer-Suche ein.
  const cloudPool = document.getElementById("pf-cloud-pool");

  async function cloudMachineAction(machineId, action, instanceId) {
    const body = { machine_id: machineId, action };
    if (instanceId) body.instance_id = instanceId;
    const res = await fetch("/api/cloud/machine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) alert(data.error || "Aktion fehlgeschlagen");
    else if (data.destroy_error) alert("Maschine vermerkt, aber Instanz-Löschen schlug fehl: " + data.destroy_error);
    await loadCloudPool();
  }

  function cloudJudgement(m) {
    if (!m) return "–";
    if (m.favorite) return "★ Favorit" + (m.manual ? "" : " (auto)");
    if (m.avoid) return "✗ verworfen";
    if (m.blacklisted) return "✗ blacklisted (temporär)";
    return "–";
  }

  async function loadCloudPool() {
    if (!cloudPool) return;
    let data;
    try {
      data = await (await fetch("/api/cloud/instances")).json();
    } catch {
      cloudPool.innerHTML = '<p class="hint">Server-Liste nicht erreichbar.</p>';
      return;
    }
    const machines = data.machines || {};
    const rows = [];
    const liveMachineIds = new Set();
    for (const inst of data.instances || []) {
      liveMachineIds.add(String(inst.machine_id));
      const m = machines[String(inst.machine_id)];
      const fav = m && m.favorite;
      rows.push(`<tr>
        <td>Instanz ${inst.instance_id}</td>
        <td>Maschine ${inst.machine_id}</td>
        <td>${inst.gpu_name || "?"} · ${inst.geolocation || "?"} · $${(inst.dph_total || 0).toFixed(3)}/h</td>
        <td>${inst.status || "?"}</td>
        <td>${cloudJudgement(m)}</td>
        <td>
          <button class="cloud-fav-btn" data-machine="${inst.machine_id}" data-fav="${fav ? 1 : 0}">${fav ? "☆ Favorit entfernen" : "★ Favorit"}</button>
          <button class="cloud-reject-btn" data-machine="${inst.machine_id}" data-instance="${inst.instance_id}">✗ Verwerfen</button>
        </td>
      </tr>`);
    }
    // Gelernte Maschinen ohne Live-Instanz (der eigentliche "Pool"):
    for (const [mid, m] of Object.entries(machines)) {
      if (liveMachineIds.has(mid)) continue;
      // Manuell beurteilte bleiben immer sichtbar — sonst verschwindet eine
      // Maschine nach "Favorit entfernen" aus der Liste und das Urteil wäre
      // im WebUI nicht mehr umkehrbar.
      if (!m.favorite && !m.avoid && !m.blacklisted && !m.manual) continue;
      rows.push(`<tr>
        <td>–</td>
        <td>Maschine ${mid}</td>
        <td></td>
        <td></td>
        <td>${cloudJudgement(m)}</td>
        <td>${m.favorite
          ? `<button class="cloud-fav-btn" data-machine="${mid}" data-fav="1">☆ Favorit entfernen</button>`
          : `<button class="cloud-fav-btn" data-machine="${mid}" data-fav="0">★ Favorit</button>`}</td>
      </tr>`);
    }
    const errorLine = data.error ? `<p class="hint">⚠ ${data.error}</p>` : "";
    cloudPool.innerHTML = errorLine + (rows.length
      ? `<table class="cloud-pool-table"><tbody>${rows.join("")}</tbody></table>`
      : '<p class="hint">Keine Instanzen und noch keine beurteilten Maschinen.</p>');

    cloudPool.querySelectorAll(".cloud-fav-btn").forEach(b => {
      b.addEventListener("click", () =>
        cloudMachineAction(Number(b.dataset.machine), b.dataset.fav === "1" ? "unfavorite" : "favorite"));
    });
    cloudPool.querySelectorAll(".cloud-reject-btn").forEach(b => {
      b.addEventListener("click", () => {
        if (!confirm(`Maschine ${b.dataset.machine} dauerhaft meiden und Instanz ${b.dataset.instance} LÖSCHEN?`)) return;
        cloudMachineAction(Number(b.dataset.machine), "reject", Number(b.dataset.instance));
      });
    });
  }

  const cloudPoolRefresh = document.getElementById("pf-cloud-pool-refresh");
  if (cloudPoolRefresh) cloudPoolRefresh.addEventListener("click", () => loadCloudPool());
  loadCloudPool().catch(console.error);

  function maybeCloudRewrite(commandId, params) {
    if (!renderTarget || renderTarget.value !== "cloud") return [commandId, params];
    if (commandId !== "pf_batch" && commandId !== "pf_podcast_maker") return [commandId, params];
    const mapped = { series: params.series };
    if (commandId === "pf_podcast_maker") {
      if (!params.input_file) {
        alert("Bitte zuerst die Skript-Datei (z.B. ep1.txt) eintragen.");
        return [null, null];
      }
      mapped.only = params.input_file;
    }
    const stopAfter = document.getElementById("pf-cloud-stop-after");
    if (stopAfter && stopAfter.checked) mapped.stop_after = true;
    const localMaster = document.getElementById("pf-cloud-local-master");
    if (localMaster && localMaster.checked) mapped.local_master = true;
    return ["pf_render_remote", mapped];
  }

  document.querySelectorAll(".run-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      ensureAudioContext();
      const [commandId, params] = maybeCloudRewrite(btn.dataset.command, collectParams(btn));
      if (!commandId) return;
      if (commandId === "pf_create_series") preCreateSlug = currentSeriesSlug();
      runCommand(commandId, params, btn);
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
    const template = document.getElementById("pf-template").value;
    const minutes = document.getElementById("pf-minutes").value || 35;
    const locations = document.getElementById("pf-locations").value;
    if (!topic.trim()) { alert("Bitte zuerst ein Thema eintragen."); return; }
    const res = await fetch(`/api/blocks/pf/series-prompt?topic=${encodeURIComponent(topic)}&episodes=${episodes}&template=${encodeURIComponent(template)}&minutes=${minutes}&locations=${encodeURIComponent(locations)}`);
    const data = await res.json();
    document.getElementById("pf-series-block").textContent = data.block || data.error || "";
  });

  document.getElementById("pf-meta-load-btn").addEventListener("click", async () => {
    const res = await fetch("/api/blocks/pf/anthology-meta");
    const data = await res.json();
    document.getElementById("pf-meta-block").textContent = data.anthology_meta || "(noch nicht vorhanden)";
    document.getElementById("pf-upload-index-block").textContent = data.upload_index || "(noch nicht vorhanden)";
  });

})();
