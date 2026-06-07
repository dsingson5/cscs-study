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
  return s;
}
function saveState(s) { s.updated_at = new Date().toISOString(); lsSet(STATE_KEY, s); }

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
  // Mark THIS page's date as touched so the resume-mode redirect knows we've
  // engaged with this lesson, regardless of when (Manila-time) we did it.
  try {
    var pageDate = (typeof window !== 'undefined' && window.__CSCS_PAGE_DATE) ? window.__CSCS_PAGE_DATE : null;
    if (pageDate) { s.touchedDays = s.touchedDays || {}; s.touchedDays[pageDate] = true; }
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
    note.textContent = grade === 1
      ? "Back in ~10 min. That's the point — forgetting is where the learning happens."
      : "Next review in " + (nextDays < 1 ? "today" : nextDays + " day" + (nextDays === 1 ? "" : "s")) + ".";
    note.classList.add("shown");
  }
  root.classList.add("rated");
  updateHeaderStats();
  renderDashboard();
  buildReviewQueue();
  if (typeof scheduleSyncPush === "function") scheduleSyncPush();
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
    '<span class="q-status" data-status-for="' + qid + '"></span>' + '<span class="q-last" data-last-for="' + qid + '" data-stable="' + escapeHtml(d.stable) + '"></span></div>' +
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
  var nowD = manilaDate(new Date());
  var thenD = manilaDate(when);
  var nowT = nowD ? new Date(nowD + "T00:00:00").getTime() : NaN;
  var thenT = thenD ? new Date(thenD + "T00:00:00").getTime() : NaN;
  var dayDiff = (!isNaN(nowT) && !isNaN(thenT)) ? Math.round((nowT - thenT) / 86400000) : null;
  var hhmm = "";
  try {
    hhmm = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Manila",
      hour: "numeric", minute: "2-digit" }).format(when);
  } catch (e) {}
  if (dayDiff === 0) return "Last answered today" + (hhmm ? " at " + hhmm : "");
  if (dayDiff === 1) return "Last answered yesterday";
  if (dayDiff && dayDiff > 1 && dayDiff <= 7) return "Last answered " + dayDiff + " days ago";
  if (thenD) {
    try {
      var nice = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Manila",
        month: "short", day: "numeric" }).format(when);
      return "Last answered " + nice;
    } catch (e) { return "Last answered " + thenD; }
  }
  return "";
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

function bootRender() {
  if (!speechSupported()) { try { document.documentElement.classList.add("no-speech"); } catch (e) {} }
  updateHeaderStats();
  renderDashboard();
  buildReviewQueue();
  hydrateLastAnswered();
  hydrateLessonNav();
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
const SYNC_KEYS = { token: "sync.token", gist: "sync.gist_id", enabled: "sync.enabled", last_push: "sync.last_push_at", last_pull: "sync.last_pull_at" };
const SYNC_FILENAME = "cscs-progress.json";
const SYNC_SCHEMA = 3;

function syncEnabled() { return !!lsGet(SYNC_KEYS.enabled, false); }
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
  if (!res.ok) { const text = await res.text(); throw new Error("GitHub API " + res.status + ": " + text.slice(0, 200)); }
  return res.status === 204 ? null : res.json();
}

