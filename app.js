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

// ────────── EXPLICIT SAVE BUTTON ──────────
function saveQuestion(qid) {
  const root = document.querySelector('[data-qid="' + qid + '"]');
  if (!root) return;
  const stable = root.dataset.stable;
  if (!stable) return;
  const txt = root.querySelector('.q-answer');
  if (txt) {
    const answers = getAnswers();
    answers[stable] = txt.value;
    saveAnswers(answers);
  }
  // Flash status text
  const status = document.querySelector('[data-status-for="' + qid + '"]');
  if (status) {
    status.textContent = '✓ Saved locally';
    status.className = 'q-save-status saved';
    setTimeout(function() {
      status.textContent = '';
      status.className = 'q-save-status';
    }, 2500);
  }
  // Trigger cross-device push if enabled
  if (typeof scheduleSyncPush === 'function') scheduleSyncPush();
  showToast('Answer saved');
}

// ────────── TOAST ──────────
function showToast(msg) {
  let t = document.getElementById('cscs-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'cscs-toast';
    t.className = 'cscs-toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add('visible');
  clearTimeout(t._timer);
  t._timer = setTimeout(function() { t.classList.remove('visible'); }, 2200);
}

// ════════════════════════════════════════════════════════════════════════════
//   CROSS-DEVICE SYNC VIA GITHUB GIST
// ════════════════════════════════════════════════════════════════════════════
// One-time setup:
//   1. User creates a GitHub Personal Access Token (PAT) with only the 'gist' scope.
//   2. PAT is stored in localStorage on each device.
//   3. First device creates a private Gist; its ID is stored in localStorage.
//   4. Other devices import the same Gist ID + PAT and start syncing.
//
// Sync behavior:
//   - On page load (after restoring local state): pull remote, merge per-key
//     (last-write-wins by entry.last_seen / payload.updated_at).
//   - On any save (answer or mark): debounced push 4 seconds later.
//   - Manual "Sync now" button forces immediate pull+push.
//
// Security:
//   - PAT lives only in the user's browser localStorage.
//   - PAT should have ONLY the 'gist' scope.
//   - The Gist is private (visible only to the token's owner).

const SYNC_KEYS = {
  token: "sync.token",
  gist: "sync.gist_id",
  enabled: "sync.enabled",
  last_push: "sync.last_push_at",
  last_pull: "sync.last_pull_at",
};
const SYNC_FILENAME = "cscs-progress.json";
const SYNC_SCHEMA = 2;

function syncEnabled() { return !!lsGet(SYNC_KEYS.enabled, false); }
function getToken() { return localStorage.getItem(LS_PREFIX + SYNC_KEYS.token) || ""; }
function getGistId() { return localStorage.getItem(LS_PREFIX + SYNC_KEYS.gist) || ""; }
function setToken(t) { localStorage.setItem(LS_PREFIX + SYNC_KEYS.token, t); }
function setGistId(id) { localStorage.setItem(LS_PREFIX + SYNC_KEYS.gist, id); }

async function gistFetch(method, path, token, body) {
  const res = await fetch("https://api.github.com" + path, {
    method,
    headers: {
      "Authorization": "token " + token,
      "Accept": "application/vnd.github+json",
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error("GitHub API " + res.status + ": " + text.slice(0, 200));
  }
  return res.status === 204 ? null : res.json();
}

function buildSyncPayload() {
  return {
    schema: SYNC_SCHEMA,
    updated_at: new Date().toISOString(),
    qstate: getQuestionState(),
    answers: getAnswers()
  };
}

function mergeRemote(remote) {
  if (!remote || remote.schema > SYNC_SCHEMA) return false;
  const localQs = getQuestionState();
  const localAns = getAnswers();
  let changed = false;

  // Per-key merge of qstate using last_seen as tiebreaker
  const mergedQs = Object.assign({}, localQs);
  for (const k in (remote.qstate || {})) {
    const r = remote.qstate[k];
    const l = mergedQs[k];
    if (!l) { mergedQs[k] = r; changed = true; continue; }
    const lTime = (l.last_seen || "") + "_" + (l.seen_count || 0);
    const rTime = (r.last_seen || "") + "_" + (r.seen_count || 0);
    if (rTime > lTime) { mergedQs[k] = r; changed = true; }
  }

  // Answers merge: prefer the version whose corresponding qstate is newer.
  // If qstate is identical, prefer the longer/non-empty value.
  const mergedAns = Object.assign({}, localAns);
  for (const k in (remote.answers || {})) {
    const rVal = remote.answers[k];
    if (!mergedAns[k]) { mergedAns[k] = rVal; changed = true; continue; }
    const rNewer = ((remote.qstate && remote.qstate[k] && remote.qstate[k].last_seen) || "") >
                   ((localQs[k] && localQs[k].last_seen) || "");
    if (rNewer && rVal && rVal !== mergedAns[k]) { mergedAns[k] = rVal; changed = true; }
  }

  if (changed) {
    saveQuestionState(mergedQs);
    saveAnswers(mergedAns);
  }
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
    if (!file) {
      updateSyncButton("enabled", "Synced");
      return false;
    }
    let remote;
    if (file.truncated) {
      const r = await fetch(file.raw_url);
      remote = await r.json();
    } else {
      remote = JSON.parse(file.content);
    }
    const changed = mergeRemote(remote);
    lsSet(SYNC_KEYS.last_pull, new Date().toISOString());
    if (changed) {
      restoreAnswers();
      buildPersonalReviewQueue();
      showToast("Pulled remote progress (" + Object.keys(remote.qstate || {}).length + " questions)");
    }
    updateSyncButton("enabled", "Synced");
    return changed;
  } catch (e) {
    updateSyncButton("error", "Pull failed");
    if (opts && opts.silent !== true) showToast("Sync pull failed: " + e.message);
    return false;
  }
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
    const payload = buildSyncPayload();
    await gistFetch("PATCH", "/gists/" + gist, token, {
      files: { [SYNC_FILENAME]: { content: JSON.stringify(payload, null, 2) } }
    });
    lsSet(SYNC_KEYS.last_push, new Date().toISOString());
    updateSyncButton("enabled", "Synced");
    if (opts && opts.toast) showToast("Pushed to cloud");
    return true;
  } catch (e) {
    updateSyncButton("error", "Push failed");
    showToast("Sync push failed: " + e.message);
    return false;
  }
}

async function createNewGist() {
  const token = getToken();
  if (!token) throw new Error("No token");
  const payload = buildSyncPayload();
  const data = await gistFetch("POST", "/gists", token, {
    description: "CSCS Study Progress (sync)",
    public: false,
    files: { [SYNC_FILENAME]: { content: JSON.stringify(payload, null, 2) } }
  });
  return data.id;
}

// ────────── SYNC MODAL UI ──────────
function openSyncModal() {
  const m = document.getElementById("sync-modal");
  if (!m) return;
  document.getElementById("sync-token-input").value = getToken();
  document.getElementById("sync-gist-input").value = getGistId();
  const last = lsGet(SYNC_KEYS.last_push, null);
  const lastPull = lsGet(SYNC_KEYS.last_pull, null);
  const status = document.getElementById("sync-modal-status");
  if (syncEnabled() && last) {
    status.className = "sync-status ok";
    status.innerHTML = "Sync enabled. Last push: " + new Date(last).toLocaleString() +
                       (lastPull ? "<br>Last pull: " + new Date(lastPull).toLocaleString() : "");
  } else {
    status.className = "sync-status";
    status.textContent = "Sync not yet configured.";
  }
  m.classList.add("shown");
}
function closeSyncModal() {
  document.getElementById("sync-modal").classList.remove("shown");
}
async function applySyncSettings() {
  const token = document.getElementById("sync-token-input").value.trim();
  const gist = document.getElementById("sync-gist-input").value.trim();
  const status = document.getElementById("sync-modal-status");
  if (!token) {
    status.className = "sync-status err";
    status.textContent = "Token required.";
    return;
  }
  setToken(token);
  // Validate by hitting /user/gists or by gist GET
  status.className = "sync-status";
  status.textContent = "Validating token…";
  try {
    if (gist) {
      await gistFetch("GET", "/gists/" + gist, token);
      setGistId(gist);
    } else {
      status.textContent = "Creating new private Gist…";
      const id = await createNewGist();
      setGistId(id);
      document.getElementById("sync-gist-input").value = id;
    }
    lsSet(SYNC_KEYS.enabled, true);
    status.className = "sync-status ok";
    status.textContent = "Sync enabled. Pulling latest…";
    updateSyncButton("enabled", "Synced");
    await syncPull({ silent: true });
    await syncPush({ toast: true });
    status.className = "sync-status ok";
    status.innerHTML = "Sync active. Gist ID: <code>" + getGistId() + "</code><br>" +
                       "Copy this Gist ID to your other devices to keep them in sync.";
  } catch (e) {
    status.className = "sync-status err";
    status.textContent = "Validation failed: " + e.message;
  }
}
function disableSync() {
  lsSet(SYNC_KEYS.enabled, false);
  updateSyncButton("off", "Off");
  const status = document.getElementById("sync-modal-status");
  status.className = "sync-status";
  status.textContent = "Sync disabled. Token and Gist ID kept; re-enable any time.";
  showToast("Sync disabled");
}
async function forceSyncNow() {
  await syncPull();
  await syncPush({ toast: true });
}

function updateSyncButton(state, text) {
  const btn = document.getElementById("sync-button");
  if (!btn) return;
  btn.className = "sync-button " + (state === "off" ? "" : state);
  btn.querySelector(".sync-text").textContent = text;
}

function injectSyncUI() {
  // Floating sync button
  const btn = document.createElement("button");
  btn.id = "sync-button";
  btn.className = "sync-button " + (syncEnabled() ? "enabled" : "");
  btn.innerHTML = '<span class="sync-dot"></span><span class="sync-text">' +
                   (syncEnabled() ? "Sync" : "Cloud sync off") + '</span>';
  btn.onclick = openSyncModal;
  document.body.appendChild(btn);

  // Modal
  const modal = document.createElement("div");
  modal.id = "sync-modal";
  modal.className = "sync-modal";
  modal.innerHTML =
    '<div class="sync-modal-content">' +
      '<h3>Cross-device sync</h3>' +
      '<p>Sync your answers and SM-2 progress across phone, laptop, tablet — via a <b>private GitHub Gist</b>. Free, no external service needed.</p>' +
      '<ol>' +
        '<li>Generate a Personal Access Token (classic) with <b>only the gist scope</b>: <a href="https://github.com/settings/tokens/new?scopes=gist&description=CSCS%20Study%20Sync" target="_blank" rel="noopener">open GitHub →</a></li>' +
        '<li>Paste it below.</li>' +
        '<li>Each device with the same token finds the same Gist automatically &mdash; no IDs to copy.</li>' +
      '</ol>' +
      '<label>Personal Access Token (gist scope only)' +
        '<input type="password" id="sync-token-input" autocomplete="off" placeholder="ghp_…">' +
      '</label>' +
      '<label>Gist ID (optional — auto-discovered from your token)' +
        '<input type="text" id="sync-gist-input" autocomplete="off" placeholder="leave blank — auto-discovered">' +
      '</label>' +
      '<div class="sync-actions">' +
        '<button type="button" class="btn-primary" onclick="applySyncSettings()">Enable / Update</button>' +
        '<button type="button" onclick="forceSyncNow()">Sync now</button>' +
        '<button type="button" onclick="disableSync()">Disable</button>' +
        '<button type="button" onclick="closeSyncModal()" style="margin-left:auto;">Close</button>' +
      '</div>' +
      '<div id="sync-modal-status" class="sync-status">Sync not yet configured.</div>' +
    '</div>';
  modal.addEventListener("click", function(e) { if (e.target === modal) closeSyncModal(); });
  document.body.appendChild(modal);
}

// Wire sync into existing save flows by re-binding markSelf and onAnswerInput
const _origMarkSelf = markSelf;
markSelf = function(qid, kind) { _origMarkSelf(qid, kind); scheduleSyncPush(); };
const _origOnInput = onAnswerInput;
onAnswerInput = function(ev) { _origOnInput(ev); scheduleSyncPush(); };

// Boot sync on load
document.addEventListener("DOMContentLoaded", function() {
  injectSyncUI();
  if (syncEnabled()) {
    syncPull({ silent: true }).catch(function() {});
  } else {
    updateSyncButton("off", "Cloud sync off");
  }
});

// ────────── AUTO-SAVE FLASH INDICATOR ──────────
// Briefly flash "Saved ✓" next to a question when localStorage actually writes.
// Replaces the explicit Save button — auto-save runs on every keystroke (debounced).
(function() {
  const origInput = onAnswerInput;
  let flashTimers = {};
  onAnswerInput = function(ev) {
    origInput(ev);
    const q = ev.target.closest('.q');
    if (!q) return;
    const qid = q.dataset.qid;
    if (!qid) return;
    const status = q.querySelector('[data-status-for="' + qid + '"]');
    if (!status) return;
    status.textContent = 'Saved ✓';
    status.classList.add('flashed');
    clearTimeout(flashTimers[qid]);
    flashTimers[qid] = setTimeout(function() {
      status.textContent = 'auto-saving as you type';
      status.classList.remove('flashed');
    }, 1400);
  };
})();

// ────────── AUTO-DISCOVER GIST BY FILENAME (token-only sync) ──────────
// On a fresh device, paste the PAT and the page finds the existing CSCS sync
// Gist by its filename instead of asking the user to copy a Gist ID.
async function findOrCreateSyncGist(token) {
  // List the user's Gists (paginated; 100 per page)
  let page = 1;
  while (page <= 5) {  // up to 500 Gists; plenty
    const list = await gistFetch("GET", "/gists?per_page=100&page=" + page, token);
    if (!Array.isArray(list) || list.length === 0) break;
    for (const g of list) {
      if (g.files && g.files[SYNC_FILENAME]) {
        return g.id;  // found existing CSCS gist
      }
    }
    if (list.length < 100) break;
    page++;
  }
  // No existing Gist with our filename — create a new one
  return await createNewGist();
}

// Override applySyncSettings to auto-discover when Gist ID is blank
const _origApplySync = applySyncSettings;
applySyncSettings = async function() {
  const token = document.getElementById("sync-token-input").value.trim();
  const gistInput = document.getElementById("sync-gist-input");
  const gist = gistInput.value.trim();
  const status = document.getElementById("sync-modal-status");
  if (!token) {
    status.className = "sync-status err";
    status.textContent = "Token required.";
    return;
  }
  setToken(token);
  status.className = "sync-status";
  status.textContent = "Looking for your sync Gist...";
  try {
    let resolvedGistId = gist;
    if (!resolvedGistId) {
      resolvedGistId = await findOrCreateSyncGist(token);
      gistInput.value = resolvedGistId;
    } else {
      // Validate the provided gist
      await gistFetch("GET", "/gists/" + resolvedGistId, token);
    }
    setGistId(resolvedGistId);
    lsSet(SYNC_KEYS.enabled, true);
    status.className = "sync-status ok";
    status.textContent = "Found / created your sync Gist. Pulling latest...";
    updateSyncButton("enabled", "Synced");
    await syncPull({ silent: true });
    await syncPush({ toast: true });
    status.className = "sync-status ok";
    status.innerHTML = "Sync active automatically. On other devices, just paste the same token — they will find this Gist too.";
  } catch (e) {
    status.className = "sync-status err";
    status.textContent = "Failed: " + e.message;
  }
};
