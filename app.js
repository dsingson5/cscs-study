// CSCS daily study — learning-science runtime (v2).
//
// Implements the evidence-based stack from the learning-science review:
//   • Retrieval practice with FORCED COMMITMENT — Reveal is gated until the
//     learner types an attempt or explicitly clicks "I don't know".
//   • FSRS scheduling (ts-fsrs, Anki's default) with an internal fallback so
//     the app keeps working if the CDN module fails to load.
//   • Confidence rating BEFORE reveal + 4-button Again/Hard/Good/Easy AFTER —
//     the four-button grade is the scheduler input and the confidence is the
//     calibration probe (Brier score per domain).
//   • Interleaving the due queue across CSCS domains by exam weight.
//   • Desirable difficulty framing: forgetting ("Again") is framed as "where
//     learning happens", not failure. No streaks, no XP (evidence-free).
//
// State lives in a single localStorage key (cscs.state.v1) so it survives
// reloads AND the daily regeneration of cscs_today.html (same origin).
// Old SM-2 state (cscs.qstate / cscs.answers) is migrated on first load.

const LS_PREFIX = "cscs.";
const STATE_KEY = "state.v1";
const TODAY = new Date().toISOString().slice(0, 10);
const TARGET_RETENTION = 0.85;

// Official-NSCA-weighted sampling targets, normalised over the 4 domains the
// curriculum uses. Practical/Applied (EX + PD) is the larger, harder pool.
const EXAM_WEIGHTS = { ES: 0.30, NT: 0.12, EX: 0.18, PD: 0.40 };
const DOMAIN_NAME = { ES: "Exercise Science", NT: "Nutrition", EX: "Exercise Technique", PD: "Program Design" };
const CONF_P = { low: 0.25, med: 0.6, high: 0.9 };