function buildSyncPayload() { return { schema: SYNC_SCHEMA, updated_at: new Date().toISOString(), state: getState() }; }

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
    const lt = l.last_review || l.due || "", rt = r.last_review || r.due || "";
    if (rt > lt) { local.cards[k] = r; changed = true; }
  }
  // answers: keep non-empty / longer
  for (const k in (rstate.answers || {})) {
    const rv = rstate.answers[k];
    if (!local.answers[k] || (rv && rv.length > (local.answers[k] || "").length)) { if (rv !== local.answers[k]) { local.answers[k] = rv; changed = true; } }
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

async function syncPull(opts) {
  if (!syncEnabled()) return false;
  const token = getToken(), gist = getGistId();
  if (!token || !gist) return false;
  updateSyncButton("syncing", "Pulling…");
  try {
    const data = await gistFetch("GET", "/gists/" + gist, token);
    const file = data.files && data.files[SYNC_FILENAME];
    if (!file) { updateSyncButton("enabled", "Synced"); return false; }
    let remote;
    if (file.truncated) { const r = await fetch(file.raw_url); remote = await r.json(); }
    else remote = JSON.parse(file.content);
    const changed = mergeRemote(remote);
    lsSet(SYNC_KEYS.last_pull, new Date().toISOString());
    if (changed) { bootRender(); showToast("Pulled remote progress."); }
    updateSyncButton("enabled", "Synced");
    return changed;
  } catch (e) { updateSyncButton("error", "Pull failed"); if (!(opts && opts.silent)) showToast("Sync pull failed: " + e.message); return false; }
}

let _pushTimer = null;
function scheduleSyncPush() {
  if (!syncEnabled()) return;
  clearTimeout(_pushTimer);
  updateSyncButton("syncing", "Pending…");
  _pushTimer = setTimeout(syncPush, 4000);
}
async function syncPush(opts) {
  if (!syncEnabled()) return false;
  const token = getToken(), gist = getGistId();
  if (!token || !gist) return false;
  updateSyncButton("syncing", "Pushing…");
  try {
    await gistFetch("PATCH", "/gists/" + gist, token, { files: { [SYNC_FILENAME]: { content: JSON.stringify(buildSyncPayload(), null, 2) } } });
    lsSet(SYNC_KEYS.last_push, new Date().toISOString());
    updateSyncButton("enabled", "Synced");
    if (opts && opts.toast) showToast("Pushed to cloud");
    return true;
  } catch (e) { updateSyncButton("error", "Push failed"); showToast("Sync push failed: " + e.message); return false; }
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

function openSyncModal() {
  const m = document.getElementById("sync-modal");
  if (!m) return;
  document.getElementById("sync-token-input").value = getToken();
  document.getElementById("sync-gist-input").value = getGistId();
  const last = lsGet(SYNC_KEYS.last_push, null), lastPull = lsGet(SYNC_KEYS.last_pull, null);
  const status = document.getElementById("sync-modal-status");
  if (syncEnabled() && last) { status.className = "sync-status ok"; status.innerHTML = "Sync enabled. Last push: " + new Date(last).toLocaleString() + (lastPull ? "<br>Last pull: " + new Date(lastPull).toLocaleString() : ""); }
  else { status.className = "sync-status"; status.textContent = "Sync not yet configured."; }
  m.classList.add("shown");
}
function closeSyncModal() { document.getElementById("sync-modal").classList.remove("shown"); }
function disableSync() {
  lsSet(SYNC_KEYS.enabled, false); updateSyncButton("off", "Off");
  const status = document.getElementById("sync-modal-status");
  status.className = "sync-status"; status.textContent = "Sync disabled. Token and Gist ID kept; re-enable any time.";
  showToast("Sync disabled");
}
async function forceSyncNow() { await syncPull(); await syncPush({ toast: true }); }
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
    await syncPull({ silent: true });
    await syncPush({ toast: true });
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
    '<p>Sync your FSRS progress across devices via a <b>private GitHub Gist</b>. Free, no external service.</p>' +
    '<ol><li>Generate a Personal Access Token (classic) with <b>only the gist scope</b>: <a href="https://github.com/settings/tokens/new?scopes=gist&description=CSCS%20Study%20Sync" target="_blank" rel="noopener">open GitHub →</a></li>' +
    '<li>Paste it below.</li><li>Each device with the same token finds the same Gist automatically.</li></ol>' +
    '<label>Personal Access Token (gist scope only)<input type="password" id="sync-token-input" autocomplete="off" placeholder="ghp_…"></label>' +
    '<label>Gist ID (optional — auto-discovered)<input type="text" id="sync-gist-input" autocomplete="off" placeholder="leave blank — auto-discovered"></label>' +
    '<div class="sync-actions"><button type="button" class="btn-primary" onclick="applySyncSettings()">Enable / Update</button>' +
    '<button type="button" onclick="forceSyncNow()">Sync now</button><button type="button" onclick="disableSync()">Disable</button>' +
    '<button type="button" onclick="closeSyncModal()" style="margin-left:auto;">Close</button></div>' +
    '<div id="sync-modal-status" class="sync-status">Sync not yet configured.</div></div>';
  modal.addEventListener("click", e => { if (e.target === modal) closeSyncModal(); });
  document.body.appendChild(modal);
}

document.addEventListener("DOMContentLoaded", () => {
  injectSyncUI();
  if (syncEnabled()) {
    if (__didHardReset) syncPush({ silent: true }).catch(() => {});  // overwrite cloud with the wiped state
    else syncPull({ silent: true }).catch(() => {});
  }
  else updateSyncButton("off", "Cloud sync off");
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
