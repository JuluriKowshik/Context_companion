// Context Companion content script (YouTube), v0.3.
//
// The Companion is a switch. ON means: watch the captions, run every upcoming
// line through the pipeline ahead of time, and show a tiny card at the exact
// moment a genuinely useful term is spoken. OFF means: do nothing at all.
// The switch state persists in chrome.storage.local across videos and reloads.
//
// Spoiler rule, enforced in Engine.contextFor(): the context for a cue at time
// T contains only cues with start <= T. Work may run before T. Nothing is
// displayed before T.

(() => {
  "use strict";

  // ---------------------------------------------------------------------
  // Settings (persistent) and policy (from backend /config, with fallbacks)
  // ---------------------------------------------------------------------
  // Embedded caption tracks are processed automatically; captions do not need
  // to be visible in YouTube for this to work.
  const STORED_DEFAULTS = { companionEnabled: true, settingsVersion: 3, backendUrl: "http://localhost:8000", recentConcepts: {} };
  const POLICY_DEFAULTS = {
    prefetch_window_seconds: 6,
    auto_show_confidence: 0.85,
    auto_hint_cooldown_seconds: 8,
    max_hints_per_minute: 4,
    recent_concept_ttl_seconds: 1800,
    late_display_grace_seconds: 2.5,
    card_lifetime_seconds: 5,
    max_card_queue_size: 12,
    max_cards_per_cue: 3,
  };
  const CONST = {
    cardMs: 5000,
    requestTimeoutMs: 8000,
    maxConcurrent: 3,
    tickMs: 100, // display alignment resolution
    cueGraceSec: 0.6,
    contextCues: 3,
  };

  const stored = { ...STORED_DEFAULTS };
  let policy = { ...POLICY_DEFAULTS };

  const log = (...a) => console.debug("[Companion]", ...a);
  const videoEl = () => document.querySelector("video.html5-main-video");
  const currentVideoId = () => new URLSearchParams(location.search).get("v") || "";
  const norm = (s) => String(s || "").toLowerCase().replace(/[^\w\s'-]/g, " ").replace(/\s+/g, " ").trim();

  async function loadStored() {
    try {
      const saved = await chrome.storage.local.get(STORED_DEFAULTS);
      Object.assign(stored, saved);
      // v3 changes the product default from manual-only to embedded-caption
      // automation. Migrate the old setting once rather than leaving users
      // silently switched off.
      if (saved.settingsVersion !== STORED_DEFAULTS.settingsVersion) await saveStored({ companionEnabled: true, settingsVersion: STORED_DEFAULTS.settingsVersion });
    } catch (_) {}
  }
  async function saveStored(patch) {
    Object.assign(stored, patch);
    try { await chrome.storage.local.set(patch); } catch (_) {}
  }
  async function loadPolicy() {
    try {
      const res = await fetch(`${stored.backendUrl}/config`);
      if (res.ok) policy = { ...POLICY_DEFAULTS, ...(await res.json()) };
    } catch (_) {}
  }

  // ---------------------------------------------------------------------
  // Timed text parsing. Keeps per-word offsets when the track has them, so a
  // card can be aligned to the word rather than the line.
  // ---------------------------------------------------------------------
  const TimedText = {
    parse(body) {
      const t = body.trim();
      let cues = [];
      if (t.startsWith("{")) cues = this.json3(t);
      else if (t.startsWith("WEBVTT")) cues = this.vtt(t);
      else if (t.startsWith("<")) cues = this.xml(t);
      return this.clean(cues);
    },
    json3(text) {
      const cues = [];
      for (const ev of JSON.parse(text).events || []) {
        if (!ev.segs) continue;
        const words = [];
        for (const s of ev.segs) {
          const w = (s.utf8 || "").replace(/\n/g, " ").trim();
          if (w) words.push({ t: (s.tOffsetMs || 0) / 1000, text: w });
        }
        if (!words.length) continue;
        const start = (ev.tStartMs || 0) / 1000;
        const textJoined = words.map((w) => w.text).join(" ");
        if (ev.aAppend && cues.length) { cues[cues.length - 1].text += " " + textJoined; continue; }
        cues.push({ start, end: start + (ev.dDurationMs || 0) / 1000, text: textJoined, words });
      }
      return cues;
    },
    xml(text) {
      const doc = new DOMParser().parseFromString(text, "text/xml");
      const cues = [];
      for (const p of doc.querySelectorAll("p")) {
        const start = Number(p.getAttribute("t")) / 1000;
        const dur = Number(p.getAttribute("d") || 0) / 1000;
        const segs = Array.from(p.querySelectorAll("s"));
        const words = segs.length
          ? segs.map((s) => ({ t: Number(s.getAttribute("t") || 0) / 1000, text: (s.textContent || "").trim() })).filter((w) => w.text)
          : [];
        const t = words.length ? words.map((w) => w.text).join(" ") : (p.textContent || "").replace(/\s+/g, " ").trim();
        if (!t) continue;
        if (p.getAttribute("a") === "1" && cues.length) { cues[cues.length - 1].text += " " + t; continue; }
        cues.push({ start, end: start + dur, text: t, words });
      }
      if (cues.length) return cues;
      for (const node of doc.querySelectorAll("text")) {
        const start = Number(node.getAttribute("start"));
        const dur = Number(node.getAttribute("dur") || 0);
        const el = document.createElement("textarea"); el.innerHTML = node.textContent || "";
        const t = el.value.replace(/\s+/g, " ").trim();
        if (t) cues.push({ start, end: start + dur, text: t, words: [] });
      }
      return cues;
    },
    vtt(text) {
      const cues = [];
      const toSec = (s) => s.trim().split(":").reduce((acc, v) => acc * 60 + parseFloat(v.replace(",", ".")), 0);
      for (const block of text.split(/\n\s*\n/)) {
        const lines = block.split("\n");
        const i = lines.findIndex((l) => l.includes("-->"));
        if (i < 0) continue;
        const [a, b] = lines[i].split("-->");
        const t = lines.slice(i + 1).join(" ").replace(/<[^>]+>/g, "").trim();
        if (t) cues.push({ start: toSec(a), end: toSec(b.trim().split(/\s+/)[0]), text: t, words: [] });
      }
      return cues;
    },
    clean(cues) {
      const seen = new Set();
      return cues
        .filter((c) => Number.isFinite(c.start) && c.text)
        .sort((a, b) => a.start - b.start)
        .filter((c) => { const k = `${c.start.toFixed(2)}|${c.text}`; if (seen.has(k)) return false; seen.add(k); return true; })
        .map((c, i) => ({ ...c, index: i }));
    },
  };

  class Timeline {
    constructor(cues) { this.cues = cues; }
    indexAt(t) {
      let lo = 0, hi = this.cues.length - 1, best = -1;
      while (lo <= hi) { const m = (lo + hi) >> 1; if (this.cues[m].start <= t) { best = m; lo = m + 1; } else hi = m - 1; }
      if (best < 0) return -1;
      return t <= this.cues[best].end + CONST.cueGraceSec ? best : -1;
    }
    upcoming(t, windowSec) {
      const out = [];
      for (const c of this.cues) { if (c.start > t + windowSec) break; if (c.end + CONST.cueGraceSec >= t) out.push(c); }
      return out;
    }
    before(index, n) { return this.cues.slice(Math.max(0, index - n), index); }
  }

  // When the track has word timings, find the moment the term is actually spoken.
  function showAtFor(cue, term) {
    if (!cue.words?.length || !term) return cue.start;
    const first = norm(term).split(" ")[0];
    if (!first) return cue.start;
    for (const w of cue.words) {
      const nw = norm(w.text);
      if (nw === first || nw.startsWith(first) || first.startsWith(nw)) return cue.start + w.t;
    }
    return cue.start;
  }

  // ---------------------------------------------------------------------
  // Live DOM fallback (no timeline captured: live streams, hook missed)
  // ---------------------------------------------------------------------
  class LiveDomSource {
    constructor(onSegment) { this.onSegment = onSegment; this.observer = null; this.lastText = ""; this.retry = null; }
    start() {
      this.stop();
      const player = document.getElementById("movie_player");
      if (!player) { this.retry = setTimeout(() => this.start(), 500); return; }
      this.observer = new MutationObserver(() => this.read());
      this.observer.observe(player, { childList: true, subtree: true, characterData: true });
    }
    stop() { clearTimeout(this.retry); this.observer?.disconnect(); this.observer = null; this.lastText = ""; }
    read() {
      const lines = document.querySelectorAll(".ytp-caption-window-container .caption-visual-line");
      const text = Array.from(lines)
        .map((l) => Array.from(l.querySelectorAll(".ytp-caption-segment")).map((s) => s.textContent).join("").trim())
        .filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
      if (!text || text === this.lastText) return;
      this.lastText = text;
      this.onSegment({ text, start: videoEl()?.currentTime || 0 });
    }
  }

  // ---------------------------------------------------------------------
  // Backend
  // ---------------------------------------------------------------------
  async function postJson(path, payload, signal, timeoutMs = CONST.requestTimeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
    signal?.addEventListener("abort", () => controller.abort("cancelled"), { once: true });
    const sentAt = performance.now();
    try {
      const res = await fetch(`${stored.backendUrl}${path}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal: controller.signal,
      });
      const networkMs = performance.now() - sentAt;
      if (!res.ok) return { error: `Backend returned ${res.status}`, networkMs };
      return { ...(await res.json()), networkMs };
    } catch (_) {
      if (controller.signal.reason === "cancelled") return { cancelled: true };
      return { error: controller.signal.reason === "timeout" ? "timeout" : "unreachable" };
    } finally { clearTimeout(timer); }
  }

  // ---------------------------------------------------------------------
  // Display policy: the part that keeps the Companion quiet
  // ---------------------------------------------------------------------
  class DisplayPolicy {
    constructor() { this.shownThisVideo = new Set(); this.shownAt = []; }
    resetVideo() { this.shownThisVideo.clear(); }
    recentGlobal() {
      const ttl = policy.recent_concept_ttl_seconds * 1000, now = Date.now(), map = stored.recentConcepts || {};
      for (const k of Object.keys(map)) if (now - map[k] > ttl) delete map[k];
      return map;
    }
    decide(result) {
      if (!result?.useful) return "not_useful";
      const key = norm(result.normalized_concept || result.term);
      if (this.shownThisVideo.has(key)) return "shown_this_video";
      if (key in this.recentGlobal()) return "shown_recently";
      if ((result.confidence ?? 0) < policy.auto_show_confidence) return `low_confidence_${result.confidence}`;
      const now = Date.now();
      const last = this.shownAt[this.shownAt.length - 1] || 0;
      if (now - last < policy.auto_hint_cooldown_seconds * 1000) return "cooldown";
      this.shownAt = this.shownAt.filter((t) => now - t < 60000);
      if (this.shownAt.length >= policy.max_hints_per_minute) return "density_cap";
      return "show";
    }
    recordShown(result) {
      const key = norm(result.normalized_concept || result.term);
      this.shownThisVideo.add(key);
      this.shownAt.push(Date.now());
      const map = this.recentGlobal(); map[key] = Date.now();
      saveStored({ recentConcepts: map });
    }
  }

  // ---------------------------------------------------------------------
  // UI: pill and card
  // ---------------------------------------------------------------------
  class Pill {
    constructor(onToggle) { this.onToggle = onToggle; this.el = null; }
    mount() {
      const player = document.getElementById("movie_player");
      if (!player) return false;
      if (this.el?.isConnected) return true;
      this.el = document.createElement("div");
      this.el.className = "cc-pill";
      this.el.setAttribute("role", "switch");
      this.el.setAttribute("aria-label", "Context Companion");
      this.el.innerHTML = '<span class="cc-dot"></span><span class="cc-label">Companion</span><span class="cc-switch">OFF</span>';
      this.el.addEventListener("click", (e) => { e.stopPropagation(); this.onToggle(); });
      player.appendChild(this.el);
      return true;
    }
    render(on, busy) {
      if (!this.mount()) return;
      this.el.classList.toggle("cc-on", on);
      this.el.classList.toggle("cc-busy", on && busy);
      this.el.setAttribute("aria-checked", String(on));
      this.el.querySelector(".cc-switch").textContent = on ? "ON" : "OFF";
    }
  }

  class CardQueue {
    // One head timer, never timers per card: removal is necessarily FIFO.
    constructor() { this.el = null; this.items = []; this.timer = null; this.headStartedAt = 0; this.paused = false; this.remainingMs = 0; }
    mount() {
      const player = document.getElementById("movie_player");
      if (!player) return false;
      if (this.el?.isConnected) return true;
      this.el = document.createElement("div"); this.el.className = "cc-card-stack";
      this.el.setAttribute("aria-live", "polite"); player.appendChild(this.el); return true;
    }
    enqueue(card) {
      if (!this.mount()) return false;
      if (this.items.length >= Math.max(1, Number(policy.max_card_queue_size) || 12)) return false;
      const node = document.createElement("div"); node.className = "cc-card"; node.setAttribute("role", "status");
      const title = document.createElement("span"); title.className = "cc-title"; title.textContent = card.title;
      const body = document.createElement("span"); body.className = "cc-body";
      if (card.source === "dictionary" || card.source === "llm") { const label = document.createElement("em"); label.className = "cc-source"; label.textContent = card.source === "dictionary" ? "Dictionary:" : "AI:"; body.append(label, " "); }
      body.append(String(card.body || "").slice(0, 240)); node.append(title, body); this.el.appendChild(node);
      this.items.push({ ...card, node }); requestAnimationFrame(() => node.classList.add("cc-visible"));
      if (this.items.length === 1 && !this.paused) this._startHead();
      return true;
    }
    _startHead(delay = null) { clearTimeout(this.timer); if (!this.items.length || this.paused) return; const ms = delay ?? Math.max(1, Number(policy.card_lifetime_seconds || (CONST.cardMs / 1000)) * 1000); this.headStartedAt = performance.now(); this.remainingMs = ms; this.timer = setTimeout(() => this._removeHead(), ms); }
    _removeHead() { if (this.paused || !this.items.length) return; this.items.shift().node.remove(); this._startHead(); }
    pause() { if (this.paused) return; this.paused = true; if (this.timer) { this.remainingMs = Math.max(0, this.remainingMs - (performance.now() - this.headStartedAt)); clearTimeout(this.timer); this.timer = null; } }
    resume() { if (!this.paused) return; this.paused = false; if (this.items.length) this._startHead(this.remainingMs || 1); }
    clear() { clearTimeout(this.timer); this.timer = null; this.items = []; this.el?.replaceChildren(); }
    show(title, body, source = null) { return this.enqueue({ title, body, source }); }
  }

  // ---------------------------------------------------------------------
  // Engine: prefetch ahead, display on time
  // ---------------------------------------------------------------------
  class Engine {
    constructor(ui) {
      this.ui = ui;
      this.timeline = null;
      this.videoId = "";
      this.generation = 0; // bumped on every video change; stale results are ignored
      this.jobs = new Map(); // cueIndex -> job
      this.liveJobs = new Map(); // normalised text -> job (fallback mode)
      this.policy = new DisplayPolicy();
      this.timer = null;
    }

    // ---- lifecycle
    resetForVideo(videoId) {
      this.generation++;
      for (const j of this.jobs.values()) j.controller.abort();
      for (const j of this.liveJobs.values()) j.controller.abort();
      this.jobs.clear(); this.liveJobs.clear();
      this.timeline = null;
      this.videoId = videoId;
      this.policy.resetVideo();
      this.ui.cards.clear();
    }
    setTimeline(cues) {
      this.timeline = new Timeline(cues);
      log(`timeline ready: ${cues.length} cues, word timings: ${cues.some((c) => c.words?.length) ? "yes" : "no"}`);
    }
    start() { if (!this.timer) this.timer = setInterval(() => this.tick(), CONST.tickMs); }
    stop() {
      clearInterval(this.timer); this.timer = null;
      for (const j of this.jobs.values()) j.controller.abort();
      this.jobs.clear();
      this.ui.cards.clear();
    }
    busy() { for (const j of this.jobs.values()) if (j.status === "pending") return true; return false; }

    // ---- the spoiler gate
    contextFor(cue) {
      return this.timeline.before(cue.index, CONST.contextCues)
        .filter((p) => p.start <= cue.start)
        .map((p) => ({ text: p.text, timestamp: p.start }));
    }

    // ---- prefetch
    startJob(cue) {
      const controller = new AbortController();
      const gen = this.generation;
      const job = { status: "pending", controller, cue, startedAt: performance.now() };
      job.promise = postJson("/explain", {
        current_subtitle: cue.text, context: this.contextFor(cue), force: false, mode: "prefetch",
        video_id: this.videoId, cue_start: cue.start,
      }, controller.signal).then((result) => {
        if (gen !== this.generation || result.cancelled) { job.status = "stale"; return; }
        job.status = "done"; job.result = result; job.readyAt = performance.now();
        job.showAt = result.useful ? showAtFor(cue, result.term) : cue.start;
        if (result.error) log(`cue@${cue.start.toFixed(1)} backend error: ${result.error}`);
      });
      this.jobs.set(cue.index, job);
      return job;
    }

    pendingCount() { let n = 0; for (const j of this.jobs.values()) if (j.status === "pending") n++; return n; }

    tick() {
      const v = videoEl();
      if (!v) return;
      const t = v.currentTime;
      this.ui.pill.render(true, this.busy());
      if (!this.timeline) return;

      for (const cue of this.timeline.upcoming(t, policy.prefetch_window_seconds)) {
        if (this.pendingCount() >= CONST.maxConcurrent) break;
        if (!this.jobs.has(cue.index)) this.startJob(cue);
      }
      if (v.paused) { this.ui.cards.pause(); return; }
      this.ui.cards.resume();

      // Display pass: any done job whose moment has arrived and not yet passed.
      for (const job of this.jobs.values()) {
        if (job.status !== "done" || job.displayed) continue;
        const late = t - job.cue.end;
        if (late > policy.late_display_grace_seconds) { job.displayed = "dropped_late"; continue; }
        if (t < job.showAt) continue;
        job.displayed = this.tryDisplay(job, t);
      }
    }

    onSeek(t) {
      // A seek invalidates visible, completed and in-flight cue context.
      this.generation++;
      for (const job of this.jobs.values()) job.controller.abort();
      this.jobs.clear(); this.ui.cards.clear();
    }

    tryDisplay(job, t) {
      this.ui.cards.mount();
      const { result, cue } = job;
      // Batch results carry per-item details while the overall response still owns
      // the usefulness/confidence flags. Normalize them before policy evaluation so
      // auto-display works with both the top-level object and item entries.
      const items = (Array.isArray(result.items) && result.items.length ? result.items : [result])
        .slice(0, Math.max(1, Number(policy.max_cards_per_cue) || 3))
        .map((item) => ({
          ...result,
          ...item,
          useful: item?.useful ?? result?.useful ?? true,
          confidence: item?.confidence ?? result?.confidence ?? 0,
          normalized_concept: item?.normalized_concept || item?.term || result?.normalized_concept || result?.term,
          term: item?.term || result?.term,
          source: item?.source || result?.source,
          title: item?.title || item?.term || result?.title || result?.term,
          explanation: item?.explanation || result?.explanation || "",
        }));
      const eligible = items.filter((item) => this.policy.decide(item) === "show");
      if (!eligible.length) { this.logDecision(job, "not_eligible", t); return "not_eligible"; }
      let shown = 0;
      for (const item of eligible) {
        if (!this.ui.cards.enqueue({ title: item.title || item.term, body: item.explanation, source: item.source })) break;
        this.policy.recordShown(item);
        postJson("/shown", { video_id: this.videoId, concept: item.normalized_concept || item.term, cue_start: cue.start }, null, 3000);
        shown++;
      }
      this.logDecision(job, shown ? "shown" : "queue_full", t);
      return shown ? "shown" : "queue_full";
    }

    logDecision(job, verdict, t) {
      const { result, cue } = job, tm = result?.timings || {};
      const readyLead = job.readyAt ? (job.showAt - (t - (performance.now() - job.readyAt) / 1000)) : NaN;
      log(
        `${verdict.padEnd(16)} cue@${cue.start.toFixed(2)} show@${(job.showAt ?? cue.start).toFixed(2)} "${cue.text.slice(0, 40)}"`,
        `| ${result?.normalized_concept || "-"} src=${result?.source || "-"} conf=${result?.confidence ?? "-"}`,
        `| knowledge ${tm.knowledge_ms ?? 0}ms session ${tm.session_ms ?? 0}ms classifier ${tm.classifier_ms ?? 0}ms llm ${tm.llm_ms ?? 0}ms net ${Math.round(result?.networkMs ?? 0)}ms`,
        Number.isFinite(readyLead) ? `| ready ${readyLead >= 0 ? readyLead.toFixed(1) + "s early" : (-readyLead).toFixed(1) + "s late"}` : ""
      );
    }

    // ---- live DOM fallback: reactive, still aligned to the line on screen
    onLiveSegment(seg) {
      if (!this.timer || this.timeline) return;
      const key = norm(seg.text);
      if (this.liveJobs.has(key)) return;
      const controller = new AbortController(), gen = this.generation;
      const context = Array.from(this.liveJobs.values()).slice(-CONST.contextCues).map((j) => ({ text: j.text, timestamp: j.start }));
      const job = { controller, text: seg.text, start: seg.start };
      this.liveJobs.set(key, job);
      if (this.liveJobs.size > 50) this.liveJobs.delete(this.liveJobs.keys().next().value);
      postJson("/explain", { current_subtitle: seg.text, context, force: false, mode: "live", video_id: this.videoId, cue_start: seg.start }, controller.signal)
        .then((result) => {
          if (gen !== this.generation || result.cancelled) return;
          const v = videoEl(); if (!v) return;
          const cue = { start: seg.start, end: seg.start + 4, text: seg.text, index: -1, words: [] };
          const fake = { result, cue, showAt: seg.start, readyAt: performance.now() };
          if (v.currentTime - cue.end > policy.late_display_grace_seconds) { this.logDecision(fake, "dropped_late", v.currentTime); return; }
          this.tryDisplay(fake, v.currentTime);
        });
    }
  }

  // ---------------------------------------------------------------------
  // Controller: wires storage, navigation, hook messages, UI
  // ---------------------------------------------------------------------
  class Controller {
    constructor() {
      this.ui = { pill: new Pill(() => this.toggle()), cards: new CardQueue() };
      this.engine = new Engine(this.ui);
      this.live = new LiveDomSource((seg) => this.engine.onLiveSegment(seg));
      this.pendingTracks = new Map();
      this.boundVideo = null;
      this.navigationTimer = null;
    }

    async init() {
      await loadStored();
      await loadPolicy();
      window.addEventListener("message", (e) => this.onHookMessage(e));
      window.addEventListener("yt-navigate-finish", () => this.onNavigate());
      window.addEventListener("load", () => this.onNavigate());
      chrome.storage.onChanged.addListener((changes, area) => {
        if (area !== "local") return;
        if (changes.companionEnabled) { stored.companionEnabled = changes.companionEnabled.newValue; this.applyEnabled(); }
        if (changes.backendUrl) { stored.backendUrl = changes.backendUrl.newValue; loadPolicy(); }
        if (changes.recentConcepts) stored.recentConcepts = changes.recentConcepts.newValue;
      });
      // Manual fallback only. The core UX is automatic subtitle-driven processing.
      document.addEventListener("keydown", (e) => {
        if (e.altKey && e.code === "KeyX" && !e.ctrlKey && !e.metaKey) { e.preventDefault(); this.explainNow(); }
      }, true);
      chrome.runtime.onMessage.addListener((message) => {
        if (message?.type === "CC_EXPLAIN_NOW") this.explainNow();
      });
      this.onNavigate();
    }

    toggle() { saveStored({ companionEnabled: !stored.companionEnabled }); this.applyEnabled(); }

    applyEnabled() {
      const on = Boolean(stored.companionEnabled);
      this.ui.pill.render(on, false);
      if (on) {
        this.engine.start();
        this.live.start();
        this.requestEmbeddedCaptions();
        log("Companion ON");
      } else {
        this.engine.stop();
        this.live.stop();
        log("Companion OFF");
      }
    }

    requestEmbeddedCaptions() {
      const vid = currentVideoId();
      if (!vid && !document.querySelector("video.html5-main-video")) return;
      window.postMessage({ __cc: true, type: "REQUEST_EMBEDDED_CAPTIONS" }, location.origin);
    }

    onNavigate() {
      const vid = currentVideoId();
      this.engine.resetForVideo(vid);
      this.live.stop();
      this.bindVideo();
      this.ui.pill.mount(); this.ui.cards.mount();
      if (this.pendingTracks.has(vid)) { this.engine.setTimeline(this.pendingTracks.get(vid)); this.pendingTracks.delete(vid); }
      this.applyEnabled();
      this.requestEmbeddedCaptions();
      log(`video ${vid || "(none)"}: ${this.engine.timeline ? "timeline adopted" : "waiting for caption track"}`);
    }

    bindVideo() {
      const v = videoEl();
      if (!v) {
        clearTimeout(this.navigationTimer);
        this.navigationTimer = setTimeout(() => this.bindVideo(), 500);
        return;
      }
      clearTimeout(this.navigationTimer);
      if (this.boundVideo === v) return;
      this.boundVideo = v;
      v.addEventListener("seeking", () => this.engine.onSeek(v.currentTime));
      v.addEventListener("play", () => {
        if (stored.companionEnabled) {
          this.engine.start();
          this.live.start();
          this.requestEmbeddedCaptions();
        }
      });
      v.addEventListener("timeupdate", () => {
        if (stored.companionEnabled && !v.paused) {
          this.engine.start();
        }
      });
    }

    onHookMessage(e) {
      if (e.source !== window || !e.data || e.data.__cc !== true || e.data.type !== "TIMEDTEXT") return;
      let cues;
      try { cues = TimedText.parse(e.data.body); } catch (err) { log("caption parse failed", err); return; }
      if (!cues.length) return;
      const trackVideo = new URL(e.data.url, location.origin).searchParams.get("v") || currentVideoId();
      if (trackVideo !== currentVideoId()) {
        this.pendingTracks.set(trackVideo, cues);
        if (this.pendingTracks.size > 5) this.pendingTracks.delete(this.pendingTracks.keys().next().value);
        return;
      }
      this.engine.setTimeline(cues);
    }

    // Secondary: explain whatever is on screen right now, regardless of policy.
    async explainNow() {
      const v = videoEl(); if (!v) return;
      let cue = null, context = [];
      if (this.engine.timeline) {
        const i = this.engine.timeline.indexAt(v.currentTime);
        if (i >= 0) { cue = this.engine.timeline.cues[i]; context = this.engine.contextFor(cue); }
      }
      if (!cue) { this.ui.cards.show("Companion", "No subtitle on screen right now.", null); return; }
      const r = await postJson("/explain", { current_subtitle: cue.text, context, force: true, mode: "manual", video_id: this.engine.videoId, cue_start: cue.start });
      if (r.useful) this.ui.cards.show(r.title || r.term, r.explanation, r.source);
      else this.ui.cards.show("Companion", r.error_detail || (r.stage === "error" ? "Model request failed." : "Nothing here needs explaining."), null);
    }
  }

  const controller = new Controller();
  controller.init();
  // Test seam for the browser harness; it exposes no extension privilege.
  window.__ccTest = { cards: controller.ui.cards, engine: controller.engine };
})();