function lsGet(key, fallback) {
  try {
    const raw = localStorage.getItem(LS_PREFIX + key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch (e) { return fallback; }
}
function lsSet(key, value) {
  try { localStorage.setItem(LS_PREFIX + key, JSON.stringify(value)); } catch (e) {}
}

// ── One-time hard reset ──────────────────────────────────────────────────────
// Bump RESET_EPOCH to wipe ALL study progress on each device's next load.
// A local backup (cscs.backup.<epoch>) is kept first so the wipe is recoverable.
const RESET_EPOCH = "2026-05-24";
let __didHardReset = false;
function maybeHardReset() {
  try {
    if (localStorage.getItem(LS_PREFIX + "reset_epoch") === RESET_EPOCH) return;
    const prev = localStorage.getItem(LS_PREFIX + STATE_KEY);
    if (prev) localStorage.setItem(LS_PREFIX + "backup." + RESET_EPOCH, prev);
    localStorage.removeItem(LS_PREFIX + STATE_KEY);
    localStorage.removeItem(LS_PREFIX + "qstate");
    localStorage.removeItem(LS_PREFIX + "answers");
    lsSet(STATE_KEY, { version: 1, user: { examDate: null, targetRetention: TARGET_RETENTION },
      cards: {}, answers: {}, log: [], calibration: { byDomain: {} }, touchedDays: {}, updated_at: new Date().toISOString() });
    localStorage.setItem(LS_PREFIX + "reset_epoch", RESET_EPOCH);
    __didHardReset = true;
  } catch (e) {}
}
maybeHardReset();

// ── Question-bank migration (5th-edition rewrite) — DISARMED ─────────────────
const QBANK_EPOCH = "2026-07-04-5e";
const QBANK_BACKUP_KEY = "backup.qbank." + QBANK_EPOCH;
const QBANK_HEAL_EPOCH = "2026-07-20-heal";

// DISARMED 2026-07-20. This used to clear cards/log/answers so that FSRS state
// keyed <topic_id>__<index> could not point at rewritten 5E questions. The cure
// was worse than the disease: on 2026-07-20 it wiped 84 cards / 646 grades and
// then pushed the emptied state over the cloud copy, so the Review schedule read
// "Nothing tracked yet". A stale "Last answered" label is not worth months of
// scheduling history. Stamp the epoch only, so devices that have not yet run the
// old code never wipe.
function maybeQBankMigrate() {
  try { localStorage.setItem(LS_PREFIX + "qbank_epoch", QBANK_EPOCH); } catch (e) {}
}
maybeQBankMigrate();

// Heal a device the wipe already hit: fold its pre-wipe backup back into state.
// Union merge, newer last_review wins, so it is safe alongside anything graded
// since. Runs once per device (qbank_heal_epoch).
function maybeQBankHeal() {
  try {
    if (localStorage.getItem(LS_PREFIX + "qbank_heal_epoch") === QBANK_HEAL_EPOCH) return;
    // A RESET_EPOCH wipe on this very load is deliberate — don't resurrect it.
    if (__didHardReset) { localStorage.setItem(LS_PREFIX + "qbank_heal_epoch", QBANK_HEAL_EPOCH); return; }
    const bak = lsGet(QBANK_BACKUP_KEY, null);
    if (bak && bak.cards) {
      const s = getState();
      s.touchedDays = s.touchedDays || {};
      let healed = 0;
      for (const k in bak.cards) {
        const r = bak.cards[k], l = s.cards[k];
        const lt = l ? (l.last_review || l.due || "") : "", rt = r.last_review || r.due || "";
        if (!l || rt > lt) { s.cards[k] = r; healed++; }
      }
      const seen = new Set(s.log.map(e => e.cardId + "|" + e.ts));
      (bak.log || []).forEach(e => {
        const key = e.cardId + "|" + e.ts;
        if (!seen.has(key)) { s.log.push(e); seen.add(key); healed++; }
      });
      s.log.sort((a, b) => (a.ts || "").localeCompare(b.ts || ""));
      for (const d in (bak.touchedDays || {})) if (bak.touchedDays[d]) s.touchedDays[d] = true;
      for (const k in (bak.answers || {})) {
        const rv = bak.answers[k];
        if (rv && (!s.answers[k] || rv.length > (s.answers[k] || "").length)) s.answers[k] = rv;
      }
      const nOf = c => Object.values((c && c.byDomain) || {}).reduce((a, d) => a + (d.n || 0), 0);
      if (nOf(bak.calibration) > nOf(s.calibration)) s.calibration = bak.calibration;
      if (healed) saveState(s);
    }
    localStorage.setItem(LS_PREFIX + "qbank_heal_epoch", QBANK_HEAL_EPOCH);
  } catch (e) {}
}

function domainFor(stable) {
  const topic = String(stable).split("__")[0];
  return (window.__CSCS_DOMAINS && window.__CSCS_DOMAINS[topic]) || "ES";
}
function topicOf(stable) { return String(stable).split("__")[0]; }

// ════════════════════════════════════════════════════════════════════════════
//   FSRS SCHEDULER (ts-fsrs via CDN module, with internal fallback)
// ════════════════════════════════════════════════════════════════════════════
// The page loads ts-fsrs in a <script type="module"> that sets window.__FSRS.
// Scheduling only happens on user interaction (well after load), so the module
// is ready by then; the initial queue build also waits for the ready event.

let __scheduler = null;
function fsrsReady() { return !!(window.__FSRS && window.__FSRS.fsrs); }
function getScheduler() {
  if (__scheduler) return __scheduler;
  if (fsrsReady()) {
    const p = window.__FSRS.generatorParameters({
      request_retention: TARGET_RETENTION, maximum_interval: 365, enable_fuzz: true
    });
    __scheduler = window.__FSRS.fsrs(p);
  }
  return __scheduler;
}

function newCard() {
  const now = new Date();
  if (fsrsReady()) {
    try { return fromFsrsCard(window.__FSRS.createEmptyCard(now)); } catch (e) {}
  }
  return {
    due: now.toISOString(), stability: 0, difficulty: 0, elapsed_days: 0,
    scheduled_days: 0, reps: 0, lapses: 0, state: 0, last_review: null, learning_steps: 0
  };
}

function toFsrsCard(s) {
  return {
    due: new Date(s.due),
    stability: s.stability || 0,
    difficulty: s.difficulty || 0,
    elapsed_days: s.elapsed_days || 0,
    scheduled_days: s.scheduled_days || 0,
    reps: s.reps || 0,
    lapses: s.lapses || 0,
    state: s.state || 0,
    last_review: s.last_review ? new Date(s.last_review) : undefined,
    learning_steps: s.learning_steps || 0
  };
}
function fromFsrsCard(c) {
  const iso = d => (d instanceof Date ? d : new Date(d)).toISOString();
  return {
    due: iso(c.due),
    stability: c.stability, difficulty: c.difficulty,
    elapsed_days: c.elapsed_days, scheduled_days: c.scheduled_days,
    reps: c.reps, lapses: c.lapses, state: c.state,
    last_review: c.last_review ? iso(c.last_review) : null,
    learning_steps: c.learning_steps || 0
  };
}

// Pure-JS fallback FSRS-flavoured update (only used if the CDN module fails).
function fallbackSchedule(s, grade, now) {
  let interval = Math.max(1, s.scheduled_days || 1);
  let stab = s.stability || 1;
  let diff = s.difficulty || 5;
  let reps = (s.reps || 0) + 1;
  let lapses = s.lapses || 0;
  let due = new Date(now);
  if (grade === 1) {
    lapses++; stab = Math.max(0.5, stab * 0.5); diff = Math.min(10, diff + 1);
    due = new Date(now.getTime() + 10 * 60 * 1000); interval = 0;
  } else {
    const mult = grade === 2 ? 1.2 : grade === 3 ? 2.2 : 3.2;
    interval = Math.max(1, Math.round((interval || 1) * mult));
    stab = stab * mult;
    diff = Math.max(1, diff - (grade === 4 ? 0.3 : grade === 3 ? 0.1 : 0));
    due.setDate(due.getDate() + interval);
  }
  return {
    due: due.toISOString(), stability: stab, difficulty: diff, elapsed_days: 0,
    scheduled_days: interval, reps, lapses, state: grade === 1 ? 3 : 2,
    last_review: now.toISOString(), learning_steps: 0
  };
}

// Returns { card, log }. Never throws.
function schedule(storedCard, grade, when) {
  const now = when || new Date();
  const sched = getScheduler();
  if (sched) {
    const card = toFsrsCard(storedCard);
    let res = null;
    try { if (typeof sched.next === "function") res = sched.next(card, now, grade); } catch (e) { res = null; }
    if (!res) { try { res = sched.repeat(card, now)[grade]; } catch (e) { res = null; } }
    if (res && res.card) return { card: fromFsrsCard(res.card), log: res.log || null };
  }
  return { card: fallbackSchedule(storedCard, grade, now), log: null };
}

// Project the next interval text for each grade WITHOUT mutating state.
function previewIntervals(storedCard) {
  const out = {};
  const now = new Date();
  [1, 2, 3, 4].forEach(g => {
    if (g === 1) { out[g] = "<10m"; return; }
    const r = schedule(storedCard, g, now);
    const days = Math.max(1, Math.round((new Date(r.card.due) - now) / 86400000));
    out[g] = days >= 365 ? "1y+" : days >= 30 ? Math.round(days / 30) + "mo" : days + "d";
  });
  return out;
}

function retrievability(storedCard) {
  const now = new Date();
  const sched = getScheduler();
  if (sched && typeof sched.get_retrievability === "function") {
    try {
      const v = sched.get_retrievability(toFsrsCard(storedCard), now, false);
      if (typeof v === "number") return v;
      if (typeof v === "string") return parseFloat(v) / 100;
    } catch (e) {}
  }
  const S = storedCard.stability || 1;
  if (!storedCard.last_review) return null;
  const t = Math.max(0, (now - new Date(storedCard.last_review)) / 86400000);
  return Math.pow(1 + t / (9 * S), -1);
}

// ════════════════════════════════════════════════════════════════════════════
//   STATE  (single key) + migration from the old SM-2 schema
// ════════════════════════════════════════════════════════════════════════════
function getState() {
  let s = lsGet(STATE_KEY, null);
  if (!s || s.version !== 1) { s = migrateOrInit(); lsSet(STATE_KEY, s); }
  if (!s.cards) s.cards = {};
  if (!s.answers) s.answers = {};
  if (!s.log) s.log = [];
  if (!s.calibration) s.calibration = { byDomain: {} };
  if (!s.user) s.user = { examDate: null, targetRetention: TARGET_RETENTION };
  // migrateOrInit() predates touchedDays and never emits it, so a state built
  // that way would make every `s.touchedDays[d] = ...` writer throw.
  if (!s.touchedDays) s.touchedDays = {};
  // completedDays: stamped only when EVERY core question of a page has been
  // graded — the resume redirect advances past a day on this, not on touch.
  if (!s.completedDays) s.completedDays = {};
  return s;
}
function saveState(s) { s.updated_at = new Date().toISOString(); lsSet(STATE_KEY, s); }

maybeQBankHeal();  // defined above; deferred to here so getState/saveState exist

function migrateOrInit() {
  const old = lsGet("qstate", null);
  const oldAns = lsGet("answers", {}) || {};
  const cards = {};
  if (old && typeof old === "object") {
    for (const k in old) {
      const e = old[k];
      if (!e) continue;
      const interval = Math.max(1, e.interval || 1);
      const ease = e.ease || 2.5;
      const dueIso = e.next_due ? new Date(e.next_due + "T07:00:00").toISOString() : new Date().toISOString();
      const lapses = (e.history || []).filter(h => h.m === "missed").length;
      cards[k] = {
        due: dueIso,
        stability: interval,
        difficulty: Math.min(10, Math.max(1, 10 - (ease - 1.3) / 1.4 * 7)),
        elapsed_days: 0, scheduled_days: interval,
        reps: e.seen_count || 0, lapses,
        state: (e.seen_count || 0) > 0 ? 2 : 0,
        last_review: e.last_seen ? new Date(e.last_seen + "T07:00:00").toISOString() : null,
        learning_steps: 0, migrated: true
      };
    }
  }
  return {
    version: 1,
    user: { examDate: null, targetRetention: TARGET_RETENTION },
    cards, answers: oldAns, log: [],
    calibration: { byDomain: {} },
    updated_at: new Date().toISOString()
  };
}

function getCard(stable) {
  const s = getState();
  return s.cards[stable] || null;
}

// ════════════════════════════════════════════════════════════════════════════
//   QUESTION INTERACTION  (commitment → reveal → confidence → grade)
// ════════════════════════════════════════════════════════════════════════════
const pendingConf = {};   // qid -> 'low'|'med'|'high'
const revealed = {};      // qid -> true once revealed

function onAnswerInput(ev) {
  const q = ev.target.closest(".q");
  if (!q) return;
  const stable = q.dataset.stable;
  if (stable) {
    const s = getState();
    s.answers[stable] = ev.target.value;
    saveState(s);
  }
  // Forced commitment: enable Reveal only once there's a non-whitespace attempt.
  const qid = q.dataset.qid;
  const btn = document.getElementById("revealbtn_" + qid);
  if (btn) {
    const hasText = ev.target.value.trim().length > 0;
    btn.disabled = !hasText && !revealed[qid];
    btn.classList.toggle("ready", hasText);
  }
  const status = q.querySelector('[data-status-for="' + qid + '"]');
  if (status) { status.textContent = "saved"; status.classList.add("flashed");
    clearTimeout(status._t); status._t = setTimeout(() => { status.textContent = ""; status.classList.remove("flashed"); }, 1200); }
  if (typeof scheduleSyncPush === "function") scheduleSyncPush();
}

function onSelfExplainInput(ev) {
  const q = ev.target.closest(".q");
  if (!q) return;
  const stable = q.dataset.stable;
  if (!stable) return;
  const s = getState();
  s.answers[stable + "::why"] = ev.target.value;
  saveState(s);
}

function pickConfidence(qid, level) {
  pendingConf[qid] = level;
  const root = document.querySelector('[data-qid="' + qid + '"]');
  if (!root) return;
  root.querySelectorAll(".conf-btn").forEach(b => b.classList.toggle("active", b.dataset.conf === level));
}

function dontKnowQ(qid) {
  // An honest "I don't know" is a legitimate commitment — it forces the
  // retrieval attempt to resolve before the answer is shown.
  if (!pendingConf[qid]) pickConfidence(qid, "low");
  revealQ(qid, true);
}

function revealQ(qid, fromIDK) {
  const root = document.querySelector('[data-qid="' + qid + '"]');
  if (!root) return;
  const txt = root.querySelector(".q-answer");
  const committed = fromIDK || (txt && txt.value.trim().length > 0) || revealed[qid];
  if (!committed) { showToast("Type an attempt first — or tap “I don't know”."); return; }
  revealed[qid] = true;
  const panel = document.getElementById("reveal_" + qid);
  if (panel) panel.classList.add("shown");
  // Fill projected intervals on the grade buttons (dual-coding the schedule).
  const stable = root.dataset.stable;
  const card = getCard(stable) || newCard();
  const prev = previewIntervals(card);
  root.querySelectorAll(".rate-btn").forEach(b => {
    const g = parseInt(b.dataset.grade, 10);
    const small = b.querySelector("small");
    if (small && prev[g]) small.textContent = prev[g];
  });
  // Disable confidence editing once committed.
  root.querySelectorAll(".conf-btn").forEach(b => b.disabled = true);
  const rb = document.getElementById("revealbtn_" + qid);
  if (rb) rb.disabled = true;
}

function rateQ(qid, grade) {
  const root = document.querySelector('[data-qid="' + qid + '"]');
  if (!root) return;
  if (!revealed[qid]) revealQ(qid, true);
  const stable = root.dataset.stable;
  const domain = root.dataset.domain || domainFor(stable);
  const s = getState();
  let card = s.cards[stable] || newCard();
  const r = schedule(card, grade);
  s.cards[stable] = r.card;
  // Review log
  s.log.push({ cardId: stable, ts: new Date().toISOString(), rating: grade, domain: domain });
  // Mark THIS page's date as touched (engagement marker, kept for sync), and
  // stamp completedDays ONLY once every core question on the page has been
  // graded at least once. The resume redirect advances past a day solely on
  // completion, so answering one question can no longer skip the whole day.
  var __dayJustCompleted = false;
  try {
    var pageDate = (typeof window !== 'undefined' && window.__CSCS_PAGE_DATE) ? window.__CSCS_PAGE_DATE : null;
    if (pageDate) {
      s.touchedDays = s.touchedDays || {}; s.touchedDays[pageDate] = true;
      var core = (typeof window !== 'undefined' && window.__CSCS_CORE_QIDS) ? window.__CSCS_CORE_QIDS : null;
      // A page with NO baked core set must never stamp completedDays: the old
      // `= true` initialiser meant one grade on such a page marked the whole
      // day done, and complete() in the redirect checks completedDays FIRST,
      // so the all-core gate never got a vote. No core set = nothing to
      // verify = not completable (legacy pre-cutoff days are still covered by
      // the touchedDays rule; re-render the page to give it a core set).
      var allDone = !!(core && core.length);
      if (allDone) {
        for (var ci = 0; ci < core.length; ci++) { if (!s.cards[core[ci]]) { allDone = false; break; } }
      }
      if (allDone) {
        s.completedDays = s.completedDays || {};
        if (!s.completedDays[pageDate]) { s.completedDays[pageDate] = true; __dayJustCompleted = true; }
      }
    }
  } catch (e) {}
  refreshLastAnsweredFor(stable);
  if (s.log.length > 4000) s.log = s.log.slice(-4000);
  // Calibration: confidence (pre-reveal) vs. outcome (Again=miss, else hit)
  const conf = pendingConf[qid] || "med";
  const predicted = CONF_P[conf];
  const outcome = grade >= 2 ? 1 : 0;
  const cal = s.calibration.byDomain[domain] || { n: 0, brierSum: 0, confSum: 0, accSum: 0 };
  cal.n += 1;
  cal.brierSum += Math.pow(predicted - outcome, 2);
  cal.confSum += predicted;
  cal.accSum += outcome;
  s.calibration.byDomain[domain] = cal;
  saveState(s);

  // UI feedback
  root.querySelectorAll(".rate-btn").forEach(b => b.classList.remove("chosen"));
  const chosen = root.querySelector('.rate-btn[data-grade="' + grade + '"]');
  if (chosen) chosen.classList.add("chosen");
  const nextDays = Math.max(0, Math.round((new Date(r.card.due) - new Date()) / 86400000));
  const note = root.querySelector(".rate-result");
  if (note) {
    var __due = r.card.due;
    note.innerHTML = (grade === 1
      ? "Back in ~10 min - forgetting is where the learning happens. "
      : "Next review " + relDueLong(__due) + " &middot; " + fmtDueAbs(__due) + ". ")
      + '<button type="button" class="cd-open">&#9201; Countdown</button>';
    var __b = note.querySelector(".cd-open");
    if (__b) __b.addEventListener("click", function(){ openCountdown(__due); });
    note.classList.add("shown");
  }
  refreshNextReviewFor(stable);
  root.classList.add("rated");
  updateHeaderStats();
  renderDashboard();
  buildReviewQueue();
  renderDayProgress();
  if (__dayJustCompleted) showToast("Question set complete ✓ — the daily resume will move on from this day.");
  if (typeof scheduleSyncPush === "function") scheduleSyncPush();
}

// ── Day-completion progress ─────────────────────────────────────────────────
// The generator bakes the page's core question ids (__CSCS_CORE_QIDS). A day
// only counts as done — and the resume redirect only moves on — once every
// one of them has been graded at least once (on any page; review-queue grades
// of the same card count too).
// Keep in sync with COMPLETION_CUTOFF in generate_daily.py: days before this
// ran under the old touch-based rule and stay grandfathered in the redirect.
var COMPLETION_CUTOFF = "2026-07-22";
function coreProgress() {
  var core = (typeof window !== "undefined" && window.__CSCS_CORE_QIDS) ? window.__CSCS_CORE_QIDS : null;
  if (!core || !core.length) return null;
  var s = getState(), done = 0;
  for (var i = 0; i < core.length; i++) if (s.cards[core[i]]) done++;
  return { total: core.length, done: done };
}
function renderDayProgress() {
  var host = document.querySelector(".session-goal");
  if (!host) return;
  var p = coreProgress();
  var el = document.getElementById("day-progress");
  if (!p) { if (el && el.parentNode) el.parentNode.removeChild(el); return; }
  if (!el) { el = document.createElement("span"); el.id = "day-progress"; host.appendChild(el); }
  var pageDate = (typeof window !== "undefined" && window.__CSCS_PAGE_DATE) ? window.__CSCS_PAGE_DATE : null;
  var legacyDone = !!(pageDate && pageDate < COMPLETION_CUTOFF && getState().touchedDays[pageDate]);
  el.innerHTML = (p.done >= p.total)
    ? ' · <span class="dp-done">✓ day complete</span>'
    : legacyDone
      ? ' · <span class="dp-done">✓ counted done (pre-update)</span> · ' + p.done + "/" + p.total + " answered"
      : ' · <b>' + p.done + "/" + p.total + '</b> of this day’s set — answer all to mark it done (the site resumes here until finished)';
}

// ════════════════════════════════════════════════════════════════════════════
//   INTERLEAVED REVIEW QUEUE  (exam-weighted, no two consecutive same topic)
// ════════════════════════════════════════════════════════════════════════════
function dueCards() {
  const s = getState();
  const now = new Date();
  const out = [];
  for (const stable in s.cards) {
    const c = s.cards[stable];
    if (!c.due || new Date(c.due) > now) continue;
    const parts = stable.split("__");
    if (parts.length !== 2) continue;
    const topicId = parts[0], idx = parseInt(parts[1], 10);
    const pool = window.__CSCS_QUESTIONS && window.__CSCS_QUESTIONS[topicId];
    if (!pool || !pool[idx]) continue;
    out.push({ stable, topicId, idx, q: pool[idx], card: c, domain: domainFor(stable) });
  }
  return out;
}

// Weighted round-robin interleave so domains appear ~proportionally to exam
// weight and adjacent cards avoid sharing a topic (discrimination practice).
function interleave(items) {
  const byDom = {};
  items.forEach(it => { (byDom[it.domain] = byDom[it.domain] || []).push(it); });
  // within a domain, most-overdue first
  for (const d in byDom) byDom[d].sort((a, b) => new Date(a.card.due) - new Date(b.card.due));
  const served = {}; Object.keys(byDom).forEach(d => served[d] = 0);
  const out = [];
  let remaining = items.length;
  let lastTopic = null;
  while (remaining > 0) {
    // pick the available domain with the largest weight deficit
    let best = null, bestScore = -Infinity;
    for (const d in byDom) {
      if (!byDom[d].length) continue;
      const w = EXAM_WEIGHTS[d] || 0.1;
      const deficit = w - served[d] / Math.max(1, out.length);
      // prefer not repeating the last topic
      const penalty = byDom[d][0].topicId === lastTopic ? 0.15 : 0;
      const score = deficit - penalty;
      if (score > bestScore) { bestScore = score; best = d; }
    }
    if (best === null) break;
    const it = byDom[best].shift();
    out.push(it); served[best]++; remaining--; lastTopic = it.topicId;
  }
  return out;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
}

function questionCardHTML(d, qid, opts) {
  opts = opts || {};
  const qtype = d.q.type || "recall";
  const selfexplain = qtype === "applied";
  const dueDate = d.card && d.card.due ? new Date(d.card.due) : null;
  const overdue = dueDate ? Math.max(0, Math.round((new Date() - dueDate) / 86400000)) : 0;
  const R = d.card ? retrievability(d.card) : null;
  const meta = (R != null ? '<span class="q-recall">recall ' + Math.round(R * 100) + "%</span>" : "") +
    (overdue > 0 ? '<span class="q-overdue">' + overdue + "d overdue</span>" : "");
  const se = selfexplain
    ? '<div class="q-selfexplain"><label>In your own words — why is this true?</label>' +
      '<textarea class="se-answer" placeholder="One sentence is enough. The attempt is what builds the memory." oninput="onSelfExplainInput(event)"></textarea></div>'
    : "";
  return '<div class="q' + (opts.pretest ? " pretest" : "") + '" data-qid="' + qid + '" data-stable="' + escapeHtml(d.stable) +
    '" data-domain="' + d.domain + '" data-qtype="' + qtype + '">' +
    '<div class="q-head"><span class="q-num">' + (opts.label || "&#10227; Due") + '</span>' +
    '<span class="q-type ' + qtype + '">' + qtype + '</span>' +
    '<span class="q-domain">' + (DOMAIN_NAME[d.domain] || d.domain) + '</span>' +
    '<span class="pr-meta">' + meta + '</span>' +
    '<span class="q-status" data-status-for="' + qid + '"></span>' + '<span class="q-last" data-last-for="' + qid + '" data-stable="' + escapeHtml(d.stable) + '"></span><span class="q-next" data-stable="' + escapeHtml(d.stable) + '"></span></div>' +
    '<div class="q-text">' + escapeHtml(d.q.q) + '</div>' +
    '<textarea class="q-answer" placeholder="Recall and type your answer first…" oninput="onAnswerInput(event)"></textarea>' +
    '<button type="button" class="mic-btn" aria-pressed="false" title="Answer by voice" onclick="toggleDictation(this)"><svg class="mic-ico" viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"></path><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M5 11a7 7 0 0 0 14 0M12 18v3"></path></svg><span class="mic-lbl">Speak</span></button>' +
    '<div class="q-confidence"><span class="conf-label">How sure are you?</span>' +
    '<button type="button" class="conf-btn" data-conf="low" onclick="pickConfidence(\'' + qid + '\',\'low\')">Low</button>' +
    '<button type="button" class="conf-btn" data-conf="med" onclick="pickConfidence(\'' + qid + '\',\'med\')">Medium</button>' +
    '<button type="button" class="conf-btn" data-conf="high" onclick="pickConfidence(\'' + qid + '\',\'high\')">High</button></div>' +
    '<div class="q-actions">' +
    '<button type="button" class="btn-reveal" id="revealbtn_' + qid + '" disabled onclick="revealQ(\'' + qid + '\')">Reveal answer</button>' +
    '<button type="button" class="btn-idk" onclick="dontKnowQ(\'' + qid + '\')">I don\'t know</button></div>' +
    '<div class="q-reveal" id="reveal_' + qid + '"><div class="reveal-label">Answer</div>' +
    '<div class="reveal-body">' + escapeHtml(d.q.a) + '</div>' + se +
    '<div class="q-rate"><div class="rate-label">How did that go? <span class="rate-hint">(this sets when you see it next)</span></div>' +
    '<button type="button" class="rate-btn rate-again" data-grade="1" onclick="rateQ(\'' + qid + '\',1)">Again<small>&lt;10m</small></button>' +
    '<button type="button" class="rate-btn rate-hard" data-grade="2" onclick="rateQ(\'' + qid + '\',2)">Hard<small></small></button>' +
    '<button type="button" class="rate-btn rate-good" data-grade="3" onclick="rateQ(\'' + qid + '\',3)">Good<small></small></button>' +
    '<button type="button" class="rate-btn rate-easy" data-grade="4" onclick="rateQ(\'' + qid + '\',4)">Easy<small></small></button>' +
    '</div><div class="rate-result"></div></div></div>';
}

function buildReviewQueue() {
  const container = document.getElementById("personal-reviews");
  if (!container) return;
  if (!window.__CSCS_QUESTIONS) return;
  const due = interleave(dueCards());
  const goalDue = document.getElementById("goal-due");
  if (goalDue) goalDue.textContent = due.length;
  if (due.length === 0) {
    container.innerHTML =
      '<section class="caught-up"><div class="cu-check">&#10003;</div>' +
      '<div class="cu-text"><b>All caught up.</b> Nothing is due right now. ' +
      'Sleep is part of the schedule — don\'t cram tonight. A short review the morning of beats a late session.</div></section>';
    return;
  }
  const top = due.slice(0, 12);
  let html = '<section class="personal-review-section">' +
    '<h2 class="rs-title">Your review queue &middot; ' + due.length + ' due</h2>' +
    '<p class="rs-sub">Interleaved across domains by exam weight (FSRS-scheduled). Mixing topics feels harder but roughly doubles what transfers to test day. Forgetting one is fine — that\'s where learning happens.</p>';
  top.forEach((d, i) => { html += questionCardHTML(d, "pr_" + i, { label: "&#10227; Due" }); });
  if (due.length > 12) html += '<div class="pr-overflow">+ ' + (due.length - 12) + ' more appear after you clear these.</div>';
  html += "</section>";
  container.innerHTML = html;
}

// ════════════════════════════════════════════════════════════════════════════
//   CALIBRATION DASHBOARD  (the highest-utility widget per the review)
// ════════════════════════════════════════════════════════════════════════════
function renderDashboard() {
  const host = document.getElementById("cscs-dashboard");
  if (!host) return;
  const s = getState();
  // aggregate retrievability + due counts per domain from cards
  const agg = {};
  const now = new Date();
  for (const stable in s.cards) {
    const dom = domainFor(stable);
    const a = agg[dom] = agg[dom] || { n: 0, due: 0, rSum: 0, rN: 0 };
    a.n++;
    if (new Date(s.cards[stable].due) <= now) a.due++;
    const R = retrievability(s.cards[stable]);
    if (R != null) { a.rSum += R; a.rN++; }
  }
  const cal = s.calibration.byDomain;
  const tracked = Object.keys(s.cards).length;
  if (tracked === 0) { host.innerHTML = ""; return; }

  const order = ["ES", "EX", "PD", "NT"];
  let rows = "";
  order.forEach(dom => {
    const a = agg[dom]; const c = cal[dom];
    if (!a && !c) return;
    const meanR = a && a.rN ? a.rSum / a.rN : null;
    const acc = c && c.n ? c.accSum / c.n : null;
    const brier = c && c.n ? c.brierSum / c.n : null;
    const conf = c && c.n ? c.confSum / c.n : null;
    // calibration gap: confidence minus accuracy (positive = overconfident)
    const gap = (conf != null && acc != null) ? conf - acc : null;
    const rPct = meanR != null ? Math.round(meanR * 100) : null;
    const rColor = rPct == null ? "var(--text-dim)" : rPct >= 85 ? "var(--good,#67e8b0)" : rPct >= 70 ? "var(--warn,#ffb86b)" : "var(--bad,#ff7a7a)";
    rows +=
      '<div class="dash-row">' +
      '<div class="dash-dom">' + (DOMAIN_NAME[dom] || dom) + '</div>' +
      '<div class="dash-bar"><div class="dash-fill" style="width:' + (rPct == null ? 0 : rPct) + '%;background:' + rColor + '"></div>' +
      '<span class="dash-bartxt">' + (rPct == null ? "—" : rPct + "% recall") + '</span></div>' +
      '<div class="dash-due">' + (a ? a.due : 0) + ' due</div>' +
      '<div class="dash-cal">' + (gap == null ? "—" :
        (Math.abs(gap) <= 0.07 ? '<span class="cal-ok">well-calibrated</span>' :
         gap > 0 ? '<span class="cal-over">overconfident +' + Math.round(gap * 100) + '</span>' :
                   '<span class="cal-under">underconfident ' + Math.round(gap * 100) + '</span>')) +
      '</div></div>';
  });
  // 14-day review volume sparkline
  const counts = {};
  s.log.forEach(l => { const d = (l.ts || "").slice(0, 10); if (d) counts[d] = (counts[d] || 0) + 1; });
  let spark = "";
  let maxc = 1; const days = [];
  for (let i = 13; i >= 0; i--) { const d = new Date(); d.setDate(d.getDate() - i); const k = d.toISOString().slice(0, 10); const v = counts[k] || 0; days.push(v); if (v > maxc) maxc = v; }
  spark = days.map(v => '<span class="spk" style="height:' + Math.max(3, Math.round(v / maxc * 26)) + 'px" title="' + v + ' reviews"></span>').join("");

  host.innerHTML =
    '<details class="dashboard" open><summary>Your dashboard — where to study, not how much you\'ve studied</summary>' +
    '<div class="dash-grid">' + (rows || '<div class="dash-empty">Rate a few questions to populate your calibration.</div>') + '</div>' +
    '<div class="dash-foot"><div class="dash-spark-wrap"><span class="dash-spark-label">14-day reviews</span><div class="dash-spark">' + spark + '</div></div>' +
    '<div class="dash-legend">Recall = FSRS retrievability. Calibration compares your stated confidence to your real accuracy — overconfidence is the signal to study that domain harder.</div></div>' +
    '</details>';
}

function updateHeaderStats() {
  const s = getState();
  const tracked = Object.keys(s.cards).length;
  const now = new Date();
  const due = Object.values(s.cards).filter(c => c.due && new Date(c.due) <= now).length;
  const todayLog = s.log.filter(l => (l.ts || "").slice(0, 10) === TODAY);
  const correct = todayLog.filter(l => l.rating >= 2).length;
  const sc = document.getElementById("self-score"); if (sc) sc.textContent = correct;
  const stats = document.getElementById("lifetime-stats");
  if (stats) stats.innerHTML = "Lifetime: <b>" + tracked + "</b> tracked &middot; <b>" + due + "</b> due now";
  const gd = document.getElementById("goal-due"); if (gd) gd.textContent = due;
  const gmin = document.getElementById("goal-min");
  const newc = window.__CSCS_NEWCOUNT || 0;
  if (gmin) gmin.textContent = Math.min(40, Math.round((newc + due) * 0.6) + 4);
}

// ════════════════════════════════════════════════════════════════════════════
//   EXPORT / IMPORT
// ════════════════════════════════════════════════════════════════════════════
function exportProgress() {
  const blob = new Blob([JSON.stringify(getState(), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "cscs-progress-" + TODAY + ".json";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
function importProgress(file) {
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const data = JSON.parse(e.target.result);
      if (data.version === 1 && data.cards) { lsSet(STATE_KEY, data); }
      else if (data.qstate) { // legacy export
        lsSet("qstate", data.qstate); lsSet("answers", data.answers || {});
        const migrated = migrateOrInit(); lsSet(STATE_KEY, migrated);
      }
      bootRender(); showToast("Progress imported.");
    } catch (err) { showToast("Import failed: " + err.message); }
  };
  reader.readAsText(file);
}

// ════════════════════════════════════════════════════════════════════════════
//   TOAST
// ════════════════════════════════════════════════════════════════════════════
function showToast(msg) {
  let t = document.getElementById("cscs-toast");
  if (!t) { t = document.createElement("div"); t.id = "cscs-toast"; t.className = "cscs-toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("visible");
  clearTimeout(t._timer); t._timer = setTimeout(() => t.classList.remove("visible"), 2400);
}

// ════════════════════════════════════════════════════════════════════════════
//   REVEAL-ON-SCROLL for lesson cards
// ════════════════════════════════════════════════════════════════════════════
const obs = new IntersectionObserver(entries => {
  entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add("visible"); obs.unobserve(e.target); } });
}, { threshold: 0.08 });


// ────────────────────────────────────────────────────────────────────────────
//   "Last answered" labels next to each question
// ────────────────────────────────────────────────────────────────────────────
function manilaDate(d) {
  try {
    var p = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila",
      year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(d || new Date());
    var o = {}; p.forEach(function (x) { o[x.type] = x.value; });
    return o.year + "-" + o.month + "-" + o.day;
  } catch (e) { return null; }
}
function formatLastAnswered(ts) {
  if (!ts) return "";
  var when = new Date(ts);
  if (isNaN(when.getTime())) return "";
  try {
    var dateP = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Manila", year: "numeric", month: "short", day: "numeric" }).format(when);
    var timeP = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Manila", hour: "numeric", minute: "2-digit" }).format(when);
    return "Answered " + dateP + " at " + timeP;
  } catch (e) { return "Answered " + ts; }
}
function latestLogTsFor(stable) {
  var s = getState();
  if (!s || !s.log || !s.log.length) return null;
  var latest = null;
  for (var i = s.log.length - 1; i >= 0; i--) {
    var l = s.log[i];
    if (l && l.cardId === stable) {
      if (!latest || l.ts > latest) latest = l.ts;
    }
  }
  return latest;
}
function refreshLastAnsweredFor(stable) {
  if (!stable) return;
  var ts = latestLogTsFor(stable);
  var txt = ts ? formatLastAnswered(ts) : "Not answered yet";
  document.querySelectorAll('.q-last[data-stable="' + (window.CSS && CSS.escape ? CSS.escape(stable) : stable) + '"]').forEach(function (el) {
    el.textContent = txt;
    el.classList.toggle("q-last-never", !ts);
  });
}
function hydrateLastAnswered() {
  document.querySelectorAll(".q-last[data-stable]").forEach(function (el) {
    var stable = el.dataset.stable;
    var ts = latestLogTsFor(stable);
    el.textContent = ts ? formatLastAnswered(ts) : "Not answered yet";
    el.classList.toggle("q-last-never", !ts);
  });
}


// ────────────────────────────────────────────────────────────────────────────
//   Prev / Next lesson nav (uses __CSCS_PREV / __CSCS_NEXT baked by generator)
// ────────────────────────────────────────────────────────────────────────────
function cscsNavPrev() {
  if (typeof window === "undefined" || !window.__CSCS_PREV) return false;
  window.location.href = "cscs_" + window.__CSCS_PREV + ".html";
  return false;
}
function cscsNavNext() {
  if (typeof window === "undefined" || !window.__CSCS_NEXT) return false;
  window.location.href = "cscs_" + window.__CSCS_NEXT + ".html";
  return false;
}
function hydrateLessonNav() {
  var prev = document.getElementById("ln-prev");
  var next = document.getElementById("ln-next");
  if (prev && !window.__CSCS_PREV) { prev.classList.add("ln-disabled"); prev.setAttribute("aria-disabled","true"); prev.onclick = function(){ return false; }; }
  if (next && !window.__CSCS_NEXT) { next.classList.add("ln-disabled"); next.setAttribute("aria-disabled","true"); next.onclick = function(){ return false; }; }
}


/* ── Voice dictation (Web Speech API) — answer by speaking when you can't type.
   Appends the transcript into the answer box and fires `input`, which runs
   onAnswerInput → unlocks the gated Reveal exactly like typing would. Hidden
   where the browser has no SpeechRecognition. Typing is always the fallback. ── */
function speechSupported() { return ('SpeechRecognition' in window) || ('webkitSpeechRecognition' in window); }
var __saRec = null, __saTA = null, __saBtn = null, __saInitial = '', __saEditTA = null, __saEditFn = null;
function saDetachEdit() {
  if (__saEditTA && __saEditFn) { __saEditTA.removeEventListener('keydown', __saEditFn); __saEditTA.removeEventListener('paste', __saEditFn); }
  __saEditTA = null; __saEditFn = null;
}
function saMicState(btn, on, msg) {
  if (!btn) return;
  btn.classList.toggle('listening', !!on);
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  var l = btn.querySelector('.mic-lbl'); if (l) l.textContent = msg || (on ? 'Listening… tap to stop' : 'Speak');
}
function saStopMic() {
  if (__saRec) { try { __saRec.onresult = null; __saRec.onend = null; __saRec.onerror = null; __saRec.stop(); } catch (e) {} }
  if (__saBtn) saMicState(__saBtn, false);
  saDetachEdit();
  __saRec = null; __saTA = null; __saBtn = null;
}
function toggleDictation(btn) {
  if (!speechSupported()) { saMicState(btn, false, 'Voice not supported'); return; }
  var q = btn && btn.closest ? btn.closest('.q') : null; if (!q) return;
  var ta = q.querySelector('.q-answer'); if (!ta) return;
  if (__saRec && __saTA === ta) { saStopMic(); return; }   // toggle off
  if (__saRec) saStopMic();                                // switch cards
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var rec; try { rec = new SR(); } catch (e) { saMicState(btn, false, 'Voice not supported'); return; }
  rec.lang = 'en-US'; rec.interimResults = true; rec.continuous = true; rec.maxAlternatives = 1;
  __saRec = rec; __saTA = ta; __saBtn = btn;
  __saInitial = ta.value ? (ta.value.replace(/\s+$/, '') + ' ') : '';
  saMicState(btn, true);
  // The instant the user edits the box by hand, stop listening so a late
  // recognition result can't overwrite their edit.
  __saEditFn = function () { saStopMic(); };
  __saEditTA = ta;
  ta.addEventListener('keydown', __saEditFn);
  ta.addEventListener('paste', __saEditFn);
  rec.onresult = function (e) {
    if (__saRec !== rec) return;   // ignore stray events after stop
    // Rebuild the whole transcript from results[0] every event. Never keep a
    // running buffer of finals — Chrome re-reports a growing result at index 0,
    // so appending each tick duplicated every word ("linear linear is …").
    var finalT = '', interim = '';
    for (var i = 0; i < e.results.length; i++) {
      var seg = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalT += seg + ' '; else interim += seg;
    }
    ta.value = (__saInitial + finalT + interim)
      .replace(/\s+/g, ' ').replace(/\s+([.,;:!?])/g, '$1').replace(/^\s+/, '').replace(/\s+$/, '');
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  };
  rec.onerror = function (ev) {
    var code = ev && ev.error;
    var m = code === 'not-allowed' || code === 'service-not-allowed' ? 'Mic blocked — allow access'
          : code === 'no-speech' ? 'Didn’t catch that — tap to retry' : 'Speak';
    saMicState(btn, false, m);
  };
  rec.onend = function () {
    if (__saBtn === btn) saStopMic();
  };
  try { rec.start(); } catch (e) { saStopMic(); }
}

/* -- Next-review countdown: show when a graded card returns, with a live modal -- */
function fmtDueAbs(iso){try{var d=new Date(iso);var dt=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Manila',year:'numeric',month:'short',day:'numeric'}).format(d);var tm=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Manila',hour:'numeric',minute:'2-digit'}).format(d);return dt+' at '+tm;}catch(e){return '';}}
function fmtCountdown(ms){if(ms<=0)return 'available now';var s=Math.floor(ms/1000);var d=Math.floor(s/86400);s-=d*86400;var h=Math.floor(s/3600);s-=h*3600;var m=Math.floor(s/60);s-=m*60;function p(n){return (n<10?'0':'')+n;}if(d>0)return d+'d '+p(h)+'h '+p(m)+'m '+p(s)+'s';if(h>0)return p(h)+'h '+p(m)+'m '+p(s)+'s';return p(m)+'m '+p(s)+'s';}
function relDueLong(iso){var ms=new Date(iso)-new Date();if(ms<=0)return 'now';var days=Math.round(ms/86400000);if(days<1){var h=Math.round(ms/3600000);return h<1?'in <1h':'in ~'+h+'h';}return 'in '+days+' day'+(days===1?'':'s');}
function relDueShort(ms){if(ms<=0)return 'now';var days=Math.floor(ms/86400000);if(days>=1)return days+'d';var h=Math.floor(ms/3600000);if(h>=1)return h+'h';var m=Math.max(1,Math.floor(ms/60000));return m+'m';}
var __cdTimer=null;
function cdEsc(e){if(e.key==='Escape')closeCountdown();}
function closeCountdown(){if(__cdTimer){clearInterval(__cdTimer);__cdTimer=null;}var ov=document.getElementById('cd-modal');if(ov&&ov.parentNode)ov.parentNode.removeChild(ov);document.removeEventListener('keydown',cdEsc);}
function openCountdown(iso){
  closeCountdown();
  var due=new Date(iso);if(isNaN(due.getTime()))return;
  var ov=document.createElement('div');ov.id='cd-modal';ov.className='cd-overlay';
  ov.innerHTML='<div class="cd-card" role="dialog" aria-modal="true" aria-label="Next review countdown">'
    +'<button class="cd-x" type="button" aria-label="Close">&times;</button>'
    +'<div class="cd-lab">This card returns in</div>'
    +'<div class="cd-time" id="cd-time">--</div>'
    +'<div class="cd-abs">'+fmtDueAbs(iso)+' (Manila)</div>'
    +'<div class="cd-note">Spaced repetition sets the gap from how well you knew it. Letting it fade a little before review is what makes the memory stick.</div>'
    +'</div>';
  document.body.appendChild(ov);
  ov.addEventListener('click',function(e){if(e.target===ov)closeCountdown();});
  ov.querySelector('.cd-x').addEventListener('click',closeCountdown);
  function tick(){var t=document.getElementById('cd-time');if(!t){closeCountdown();return;}var ms=due-new Date();t.textContent=fmtCountdown(ms);t.classList.toggle('cd-now',ms<=0);}
  tick();__cdTimer=setInterval(tick,1000);
  document.addEventListener('keydown',cdEsc);
}
function nextDueFor(stable){var s=getState();var c=s&&s.cards&&s.cards[stable];if(!c||!c.due)return null;return c.due;}
function fillNext(elm){
  var stable=elm.dataset.stable;var iso=nextDueFor(stable);
  if(!iso){elm.textContent='';elm.style.display='none';return;}
  elm.style.display='';var ms=new Date(iso)-new Date();
  var lab=ms<=0?'due now':'next in '+relDueShort(ms);
  elm.innerHTML='';
  var b=document.createElement('button');b.type='button';b.className='q-next-btn';b.title='See when this card returns';b.innerHTML='&#9201; '+lab;
  b.addEventListener('click',function(){openCountdown(iso);});
  elm.appendChild(b);
}
function hydrateNextReview(){var list=document.querySelectorAll('.q-next[data-stable]');for(var i=0;i<list.length;i++)fillNext(list[i]);}
function refreshNextReviewFor(stable){var sel='.q-next[data-stable="'+(window.CSS&&CSS.escape?CSS.escape(stable):stable)+'"]';var list=document.querySelectorAll(sel);for(var i=0;i<list.length;i++)fillNext(list[i]);}


