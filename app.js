// CSCS daily study — persistence + adaptive spaced repetition.
//
// State is kept in localStorage so answers and self-marks survive page reloads
// AND survive the daily regeneration of cscs_today.html (same URL → same
// origin → same localStorage).
//
// Per-question state implements an SM-2-style adaptive interval:
//   missed  → next due in 1 day,           ease -= 0.2 (floor 1.3)
//   partial → next due in max(1, prev × 0.6) days, ease unchanged
//   correct → next due in round(prev × ease) days, ease += 0.1 (cap 2.7)
// First-time seen entries default to interval 1, ease 2.5 (SM-2 defaults).

const LS_PREFIX = "cscs.";
const TODAY = new Date().toISOString().slice(0, 10);

function lsGet(key, fallback) {
  try {
    const raw = localStorage.getItem(LS_PREFIX + key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch (e) { return fallback; }
}
function lsSet(key, value) {
  try { localStorage.setItem(LS_PREFIX + key, JSON.stringify(value)); } catch (e) {}
}

function getQuestionState() { return lsGet("qstate", {}); }
function saveQuestionState(s) { lsSet("qstate", s); }
function getAnswers() { return lsGet("answers", {}); }
function saveAnswers(a) { lsSet("answers", a); }

function daysBetween(aIso, bIso) {
  const a = new Date(aIso), b = new Date(bIso);
  return Math.round((b - a) / (1000 * 60 * 60 * 24));
}
function addDays(iso, n) {
  const d = new Date(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function restoreAnswers() {
  const answers = getAnswers();
  const state = getQuestionState();
  document.querySelectorAll(".q").forEach(q => {
    const stable = q.dataset.stable;
    if (!stable) return;
    const txt = q.querySelector(".q-answer");
    if (txt && answers[stable]) txt.value = answers[stable];
    const mark = state[stable] && state[stable].last_mark;
    if (mark) {
      const btn = q.querySelector('button[data-self="' + mark + '"]');
      if (btn) btn.classList.add("active");
    }
  });
  updateScore();
}

function onAnswerInput(ev) {
  const q = ev.target.closest(".q");
  if (!q) return;
  const stable = q.dataset.stable;
  if (!stable) return;
  const answers = getAnswers();
  answers[stable] = ev.target.value;
  saveAnswers(answers);
}

function toggleAnswer(qid) {
  const el = document.getElementById("reveal_" + qid);
  if (el) el.classList.toggle("shown");
}

function markSelf(qid, kind) {
  const root = document.querySelector('[data-qid="' + qid + '"]');
  if (!root) return;
  root.querySelectorAll("button[data-self]").forEach(b => b.classList.remove("active"));
  const target = root.querySelector('button[data-self="' + kind + '"]');
  if (target) target.classList.add("active");
  const stable = root.dataset.stable;
  if (stable) {
    const state = getQuestionState();
    const prev = state[stable] || { seen_count: 0, interval: 1, ease: 2.5, history: [] };
    prev.seen_count = (prev.seen_count || 0) + 1;
    prev.last_seen = TODAY;
    prev.last_mark = kind;
    if (kind === "missed") {
      prev.interval = 1;
      prev.ease = Math.max(1.3, (prev.ease || 2.5) - 0.2);
    } else if (kind === "partial") {
      prev.interval = Math.max(1, Math.round((prev.interval || 1) * 0.6));
    } else {
      prev.interval = Math.max(1, Math.round((prev.interval || 1) * (prev.ease || 2.5)));
      prev.ease = Math.min(2.7, (prev.ease || 2.5) + 0.1);
    }
    prev.next_due = addDays(TODAY, prev.interval);
    prev.history = (prev.history || []).slice(-9).concat([{ d: TODAY, m: kind }]);
    state[stable] = prev;
    saveQuestionState(state);
  }
  updateScore();
  buildPersonalReviewQueue();
}

function updateScore() {
  const correct = document.querySelectorAll('button[data-self="correct"].active').length;
  const el = document.getElementById("self-score");
  if (el) el.textContent = correct;
  const stats = document.getElementById("lifetime-stats");
  if (stats) {
    const state = getQuestionState();
    const total = Object.keys(state).length;
    const due = Object.values(state).filter(s => s.next_due && s.next_due <= TODAY).length;
    stats.innerHTML = 'Lifetime: <b>' + total + '</b> tracked &middot; <b>' + due + '</b> due now';
  }
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
}

function buildPersonalReviewQueue() {
  const container = document.getElementById('personal-reviews');
  if (!container) return;
  if (!window.__CSCS_QUESTIONS) return;
  const state = getQuestionState();
  const due = [];
  for (const stable in state) {
    const entry = state[stable];
    if (!entry.next_due || entry.next_due > TODAY) continue;
    const parts = stable.split('__');
    if (parts.length !== 2) continue;
    const topicId = parts[0];
    const idx = parseInt(parts[1], 10);
    const pool = window.__CSCS_QUESTIONS[topicId];
    if (!pool || !pool[idx]) continue;
    due.push({ stable: stable, topicId: topicId, idx: idx, q: pool[idx], entry: entry });
  }
  due.sort(function(a, b) {
    var rank = function(m) { return m === 'missed' ? 0 : m === 'partial' ? 1 : 2; };
    var r = rank(a.entry.last_mark) - rank(b.entry.last_mark);
    if (r !== 0) return r;
    return a.entry.next_due.localeCompare(b.entry.next_due);
  });
  if (due.length === 0) { container.innerHTML = ''; return; }
  var top = due.slice(0, 10);
  var html = '<section class="personal-review-section">' +
    '<h2 class="rs-title">Your personal review queue &middot; ' + due.length + ' due</h2>' +
    '<p class="rs-sub">Adaptive spacing (SM-2). Missed questions resurface in 1 day. Correct ones get longer intervals as you build confidence.</p>';
  top.forEach(function(d, i) {
    var qid = 'pr_' + i;
    var overdueDays = d.entry.next_due ? Math.max(0, daysBetween(d.entry.next_due, TODAY)) : 0;
    var meta = 'last: <b class="mark-' + (d.entry.last_mark || 'new') + '">' + (d.entry.last_mark || 'new') + '</b>' +
      ' &middot; seen &times;' + (d.entry.seen_count || 1) + ' &middot; ease ' + (d.entry.ease || 2.5).toFixed(2) +
      (overdueDays > 0 ? ' &middot; <b>' + overdueDays + 'd overdue</b>' : '');
    html += '<div class="q personal-review" data-qid="' + qid + '" data-stable="' + escapeHtml(d.stable) + '">' +
      '<div class="q-head"><span class="q-num">&#10227; Due</span>' +
      '<span class="q-type ' + (d.q.type || 'recall') + '">' + (d.q.type || 'recall') + '</span>' +
      '<span class="pr-meta">' + meta + '</span></div>' +
      '<div class="q-text">' + escapeHtml(d.q.q) + '</div>' +
      '<textarea class="q-answer" placeholder="Type your answer here..." oninput="onAnswerInput(event)"></textarea>' +
      '<div class="q-actions">' +
      '<button type="button" onclick="toggleAnswer(\'' + qid + '\')">Reveal</button>' +
      '<button type="button" class="btn-self" data-self="correct" onclick="markSelf(\'' + qid + '\', \'correct\')">I got it</button>' +
      '<button type="button" class="btn-self" data-self="partial" onclick="markSelf(\'' + qid + '\', \'partial\')">Close</button>' +
      '<button type="button" class="btn-self" data-self="missed" onclick="markSelf(\'' + qid + '\', \'missed\')">Missed</button>' +
      '</div>' +
      '<div class="q-reveal" id="reveal_' + qid + '"><div class="reveal-label">Answer</div>' +
      '<div class="reveal-body">' + escapeHtml(d.q.a) + '</div></div></div>';
  });
  if (due.length > 10) {
    html += '<div class="pr-overflow">+ ' + (due.length - 10) + ' more due will appear after you clear these.</div>';
  }
  html += '</section>';
  container.innerHTML = html;
  var answers = getAnswers();
  container.querySelectorAll('.q').forEach(function(q) {
    var s = q.dataset.stable;
    var txt = q.querySelector('.q-answer');
    if (txt && answers[s]) txt.value = answers[s];
    var mark = state[s] && state[s].last_mark;
    if (mark) {
      var btn = q.querySelector('button[data-self="' + mark + '"]');
      if (btn) btn.classList.add('active');
    }
  });
}

function exportProgress() {
  var blob = new Blob([JSON.stringify({
    exported_at: new Date().toISOString(),
    qstate: getQuestionState(),
    answers: getAnswers()
  }, null, 2)], { type: 'application/json' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'cscs-progress-' + TODAY + '.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
function importProgress(file) {
  var reader = new FileReader();
  reader.onload = function(e) {
    try {
      var data = JSON.parse(e.target.result);
      if (data.qstate) saveQuestionState(data.qstate);
      if (data.answers) saveAnswers(data.answers);
      restoreAnswers();
      buildPersonalReviewQueue();
      alert('Progress imported.');
    } catch (err) { alert('Import failed: ' + err.message); }
  };
  reader.readAsText(file);
}

var obs = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      obs.unobserve(e.target);
    }
  });
}, { threshold: 0.08 });

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.reveal').forEach(function(el) { obs.observe(el); });
  restoreAnswers();
  buildPersonalReviewQueue();
});
