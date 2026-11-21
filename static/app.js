/* VoiceFit page. No frameworks. Serves against /api/* or, with ?mock=1,
   against static/mock-turn.json (turn responses and mock_sessions rows). */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const els = {
    mic: $('mic-btn'),
    status: $('status'),
    heard: $('heard'),
    coach: $('coach'),
    coachAudio: $('coach-audio'),
    coachReplay: $('coach-replay'),
    textForm: $('text-form'),
    textInput: $('text-input'),
    send: $('send-btn'),
    sessions: $('sessions'),
    trace: $('trace'),
    traceSummary: $('trace-summary'),
    traceList: $('trace-list'),
    reset: $('reset-btn'),
    error: $('error'),
    chips: { low: $('mood-low'), active: $('mood-active'), pumped: $('mood-pumped') },
  };

  const MOODS = ['low', 'active', 'pumped'];
  const MOCK = new URLSearchParams(window.location.search).get('mock') === '1';

  const STATUS_TEXT = {
    idle: 'Tap to speak',
    listening: 'Listening…',
    thinking: 'Thinking…',
    speaking: '',
    error: 'Tap to try again',
  };

  let state = 'idle';
  let sessionId = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let recordStart = 0;
  let listenTimer = null;
  let exerciseNames = {};

  /* ---------- helpers ---------- */

  function setState(next) {
    state = next;
    els.mic.classList.toggle('listening', next === 'listening');
    els.mic.classList.toggle('busy', next === 'thinking' || next === 'speaking');
    els.mic.disabled = next === 'thinking' || next === 'speaking';
    els.status.textContent = STATUS_TEXT[next] || '';
    const thinking = next === 'thinking';
    els.send.disabled = thinking;
    els.reset.disabled = thinking;
    for (const m of MOODS) els.chips[m].disabled = thinking;
  }

  function showError(message) {
    els.error.textContent = message;
    els.error.hidden = false;
  }

  function clearError() {
    els.error.hidden = true;
    els.error.textContent = '';
  }

  function setMood(mood) {
    for (const m of MOODS) els.chips[m].classList.toggle('active', m === mood);
  }

  // 80.0 -> "80", 77.5 -> "77.5": one decimal, trailing ".0" removed.
  function fmtKg(weight) {
    const s = Number(weight).toFixed(1);
    return s.endsWith('.0') ? s.slice(0, -2) : s;
  }

  function relDay(iso) {
    const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    return days <= 0 ? 'Today' : days + ' d ago';
  }

  function repsArray(reps) {
    if (Array.isArray(reps)) return reps;
    if (typeof reps === 'string') {
      try {
        const parsed = JSON.parse(reps);
        if (Array.isArray(parsed)) return parsed;
      } catch (e) { /* fall through */ }
    }
    return [];
  }

  function nameFor(exerciseId) {
    if (exerciseNames[exerciseId]) return exerciseNames[exerciseId];
    return exerciseId.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  }

  /* ---------- API ---------- */

  async function loadMock() {
    const res = await fetch('mock-turn.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  async function fetchSessions(exerciseId, limit) {
    if (MOCK) {
      const mock = await loadMock();
      return (mock.mock_sessions[exerciseId] || []).slice(0, limit);
    }
    const res = await fetch('/api/sessions?exercise=' + encodeURIComponent(exerciseId) + '&limit=' + limit);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  async function postTurn(formData) {
    setState('thinking');
    try {
      let turn;
      if (MOCK) {
        turn = await loadMock();
      } else {
        const res = await fetch('/api/turn', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        turn = await res.json();
      }
      applyTurn(turn);
    } catch (err) {
      setState('error');
      showError('Could not reach VoiceFit. Try again or type your entry.');
    }
  }

  function applyTurn(turn) {
    clearError();
    if (turn.session_id) sessionId = turn.session_id;

    if (turn.transcript) {
      els.heard.textContent = '“' + turn.transcript + '”';
    } else {
      showError("Didn't catch that. Try again.");
    }
    els.coach.textContent = turn.reply_text || '';

    setMood(MOODS.includes(turn.mood) ? turn.mood : null);
    renderTrace(turn.trace || []);
    renderSavedSessions(turn.saved_sessions || []);

    if (turn.audio_base64) {
      els.coachAudio.src = 'data:' + (turn.audio_mime || 'audio/mpeg') + ';base64,' + turn.audio_base64;
      els.coachReplay.hidden = false;
      const played = els.coachAudio.play();
      if (played && typeof played.catch === 'function') {
        played.catch(() => setState('idle'));
      }
    } else {
      els.coachReplay.hidden = true;
      setState('idle');
    }
  }

  /* ---------- recording ---------- */

  async function startRecording() {
    clearError();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showError('Microphone unavailable. Type your entry below.');
      setState('error');
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      showError('Microphone unavailable. Type your entry below.');
      setState('error');
      return;
    }
    audioChunks = [];
    let options;
    if (window.MediaRecorder && MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      options = { mimeType: 'audio/webm;codecs=opus' };
    }
    mediaRecorder = new MediaRecorder(stream, options);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size) audioChunks.push(e.data);
    };
    mediaRecorder.onstop = onRecordingStop;
    recordStart = Date.now();
    mediaRecorder.start();
    setState('listening');
    listenTimer = setTimeout(() => stopRecording(), 30000);
  }

  function stopRecording() {
    if (listenTimer) { clearTimeout(listenTimer); listenTimer = null; }
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      setState('thinking');
      mediaRecorder.stop();
    }
  }

  function onRecordingStop() {
    const mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
    const blob = new Blob(audioChunks, { type: mime });
    if (mediaRecorder && mediaRecorder.stream) {
      mediaRecorder.stream.getTracks().forEach((t) => t.stop());
    }
    const durationMs = Date.now() - recordStart;
    if (durationMs < 500 || blob.size === 0) {
      setState('idle');
      return;
    }
    console.log('recorded audio blob:', blob.size, 'bytes,', durationMs, 'ms');
    const fd = new FormData();
    fd.append('audio', blob, 'clip.webm');
    if (sessionId) fd.append('session_id', sessionId);
    postTurn(fd);
  }

  function toggleMic() {
    if (state === 'idle' || state === 'error') startRecording();
    else if (state === 'listening') stopRecording();
  }

  /* ---------- text input ---------- */

  function sendText() {
    const text = els.textInput.value.trim();
    if (!text || state === 'thinking') return;
    const fd = new FormData();
    fd.append('transcript', text);
    if (sessionId) fd.append('session_id', sessionId);
    els.textInput.value = '';
    postTurn(fd);
  }

  /* ---------- sessions ---------- */

  function outcomeBadge(outcome, deltaReps) {
    const b = document.createElement('span');
    b.className = 'badge ' + outcome;
    let text = outcome;
    if (outcome === 'beat') {
      text = '▲ BEAT' + (deltaReps != null ? ' +' + deltaReps + (Math.abs(deltaReps) === 1 ? ' rep' : ' reps') : '');
    } else if (outcome === 'held') {
      text = '● HELD';
    } else if (outcome === 'dropped') {
      text = '▼ DROPPED' + (deltaReps != null ? ' −' + Math.abs(deltaReps) + (Math.abs(deltaReps) === 1 ? ' rep' : ' reps') : '');
    } else if (outcome === 'first') {
      text = '★ FIRST';
    }
    b.textContent = text;
    return b;
  }

  function sessionRow(row, highlightId, saved) {
    const reps = repsArray(row.reps);
    const total = row.total_reps != null ? row.total_reps : reps.reduce((a, b) => a + b, 0);
    const isNew = highlightId != null && row.id === highlightId;

    const el = document.createElement('div');
    el.className = 'row' + (isNew ? ' new' : '');

    const main = document.createElement('div');
    main.className = 'row-main';
    const day = document.createElement('span');
    day.className = 'day';
    day.textContent = relDay(row.performed_at);
    const weight = document.createElement('span');
    weight.className = 'weight';
    weight.textContent = fmtKg(row.weight_kg) + ' kg';
    const repsEl = document.createElement('span');
    repsEl.className = 'reps';
    repsEl.textContent = reps.join(' · ');
    const totalEl = document.createElement('span');
    totalEl.className = 'total';
    totalEl.textContent = String(total);
    main.append(day, weight, repsEl, totalEl);

    const tags = document.createElement('div');
    tags.className = 'tags';
    if (isNew && saved) tags.appendChild(outcomeBadge(saved.outcome, saved.delta_reps));
    if (isNew) {
      const n = document.createElement('span');
      n.className = 'tag new-tag';
      n.textContent = 'NEW';
      tags.appendChild(n);
    }
    if (row.is_seed) {
      const s = document.createElement('span');
      s.className = 'tag seed-tag';
      s.textContent = 'seed';
      tags.appendChild(s);
    }
    if (row.mood) {
      const m = document.createElement('span');
      m.className = 'tag mood-tag';
      m.textContent = row.mood;
      tags.appendChild(m);
    }

    el.append(main, tags);
    return el;
  }

  function sessionCard(title, rows, highlightId, saved) {
    const card = document.createElement('section');
    card.className = 'card';
    const h = document.createElement('h3');
    h.textContent = title;
    card.appendChild(h);
    for (const row of rows) card.appendChild(sessionRow(row, highlightId, saved));
    return card;
  }

  async function renderSavedSessions(saved) {
    if (!saved.length) return; // no saves: leave the cards as they are
    try {
      const cards = [];
      for (const s of saved) {
        const rows = await fetchSessions(s.exercise_id, 4);
        cards.push(sessionCard(s.exercise_name || nameFor(s.exercise_id), rows, s.session_id, s));
      }
      els.sessions.innerHTML = '';
      for (const c of cards) els.sessions.appendChild(c);
    } catch (err) {
      setState('error');
      showError('Could not reach VoiceFit. Try again or type your entry.');
    }
  }

  async function loadInitialSessions() {
    try {
      const rows = await fetchSessions('romanian_deadlift', 4);
      els.sessions.innerHTML = '';
      els.sessions.appendChild(sessionCard(nameFor('romanian_deadlift'), rows, null, null));
    } catch (err) {
      // no backend yet: the sessions column stays empty
    }
  }

  async function loadExerciseNames() {
    if (MOCK) return;
    try {
      const res = await fetch('/api/exercises');
      if (!res.ok) return;
      const list = await res.json();
      for (const e of list) exerciseNames[e.id] = e.name;
    } catch (err) { /* names fall back to prettified ids */ }
  }

  /* ---------- trace ---------- */

  function compactArgs(entry) {
    const a = entry.args || {};
    if (entry.tool === 'get_last_session') return String(a.exercise != null ? a.exercise : '');
    if (entry.tool === 'log_session') {
      const reps = repsArray(a.reps).join(',');
      let s = fmtKg(a.weight) + ' ' + (a.unit || 'kg') + ' ' + reps;
      if (a.mood) s += ' · ' + a.mood;
      return s;
    }
    if (entry.tool === 'get_mood_history') return String(a.mood != null ? a.mood : '');
    return JSON.stringify(a);
  }

  function compactResult(entry) {
    const r = entry.result || {};
    if (entry.tool === 'get_last_session') {
      if (r.found) return fmtKg(r.weight_kg) + ' kg · ' + repsArray(r.reps).join(',');
      if (r.error) return 'unknown exercise';
      return 'no history';
    }
    if (entry.tool === 'log_session') {
      if (r.saved) {
        let s = 'saved · ' + r.outcome;
        if (r.delta_reps != null) s += ' · ' + (r.delta_reps > 0 ? '+' : '') + r.delta_reps;
        return s;
      }
      return 'not saved · ' + (r.error || 'error');
    }
    if (entry.tool === 'get_mood_history') {
      if (r.error) return String(r.error);
      return (r.by_exercise || [])
        .slice(0, 3)
        .map((e) => e.exercise_name + ' ' + e.held_or_beat + '/' + e.sessions)
        .join(' · ');
    }
    return JSON.stringify(r);
  }

  function traceEntry(entry, n) {
    const box = document.createElement('div');
    box.className = 'trace-entry';

    const line1 = document.createElement('div');
    line1.className = 'trace-line';
    const tool = document.createElement('span');
    tool.className = 'trace-tool';
    tool.textContent = n + ' ' + entry.tool;
    const args = document.createElement('span');
    args.className = 'trace-args';
    args.textContent = compactArgs(entry);
    const ms = document.createElement('span');
    ms.className = 'trace-ms';
    ms.textContent = entry.ms + ' ms';
    line1.append(tool, args, ms);

    const line2 = document.createElement('div');
    line2.className = 'trace-line trace-result';
    line2.textContent = '→ ' + compactResult(entry);

    const full = document.createElement('pre');
    full.className = 'trace-json';
    full.hidden = true;
    full.textContent = JSON.stringify({ args: entry.args, result: entry.result }, null, 2);

    box.append(line1, line2, full);
    box.addEventListener('click', () => { full.hidden = !full.hidden; });
    return box;
  }

  function renderTrace(trace) {
    els.traceSummary.textContent = 'TOOL TRACE (' + trace.length + (trace.length === 1 ? ' call' : ' calls') + ')';
    els.traceList.innerHTML = '';
    trace.forEach((entry, i) => els.traceList.appendChild(traceEntry(entry, i + 1)));
  }

  /* ---------- mood chips ---------- */

  async function chipClick(mood) {
    setMood(mood);
    if (MOCK) return;
    try {
      await fetch('/api/mood', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mood: mood }),
      });
    } catch (err) { /* highlight stays; the mood is demo state */ }
  }

  /* ---------- reset ---------- */

  async function resetDemo() {
    sessionId = null;
    els.heard.textContent = '';
    els.coach.textContent = '';
    els.traceList.innerHTML = '';
    els.traceSummary.textContent = 'TOOL TRACE (0 calls)';
    els.trace.open = false;
    setMood(null);
    els.coachAudio.pause();
    els.coachAudio.removeAttribute('src');
    els.coachAudio.load();
    els.coachReplay.hidden = true;
    clearError();
    setState('idle');
    if (!MOCK) {
      try { await fetch('/api/reset', { method: 'POST' }); } catch (err) { /* local reset still applies */ }
    }
    loadInitialSessions();
  }

  /* ---------- wiring ---------- */

  els.mic.addEventListener('click', toggleMic);

  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && document.activeElement !== els.textInput) {
      e.preventDefault();
      toggleMic();
    }
  });

  els.textForm.addEventListener('submit', (e) => {
    e.preventDefault();
    sendText();
  });

  els.coachReplay.addEventListener('click', () => {
    if (els.coachAudio.src) els.coachAudio.play();
  });

  els.coachAudio.addEventListener('play', () => setState('speaking'));
  els.coachAudio.addEventListener('ended', () => setState('idle'));

  for (const m of MOODS) els.chips[m].addEventListener('click', () => chipClick(m));

  els.reset.addEventListener('click', resetDemo);

  /* ---------- init ---------- */

  setState('idle');
  if (MOCK) {
    loadMock()
      .then((turn) => applyTurn(turn))
      .catch(() => {
        setState('error');
        showError('Could not reach VoiceFit. Try again or type your entry.');
      });
  } else {
    loadExerciseNames();
    loadInitialSessions();
  }
})();