/* -- Full review schedule: every scheduled card, soonest-due first -- */
function __cscsQMap(){return (window.__CSCS_QUESTIONS)||{};}
function qMetaForStable(stable){
  var parts=String(stable).split("__");var idx=parts.pop();var topic=parts.join("__");
  var qm=__cscsQMap();var arr=qm[topic];var item=arr&&arr[+idx];
  var pretty=topic.replace(/_/g," ").replace(/\b\w/g,function(c){return c.toUpperCase();});
  return {q:(item&&item.q)?item.q:(pretty+" · Q"+((+idx)+1)),topic:pretty};
}
function collectSchedule(){
  var s=getState();var cards=(s&&s.cards)||{};var now=Date.now();var out=[];
  for(var k in cards){if(!Object.prototype.hasOwnProperty.call(cards,k))continue;
    var c=cards[k];if(!c||!c.due)continue;var t=new Date(c.due).getTime();if(isNaN(t))continue;
    var m=qMetaForStable(k);out.push({stable:k,iso:c.due,ms:t-now,t:t,q:m.q,topic:m.topic});}
  out.sort(function(a,b){return a.t-b.t;});return out;
}
var __schTimer=null;
function schEsc(e){if(e.key==='Escape'){if(document.getElementById('cd-modal'))return;closeSchedule();}}
function closeSchedule(){if(__schTimer){clearInterval(__schTimer);__schTimer=null;}var ov=document.getElementById('sch-modal');if(ov&&ov.parentNode)ov.parentNode.removeChild(ov);document.removeEventListener('keydown',schEsc);}
function schRowHTML(it){
  var soon=it.ms<=0;
  var badge=soon?'<span class="sch-badge now">due now</span>':'<span class="sch-badge">in '+relDueShort(it.ms)+'</span>';
  var abs=soon?'available now':fmtDueAbs(it.iso);
  return '<button type="button" class="sch-row" data-iso="'+escapeHtml(it.iso)+'">'
    +'<span class="sch-q">'+escapeHtml(it.q)+'</span>'
    +'<span class="sch-meta">'+badge+'<span class="sch-abs">'+escapeHtml(abs)+'</span></span>'
    +'</button>';
}
function openSchedule(){
  closeSchedule();
  var list=collectSchedule();var up=[],dueNow=[];
  for(var i=0;i<list.length;i++){(list[i].ms<=0?dueNow:up).push(list[i]);}
  var body='';
  if(!list.length){
    body='<div class="sch-empty">No reviews scheduled yet. Grade a few questions and they’ll line up here, soonest first.</div>';
  }else{
    if(up.length){
      var hero=up[0];
      body+='<div class="sch-hero"><div class="sch-hero-lab">Next card returns in</div>'
        +'<div class="sch-hero-time" id="sch-hero-time" data-iso="'+escapeHtml(hero.iso)+'">--</div>'
        +'<div class="sch-hero-q">'+escapeHtml(hero.q)+'</div></div>';
      body+='<div class="sch-sec">Coming up · '+up.length+'</div>';
      for(var u=0;u<up.length;u++)body+=schRowHTML(up[u]);
    }
    if(dueNow.length){
      body+='<div class="sch-sec">Due now · '+dueNow.length+'</div>';
      for(var n=0;n<dueNow.length;n++)body+=schRowHTML(dueNow[n]);
    }
  }
  var sub=list.length?(list.length+' card'+(list.length===1?'':'s')+' tracked · soonest first'):'Nothing tracked yet';
  var ov=document.createElement('div');ov.id='sch-modal';ov.className='sch-overlay';
  ov.innerHTML='<div class="sch-card" role="dialog" aria-modal="true" aria-label="Review schedule">'
    +'<button class="sch-x" type="button" aria-label="Close">&times;</button>'
    +'<div class="sch-title">Review schedule</div>'
    +'<div class="sch-subtitle">'+sub+'</div>'
    +'<div class="sch-scroll">'+body+'</div>'
    +'<div class="sch-foot">Gaps widen as recall gets stronger — letting a memory fade a little before you see it again is what locks it in.</div>'
    +'</div>';
  document.body.appendChild(ov);
  ov.addEventListener('click',function(e){if(e.target===ov)closeSchedule();});
  ov.querySelector('.sch-x').addEventListener('click',closeSchedule);
  var rows=ov.querySelectorAll('.sch-row');
  for(var r=0;r<rows.length;r++){rows[r].addEventListener('click',function(){var iso=this.getAttribute('data-iso');if(iso)openCountdown(iso);});}
  function tick(){var h=document.getElementById('sch-hero-time');if(!h)return;var ms=new Date(h.getAttribute('data-iso'))-new Date();h.textContent=fmtCountdown(ms);h.classList.toggle('sch-now',ms<=0);}
  tick();__schTimer=setInterval(tick,1000);
  document.addEventListener('keydown',schEsc);
}
function wireScheduleOpeners(){
  var box=document.querySelector('.session-summary');
  if(box){box.classList.add('is-clickable');
    var stats=box.querySelectorAll('.stat');
    for(var i=0;i<stats.length;i++){(function(st){
      st.setAttribute('role','button');st.setAttribute('tabindex','0');st.title='See your full review schedule';
      st.addEventListener('click',openSchedule);
      st.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();openSchedule();}});
    })(stats[i]);}}
  var btn=document.querySelector('.sched-open');
  if(btn)btn.addEventListener('click',openSchedule);
}


/* -- Daily load discipline: require only what's NEW or actually DUE today.
   The static pretest/practice sections are stamped by day-number and don't
   know your FSRS state, so they re-show cards you already cleared (now
   scheduled far out) every visit. Reviewing a card before it's due is massed
   practice; the spacing is what makes it stick. So we collapse anything that
   is scheduled for later (already learned) and keep new + genuinely-due. A
   card is only "not due" because you graded it before, and day-completion
   counts a card as done once it's ever been graded -- so hiding these never
   traps the day. -- */
function gateStaticPractice(){
  var st=getState();var cards=(st&&st.cards)||{};var now=Date.now();
  var sections=document.querySelectorAll('.pretest-section, .question-block');
  var totalVisible=0;
  for(var s=0;s<sections.length;s++){
    var sec=sections[s];
    var qcards=sec.querySelectorAll('.q[data-stable]');
    var deferred=0, visible=0;
    for(var i=0;i<qcards.length;i++){
      var q=qcards[i];
      if(q.classList.contains('rated')){visible++;continue;} // answered this session: keep w/ its result
      var c=cards[q.getAttribute('data-stable')];
      var notDue=!!(c&&c.due&&new Date(c.due).getTime()>now);
      if(notDue){q.classList.add('q-deferred');deferred++;}
      else{q.classList.remove('q-deferred');visible++;}
    }
    totalVisible+=visible;
    addDeferNote(sec, deferred, visible);
  }
  try{
    var stats=document.querySelectorAll('.session-summary .stat');
    for(var k=0;k<stats.length;k++){
      var b=stats[k].querySelector('b');
      if(b&&!b.id&&/questions/i.test(stats[k].textContent)){b.textContent=totalVisible;}
    }
  }catch(e){}
}
function addDeferNote(sec, deferred, visible){
  var old=sec.querySelector('.defer-note');if(old&&old.parentNode)old.parentNode.removeChild(old);
  sec.classList.remove('show-deferred');
  if(deferred<=0)return;
  var qs=sec.querySelector('.qs');if(!qs)return;
  var allDone=visible===0;
  var plural=deferred===1?'':'s';
  var msg=allDone
    ? '<b>Caught up here.</b> '+deferred+' card'+plural+' scheduled for later — hidden so you’re not re-answering early. The spacing is the method working.'
    : '<b>'+visible+'</b> to do now · <b>'+deferred+'</b> scheduled for later, hidden — you already know '+(deferred===1?'it':'them')+' well enough that today would be too soon.';
  var note=document.createElement('div');note.className='defer-note'+(allDone?' all-done':'');
  note.innerHTML='<span class="dn-txt">'+msg+' <span class="dn-link">Review schedule</span> has the return dates.</span>'
    +'<button type="button" class="dn-toggle">Show '+deferred+' hidden</button>';
  qs.parentNode.insertBefore(note, qs);
  var btn=note.querySelector('.dn-toggle');
  btn.addEventListener('click',function(){
    var on=sec.classList.toggle('show-deferred');
    btn.textContent=on?('Hide '+deferred+' scheduled'):('Show '+deferred+' hidden');
  });
  var lnk=note.querySelector('.dn-link');
  if(lnk&&typeof openSchedule==='function'){lnk.style.cursor='pointer';lnk.addEventListener('click',function(){openSchedule();});}
}

function bootRender() {
  if (!speechSupported()) { try { document.documentElement.classList.add("no-speech"); } catch (e) {} }
  updateHeaderStats();
  renderDashboard();
  buildReviewQueue();
  hydrateLastAnswered();
  hydrateNextReview();
  wireScheduleOpeners();
  gateStaticPractice();
  hydrateLessonNav();
  renderDayProgress();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".reveal").forEach(el => obs.observe(el));
  // Wait briefly for the FSRS module so the first queue uses real retrievability.
  if (fsrsReady()) bootRender();
  else {
    window.addEventListener("fsrs-ready", bootRender, { once: true });
    setTimeout(() => { if (!__scheduler) bootRender(); }, 1200); // fallback if module never loads
  }
});

// ════════════════════════════════════════════════════════════════════════════
//   CROSS-DEVICE SYNC VIA GITHUB GIST  (adapted to the single-state schema)
// ════════════════════════════════════════════════════════════════════════════
const SYNC_KEYS = { token: "sync.token", gist: "sync.gist_id", enabled: "sync.enabled", last_push: "sync.last_push_at", last_pull: "sync.last_pull_at",
  // Separate stamps per transport. Shared ones let a GitHub-token push from a
  // year ago show up as the signed-in account's "last push".
  acct_last_push: "sync.acct_last_push_at", acct_last_pull: "sync.acct_last_pull_at" };
const SYNC_FILENAME = "cscs-progress.json";
const SYNC_SCHEMA = 3;

// ── ACCOUNT SYNC (Hybrid Crew sign-in) ──────────────────────────────────────
// The hub (dsingson5.github.io/hybrid-crew) and this study site share ONE
// origin, so a hub sign-in has already left `hcUser` + `roxlive.session` in
// localStorage AT THE ROOT — raw keys, NOT under LS_PREFIX. If they are there
// the athlete is already signed in here and sync needs zero setup: we talk to
// the worker's /study endpoint, which derives the user FROM THE TOKEN. There is
// no user parameter, so nobody can read or write anyone else's progress.
// The bearer token goes to STUDY_WORKER and nowhere else — never to GitHub.
const STUDY_WORKER = "https://roxlive-sync.david-singson.workers.dev";
const STUDY_SITE = "cscs";
const ACCOUNT_KEYS = { rev: "sync.acct_rev", stale: "sync.acct_stale", owner: "sync.acct_owner" };
const STUDY_MAX_BYTES = 1500000;   // ~1.5 MB — past this we trim the review log
const STUDY_LOG_KEEP = 2000;       // newest N log entries kept when trimming

function accountSession() {
  try {
    const user = (localStorage.getItem("hcUser") || "").trim();
    const token = (localStorage.getItem("roxlive.session") || "").trim();
    if (!user || !token) return null;
    return { user: user, token: token };
  } catch (e) { return null; }
}
// A 401 marks the SPECIFIC token that failed, so signing in again anywhere on
// the origin (which writes a fresh token) clears the stale flag by itself.
function accountStale() {
  const s = accountSession();
  if (!s) return false;
  return lsGet(ACCOUNT_KEYS.stale, "") === s.token;
}
function markAccountStale(on) {
  const s = accountSession();
  lsSet(ACCOUNT_KEYS.stale, on && s ? s.token : "");
}
// Read straight from localStorage every time. The in-memory cache this replaces
// went stale the moment a SECOND TAB of this site pushed: that tab wrote the new
// rev to localStorage, this tab kept serving the one it read at boot, and every
// later push here carried a revision the server had already retired.
function getAcctRev() { return lsGet(ACCOUNT_KEYS.rev, "") || ""; }
function setAcctRev(rev) { lsSet(ACCOUNT_KEYS.rev, rev || ""); }

// A push is an OVERWRITE of the cloud record. This tab may only publish its
// state once it has actually READ and merged the server's copy — see
// accountPush. Cleared on sign-out, on 401/403, and when the owner changes.
let _acctMerged = false;
// Latched when the worker refuses the payload as too large. Retrying on every
// grade only burns battery and hides the fact that sync has stopped; the latch
// holds until the athlete taps "Sync now".
let _acctTooLarge = false;
// "Access revoked" (dropped from the crew, coach-disabled, trial over) reads
// nothing like "sign-in expired" and needs different words. "" = neither.
let _acctRevokedMsg = "";
// Last account-sync outcome, so the UI stops claiming everything syncs
// automatically while the button beside it reads "Push failed".
let _acctOutcome = "";

// The study state key is per SITE (hyroxl2.state.v1), not per user, and the
// state records no owner. Two athletes on one device — a family iPad, the gym
// tablet, one shared laptop — would therefore have their cards UNIONED into
// each other's cloud copy, permanently and in both directions: the merge is a
// union with no tombstones, so re-syncing cannot undo it. Park the outgoing
// athlete's state under a recoverable backup key and start this one clean.
// Never a silent wipe — back up first, exactly like maybeHardReset.
function ensureStateOwner() {
  const s = accountSession();
  if (!s) return;
  const owner = lsGet(ACCOUNT_KEYS.owner, "");
  if (owner === s.user) return;
  if (owner) {
    const stamp = "." + owner + "." + Date.now();
    try {
      // The legacy keys go too: getState() re-migrates from qstate/answers when
      // state.v1 is missing, which would resurrect the previous athlete's cards.
      ["state.v1", "qstate", "answers"].forEach(function (k) {
        const prev = localStorage.getItem(LS_PREFIX + k);
        if (prev != null) localStorage.setItem(LS_PREFIX + "backup.user." + k + stamp, prev);
        localStorage.removeItem(LS_PREFIX + k);
      });
    } catch (e) {}
    setAcctRev("");        // a different key on the server: this device's rev means nothing there
    _acctMerged = false;
    _acctTooLarge = false;
    try { bootRender(); } catch (e) {}
  }
  lsSet(ACCOUNT_KEYS.owner, s.user);
}

async function studyFetch(method, body) {
  const s = accountSession();
  if (!s) throw new Error("Not signed in");
  const res = await fetch(STUDY_WORKER + "/study?site=" + encodeURIComponent(STUDY_SITE), {
    method: method,
    headers: { "Authorization": "Bearer " + s.token, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  });
  let data = null;
  try { data = await res.json(); } catch (e) { data = null; }
  return { status: res.status, ok: res.ok, data: data || {} };
}

function handleAccountUnauthorized(silent) {
  const wasStale = accountStale();
  markAccountStale(true);
  // Do NOT clear the rev. It is not a credential — it is the compare-and-set
  // token, the last revision this device saw, and keeping it is what makes the
  // eventual reconnect a 409 (merge, then retry) instead of a clobber.
  _acctMerged = false;   // whatever we knew, re-read the server before writing again
  _acctOutcome = "err";
  updateSyncButton("error", "Sign in again");
  // Background pulls must not nag: only the FIRST 401 (and only a foreground
  // one) says anything out loud.
  if (!silent && !wasStale) showToast("Sign-in expired — open sync settings to sign in again.");
  refreshSyncAccountUI();
}

// 403 = the coach turned access off, or a trial ended. Signing in again works
// and then fails here again, so this must not say "expired": say what happened
// and stop pushing until something changes.
function handleAccountForbidden(silent, msg) {
  _acctRevokedMsg = msg || "Your access has been turned off — message Coach David.";
  _acctMerged = false;
  _acctOutcome = "err";
  markAccountStale(true);        // also stops scheduleSyncPush retrying on every grade
  updateSyncButton("error", "Sync off");
  if (!silent) showToast(_acctRevokedMsg);
  refreshSyncAccountUI();
}

// Payload hygiene. cards / answers / completedDays / touchedDays are NEVER
// trimmed — only the review log, oldest first, and only near the size ceiling.
function buildAccountPayload() {
  const payload = buildSyncPayload();
  if (JSON.stringify(payload).length > STUDY_MAX_BYTES && payload.state &&
      Array.isArray(payload.state.log) && payload.state.log.length > STUDY_LOG_KEEP) {
    // "newest N" only means newest if the log is time-ordered. The local append
    // path keeps it so and mergeRemote re-sorts — but only when it changed
    // something. Sort a COPY here rather than trust that.
    const log = payload.state.log.slice()
      .sort(function (a, b) { return String(a.ts || "").localeCompare(String(b.ts || "")); });
    payload.state = Object.assign({}, payload.state, { log: log.slice(-STUDY_LOG_KEEP) });
  }
  return payload;
}

async function accountPull(opts) {
  const silent = !!(opts && opts.silent);
  ensureStateOwner();
  updateSyncButton("syncing", "Pulling…");
  try {
    const res = await studyFetch("GET", null);
    if (res.status === 401) { handleAccountUnauthorized(silent); return false; }
    if (res.status === 403) { handleAccountForbidden(silent, (res.data && res.data.error) || ""); return false; }
    // A 200 is not proof of a study response: a captive portal or an edge error
    // page is also 200 with a body we cannot parse, and studyFetch turns that
    // into {}. Treating it as "pulled, nothing stored" cleared the stale flag,
    // set the rev to "" and armed an empty-rev push over real progress. Demand
    // the worker's own success marker.
    if (!res.ok || res.data.ok !== true) throw new Error((res.data && res.data.error) || ("HTTP " + res.status));
    markAccountStale(false);
    _acctRevokedMsg = "";
    // Never widen the rev to "" on a response that carried none — "" is exactly
    // the value the server reads as "no record here yet".
    if (res.data.rev) setAcctRev(res.data.rev);
    else if (res.data.payload == null) setAcctRev("");
    // `payload` is exactly the {schema, updated_at, state} object mergeRemote wants.
    const changed = res.data.payload ? mergeRemote(res.data.payload) : false;
    _acctMerged = true;                // this tab has now seen the server copy
    _acctOutcome = "ok";
    lsSet(SYNC_KEYS.acct_last_pull, new Date().toISOString());
    if (changed) { bootRender(); showToast("Pulled remote progress."); }
    updateSyncButton("enabled", "Synced");
    return changed;
  } catch (e) {
    _acctOutcome = "err";
    updateSyncButton("error", "Pull failed");
    if (!silent) showToast("Sync pull failed: " + e.message);
    return false;
  }
}

async function accountPush(opts) {
  const silent = !!(opts && opts.silent);
  ensureStateOwner();
  // NEVER write the cloud copy from a tab that has not read it. A push replaces
  // the record wholesale, so without a merge behind it this is the 2026-07-20
  // wipe again — and the 4 s debounce is long enough for a keystroke's push to
  // overtake the boot pull that is still in flight.
  if (!_acctMerged) {
    await accountPull({ silent: true });
    if (!_acctMerged) {                // pull failed — do NOT fall through
      _acctOutcome = "err";
      updateSyncButton("error", "Sync paused");
      if (!silent) showToast("Couldn't reach the cloud — your progress is saved on this device and will sync next time.");
      return false;
    }
  }
  if (_acctTooLarge) { updateSyncButton("error", "Too large"); return false; }
  updateSyncButton("syncing", "Pushing…");
  try {
    let res = await studyFetch("PUT", { payload: buildAccountPayload(), baseRev: getAcctRev() });
    // Another device wrote first: merge what it stored, then retry with the rev
    // the worker just handed back. Bounded, and NEVER with an empty rev — "" is
    // the one value that means "first write" to the server, i.e. clobber.
    for (let attempt = 0; attempt < 3 && res.status === 409; attempt++) {
      if (res.data && res.data.payload && mergeRemote(res.data.payload)) bootRender();
      if (!res.data || !res.data.rev) break;
      setAcctRev(res.data.rev);
      res = await studyFetch("PUT", { payload: buildAccountPayload(), baseRev: getAcctRev() });
    }
    if (res.status === 401) { handleAccountUnauthorized(silent); return false; }
    if (res.status === 403) { handleAccountForbidden(silent, (res.data && res.data.error) || ""); return false; }
    if (res.status === 413) {
      // Latched, not retried: the payload the server just refused will be
      // refused again on the next grade. Say so out loud — silently retrying
      // forever is how an athlete finds out months later that nothing backed up.
      _acctTooLarge = true;
      _acctOutcome = "err";
      updateSyncButton("error", "Too large");
      showToast("Your progress file is too big to sync — it's still safe on this device. Tell Coach David.");
      return false;
    }
    if (!res.ok || res.data.ok !== true) throw new Error((res.data && res.data.error) || ("HTTP " + res.status));
    markAccountStale(false);
    _acctRevokedMsg = "";
    if (res.data.rev) setAcctRev(res.data.rev);
    _acctOutcome = "ok";
    lsSet(SYNC_KEYS.acct_last_push, new Date().toISOString());
    updateSyncButton("enabled", "Synced");
    if (opts && opts.toast) showToast("Pushed to cloud");
    return true;
  } catch (e) {
    _acctOutcome = "err";
    updateSyncButton("error", "Push failed");
    if (!silent) showToast("Sync push failed: " + e.message);
    return false;
  }
}

// Signed in = synced, with nothing to configure. The Gist path stays as the
// legacy fallback for anyone who set one up before accounts existed.
function legacySyncEnabled() { return !!lsGet(SYNC_KEYS.enabled, false); }
function syncEnabled() { return !!accountSession() || legacySyncEnabled(); }
function getToken() { return localStorage.getItem(LS_PREFIX + SYNC_KEYS.token) || ""; }
function getGistId() { return localStorage.getItem(LS_PREFIX + SYNC_KEYS.gist) || ""; }
function setToken(t) { localStorage.setItem(LS_PREFIX + SYNC_KEYS.token, t); }
function setGistId(id) { localStorage.setItem(LS_PREFIX + SYNC_KEYS.gist, id); }

async function gistFetch(method, path, token, body) {
  const res = await fetch("https://api.github.com" + path, {
    method,
    headers: { "Authorization": "token " + token, "Accept": "application/vnd.github+json", "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28" },
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) {
    const text = await res.text();
    // A dead personal access token is the single most common failure here now
    // that Google sign-in has replaced it; say so plainly instead of leaking
    // GitHub's raw JSON at someone mid-study.
    if (res.status === 401 || res.status === 403) {
      throw new Error("Your GitHub token has expired. You do not need it any more — "
        + "close this and tap Sign in with Google at the top of the panel; that replaces the token entirely.");
    }
    throw new Error("GitHub API " + res.status + ": " + text.slice(0, 200));
  }
  return res.status === 204 ? null : res.json();
}

// reset_epoch rides along with the payload so the hard-reset guard never has to
// compare a Manila day-label against a UTC timestamp: that misread the first
// eight hours of any reset day as pre-epoch and threw the reset away.
function buildSyncPayload() { return { schema: SYNC_SCHEMA, reset_epoch: RESET_EPOCH, updated_at: new Date().toISOString(), state: getState() }; }
// Post-epoch = written by a device already on this epoch. The date comparison
// is only a fallback for payloads written before this field existed.
function remoteIsPostEpoch(remote) {
  if (!remote) return false;
  if (remote.reset_epoch) return remote.reset_epoch === RESET_EPOCH;
  return !!(remote.updated_at && String(remote.updated_at).slice(0, 10) >= RESET_EPOCH.slice(0, 10));
}

function mergeRemote(remote) {
  if (!remote) return false;
  const local = getState();
  let changed = false;
  // schema 3 carries the whole state; schema 2 carried qstate/answers
  let rstate = null;
  if (remote.schema === SYNC_SCHEMA && remote.state) rstate = remote.state;
  else if (remote.qstate) { // legacy remote — convert
    const tmpOld = lsGet("qstate", null);
    lsSet("qstate", remote.qstate); lsSet("answers", remote.answers || {});
    rstate = migrateOrInit();
    if (tmpOld) lsSet("qstate", tmpOld); else localStorage.removeItem(LS_PREFIX + "qstate");
  }
  if (!rstate) return false;
  // cards: newer last_review (or due) wins
  for (const k in (rstate.cards || {})) {
    const r = rstate.cards[k], l = local.cards[k];
    if (!l) { local.cards[k] = r; changed = true; continue; }
    // Compare like with like. `due` is a FUTURE date, so letting it stand in for
    // a review timestamp let a never-reviewed local placeholder (due next month)
    // outrank a card genuinely reviewed yesterday on another device — silently
    // discarding the real review history.
    const llr = l.last_review || "", rlr = r.last_review || "";
    const takeRemote = (llr || rlr) ? (rlr > llr) : ((r.due || "") > (l.due || ""));
    if (takeRemote) { local.cards[k] = r; changed = true; }
  }
  // answers: keep non-empty / longer
  for (const k in (rstate.answers || {})) {
    const rv = rstate.answers[k];
    if (!local.answers[k] || (rv && rv.length > (local.answers[k] || "").length)) { if (rv !== local.answers[k]) { local.answers[k] = rv; changed = true; } }
  }
  // touchedDays: union — a lesson engaged on ANY device stays engaged.
  // Without this, touchedDays was never merged and got clobbered on push,
  // so the synced gist (and new devices) lost cross-device progress.
  if (rstate.touchedDays) {
    local.touchedDays = local.touchedDays || {};
    for (const d in rstate.touchedDays) {
      if (rstate.touchedDays[d] && !local.touchedDays[d]) { local.touchedDays[d] = true; changed = true; }
    }
  }
  // completedDays: union — a day fully finished on ANY device stays finished.
  if (rstate.completedDays) {
    local.completedDays = local.completedDays || {};
    for (const d in rstate.completedDays) {
      if (rstate.completedDays[d] && !local.completedDays[d]) { local.completedDays[d] = true; changed = true; }
    }
  }
  // log: union by cardId+ts
  const seen = new Set(local.log.map(l => l.cardId + "|" + l.ts));
  (rstate.log || []).forEach(l => { const key = l.cardId + "|" + l.ts; if (!seen.has(key)) { local.log.push(l); seen.add(key); changed = true; } });
  if (changed) { local.log.sort((a, b) => (a.ts || "").localeCompare(b.ts || "")); }
  // calibration: take the side with more total observations (whole-object)
  const ln = Object.values(local.calibration.byDomain || {}).reduce((s, d) => s + (d.n || 0), 0);
  const rn = Object.values((rstate.calibration && rstate.calibration.byDomain) || {}).reduce((s, d) => s + (d.n || 0), 0);
  if (rn > ln) { local.calibration = rstate.calibration; changed = true; }
  if (changed) saveState(local);
  return changed;
}

// ── TRANSPORT SWITCH ────────────────────────────────────────────────────────
// An account session wins; otherwise the original Gist transport runs unchanged.
async function syncPull(opts) {
  if (accountSession()) return await accountPull(opts);
  return await gistPull(opts);
}
async function syncPush(opts) {
  if (accountSession()) return await accountPush(opts);
  return await gistPush(opts);
}

// The Gist twin of _acctMerged: set only when this tab has genuinely read the
// remote file, so nothing pushes over a copy it has never seen.
let _gistPulled = false;
async function gistPull(opts) {
  if (!legacySyncEnabled()) return false;
  const token = getToken(), gist = getGistId();
  if (!token || !gist) return false;
  updateSyncButton("syncing", "Pulling…");
  try {
    const data = await gistFetch("GET", "/gists/" + gist, token);
    const file = data.files && data.files[SYNC_FILENAME];
    if (!file) { _gistPulled = true; updateSyncButton("enabled", "Synced"); return false; }
    let remote;
    if (file.truncated) { const r = await fetch(file.raw_url); remote = await r.json(); }
    else remote = JSON.parse(file.content);
    const changed = mergeRemote(remote);
    _gistPulled = true;
    lsSet(SYNC_KEYS.last_pull, new Date().toISOString());
    if (changed) { bootRender(); showToast("Pulled remote progress."); }
    updateSyncButton("enabled", "Synced");
    return changed;
  } catch (e) { updateSyncButton("error", "Pull failed"); if (!(opts && opts.silent)) showToast("Sync pull failed: " + e.message); return false; }
}

// After a pull LANDED: if this device holds work the cloud has not seen, send
// it. A pull alone leaves an offline session's reviews single-copy here until
// the athlete happens to grade again — lose the phone, lose the reviews. The
// read gate matters: syncPull resolves false for "nothing changed" AND for "the
// request failed", and a push over an unread remote is a clobber.
function syncCatchUpAfterPull() {
  try {
    if (!(accountSession() ? _acctMerged : _gistPulled)) return;
    const st = getState();
    const lastPush = lsGet(accountSession() ? SYNC_KEYS.acct_last_push : SYNC_KEYS.last_push, "");
    if (st && st.updated_at && (!lastPush || st.updated_at > lastPush)) scheduleSyncPush();
  } catch (e) {}
}

let _pushTimer = null;
function scheduleSyncPush() {
  if (!syncEnabled()) return;
  // A token we already know is dead would just 401 on a loop while the
  // athlete grades cards. Wait for a fresh sign-in instead.
  if (accountSession() && accountStale()) { updateSyncButton("error", "Sign in again"); return; }
  // A payload the server has already refused stays refused until it shrinks.
  // Retrying it on every grade just hides that sync has stopped.
  if (accountSession() && _acctTooLarge) { updateSyncButton("error", "Too large"); return; }
  clearTimeout(_pushTimer);
  updateSyncButton("syncing", "Pending…");
  _pushTimer = setTimeout(syncPush, 4000);
}
async function gistPush(opts) {
  if (!legacySyncEnabled()) return false;
  const token = getToken(), gist = getGistId();
  if (!token || !gist) return false;
  updateSyncButton("syncing", "Pushing…");
  try {
    await gistFetch("PATCH", "/gists/" + gist, token, { files: { [SYNC_FILENAME]: { content: JSON.stringify(buildSyncPayload(), null, 2) } } });
    lsSet(SYNC_KEYS.last_push, new Date().toISOString());
    updateSyncButton("enabled", "Synced");
    if (opts && opts.toast) showToast("Pushed to cloud");
    return true;
  } catch (e) { updateSyncButton("error", "Push failed"); if (!(opts && opts.silent)) showToast("Sync push failed: " + e.message); return false; }
}

// After an epoch hard-reset, NEVER blind-push the freshly wiped state: the
// gist may hold post-reset progress from other devices (the CSCS site lost
// 84 cards / 646 reviews exactly this way on 2026-07-20). Gate on the remote
// payload's own reset_epoch (see remoteIsPostEpoch): pre-epoch remote = stale,
// overwrite it; post-epoch = live progress, merge it in first. A pull-then-push would
// union the stale pre-reset cards back in, defeating the epoch wipe.
async function hardResetSyncReconcile() {
  try {
    // Same guard, account transport: read /study first, merge only a post-epoch
    // remote, then push. Never a blind push over newer remote progress — and
    // the read is REQUIRED, not merely attempted. Without it we cannot know
    // whether the cloud holds post-reset progress from another device, so a
    // failed read means push NOTHING and let the next boot reconcile. Delaying
    // the wipe's spread is the cheap failure; pushing a freshly wiped state
    // over live progress is the expensive one.
    if (accountSession()) {
      ensureStateOwner();
      let res = null;
      try { res = await studyFetch("GET", null); } catch (e) { res = null; }
      if (res && res.status === 401) { handleAccountUnauthorized(true); return; }
      if (res && res.status === 403) { handleAccountForbidden(true, (res.data && res.data.error) || ""); return; }
      if (!res || !res.ok || res.data.ok !== true) { _acctOutcome = "err"; updateSyncButton("error", "Sync paused"); return; }
      if (res.data.rev) setAcctRev(res.data.rev);
      else if (res.data.payload == null) setAcctRev("");
      const acctRemote = res.data.payload || null;
      if (acctRemote && remoteIsPostEpoch(acctRemote)) {
        mergeRemote(acctRemote);
        bootRender();
      }
      // We have read the cloud copy and deliberately decided what to keep of it,
      // so the push interlock is satisfied — but ONLY here and ONLY after that
      // read. accountPush must not re-pull, which would union the pre-epoch
      // cards straight back in and defeat the wipe.
      _acctMerged = true;
      await accountPush({ silent: true });
      return;
    }
    const token = getToken(), gist = getGistId();
    if (!token || !gist) return;
    let remote = null, readOk = false;
    try {
      const data = await gistFetch("GET", "/gists/" + gist, token);
      const file = data.files && data.files[SYNC_FILENAME];
      if (file) {
        if (file.truncated) { const r = await fetch(file.raw_url); remote = await r.json(); }
        else remote = JSON.parse(file.content);
      }
      readOk = true;           // the gist answered; a missing file genuinely means empty
    } catch (e) { remote = null; readOk = false; }
    if (!readOk) { updateSyncButton("error", "Sync paused"); return; }   // same rule: no read, no push
    if (remote && remoteIsPostEpoch(remote)) {
      mergeRemote(remote);
      bootRender();
    }
    await syncPush({ silent: true });
  } catch (e) {}
}
async function createNewGist() {
  const token = getToken();
  if (!token) throw new Error("No token");
  const data = await gistFetch("POST", "/gists", token, { description: "CSCS Study Progress (sync)", public: false, files: { [SYNC_FILENAME]: { content: JSON.stringify(buildSyncPayload(), null, 2) } } });
  return data.id;
}
async function findOrCreateSyncGist(token) {
  let page = 1;
  while (page <= 5) {
    const list = await gistFetch("GET", "/gists?per_page=100&page=" + page, token);
    if (!Array.isArray(list) || list.length === 0) break;
    for (const g of list) { if (g.files && g.files[SYNC_FILENAME]) return g.id; }
    if (list.length < 100) break;
    page++;
  }
  return await createNewGist();
}

// ── SIGN-IN UI (Google, mirroring the hub's gate) ───────────────────────────
let _gsiClientId = "", _gsiReady = false;

function studyLoadScript(src, onload, onerror) {
  const s = document.createElement("script");
  s.src = src; s.async = true; s.defer = true;
  if (onload) s.onload = onload;
  s.onerror = function () { if (onerror) onerror(); };
  document.head.appendChild(s);
}
function syncAccountNote(msg, cls) {
  const el = document.getElementById("sync-account-note");
  if (!el) return;
  el.className = "sync-status" + (cls ? " " + cls : "");
  el.textContent = msg || "";
  el.style.display = msg ? "" : "none";
}
function renderGsiButton() {
  const slot = document.getElementById("sync-gsi-slot");
  if (!slot) return;
  try {
    slot.innerHTML = "";
    google.accounts.id.renderButton(slot, { theme: "filled_black", size: "large", shape: "pill", text: "continue_with", width: 280 });
  } catch (e) { syncAccountNote("Google sign-in couldn't render here — use the GitHub token option below.", "err"); }
}
// Ask the worker which providers are live, then load Google Identity Services.
// A content blocker can kill that script outright, so onerror says so plainly
// instead of leaving a dead button on screen.
function setupGoogleSignIn() {
  const slot = document.getElementById("sync-gsi-slot");
  if (!slot) return;
  if (_gsiReady && window.google && google.accounts && google.accounts.id) { renderGsiButton(); return; }
  syncAccountNote("Loading sign-in…", "");
  fetch(STUDY_WORKER + "/auth/config")
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (cfg) {
      const cid = cfg && cfg.providers && cfg.providers.google;
      if (!cid) { syncAccountNote("Google sign-in isn't available right now — use the GitHub token option below.", "err"); return; }
      _gsiClientId = cid;
      studyLoadScript("https://accounts.google.com/gsi/client", function () {
        try {
          google.accounts.id.initialize({ client_id: _gsiClientId, callback: onGoogleCredential });
          _gsiReady = true;
          syncAccountNote("", "");
          renderGsiButton();
        } catch (e) {
          syncAccountNote("Google sign-in couldn't start on this device — use the GitHub token option below.", "err");
        }
      }, function () {
        syncAccountNote("Google's sign-in script was blocked here (a content blocker or network filter stops it). You can still sign in: open the Hybrid Crew gate at https://dsingson5.github.io/hybrid-crew/enter.html in THIS browser, sign in there, then reload this page — sync switches on by itself, because both sites share that session.", "err");
      });
    })
    .catch(function () { syncAccountNote("Can't reach sign-in right now. Check your connection and try again.", "err"); });
}
function onGoogleCredential(resp) {
  if (!resp || !resp.credential) return;
  syncAccountNote("Signing you in…", "");
  fetch(STUDY_WORKER + "/auth/oauth", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ provider: "google", credential: resp.credential })
  })
    .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { status: r.status, ok: r.ok, d: d }; }); })
    .then(function (res) {
      if (res.ok && res.d && res.d.token) { onAccountSignedIn(res.d.user, res.d.token); return; }
      if (res.status === 202) {
        const who = res.d && (res.d.name || res.d.email);
        syncAccountNote((who ? "Got it, " + who + " — " : "") +
          "Coach David approves every new member. Once he approves you, tap sign-in again and you're in.", "");
        return;
      }
      syncAccountNote(res.d && res.d.error ? res.d.error : "Sign-in failed.", "err");
    })
    .catch(function () { syncAccountNote("Can't reach sign-in right now. Check your connection and try again.", "err"); });
}
// Store the session exactly where the hub stores it (raw keys at the origin
// root) so one sign-in covers the hub and both study sites, then pull → merge
// → push so this device's work and the cloud's meet immediately.
function onAccountSignedIn(user, token) {
  try {
    localStorage.setItem("hcUser", user);
    sessionStorage.setItem("hcUser", user);
    localStorage.setItem("roxlive.session", token);
  } catch (e) {}
  markAccountStale(false);
  _acctRevokedMsg = "";
  _acctTooLarge = false;
  _acctMerged = false;          // new session: read the cloud copy before writing
  // A DIFFERENT athlete on this device: park their predecessor's state before a
  // single card of it can be merged into this account's cloud key. (Keeps the
  // rev when it is the same athlete signing back in.)
  ensureStateOwner();
  refreshSyncAccountUI();
  updateSyncButton("syncing", "Syncing…");
  accountPull({ silent: true })
    .then(function () {
      // accountPull resolves false for "nothing changed" AND for "the request
      // failed", so the merge flag — not the return value — decides. A failed
      // first pull must leave the cloud copy untouched.
      if (!_acctMerged) {
        updateSyncButton("error", "Sync paused");
        showToast("Signed in, but your cloud progress hasn't been read yet — nothing was uploaded. Tap Sync now when you're back online.");
        return false;
      }
      return accountPush({ silent: true });
    })
    .then(function (ok) {
      if (ok) showToast("Signed in — progress syncs on every device.");
      refreshSyncAccountUI();
    })
    .catch(function () {});
}
async function accountSignOut() {
  if (!confirm("Sign out?\n\nThese keys are shared across this whole site, so this signs you out of Hybrid Crew on this device too. Everything synced so far stays in the cloud.")) return;
  // Flush first. Anything graded since the last successful push exists on this
  // device only, and signing out throws away the token that could have sent it.
  if (accountSession() && !accountStale() && !_acctRevokedMsg) {
    updateSyncButton("syncing", "Saving…");
    const flushed = await accountPush({ silent: true });
    if (!flushed && !confirm("Couldn't upload your most recent progress just now.\n\nSign out anyway? Anything since the last sync stays on this device only.")) {
      refreshSyncAccountUI();
      return;
    }
  }
  try {
    localStorage.removeItem("hcUser");
    sessionStorage.removeItem("hcUser");
    localStorage.removeItem("roxlive.session");
  } catch (e) {}
  markAccountStale(false);
  _acctMerged = false;
  _acctTooLarge = false;
  _acctRevokedMsg = "";
  _acctOutcome = "";
  try { if (window.google && google.accounts && google.accounts.id) google.accounts.id.disableAutoSelect(); } catch (e) {}
  refreshSyncAccountUI();
  if (legacySyncEnabled()) updateSyncButton("enabled", "Synced");
  else updateSyncButton("off", "Cloud sync off");
  showToast("Signed out on this device.");
}
// Built with DOM calls, not innerHTML — the user name is untrusted text.
function refreshSyncAccountUI() {
  const box = document.getElementById("sync-account-box");
  if (!box) return;
  box.innerHTML = "";
  const s = accountSession();
  const stale = accountStale();
  const note = document.createElement("div");
  note.id = "sync-account-note";
  note.className = "sync-status";
  note.style.marginTop = "10px";
  note.style.display = "none";
  // Revoked is terminal: signing in again succeeds and then fails here, so the
  // "sign in again" affordance would only send them round the loop.
  const showSignInAgain = stale && !_acctRevokedMsg;
  if (s) {
    const who = document.createElement("p");
    who.style.cssText = "margin:0 0 4px;font-size:13px;";
    who.appendChild(document.createTextNode("Signed in as "));
    const b = document.createElement("b");
    b.textContent = s.user;
    who.appendChild(b);
    box.appendChild(who);
    const sub = document.createElement("p");
    sub.style.cssText = "margin:0 0 12px;font-size:12px;";
    sub.textContent = _acctRevokedMsg
      ? _acctRevokedMsg
      : stale
        ? "Your sign-in expired. Sign in again to start syncing."
        : _acctOutcome === "err"
          ? "Signed in, but the last sync didn't go through — your progress is safe on this device. Tap Sync now to retry."
          : "Your progress syncs automatically on every device you sign in on — nothing to set up.";
    box.appendChild(sub);
    const row = document.createElement("div");
    row.className = "sync-actions";
    row.style.marginTop = "0";
    const now = document.createElement("button");
    now.type = "button"; now.className = "btn-primary"; now.textContent = "Sync now";
    now.onclick = function () { forceSyncNow(); };
    const out = document.createElement("button");
    out.type = "button"; out.textContent = "Sign out";
    out.onclick = accountSignOut;
    row.appendChild(now); row.appendChild(out);
    box.appendChild(row);
    if (showSignInAgain) {
      const slot = document.createElement("div");
      slot.id = "sync-gsi-slot";
      slot.style.cssText = "margin-top:12px;min-height:44px;";
      box.appendChild(slot);
    }
    box.appendChild(note);
    if (showSignInAgain) setupGoogleSignIn();
  } else {
    const p = document.createElement("p");
    p.style.cssText = "margin:0 0 10px;font-size:13px;";
    p.textContent = "Sign in with the same account you use on Hybrid Crew and your progress follows you to every device. Nothing to paste, nothing to set up.";
    box.appendChild(p);
    const slot = document.createElement("div");
    slot.id = "sync-gsi-slot";
    slot.style.cssText = "min-height:44px;";
    box.appendChild(slot);
    box.appendChild(note);
    setupGoogleSignIn();
  }
}

function openSyncModal() {
  const m = document.getElementById("sync-modal");
  if (!m) return;
  document.getElementById("sync-token-input").value = getToken();
  document.getElementById("sync-gist-input").value = getGistId();
  // Read the stamps of the transport actually in use: the shared keys showed an
  // ancient GitHub-token push as though it were the account's last sync.
  const acct = !!accountSession();
  const last = lsGet(acct ? SYNC_KEYS.acct_last_push : SYNC_KEYS.last_push, null);
  const lastPull = lsGet(acct ? SYNC_KEYS.acct_last_pull : SYNC_KEYS.last_pull, null);
  const label = acct ? "Signed-in sync" : "GitHub-token sync";   // constants, safe for innerHTML
  const status = document.getElementById("sync-modal-status");
  if (acct && _acctRevokedMsg) { status.className = "sync-status err"; status.textContent = _acctRevokedMsg; }
  else if (acct && accountStale()) { status.className = "sync-status err"; status.textContent = "Sign-in expired — sign in again above to resume syncing."; }
  else if (syncEnabled() && last) { status.className = "sync-status ok"; status.innerHTML = label + " enabled. Last push: " + new Date(last).toLocaleString() + (lastPull ? "<br>Last pull: " + new Date(lastPull).toLocaleString() : ""); }
  else if (acct) { status.className = "sync-status ok"; status.textContent = "Signed in — syncing automatically."; }
  else { status.className = "sync-status"; status.textContent = "Sync not yet configured."; }
  // GIS renders into a visible box, so show the modal before building it.
  m.classList.add("shown");
  refreshSyncAccountUI();
}
function closeSyncModal() { document.getElementById("sync-modal").classList.remove("shown"); }
function disableSync() {
  lsSet(SYNC_KEYS.enabled, false);
  const status = document.getElementById("sync-modal-status");
  status.className = "sync-status";
  if (accountSession()) {
    updateSyncButton("enabled", "Synced");
    status.textContent = "GitHub-token sync disabled. You are still signed in, so your account keeps syncing — use Sign out to stop that too.";
  } else {
    updateSyncButton("off", "Off");
    status.textContent = "Sync disabled. Token and Gist ID kept; re-enable any time.";
  }
  showToast("Sync disabled");
}
// The one place the athlete explicitly asks for a sync: clear the size latch and
// try again — but still only push if the pull actually landed.
async function forceSyncNow() {
  _acctTooLarge = false;
  const acct = !!accountSession();
  await syncPull();
  if (acct && !_acctMerged) {
    updateSyncButton("error", "Sync paused");
    showToast("Couldn't read your cloud progress — nothing was uploaded. Try again when you're back online.");
    return;
  }
  await syncPush({ toast: true });
}
function updateSyncButton(state, text) {
  const btn = document.getElementById("sync-button");
  if (!btn) return;
  btn.className = "sync-button " + (state === "off" ? "" : state);
  btn.querySelector(".sync-text").textContent = text;
}
async function applySyncSettings() {
  const token = document.getElementById("sync-token-input").value.trim();
  const gistInput = document.getElementById("sync-gist-input");
  const gist = gistInput.value.trim();
  const status = document.getElementById("sync-modal-status");
  if (!token) { status.className = "sync-status err"; status.textContent = "Token required."; return; }
  setToken(token);
  status.className = "sync-status"; status.textContent = "Looking for your sync Gist…";
  try {
    let resolved = gist;
    if (!resolved) { resolved = await findOrCreateSyncGist(token); gistInput.value = resolved; }
    else { await gistFetch("GET", "/gists/" + resolved, token); }
    setGistId(resolved);
    lsSet(SYNC_KEYS.enabled, true);
    status.className = "sync-status ok"; status.textContent = "Found / created your sync Gist. Pulling latest…";
    updateSyncButton("enabled", "Synced");
    // Explicitly the Gist path — don't let the account transport hijack the
    // very settings the athlete just came here to configure.
    await gistPull({ silent: true });
    await gistPush({ toast: true });
    status.className = "sync-status ok";
    status.innerHTML = "Sync active. On other devices, paste the same token — they'll find this Gist automatically.";
  } catch (e) { status.className = "sync-status err"; status.textContent = "Failed: " + e.message; }
}

function injectSyncUI() {
  const btn = document.createElement("button");
  btn.id = "sync-button";
  btn.className = "sync-button " + (syncEnabled() ? "enabled" : "");
  btn.innerHTML = '<span class="sync-dot"></span><span class="sync-text">' + (syncEnabled() ? "Sync" : "Cloud sync off") + "</span>";
  btn.onclick = openSyncModal;
  document.body.appendChild(btn);
  const modal = document.createElement("div");
  modal.id = "sync-modal"; modal.className = "sync-modal";
  modal.innerHTML =
    '<div class="sync-modal-content"><h3>Cross-device sync</h3>' +
    '<div id="sync-account-box"></div>' +
    '<details id="sync-advanced" style="margin-top:16px;">' +
    '<summary style="cursor:pointer;font-size:12px;color:var(--text-dim);">Advanced: sync with a GitHub token instead</summary>' +
    '<p style="margin-top:10px;">Sync your FSRS progress across devices via a <b>private GitHub Gist</b>. Free, no external service.</p>' +
    '<ol><li>Generate a Personal Access Token (classic) with <b>only the gist scope</b>: <a href="https://github.com/settings/tokens/new?scopes=gist&description=CSCS%20Study%20Sync" target="_blank" rel="noopener">open GitHub →</a></li>' +
    '<li>Paste it below.</li><li>Each device with the same token finds the same Gist automatically.</li></ol>' +
    '<label>Personal Access Token (gist scope only)<input type="password" id="sync-token-input" autocomplete="off" placeholder="ghp_…"></label>' +
    '<label>Gist ID (optional — auto-discovered)<input type="text" id="sync-gist-input" autocomplete="off" placeholder="leave blank — auto-discovered"></label>' +
    '<div class="sync-actions"><button type="button" class="btn-primary" onclick="applySyncSettings()">Enable / Update</button>' +
    '<button type="button" onclick="forceSyncNow()">Sync now</button><button type="button" onclick="disableSync()">Disable</button></div>' +
    '</details>' +
    '<div class="sync-actions"><button type="button" onclick="closeSyncModal()" style="margin-left:auto;">Close</button></div>' +
    '<div id="sync-modal-status" class="sync-status">Sync not yet configured.</div></div>';
  modal.addEventListener("click", e => { if (e.target === modal) closeSyncModal(); });
  document.body.appendChild(modal);
}

document.addEventListener("DOMContentLoaded", () => {
  injectSyncUI();
  // The landing page's resume redirect owns this document and already has its
  // own /study read in flight; it is about to replace the page. Booting a
  // SECOND remote pull here doubles worker load for a page nobody will read.
  // The lesson page we land on runs this block normally a moment later.
  if (typeof window !== "undefined" && window.__RESUME_REDIRECTING) return;
  // A known-dead token: say so on the button and wait for a fresh sign-in
  // rather than firing a request that can only 401.
  if (accountSession() && accountStale()) updateSyncButton("error", "Sign in again");
  else if (syncEnabled()) {
    if (__didHardReset) hardResetSyncReconcile().catch(() => {});
    else syncPull({ silent: true }).then(syncCatchUpAfterPull).catch(() => {});
  }
  else updateSyncButton("off", "Cloud sync off");
  // Reconnecting is the natural moment to send what couldn't go out while the
  // connection was down — read first, as everywhere else.
  window.addEventListener("online", function () {
    if (syncEnabled()) syncPull({ silent: true }).then(syncCatchUpAfterPull).catch(() => {});
  });
});

// ════════════════════════════════════════════════════════════════════════════
//   TERM POPOVERS — hover any glossary term to see its definition.
// ════════════════════════════════════════════════════════════════════════════
(function () {
  function collectTerms() {
    const map = {};
    document.querySelectorAll(".gloss-card").forEach(card => {
      const term = card.querySelector(".gloss-term");
      const def = card.querySelector(".gloss-def");
      if (term && def) {
        const t = term.textContent.trim(), d = def.textContent.trim();
        map[t] = d;
        const noParens = t.replace(/\s*\([^)]*\)/, "").trim();
        if (noParens && noParens !== t) map[noParens] = d;
      }
    });
    return map;
  }
  function wrapTermsIn(el, terms) {
    if (!el) return;
    const keys = Object.keys(terms).sort((a, b) => b.length - a.length);
    if (keys.length === 0) return;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode: node => {
        if (!node.nodeValue || node.nodeValue.trim().length < 3) return NodeFilter.FILTER_REJECT;
        if (node.parentElement && node.parentElement.closest(".term-pop, .gloss-card")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const targets = []; let n;
    while ((n = walker.nextNode())) targets.push(n);
    targets.forEach(node => {
      let text = node.nodeValue, changed = false;
      for (const k of keys) {
        const re = new RegExp("(\\b)(" + k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(\\b)", "i");
        if (re.test(text)) { text = text.replace(re, '$1<span class="term-pop" data-term="' + k + '">$2</span>$3'); changed = true; break; }
      }
      if (changed) { const span = document.createElement("span"); span.innerHTML = text; node.parentNode.replaceChild(span, node); }
    });
  }
  function setupPopovers() {
    let card = document.querySelector(".term-card-overlay");
    if (!card) { card = document.createElement("div"); card.className = "term-card-overlay"; card.innerHTML = '<div class="tc-term"></div><div class="tc-def"></div>'; document.body.appendChild(card); }
    let active = null;
    function place(t) {
      const def = window.__CSCS_TERMS && window.__CSCS_TERMS[t.dataset.term];
      if (!def) return false;
      card.querySelector(".tc-term").textContent = t.textContent;
      card.querySelector(".tc-def").textContent = def;
      const r = t.getBoundingClientRect(), w = 300;
      let left = r.left + r.width / 2 - w / 2, top = r.top - card.offsetHeight - 10;
      if (left < 8) left = 8;
      if (left + w > window.innerWidth - 8) left = window.innerWidth - w - 8;
      if (top < 8) top = r.bottom + 10;
      card.style.left = left + "px"; card.style.top = top + "px"; card.style.width = w + "px";
      card.classList.add("shown"); return true;
    }
    document.body.addEventListener("mouseover", e => { const t = e.target.closest(".term-pop"); if (!t) return; active = t; place(t); });
    document.body.addEventListener("mouseout", e => { if (e.target.closest(".term-pop")) { card.classList.remove("shown"); active = null; } });
    document.body.addEventListener("click", e => {
      const t = e.target.closest(".term-pop");
      if (!t) { card.classList.remove("shown"); return; }
      if (active === t && card.classList.contains("shown")) { card.classList.remove("shown"); active = null; return; }
      active = t; place(t);
    });
  }
  document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
      window.__CSCS_TERMS = collectTerms();
      document.querySelectorAll(".concept, .training-link p, .facts li").forEach(el => wrapTermsIn(el, window.__CSCS_TERMS));
      setupPopovers();
    }, 100);
  });
})();

/* 5E-FIGBOX — lightbox for extracted 5th-edition figures & tables */
(function(){
  function ensureBox(){
    var b=document.getElementById("cscs-figbox");
    if(b) return b;
    b=document.createElement("div"); b.id="cscs-figbox"; b.className="figbox";
    b.innerHTML='<span class="fb-hint">Esc or tap to close</span>'+
      '<button class="fb-x" aria-label="Close" type="button">\u00d7</button>'+
      '<img alt=""><div class="fb-cap"></div>';
    document.body.appendChild(b);
    b.addEventListener("click", function(e){ if(e.target===b||e.target.classList.contains("fb-x")) closeFig(); });
    return b;
  }
  window.openFig=function(src,cap){
    var b=ensureBox();
    b.querySelector("img").src=src;
    b.querySelector(".fb-cap").textContent=cap||"";
    b.classList.add("open"); document.body.style.overflow="hidden";
  };
  window.closeFig=function(){
    var b=document.getElementById("cscs-figbox");
    if(b){ b.classList.remove("open"); b.querySelector("img").src=""; }
    document.body.style.overflow="";
  };
  document.addEventListener("keydown", function(e){ if(e.key==="Escape") closeFig(); });
  document.addEventListener("click", function(e){
    var t=e.target.closest(".fig-thumb"); if(t) window.openFig(t.dataset.full, t.dataset.cap);
  });
  document.addEventListener("keydown", function(e){
    if((e.key==="Enter"||e.key===" ")&&document.activeElement&&document.activeElement.classList.contains("fig-thumb")){
      e.preventDefault(); var t=document.activeElement; window.openFig(t.dataset.full,t.dataset.cap);
    }
  });
})();

/* ===== study-voice v2 — listen buttons (device + neural AI voices) and
   NotebookLM helpers. Synced copies in hyrox_study/app.js and
   cscs_study/app.js — keep both in step.
   Engines: device Web Speech (free, no setup) · Gemini TTS (free API key,
   realistic) · ElevenLabs (paid key, most realistic). Keys live only in this
   browser's localStorage. NotebookLM has no public API, so those buttons
   prepare copy-paste material. ===== */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;

  var CFG = {
    prefKey: "cscs.tts.v1",
    keyKey: "cscs.tts.keys.v1",
    siteName: "CSCS exam-prep study site",
    exam: "NSCA CSCS exam",
    palette: "iron-black, gunmetal-grey and blood-red barbell-club palette",
    action: "barbell lifting, sprinting and jumping",
    applyterm: "training-floor application"
  };

  function onReady(fn) {
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  onReady(function () {
    if (!document.querySelector(".lesson-card") && !document.querySelector(".q")) return;

    var synth = window.speechSynthesis || null;

    // ── prefs + keys ─────────────────────────────────────────────────────
    var prefs = { accent: "gb", rate: 1, answers: "revealed", engine: "device",
                  voiceName: "", geminiVoice: "Charon", elevenVoice: "", min: false };
    var keys = { gemini: "", eleven: "", elevenGb: "", elevenUs: "", geminiModel: "" };
    try {
      var raw = localStorage.getItem(CFG.prefKey);
      if (raw) { var p = JSON.parse(raw); for (var k in prefs) if (p[k] !== undefined) prefs[k] = p[k]; }
      var rawk = localStorage.getItem(CFG.keyKey);
      if (rawk) { var kk = JSON.parse(rawk); for (var k2 in keys) if (kk[k2] !== undefined) keys[k2] = kk[k2]; }
    } catch (e) {}
    function savePrefs() { try { localStorage.setItem(CFG.prefKey, JSON.stringify(prefs)); } catch (e) {} }
    function saveKeys() { try { localStorage.setItem(CFG.keyKey, JSON.stringify(keys)); } catch (e) {} }

    // ── device voices ────────────────────────────────────────────────────
    // Desktop names (Edge naturals, Windows SAPI, Apple) PLUS Android's
    // Google-TTS variant codes: Android exposes e.g. "en-gb-x-gbb-local",
    // and the locale-default voice there is female — which is exactly the
    // Galaxy-tablet bug this list fixes.
    var GB_MALE = ["ryan", "thomas", "george", "daniel", "arthur", "oliver",
      "google uk english male", "brian",
      "en-gb-x-gbb", "en-gb-x-gbd", "en-gb-x-rjs"];
    var US_MALE = ["andrew", "guy", "christopher", "roger", "eric", "davis",
      "microsoft david", "microsoft mark", "alex", "aaron",
      "en-us-x-iob", "en-us-x-iom", "en-us-x-tpd"];
    var FEMALE_HINTS = /female|zira|hazel|susan|sonia|libby|aria|jenny|michelle|emma|ava|salli|joanna|kate|serena|martha|karen|moira|tessa|samantha|victoria|en-gb-x-gba|en-gb-x-gbc|en-us-x-sfg|en-us-x-tpc|en-us-x-tpf|en-us-x-iog|en-us-x-iol|google us english(?!\s+male)|google uk english female/i;
    var MALE_HINTS = /\bmale\b|ryan|thomas|george|daniel|arthur|oliver|aaron|alex\b|guy|andrew|christopher|roger|eric|davis|david|mark\b|brian|james|william|en-gb-x-gbb|en-gb-x-gbd|en-gb-x-rjs|en-us-x-iob|en-us-x-iom|en-us-x-tpd/i;

    function voiceScore(v, accent) {
      var name = (v.name || "").toLowerCase();
      var lang = (v.lang || "").toLowerCase().replace("_", "-");
      var probe = name + " " + (v.voiceURI || "").toLowerCase();
      var want = accent === "gb" ? "en-gb" : "en-us";
      var list = accent === "gb" ? GB_MALE : US_MALE;
      var s = 0;
      if (lang === want) s += 60;
      else if (lang.indexOf("en") === 0) s += 15;
      else return -1;
      for (var i = 0; i < list.length; i++)
        if (probe.indexOf(list[i]) >= 0) { s += 220 - i * 10; break; }
      if (/natural|online/.test(name)) s += 25;
      if (MALE_HINTS.test(probe)) s += 20;
      if (FEMALE_HINTS.test(probe)) s -= 60;
      return s;
    }

    function genderTag(v) {
      var probe = ((v.name || "") + " " + (v.voiceURI || "")).toLowerCase();
      if (FEMALE_HINTS.test(probe)) return "\u2640 ";
      if (MALE_HINTS.test(probe)) return "\u2642 ";
      return "";
    }

    function englishVoices() {
      var out = [];
      if (!synth) return out;
      var vs = synth.getVoices() || [];
      for (var i = 0; i < vs.length; i++)
        if ((vs[i].lang || "").toLowerCase().indexOf("en") === 0) out.push(vs[i]);
      return out;
    }

    function pickDeviceVoice() {
      var vs = englishVoices();
      if (!vs.length) return null;
      if (prefs.voiceName)
        for (var i = 0; i < vs.length; i++)
          if (vs[i].name === prefs.voiceName) return vs[i];
      var best = null, bestScore = -1;
      for (var j = 0; j < vs.length; j++) {
        var sc = voiceScore(vs[j], prefs.accent);
        if (sc > bestScore) { bestScore = sc; best = vs[j]; }
      }
      return best;
    }

    // ── neural voice catalogues ──────────────────────────────────────────
    var GEM_VOICES = [
      ["Charon", "Charon — deep, informative (recommended)"],
      ["Algenib", "Algenib — gravelly"],
      ["Gacrux", "Gacrux — mature"],
      ["Alnilam", "Alnilam — firm"],
      ["Sadaltager", "Sadaltager — knowledgeable"],
      ["Iapetus", "Iapetus — clear"],
      ["Schedar", "Schedar — even"],
      ["Enceladus", "Enceladus — breathy"],
      ["Puck", "Puck — upbeat"]
    ];
    var GEM_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-flash-tts",
                      "gemini-2.5-pro-preview-tts"];
    var ELEVEN_VOICES = [
      ["onwK4e9ZLuTAKqWW03F9", "Daniel — British, deep (GB default)"],
      ["JBFqnCBsd6RMkjVDRZzb", "George — British, warm"],
      ["nPczCjzI2devNBz1zQrb", "Brian — American, deep (US default)"],
      ["pqHfZKP75CvOlQylNhV4", "Bill — American, documentary"]
    ];
    function elevenVoiceId() {
      if (prefs.elevenVoice) return prefs.elevenVoice;
      if (prefs.accent === "gb") return keys.elevenGb || "onwK4e9ZLuTAKqWW03F9";
      return keys.elevenUs || "nPczCjzI2devNBz1zQrb";
    }
    function geminiStyle() {
      return prefs.accent === "gb"
        ? "Read the following aloud in a deep, measured BRITISH natural-history documentary narration - calm, warm, unhurried, with quiet awe. Do not add, skip or change any words.\n\n"
        : "Read the following aloud as a clear, confident AMERICAN male narrator - natural pacing, engaging but calm. Do not add, skip or change any words.\n\n";
    }

    // ── shared playback state ────────────────────────────────────────────
    var gen = 0, speaking = false, paused = false, currentEl = null;
    var queue = [], qi = 0;                    // device engine
    var rBatches = [], rIdx = 0;               // remote engines
    var audioEl = null;
    var cache = {}; var cacheCount = 0;        // text -> object URL

    function getAudioEl() {
      if (!audioEl) {
        audioEl = document.createElement("audio");
        audioEl.style.display = "none";
        document.body.appendChild(audioEl);
      }
      return audioEl;
    }

    function clearHighlight() {
      if (currentEl) { currentEl.classList.remove("sv-now"); currentEl = null; }
    }
    function highlight(el) {
      clearHighlight();
      if (el) {
        currentEl = el;
        el.classList.add("sv-now");
        try { el.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (e) {}
      }
    }
    function setStatus(msg) {
      var s = panel && panel.querySelector(".sv-status");
      if (s) s.textContent = msg || "";
    }

    function stopAll() {
      gen++;
      speaking = false; paused = false;
      queue = []; qi = 0; rBatches = []; rIdx = 0;
      if (synth) try { synth.cancel(); } catch (e) {}
      if (audioEl) { try { audioEl.pause(); audioEl.removeAttribute("src"); } catch (e) {} }
      clearHighlight(); setStatus(""); updatePanel();
    }

    function togglePause() {
      if (!speaking) return;
      if (prefs.engine === "device") {
        if (!synth) return;
        if (paused) { synth.resume(); paused = false; }
        else { synth.pause(); paused = true; }
      } else {
        var a = getAudioEl();
        if (paused) { a.play(); paused = false; }
        else { a.pause(); paused = true; }
      }
      updatePanel();
    }

    // ── device engine ────────────────────────────────────────────────────
    function chunkDevice(text) {
      var parts = text.match(/[^.!?\u2026]+[.!?\u2026]*\s*/g) || [text];
      var out = [], cur = "";
      for (var i = 0; i < parts.length; i++) {
        if ((cur + parts[i]).length > 220 && cur) { out.push(cur); cur = ""; }
        cur += parts[i];
      }
      if (cur.replace(/\s/g, "")) out.push(cur);
      return out;
    }

    function speakNextDevice() {
      if (!synth || qi >= queue.length) { stopAll(); return; }
      var item = queue[qi];
      var u = new SpeechSynthesisUtterance(item.text);
      var myGen = gen, fired = false;
      var v = pickDeviceVoice();
      if (v) { u.voice = v; u.lang = v.lang; }
      u.rate = prefs.rate;
      u.pitch = prefs.accent === "gb" ? 0.92 : 1.0;
      u.onend = u.onerror = function () {
        if (fired || myGen !== gen) return; fired = true;
        qi++; if (speaking) speakNextDevice();
      };
      highlight(item.el);
      synth.speak(u);
    }

    function playDevice(items) {
      if (!synth) { toast("Speech isn't available in this browser."); return; }
      queue = [];
      for (var i = 0; i < items.length; i++) {
        var chunks = chunkDevice(items[i].text);
        for (var c = 0; c < chunks.length; c++)
          queue.push({ text: chunks[c], el: items[i].el });
      }
      if (!queue.length) { toast("Nothing to read here yet."); return; }
      qi = 0; speaking = true; paused = false; updatePanel();
      setTimeout(speakNextDevice, 80);
    }

    setInterval(function () {
      if (synth && speaking && !paused && prefs.engine === "device" && synth.speaking) {
        try { synth.resume(); } catch (e) {}
      }
    }, 10000);

    if (synth && typeof synth.addEventListener === "function")
      synth.addEventListener("voiceschanged", function () { fillVoiceSelect(); });

    // ── remote engines: fetch + wav + playback ───────────────────────────
    function b64ToBytes(b64) {
      var bin = atob(b64), len = bin.length, bytes = new Uint8Array(len);
      for (var i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
      return bytes;
    }
    // Gemini returns raw 16-bit PCM @24 kHz mono — wrap a WAV header on it.
    function pcmToWavUrl(bytes, rate) {
      var h = new ArrayBuffer(44), d = new DataView(h);
      function ws(o, s) { for (var i = 0; i < s.length; i++) d.setUint8(o + i, s.charCodeAt(i)); }
      ws(0, "RIFF"); d.setUint32(4, 36 + bytes.length, true); ws(8, "WAVE");
      ws(12, "fmt "); d.setUint32(16, 16, true); d.setUint16(20, 1, true);
      d.setUint16(22, 1, true); d.setUint32(24, rate, true);
      d.setUint32(28, rate * 2, true); d.setUint16(32, 2, true);
      d.setUint16(34, 16, true); ws(36, "data"); d.setUint32(40, bytes.length, true);
      return URL.createObjectURL(new Blob([h, bytes], { type: "audio/wav" }));
    }

    function cachePut(key, url) {
      if (cacheCount > 80) {
        for (var k in cache) { try { URL.revokeObjectURL(cache[k]); } catch (e) {} }
        cache = {}; cacheCount = 0;
      }
      cache[key] = url; cacheCount++;
    }

    function fetchGemini(text) {
      var key = keys.gemini;
      var models = keys.geminiModel ? [keys.geminiModel] : GEM_MODELS.slice();
      var body = JSON.stringify({
        contents: [{ parts: [{ text: geminiStyle() + text }] }],
        generationConfig: {
          responseModalities: ["AUDIO"],
          speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: prefs.geminiVoice || "Charon" } } }
        }
      });
      function tryModel(i) {
        if (i >= models.length) return Promise.reject(new Error("No Gemini TTS model responded — the model name may have changed."));
        return fetch("https://generativelanguage.googleapis.com/v1beta/models/" +
            models[i] + ":generateContent", {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": key },
          body: body
        }).then(function (res) {
          if (res.status === 404) return tryModel(i + 1);
          if (!res.ok) return res.text().then(function (t) {
            var msg = "Gemini error " + res.status;
            try { msg += ": " + (JSON.parse(t).error.message || "").slice(0, 140); } catch (e) {}
            throw new Error(msg);
          });
          if (!keys.geminiModel) { keys.geminiModel = models[i]; saveKeys(); }
          return res.json().then(function (j) {
            var parts = (((j.candidates || [])[0] || {}).content || {}).parts || [];
            var chunks = [], total = 0;
            for (var p = 0; p < parts.length; p++)
              if (parts[p].inlineData && parts[p].inlineData.data) {
                var u8 = b64ToBytes(parts[p].inlineData.data);
                chunks.push(u8); total += u8.length;
              }
            if (!total) throw new Error("Gemini returned no audio (quota or safety block).");
            var bytes = new Uint8Array(total), off = 0;
            for (var c = 0; c < chunks.length; c++) { bytes.set(chunks[c], off); off += chunks[c].length; }
            return pcmToWavUrl(bytes, 24000);
          });
        });
      }
      return tryModel(0);
    }

    function fetchEleven(text) {
      return fetch("https://api.elevenlabs.io/v1/text-to-speech/" + elevenVoiceId() +
          "?output_format=mp3_44100_128", {
        method: "POST",
        headers: { "Content-Type": "application/json", "xi-api-key": keys.eleven },
        body: JSON.stringify({ text: text, model_id: "eleven_turbo_v2_5" })
      }).then(function (res) {
        if (!res.ok) return res.text().then(function (t) {
          var msg = "ElevenLabs error " + res.status;
          try { msg += ": " + (JSON.parse(t).detail.message || JSON.parse(t).detail.status || "").slice(0, 140); } catch (e) {}
          throw new Error(msg + (res.status === 401 ? " (check your API key)" : ""));
        });
        return res.blob().then(function (b) { return URL.createObjectURL(b); });
      });
    }

    function remoteKeyFor(text) {
      var v = prefs.engine === "gemini" ? (prefs.geminiVoice + prefs.accent) : elevenVoiceId();
      return prefs.engine + "|" + v + "|" + text;
    }
    function ensureAudio(i) {
      var b = rBatches[i];
      if (!b) return Promise.resolve(null);
      var ck = remoteKeyFor(b.text);
      if (cache[ck]) return Promise.resolve(cache[ck]);
      if (!b.pending)
        b.pending = (prefs.engine === "gemini" ? fetchGemini(b.text) : fetchEleven(b.text))
          .then(function (url) { cachePut(ck, url); b.pending = null; return url; });
      return b.pending;
    }

    // Merge portions into ~2200-char requests (fewer API calls, smoother audio).
    function buildBatches(items) {
      var out = [], curText = "", curEl = null;
      for (var i = 0; i < items.length; i++) {
        var t = items[i].text;
        if (curText && (curText.length + t.length) > 2200) {
          out.push({ text: curText, el: curEl }); curText = ""; curEl = null;
        }
        if (!curEl) curEl = items[i].el;
        curText += (curText ? "\n\n" : "") + t;
        // very long single portions: flush in sentence-safe slices
        while (curText.length > 2600) {
          var cut = curText.lastIndexOf(". ", 2200);
          if (cut < 400) cut = 2200;
          out.push({ text: curText.slice(0, cut + 1), el: curEl });
          curText = curText.slice(cut + 1); curEl = items[i].el;
        }
      }
      if (curText) out.push({ text: curText, el: curEl });
      return out;
    }

    function playRemoteIdx(i) {
      var myGen = gen;
      if (i >= rBatches.length) { stopAll(); return; }
      rIdx = i;
      highlight(rBatches[i].el);
      setStatus("fetching audio\u2026");
      ensureAudio(i).then(function (url) {
        if (myGen !== gen || !url) return;
        setStatus("");
        var a = getAudioEl();
        a.src = url;
        a.playbackRate = prefs.rate;
        try { a.preservesPitch = true; a.webkitPreservesPitch = true; } catch (e) {}
        a.onended = function () { if (myGen === gen) playRemoteIdx(i + 1); };
        a.onerror = function () { if (myGen === gen) { toast("Audio playback failed."); stopAll(); } };
        if (!paused) {
          var pr = a.play();
          if (pr && pr.catch) pr.catch(function () {
            if (myGen !== gen) return;
            toast("Tap again to allow audio playback.");
            stopAll();
          });
        }
        ensureAudio(i + 1).then(null, function () {}); // prefetch; error surfaces on play
      }).catch(function (err) {
        if (myGen !== gen) return;
        toast(String(err && err.message || err).slice(0, 160));
        stopAll();
      });
    }

    function playRemote(items) {
      var need = prefs.engine === "gemini" ? keys.gemini : keys.eleven;
      if (!need) { openKeyModal(prefs.engine); return; }
      rBatches = buildBatches(items);
      if (!rBatches.length) { toast("Nothing to read here yet."); return; }
      speaking = true; paused = false; updatePanel();
      playRemoteIdx(0);
    }

    function playItems(items) {
      stopAll();
      if (prefs.engine === "device") playDevice(items);
      else playRemote(items);
    }

    // ── text extraction ──────────────────────────────────────────────────
    function txt(el) { return el ? el.textContent.replace(/\s+/g, " ").trim() : ""; }

    function lessonItems(card) {
      var items = [];
      var h = card.querySelector("h2");
      if (h) items.push({ text: txt(h) + ".", el: h });
      var concept = card.querySelector(".concept");
      if (concept) items.push({ text: "Key concept. " + txt(concept), el: concept });
      var facts = card.querySelectorAll(".facts li");
      if (facts.length) {
        items.push({ text: "Key facts.", el: card.querySelector(".facts-title") });
        for (var i = 0; i < facts.length; i++)
          items.push({ text: "Fact " + (i + 1) + ". " + txt(facts[i]), el: facts[i] });
      }
      var gloss = card.querySelectorAll(".gloss-card");
      if (gloss.length) {
        items.push({ text: "Glossary.", el: card.querySelector(".gloss-title") });
        for (var g = 0; g < gloss.length; g++) {
          var term = txt(gloss[g].querySelector(".gloss-term"));
          var def = txt(gloss[g].querySelector(".gloss-def"));
          items.push({ text: term + ". " + def, el: gloss[g] });
        }
      }
      var tl = card.querySelector(".training-link");
      if (tl) items.push({ text: "Connection to your training. " +
        txt(tl).replace(/^Connection to your training\s*/i, ""), el: tl });
      return items;
    }

    function qItems(q, forceAnswers) {
      var items = [];
      var body = txt(q.querySelector(".q-text"));
      var label = txt(q.querySelector(".q-num")) || "Question";
      if (body) items.push({ text: label + ". " + body, el: q });
      var revealed = q.querySelector(".q-reveal.shown");
      var include = forceAnswers === true ||
        (forceAnswers !== false && (prefs.answers === "always" || revealed));
      if (include) {
        var a = txt(q.querySelector(".reveal-body"));
        if (a) items.push({ text: "Answer. " + a, el: q.querySelector(".reveal-body") || q });
      }
      return items;
    }

    function blockItems(section) {
      var items = [];
      var h = section.querySelector("h3");
      if (h) items.push({ text: txt(h) + ".", el: h });
      var qs = section.querySelectorAll(".q");
      for (var i = 0; i < qs.length; i++) items = items.concat(qItems(qs[i]));
      return items;
    }

    function pageItems() {
      var items = [];
      var secs = document.querySelectorAll(
        "section.lesson-card, section.question-block, section.pretest-section");
      for (var i = 0; i < secs.length; i++) {
        var s = secs[i];
        if (s.classList.contains("lesson-card")) items = items.concat(lessonItems(s));
        else items = items.concat(blockItems(s));
      }
      return items;
    }

    function sourceText() {
      var lines = [CFG.siteName, "Page: " + document.title,
                   "URL: " + location.href, ""];
      var cards = document.querySelectorAll("section.lesson-card");
      for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        lines.push("## " + txt(c.querySelector("h2")));
        var con = txt(c.querySelector(".concept"));
        if (con) lines.push("Key concept: " + con);
        var facts = c.querySelectorAll(".facts li");
        for (var f = 0; f < facts.length; f++) lines.push("- " + txt(facts[f]));
        var gloss = c.querySelectorAll(".gloss-card");
        for (var g = 0; g < gloss.length; g++)
          lines.push("Glossary — " + txt(gloss[g].querySelector(".gloss-term")) +
                     ": " + txt(gloss[g].querySelector(".gloss-def")));
        var tl = txt(c.querySelector(".training-link"));
        if (tl) lines.push(tl);
        lines.push("");
      }
      var qs = document.querySelectorAll(".q");
      if (qs.length) lines.push("## Practice questions");
      for (var q = 0; q < qs.length; q++) {
        lines.push("Q: " + txt(qs[q].querySelector(".q-text")));
        lines.push("A: " + txt(qs[q].querySelector(".reveal-body")));
      }
      return lines.join("\n");
    }

    function topicTitle() {
      var h = document.querySelector("section.lesson-card h2");
      return h ? txt(h) : document.title;
    }

    // ── NotebookLM ───────────────────────────────────────────────────────
    function nlmPrompt(mode) {
      var t = topicTitle();
      if (mode === "video")
        return 'Create a cinematic Video Overview of "' + t + '". Style: ' +
          "high-production natural-history documentary — measured, authoritative " +
          "British narration; slow, dramatic pacing; sweeping establishing shots; " +
          "moody arena lighting; slow-motion close-ups of athletes " + CFG.action + ". " +
          "Structure: a cold open that frames the core tension of the topic, then one " +
          "visual scene per key fact, closing with a single " + CFG.applyterm + ". " +
          "Keep every number and claim exactly as stated in the source. Audience: a " +
          "coach preparing for the " + CFG.exam + ".";
      if (mode === "podcast")
        return 'Make a LONG deep-dive Audio Overview of "' + t + '" — aim for 30+ ' +
          "minutes. Two hosts. Work through EVERY key fact and EVERY practice " +
          "question in the source: read each question aloud, pause so the listener " +
          "can attempt it, discuss the reasoning and common exam traps, then give " +
          "the model answer. Finish with a rapid-fire recap quiz of the whole " +
          "lesson. Keep every number and claim faithful to the source. Audience: a " +
          "coach preparing for the " + CFG.exam + ".";
      return 'Create a detailed infographic of "' + t + '". Art direction: kawaii ' +
        "chibi illustration style fused with a masculine " + CFG.palette + " — " +
        "cute big-eyed chibi athletes mid-" + CFG.action + ", each glowing with " +
        "superpower auras, crackling lightning and energy effects; bold heavy " +
        "typography on a dark background. Content: the lesson title as a hero " +
        "banner, every key fact as its own labelled panel with a chibi icon, " +
        "glossary terms as a labelled icon strip, and one '" + CFG.applyterm + "' " +
        "callout. Dense but readable; keep every number exactly as in the source.";
    }

    var NLM_LABEL = { video: "cinematic video", podcast: "deep-dive podcast", infographic: "infographic" };
    var NLM_TOOL = {
      video: "Video Overview",
      podcast: "Audio Overview (choose the longer / Deep Dive option)",
      infographic: "Infographic"
    };

    // ── clipboard + toast ────────────────────────────────────────────────
    function copyText(s, btn, okLabel) {
      function done(ok) {
        if (btn) {
          var old = btn.getAttribute("data-label") || btn.textContent;
          btn.setAttribute("data-label", old);
          btn.textContent = ok ? (okLabel || "Copied \u2713") : "Copy failed";
          setTimeout(function () { btn.textContent = btn.getAttribute("data-label"); }, 1600);
        }
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(s).then(function () { done(true); },
          function () { done(legacyCopy(s)); });
      } else done(legacyCopy(s));
    }
    function legacyCopy(s) {
      try {
        var ta = document.createElement("textarea");
        ta.value = s; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        var ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return ok;
      } catch (e) { return false; }
    }
    function toast(msg) {
      if (typeof showToast === "function") { showToast(msg); return; }
      var t = document.createElement("div");
      t.className = "sv-toast"; t.textContent = msg;
      document.body.appendChild(t);
      setTimeout(function () { t.classList.add("on"); }, 10);
      setTimeout(function () { t.classList.remove("on");
        setTimeout(function () { t.remove(); }, 300); }, 2600);
    }

    // ── UI: floating panel ───────────────────────────────────────────────
    var panel, btnPause, voiceSel, engineSel;

    function mkBtn(label, title, cls, fn) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "sv-btn " + (cls || "");
      b.textContent = label; b.title = title || "";
      b.addEventListener("click", fn);
      return b;
    }

    function audition() {
      playItems([{ text: "Here's how this voice sounds. Fast feet into the next station.", el: null }]);
    }

    function fillVoiceSelect() {
      if (!voiceSel) return;
      voiceSel.innerHTML = "";
      function opt(val, label) {
        var o = document.createElement("option");
        o.value = val; o.textContent = label; voiceSel.appendChild(o);
      }
      if (prefs.engine === "device") {
        var vs = englishVoices();
        var ranked = vs.map(function (v) { return { v: v, s: voiceScore(v, prefs.accent) }; })
          .filter(function (x) { return x.s >= 0; })
          .sort(function (a, b) { return b.s - a.s; });
        opt("", "Voice: automatic (best male match)");
        for (var i = 0; i < ranked.length; i++) {
          var v = ranked[i].v;
          opt(v.name, genderTag(v) + v.name.replace(/^Microsoft /, "").replace(/ - English.*$/, ""));
        }
        voiceSel.value = prefs.voiceName || "";
      } else if (prefs.engine === "gemini") {
        for (var g = 0; g < GEM_VOICES.length; g++) opt(GEM_VOICES[g][0], GEM_VOICES[g][1]);
        voiceSel.value = prefs.geminiVoice || "Charon";
      } else {
        for (var e = 0; e < ELEVEN_VOICES.length; e++) opt(ELEVEN_VOICES[e][0], ELEVEN_VOICES[e][1]);
        opt("__custom__", "Custom voice ID\u2026 (set in \uD83D\uDD11 Key)");
        voiceSel.value = prefs.elevenVoice || elevenVoiceId();
      }
    }

    function updatePanel() {
      if (!panel) return;
      btnPause.textContent = paused ? "\u25B6 Resume" : "\u23F8 Pause";
      btnPause.disabled = !speaking;
      var stopB = panel.querySelector(".sv-stop");
      if (stopB) stopB.disabled = !speaking;
      var gb = panel.querySelector('[data-accent="gb"]');
      var us = panel.querySelector('[data-accent="us"]');
      if (gb) gb.classList.toggle("on", prefs.accent === "gb");
      if (us) us.classList.toggle("on", prefs.accent === "us");
      var rateB = panel.querySelector(".sv-rate");
      if (rateB) rateB.textContent = prefs.rate.toFixed(2).replace(/0+$/, "").replace(/\.$/, "") + "\u00D7";
      var keyB = panel.querySelector(".sv-keybtn");
      if (keyB) keyB.style.display = prefs.engine === "device" ? "none" : "";
    }

    function buildPanel() {
      panel = document.createElement("div");
      panel.className = "sv-panel";
      panel.setAttribute("role", "region");
      panel.setAttribute("aria-label", "Listen and NotebookLM tools");

      var row1 = document.createElement("div"); row1.className = "sv-row";
      row1.appendChild(mkBtn("\uD83D\uDD0A Listen to page", "Read the whole lesson aloud", "sv-main",
        function () { playItems(pageItems()); }));
      btnPause = mkBtn("\u23F8 Pause", "Pause / resume", "", togglePause);
      row1.appendChild(btnPause);
      row1.appendChild(mkBtn("\u23F9", "Stop", "sv-stop", stopAll));
      var status = document.createElement("span");
      status.className = "sv-status";
      row1.appendChild(status);

      var row2 = document.createElement("div"); row2.className = "sv-row";
      var gb = mkBtn("\uD83C\uDDEC\uD83C\uDDE7 British", "Deep British male — documentary style", "sv-seg",
        function () { prefs.accent = "gb"; prefs.voiceName = ""; prefs.elevenVoice = "";
          savePrefs(); fillVoiceSelect(); updatePanel(); audition(); });
      gb.setAttribute("data-accent", "gb");
      var us = mkBtn("\uD83C\uDDFA\uD83C\uDDF8 American", "American male voice", "sv-seg",
        function () { prefs.accent = "us"; prefs.voiceName = ""; prefs.elevenVoice = "";
          savePrefs(); fillVoiceSelect(); updatePanel(); audition(); });
      us.setAttribute("data-accent", "us");
      var rate = mkBtn("1\u00D7", "Reading speed", "sv-rate", function () {
        var steps = [0.85, 1, 1.15, 1.3];
        prefs.rate = steps[(steps.indexOf(prefs.rate) + 1) % steps.length] || 1;
        savePrefs(); updatePanel();
        if (speaking && prefs.engine !== "device" && audioEl) audioEl.playbackRate = prefs.rate;
      });
      row2.appendChild(gb); row2.appendChild(us); row2.appendChild(rate);

      var row3 = document.createElement("div"); row3.className = "sv-row";
      engineSel = document.createElement("select");
      engineSel.className = "sv-select";
      engineSel.title = "Voice engine";
      [["device", "Engine: device voices (free)"],
       ["gemini", "Engine: Gemini AI voice (free key)"],
       ["eleven", "Engine: ElevenLabs (best, paid key)"]].forEach(function (o) {
        var op = document.createElement("option");
        op.value = o[0]; op.textContent = o[1]; engineSel.appendChild(op);
      });
      engineSel.value = prefs.engine;
      engineSel.addEventListener("change", function () {
        stopAll();
        prefs.engine = engineSel.value; savePrefs(); fillVoiceSelect(); updatePanel();
        var need = prefs.engine === "gemini" ? keys.gemini :
                   prefs.engine === "eleven" ? keys.eleven : "ok";
        if (!need) openKeyModal(prefs.engine); else if (prefs.engine !== "device") audition();
      });
      var keyBtn = mkBtn("\uD83D\uDD11 Key", "Set / change the API key for this engine", "sv-keybtn",
        function () { openKeyModal(prefs.engine); });
      row3.appendChild(engineSel); row3.appendChild(keyBtn);

      var row4 = document.createElement("div"); row4.className = "sv-row";
      voiceSel = document.createElement("select");
      voiceSel.className = "sv-select sv-voice";
      voiceSel.title = "Voice";
      voiceSel.addEventListener("change", function () {
        if (prefs.engine === "device") prefs.voiceName = voiceSel.value;
        else if (prefs.engine === "gemini") prefs.geminiVoice = voiceSel.value;
        else if (voiceSel.value !== "__custom__") prefs.elevenVoice = voiceSel.value;
        savePrefs(); audition();
      });
      var ansSel = document.createElement("select");
      ansSel.className = "sv-select";
      ansSel.title = "Whether question answers are read aloud";
      [["revealed", "Answers: revealed only"], ["always", "Answers: always read"]]
        .forEach(function (o) {
          var op = document.createElement("option");
          op.value = o[0]; op.textContent = o[1]; ansSel.appendChild(op);
        });
      ansSel.value = prefs.answers;
      ansSel.addEventListener("change", function () {
        prefs.answers = ansSel.value; savePrefs();
      });
      row4.appendChild(voiceSel); row4.appendChild(ansSel);

      var row5 = document.createElement("div"); row5.className = "sv-row";
      var lab = document.createElement("span");
      lab.className = "sv-lab"; lab.textContent = "NotebookLM:";
      row5.appendChild(lab);
      row5.appendChild(mkBtn("\uD83C\uDFAC Video", "Prepare a cinematic NotebookLM Video Overview", "",
        function () { openNlm("video"); }));
      row5.appendChild(mkBtn("\uD83C\uDF99\uFE0F Podcast", "Prepare a long NotebookLM Deep Dive podcast", "",
        function () { openNlm("podcast"); }));
      row5.appendChild(mkBtn("\uD83D\uDCCA Infographic", "Prepare a kawaii-powers NotebookLM infographic", "",
        function () { openNlm("infographic"); }));

      panel.appendChild(row1); panel.appendChild(row2); panel.appendChild(row3);
      panel.appendChild(row4); panel.appendChild(row5);
      function setMin(v) {
        prefs.min = !!v; savePrefs();
        panel.classList.toggle("sv-min", prefs.min);
      }
      var minB = mkBtn("\u2212", "Minimise \u2014 tuck this panel into a small button", "sv-minb",
        function (ev) { ev.stopPropagation(); setMin(true); });
      var chip = document.createElement("button");
      chip.type = "button"; chip.className = "sv-minchip";
      chip.title = "Open Listen & NotebookLM tools";
      chip.setAttribute("aria-label", "Open Listen and NotebookLM tools");
      chip.textContent = "\uD83D\uDD0A";
      chip.addEventListener("click", function () { setMin(false); });
      panel.appendChild(minB); panel.appendChild(chip);
      document.body.appendChild(panel);
      panel.classList.toggle("sv-min", !!prefs.min);
      fillVoiceSelect(); updatePanel();
    }

    // ── UI: key modal ────────────────────────────────────────────────────
    function overlay() {
      var old = document.querySelector(".sv-overlay");
      if (old) old.remove();
      var ov = document.createElement("div");
      ov.className = "sv-overlay";
      ov.addEventListener("click", function (e) { if (e.target === ov) ov.remove(); });
      return ov;
    }

    function openKeyModal(engine) {
      var ov = overlay();
      var d = document.createElement("div");
      d.className = "sv-dialog";
      var isG = engine === "gemini";
      var h = document.createElement("h3");
      h.textContent = isG ? "Gemini AI voice — free API key" : "ElevenLabs — API key";
      var note = document.createElement("p");
      note.className = "sv-note";
      note.innerHTML = isG
        ? "Much more natural than device voices. Get a <b>free</b> key at " +
          "<a href='https://aistudio.google.com/apikey' target='_blank' rel='noopener'>aistudio.google.com/apikey</a> " +
          "(Google account, no card). Free tier has daily limits — plenty for lessons. " +
          "The key is stored only in this browser."
        : "The most realistic voices available. Get a key at " +
          "<a href='https://elevenlabs.io' target='_blank' rel='noopener'>elevenlabs.io</a> " +
          "(free tier \u2248 10 min/month, paid from $5/mo). " +
          "The key is stored only in this browser.";
      var inp = document.createElement("input");
      inp.type = "password"; inp.className = "sv-key-input";
      inp.setAttribute("autocomplete", "new-password");
      inp.setAttribute("name", "tts-api-key");
      inp.placeholder = isG ? "Paste Gemini API key (AIza\u2026)" : "Paste ElevenLabs API key";
      inp.value = isG ? keys.gemini : keys.eleven;
      d.appendChild(h); d.appendChild(note); d.appendChild(inp);

      var cGb, cUs;
      if (!isG) {
        var small = document.createElement("p");
        small.className = "sv-note";
        small.textContent = "Optional: custom voice IDs (from your ElevenLabs voice library).";
        cGb = document.createElement("input");
        cGb.className = "sv-key-input"; cGb.placeholder = "Custom British voice ID (optional)";
        cGb.value = keys.elevenGb;
        cUs = document.createElement("input");
        cUs.className = "sv-key-input"; cUs.placeholder = "Custom American voice ID (optional)";
        cUs.value = keys.elevenUs;
        d.appendChild(small); d.appendChild(cGb); d.appendChild(cUs);
      }

      var foot = document.createElement("div");
      foot.className = "sv-row sv-foot";
      foot.appendChild(mkBtn("Save & test", "", "sv-main", function () {
        if (isG) { keys.gemini = inp.value.trim(); keys.geminiModel = ""; }
        else {
          keys.eleven = inp.value.trim();
          keys.elevenGb = cGb.value.trim(); keys.elevenUs = cUs.value.trim();
        }
        saveKeys(); ov.remove();
        if (inp.value.trim()) audition(); else toast("Key cleared.");
      }));
      foot.appendChild(mkBtn("Cancel", "", "", function () { ov.remove(); }));
      d.appendChild(foot);
      ov.appendChild(d);
      document.body.appendChild(ov);
      inp.focus();
    }

    // ── UI: NotebookLM modal ─────────────────────────────────────────────
    function openNlm(mode) {
      var ov = overlay();
      var d = document.createElement("div");
      d.className = "sv-dialog";
      var h = document.createElement("h3");
      h.textContent = "Create " + (/^[aeiou]/i.test(NLM_LABEL[mode]) ? "an " : "a ") +
        NLM_LABEL[mode] + " with NotebookLM";
      var note = document.createElement("p");
      note.className = "sv-note";
      note.textContent = "NotebookLM has no public API, so this can't run by itself — " +
        "but everything is prepared below. Three pastes and you're done.";

      var ol = document.createElement("ol");
      ol.className = "sv-steps";
      var li1 = document.createElement("li");
      li1.appendChild(document.createTextNode("Copy this lesson as source material: "));
      li1.appendChild(mkBtn("Copy lesson text", "", "sv-small",
        function () { copyText(sourceText(), this); }));
      li1.appendChild(document.createTextNode(" or "));
      li1.appendChild(mkBtn("Copy page link", "", "sv-small",
        function () { copyText(location.href, this); }));
      var li2 = document.createElement("li");
      li2.textContent = "In NotebookLM: New notebook \u2192 Add source \u2192 \u201CCopied text\u201D " +
        "(paste the lesson) — or \u201CWebsite\u201D (paste the link).";
      var li3 = document.createElement("li");
      li3.appendChild(document.createTextNode("Open " + NLM_TOOL[mode] +
        " \u2192 Customise, and paste the tailored prompt: "));
      li3.appendChild(mkBtn("Copy " + NLM_LABEL[mode] + " prompt", "", "sv-small sv-primary",
        function () { copyText(nlmPrompt(mode), this); }));
      ol.appendChild(li1); ol.appendChild(li2); ol.appendChild(li3);

      var foot = document.createElement("div");
      foot.className = "sv-row sv-foot";
      foot.appendChild(mkBtn("Open NotebookLM \u2197", "notebooklm.google.com", "sv-main",
        function () { window.open("https://notebooklm.google.com/", "_blank", "noopener"); }));
      foot.appendChild(mkBtn("Close", "", "", function () { ov.remove(); }));

      d.appendChild(h); d.appendChild(note); d.appendChild(ol); d.appendChild(foot);
      ov.appendChild(d);
      document.body.appendChild(ov);
    }

    // ── UI: per-section buttons (idempotent — safe to re-run) ────────────
    function mini(title, fn) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "sv-mini"; b.textContent = "\uD83D\uDD0A";
      b.title = title;
      b.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
      return b;
    }

    function injectButtons() {
      document.querySelectorAll("section.lesson-card").forEach(function (card) {
        var head = card.querySelector(".lesson-head");
        if (head && !head.querySelector(".sv-chip")) {
          var b = document.createElement("button");
          b.type = "button"; b.className = "sv-mini sv-chip";
          b.textContent = "\uD83D\uDD0A Listen to this lesson";
          b.addEventListener("click", function () { playItems(lessonItems(card)); });
          head.appendChild(b);
        }
        var concept = card.querySelector(".concept");
        if (concept && !concept.querySelector(".sv-mini")) concept.insertBefore(
          mini("Read the key concept", function () {
            playItems([{ text: "Key concept. " + txt(concept), el: concept }]);
          }), concept.firstChild);
        var ft = card.querySelector(".facts-title");
        if (ft && !ft.querySelector(".sv-mini")) ft.appendChild(mini("Read the key facts", function () {
          var items = [{ text: "Key facts.", el: ft }];
          card.querySelectorAll(".facts li").forEach(function (li, i) {
            items.push({ text: "Fact " + (i + 1) + ". " + txt(li), el: li });
          });
          playItems(items);
        }));
        var gt = card.querySelector(".gloss-title");
        if (gt && !gt.querySelector(".sv-mini")) gt.appendChild(mini("Read the glossary", function () {
          var items = [{ text: "Glossary.", el: gt }];
          card.querySelectorAll(".gloss-card").forEach(function (gc) {
            items.push({ text: txt(gc.querySelector(".gloss-term")) + ". " +
              txt(gc.querySelector(".gloss-def")), el: gc });
          });
          playItems(items);
        }));
        var tl = card.querySelector(".training-link");
        if (tl && !tl.querySelector(".sv-mini")) tl.insertBefore(mini("Read the training connection", function () {
          playItems([{ text: "Connection to your training. " +
            txt(tl).replace(/^Connection to your training\s*/i, ""), el: tl }]);
        }), tl.firstChild);
      });

      document.querySelectorAll("section.question-block, section.pretest-section")
        .forEach(function (sec) {
          var h = sec.querySelector("h3");
          if (h && !h.querySelector(".sv-mini")) h.appendChild(mini("Read this whole practice block",
            function () { playItems(blockItems(sec)); }));
        });

      document.querySelectorAll(".q .q-head").forEach(function (head) {
        var q = head.closest(".q");
        if (!q || head.querySelector(".sv-mini")) return;
        head.appendChild(mini("Read this question (answer once revealed)",
          function () { playItems(qItems(q)); }));
      });
    }

    buildPanel();
    injectButtons();
    // Review-queue cards render late (async FSRS module) and the container is
    // rebuilt after every grade — re-inject when that happens.
    var rq = document.getElementById("personal-reviews");
    if (rq && typeof MutationObserver === "function")
      new MutationObserver(function () { injectButtons(); })
        .observe(rq, { childList: true });
  });
})();
/* ===== end study-voice v2 ===== */

/* ===== study-anim v1 — glossary-icon animator (synced: hyrox/cscs).
   Entrance draw-in for static icons; viewport + reduced-motion pausing for
   SMIL icons. ===== */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;
  function onReady(fn) {
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }
  onReady(function () {
    var svgs = Array.prototype.slice.call(
      document.querySelectorAll(".gloss-svg svg"));
    if (!svgs.length) return;

    var reduced = false;
    try {
      reduced = window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (e) {}

    function hasSmil(svg) {
      return !!svg.querySelector("animate,animateTransform,animateMotion");
    }
    function pauseSmil(svg) { try { svg.pauseAnimations(); } catch (e) {} }
    function playSmil(svg) { try { svg.unpauseAnimations(); } catch (e) {} }

    // SMIL autostarts — hold everything until it is actually looked at.
    svgs.forEach(function (s) { if (hasSmil(s)) pauseSmil(s); });
    if (reduced) return; // paused stays paused; no entrances; CSS handles the rest

    var visible = []; // SMIL svgs currently in view (for visibilitychange)

    function entrance(svg) {
      var shapes = svg.querySelectorAll("path,line,polyline,circle,rect,ellipse");
      var di = 0, pi = 0;
      Array.prototype.forEach.call(shapes, function (el) {
        var stroke = el.getAttribute("stroke");
        var fill = el.getAttribute("fill");
        if (stroke && stroke !== "none") {
          if (el.getAttribute("stroke-dasharray")) {
            el.classList.add("sva-flow"); // dashed = a flow: march, don't draw
            return;
          }
          var L = 0;
          try { L = el.getTotalLength(); } catch (e) { return; }
          if (!L || !isFinite(L)) return;
          el.style.strokeDasharray = L + " " + L;
          el.style.strokeDashoffset = L;
          el.style.transition = "stroke-dashoffset 0.8s ease-out " + (di * 0.12) + "s";
          di++;
          requestAnimationFrame(function () {
            requestAnimationFrame(function () { el.style.strokeDashoffset = "0"; });
          });
          el.addEventListener("transitionend", function te() {
            el.style.strokeDasharray = "";
            el.style.strokeDashoffset = "";
            el.style.transition = "";
            el.removeEventListener("transitionend", te);
          });
        } else if (fill && fill !== "none") {
          el.classList.add("sva-pop");
          el.style.animationDelay = (pi * 0.09) + "s";
          pi++;
        }
      });
    }

    var seen = typeof WeakSet === "function" ? new WeakSet() : null;
    function markSeen(s) { if (seen) seen.add(s); else s.__svaSeen = true; }
    function wasSeen(s) { return seen ? seen.has(s) : !!s.__svaSeen; }

    if (typeof IntersectionObserver !== "function") {
      // Old browser: just let SMIL run and skip entrances.
      svgs.forEach(function (s) { if (hasSmil(s)) playSmil(s); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var svg = en.target;
        var smil = hasSmil(svg);
        if (en.isIntersecting) {
          if (smil) {
            playSmil(svg);
            if (visible.indexOf(svg) < 0) visible.push(svg);
          } else if (!wasSeen(svg)) {
            markSeen(svg);
            entrance(svg);
          }
        } else if (smil) {
          pauseSmil(svg);
          var ix = visible.indexOf(svg);
          if (ix >= 0) visible.splice(ix, 1);
        }
      });
    }, { threshold: 0.15 });
    svgs.forEach(function (s) { io.observe(s); });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden)
        svgs.forEach(function (s) { if (hasSmil(s)) pauseSmil(s); });
      else
        visible.forEach(playSmil);
    });
  });
})();
/* ===== end study-anim v1 ===== */

/* ===== study-offline v1.1 — sw registration + offline pack (synced: hyrox/cscs).
   Registers sw.js (scope = site root) and adds an "Offline: Download all"
   row to the study-voice panel: fetches data/pages.json and stores every
   page in the sw's cache so the whole site works with no connection.
   v1.1: the sw serves pages cache-first, so after a redeploy a packed device
   keeps showing its stored copies. data/build.json carries the stamp of the
   deployed build and we remember the stamp the pack was downloaded against;
   when the two differ the row says so ("Update offline copy" / "new lessons
   available") instead of letting him study stale lessons for days. Advisory
   only — it NEVER wipes the cache: a stale pack still beats no pack. ===== */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof document === "undefined") return;
  if (!("serviceWorker" in navigator) || !window.caches) return;
  var path = location.pathname;
  var di = path.indexOf("/daily/");
  var base = di >= 0 ? path.slice(0, di + 1) : path.replace(/[^\/]*$/, "");
  var siteKey = base.replace(/[^a-z0-9]/gi, "") || "root";
  var CACHE = "svoff-" + siteKey + "-v1";
  var LSK = "svoff." + siteKey + ".packed";
  var LSB = "svoff." + siteKey + ".build"; /* build stamp the stored pack matches */
  var DL_LABEL = "\uD83D\uDCE5 Download all";
  var DL_TITLE = "Store every lesson on this device so the whole site works with no connection";
  var UP_LABEL = "\u21BB Update offline copy";
  var UP_TITLE = "New lessons were published after this device stored its copy";

  try { navigator.serviceWorker.register(base + "sw.js").catch(function () {}); } catch (e) {}

  /* Stamp of the build that is deployed right now. no-store so the sw hands it
     straight to the network (see sw.js) — a cached copy could otherwise vouch
     for the very pack we are questioning. ANY failure (offline, blocked, file
     missing, junk JSON) resolves to "" and every caller then does nothing: no
     warning shown, nothing stored, and never anything evicted. */
  function liveBuild() {
    try {
      return fetch(base + "data/build.json", { cache: "no-store" })
        .then(function (r) { if (!r.ok) throw new Error("build"); return r.json(); })
        .then(function (b) { return b && b.built ? String(b.built) : ""; })
        .catch(function () { return ""; });
    } catch (e) { return Promise.resolve(""); }
  }
  function savedBuild() {
    try { return localStorage.getItem(LSB) || ""; } catch (e) { return ""; }
  }

  function onReady(fn) {
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }
  onReady(function () {
    var panel = document.querySelector(".sv-panel");
    if (!panel || panel.querySelector(".sv-offbtn")) return;
    var row = document.createElement("div"); row.className = "sv-row";
    var lab = document.createElement("span"); lab.className = "sv-lab";
    lab.textContent = "Offline:";
    var btn = document.createElement("button"); btn.type = "button";
    btn.className = "sv-btn sv-offbtn";
    btn.textContent = DL_LABEL;
    btn.title = DL_TITLE;
    var st = document.createElement("span"); st.className = "sv-status";
    row.appendChild(lab); row.appendChild(btn); row.appendChild(st);
    var chip = panel.querySelector(".sv-minchip");
    panel.insertBefore(row, chip || null);

    /* trust the CACHE, not the stamp — iOS can evict the pack while
       localStorage survives, and a lying checkmark strands the user offline. */
    caches.open(CACHE).then(function (c) { return c.keys(); }).then(function (ks) {
      if (ks.length) {
        st.textContent = "\u2713 " + ks.length + " stored on this device";
        /* A real pack is here — is it still the deployed build? An unrecorded
           stamp counts as behind: that copy was stored before this check
           existed, so nothing can vouch for it. */
        liveBuild().then(function (v) {
          if (!v || v === savedBuild()) return;
          btn.textContent = UP_LABEL;
          btn.title = UP_TITLE;
          st.textContent = "new lessons available";
        });
        return;
      }
      try {
        var p = JSON.parse(localStorage.getItem(LSK) || "null");
        if (p && p.n) st.textContent = "stored copy missing \u2014 download again";
      } catch (e) {}
    }).catch(function () {});

    var busy = false;
    btn.addEventListener("click", function () {
      if (busy) return;
      busy = true; btn.disabled = true; st.textContent = "listing\u2026";
      fetch(base + "data/pages.json", { cache: "no-store" })
        .then(function (r) { if (!r.ok) throw new Error("list"); return r.json(); })
        .then(function (list) {
          if (!list || !list.length) throw new Error("empty");
          return caches.open(CACHE).then(function (cache) {
            var done = 0, fail = 0, total = list.length;
            /* One dropped request out of ~364 on mobile data used to cost the
               build stamp permanently: the stamp is written only after a clean
               sweep, so a single miss left the row reading "new lessons
               available" on every load until a flawless run happened. Sweep
               once, then retry ONLY the entries that failed before giving up. */
            function sweep(items, isRetry) {
              var idx = 0, missed = [];
              function one() {
                if (idx >= items.length) return Promise.resolve();
                var u = base + items[idx++];
                return fetch(u, { cache: "no-store" }).then(function (r) {
                  if (r && r.ok && !r.redirected) {
                    var k = new URL(u, location.href).href.split("#")[0].split("?")[0];
                    return cache.put(k, r).then(function () { done++; });
                  }
                  fail++; missed.push(u.slice(base.length));
                }).catch(function () {
                  fail++; missed.push(u.slice(base.length));
                }).then(function () {
                  var n = done + fail;
                  if (n % 5 === 0 || n === total)
                    st.textContent = (isRetry ? "retrying \u00B7 " : "") + n + " / " + total +
                      (fail ? " \u00B7 " + fail + " failed" : "");
                  return one();
                });
              }
              var lanes = [];
              for (var w = 0; w < 5; w++) lanes.push(one());
              return Promise.all(lanes).then(function () { return missed; });
            }
            st.textContent = "0 / " + total;
            return sweep(list, false).then(function (missed) {
              if (!missed.length) return null;
              fail = 0;              /* the retry pass decides these ones */
              return sweep(missed, true);
            }).then(function () {
              try {
                localStorage.setItem(LSK, JSON.stringify({ n: done, at: new Date().toISOString() }));
              } catch (e) {}
              try {
                if (navigator.storage && navigator.storage.persist)
                  navigator.storage.persist().catch(function () {});
              } catch (e) {}
              st.textContent = fail
                ? "\u2713 " + done + " stored \u00B7 " + fail + " failed \u2014 tap again to retry"
                : "\u2713 " + done + " pages \u2014 this device now works offline";
              /* Only a clean sweep may claim the pack matches this build; with
                 pages still missing after the retry, the update prompt honestly
                 stays up. Fired and forgotten — it must never hold up the
                 button. */
              if (!fail && done) {
                liveBuild().then(function (v) {
                  if (!v) return;
                  try { localStorage.setItem(LSB, v); } catch (e) {}
                  btn.textContent = DL_LABEL;
                  btn.title = DL_TITLE;
                });
              }
            });
          });
        })
        .catch(function () { st.textContent = "couldn't fetch the page list \u2014 are you online?"; })
        .then(function () { busy = false; btn.disabled = false; });
    });
  });
})();
/* ===== end study-offline v1.1 ===== */
