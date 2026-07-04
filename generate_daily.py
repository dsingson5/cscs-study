#!/usr/bin/env python3
"""CSCS Daily Study Generator — Interactive Edition.

Reads curriculum.json + questions.json, picks today's lesson, stacks
spaced-repetition reviews at 1/3/7/14/30/90-day intervals (Cepeda et al. 2008),
injects topic-specific interactive widgets, and writes a self-contained
interactive HTML to ./daily/cscs_YYYY-MM-DD.html.

Learning-science layer (v2): forced-commitment reveal, FSRS scheduling,
confidence + 4-button grading with per-domain calibration, errorful-generation
pretest, and exam-weighted interleaving. See app.js for the runtime.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import random
import sys
from pathlib import Path
from typing import Any

import widgets
import themes
import motifs

def render_fig_strip(lesson):
    """Thumbnails of the 5E figures/tables chosen for this lesson -> lightbox."""
    labels = lesson.get("figures") or []
    cards = ""
    for lab in labels:
        f = FIGS.get(lab)
        if not f:
            continue
        url = FIG_BASE + f["file"]
        cap = f'{f["label"]} — {f["caption"]}' if f.get("caption") else f["label"]
        cards += (f'<figure class="fig-thumb" data-full="{esc(url)}" data-cap="{esc(cap)}" '
                  f'tabindex="0" role="button" aria-label="{esc(cap)}">'
                  f'<img loading="lazy" src="{esc(url)}" alt="{esc(f["label"])}">'
                  f'<figcaption>{esc(f["label"])}</figcaption></figure>')
    if not cards:
        return ""
    return ('<div class="fig-strip"><div class="fig-title">Figures from the 5th edition '
            '<span class="fig-hint">tap to enlarge</span></div>'
            f'<div class="fig-row">{cards}</div></div>')

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "daily"
LAST_PAGE_QIDS = []  # core question stable-ids on the last rendered page
STYLES = ROOT / "styles.css"
APP_JS = ROOT / "app.js"

# ── 5th-edition figure library (extracted high-res scans in ./figures) ──────────
FIG_BASE = "../figures/"                    # relative: daily pages live in /daily/
FIG_MANIFEST = ROOT / "figures" / "manifest.json"
try:
    _figs_list = json.loads(FIG_MANIFEST.read_text(encoding="utf-8"))
except Exception:
    _figs_list = []
FIGS = {f["label"]: f for f in _figs_list}          # "Figure 3.1" -> record
FIGS_BY_CH = {}
for _f in _figs_list:
    FIGS_BY_CH.setdefault(_f["chapter"], []).append(_f)



SPACING_DAYS = [1, 3, 7, 14, 30, 90]
SPACING_LABELS = {
    1: "Yesterday (24 hr)",
    3: "3 days back",
    7: "1 week back",
    14: "2 weeks back",
    30: "1 month back",
    90: "3 months back",
}

DOMAIN_THEME = {
    "ES": {"name": "Exercise Science", "accent": "#5ec8ff", "accent_2": "#8fdfff", "glow": "rgba(94, 200, 255, 0.18)",
           "icon": "M5 22a7 7 0 0 0 7-7c0-2 0-3 2-5 1.5-1.5 3-3 3-5a5 5 0 0 0-10 0c0 2 1.5 3.5 3 5 2 2 2 3 2 5a7 7 0 0 0-7 7"},
    "NT": {"name": "Nutrition", "accent": "#67e8b0", "accent_2": "#9bf2cf", "glow": "rgba(103, 232, 176, 0.18)",
           "icon": "M12 2C8 6 6 10 6 14a6 6 0 0 0 12 0c0-4-2-8-6-12z"},
    "EX": {"name": "Exercise Technique", "accent": "#ffb86b", "accent_2": "#ffd09a", "glow": "rgba(255, 184, 107, 0.18)",
           "icon": "M6 4l4 4-2 2 4 4 2-2 4 4-4 4-4-4 2-2-4-4-2 2-4-4z"},
    "PD": {"name": "Program Design & Testing", "accent": "#c08fff", "accent_2": "#d8b8ff", "glow": "rgba(192, 143, 255, 0.18)",
           "icon": "M3 17l6-6 4 4 8-8M14 7h7v7"},
}

# Short domain names used on the question cards (match app.js DOMAIN_NAME).
DOMAIN_FULL = {"ES": "Exercise Science", "NT": "Nutrition", "EX": "Exercise Technique", "PD": "Program Design"}
# Official-NSCA-weighted interleave targets, normalised over the 4 curriculum
# domains. Practical/Applied (EX + PD) is the larger, harder pool.
EXAM_WEIGHTS = {"ES": 0.30, "NT": 0.12, "EX": 0.18, "PD": 0.40}

# Pinned ts-fsrs (Anki's default scheduler since 23.10). ESM via jsDelivr — no
# build step, runs in a static GitHub Pages site. app.js falls back to an
# internal scheduler if this fails to load.
FSRS_MODULE = (
    '<script type="module">\n'
    "  try {\n"
    "    const m = await import('https://cdn.jsdelivr.net/npm/ts-fsrs@5.4.1/+esm');\n"
    "    window.__FSRS = { createEmptyCard: m.createEmptyCard, fsrs: m.fsrs,\n"
    "      generatorParameters: m.generatorParameters, Rating: m.Rating, State: m.State };\n"
    "  } catch (e) { console.warn('ts-fsrs load failed, using fallback scheduler', e); }\n"
    "  window.dispatchEvent(new Event('fsrs-ready'));\n"
    "</script>"
)


def load_data():
    curriculum = json.loads((DATA / "curriculum.json").read_text(encoding="utf-8"))
    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    return curriculum, questions


def day_number(start_date, today):
    return (today - _dt.date.fromisoformat(start_date)).days + 1


def today_local():
    """Return today's date in the curriculum's local timezone.
    Avoids GitHub-runner UTC giving you yesterday's lesson at 11pm Manila."""
    try:
        from zoneinfo import ZoneInfo
        return _dt.datetime.now(ZoneInfo("Asia/Manila")).date()
    except Exception:
        return _dt.date.today()


def relevant_lessons(lessons):
    """Training-relevant lessons (Tiers 1-3 + advanced), in day order.
    Lessons marked relevant=False (Tier-4 test-only) are excluded so the
    Deep-Review rotation and spaced recaps stay training-focused."""
    return [lessons[k] for k in sorted(lessons, key=lambda x: int(x))
            if lessons[k].get("relevant", True)]


def pick_review_lessons(today_day, lessons, seen_through=0):
    """Spaced recaps of prior lessons. Any lesson on a day <= seen_through is a
    lesson the learner has declared 'done and not to be re-reviewed' (meta
    seen_through_day), so it is never resurfaced as a spaced recap."""
    out = []
    for s in SPACING_DAYS:
        t = today_day - s
        if t < 1 or t <= seen_through:
            continue
        if str(t) in lessons and lessons[str(t)].get("relevant", True):
            out.append((s, lessons[str(t)]))
    return out


def get_today_lesson(today_day, lessons):
    # Scheduled days serve their authored lesson as-is.
    if str(today_day) in lessons:
        return lessons[str(today_day)], False
    # Beyond the authored calendar: Deep Review rotates EVENLY through the
    # training-relevant pool only (no random repeats, no Tier-4 test-only).
    pool = relevant_lessons(lessons) or list(lessons.values())
    return pool[(today_day - 1) % len(pool)], True


def sample_questions(topic_id, questions, n, seed):
    """Return [(orig_index, question_dict), ...] — orig_index is the position
    in the source pool so we can build stable IDs for persistence."""
    pool = questions.get(topic_id, [])
    if not pool:
        return []
    rng = random.Random(seed)
    indices = list(range(len(pool)))
    rng.shuffle(indices)
    chosen = indices[:min(n, len(pool))]
    return [(i, pool[i]) for i in chosen]


def esc(s):
    return _html.escape(s, quote=True)


def render_lesson_card(lesson, badge, badge_class, show_widget=True, is_today=False):
    domain = lesson.get("domain", "ES")
    theme = DOMAIN_THEME.get(domain, DOMAIN_THEME["ES"])
    motif = motifs.motif_for(lesson["topic_id"])
    hero_html = motifs.render_motif_hero(motif) if (is_today and motif) else ""
    motif_class = " has-motif" if (is_today and motif) else ""
    facts = "".join(f"<li>{esc(f)}</li>" for f in lesson.get("key_facts", []))
    tl = lesson.get("training_link", "").strip()
    tl_html = (f'<div class="training-link"><span class="tl-label">Connection to your training</span>'
               f'<p>{esc(tl)}</p></div>') if tl else ""
    v = lesson.get("video", {}); a = lesson.get("audio", {})
    media = ""
    if v.get("url"):
        media += (f'<a class="media-link video" href="{esc(v["url"])}" target="_blank" rel="noopener">'
                  f'<span class="m-icon">▶</span><div><div class="m-title">{esc(v["title"])}</div>'
                  f'<div class="m-cred">{esc(v.get("credibility", ""))}</div></div></a>')
    if a.get("url"):
        media += (f'<a class="media-link audio" href="{esc(a["url"])}" target="_blank" rel="noopener">'
                  f'<span class="m-icon">♪</span><div><div class="m-title">{esc(a["title"])}</div>'
                  f'<div class="m-cred">{esc(a.get("credibility", ""))}</div></div></a>')
    for rsrc in (lesson.get("resources") or []):
        if rsrc.get("url"):
            media += (f'<a class="media-link resource" href="{esc(rsrc["url"])}" target="_blank" rel="noopener">'
                      f'<span class="m-icon">🔗</span><div><div class="m-title">{esc(rsrc["title"])}</div>'
                      f'<div class="m-cred">{esc(rsrc.get("credibility", ""))}</div></div></a>')
    widget_html = widgets.render(lesson["topic_id"]) if show_widget else ""
    chip = (f'<span class="domain-chip" style="background: {theme["glow"]}; color: {theme["accent"]}; border-color: {theme["accent"]}66;">'
            f'<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="{theme["icon"]}"/></svg>{esc(theme["name"])}</span>')
    # Glossary — animated definition cards for technical terms
    glossary_html = ""
    if lesson.get("glossary"):
        items = ""
        for i, g in enumerate(lesson["glossary"]):
            items += (f'<div class="gloss-card" style="animation-delay: {i*0.08:.2f}s">'
                      f'<div class="gloss-svg">{g.get("svg","")}</div>'
                      f'<div class="gloss-text"><div class="gloss-term">{esc(g["term"])}</div>'
                      f'<div class="gloss-def">{esc(g["def"])}</div></div></div>')
        glossary_html = (f'<div class="glossary"><div class="gloss-title">Visual glossary</div>'
                         f'<div class="gloss-grid">{items}</div></div>')

    fig_html = render_fig_strip(lesson)
    return (f'<section class="lesson-card reveal{motif_class}" data-domain="{domain}" '
            f'style="--accent: {theme["accent"]}; --accent-2: {theme["accent_2"]}; --glow: {theme["glow"]};">'
            f'{hero_html}'
            f'<div class="lesson-head"><span class="badge {badge_class}">{esc(badge)}</span>{chip}'
            f'<span class="domain">{esc(lesson.get("chapter", ""))} · {esc(lesson.get("page_refs", ""))}</span></div>'
            f'<h2>{esc(lesson["title"])}</h2>'
            f'<p class="concept">{esc(lesson.get("key_concept", ""))}</p>'
            f'{widget_html}'
            f'<div class="facts"><div class="facts-title">Key facts to memorize</div><ul>{facts}</ul></div>'
            f'{glossary_html}'
            f'{fig_html}'
            f'{tl_html}<div class="media">{media}</div></section>')


def render_q_card(topic_id, orig_idx, q, qid, domain, label="Q", pretest=False):
    """One interactive retrieval card. Reveal is gated client-side until the
    learner types an attempt or clicks 'I don't know' (forced commitment);
    after reveal, the 4-button Again/Hard/Good/Easy grade feeds FSRS. Applied
    (mechanism) cards also get a self-explanation prompt. Markup mirrors
    app.js questionCardHTML so generator and runtime cards behave identically."""
    qtype = q.get("type", "recall")
    selfexplain = qtype == "applied"
    stable = f"{topic_id}__{orig_idx}"
    se = ""
    if selfexplain:
        se = ('<div class="q-selfexplain"><label>In your own words — why is this true?</label>'
              '<textarea class="se-answer" placeholder="One sentence is enough. The attempt is what builds the memory." '
              'oninput="onSelfExplainInput(event)"></textarea></div>')
    cls = "q pretest" if pretest else "q"
    dom_name = DOMAIN_FULL.get(domain, domain)
    return (
        f'<div class="{cls}" data-qid="{qid}" data-stable="{esc(stable)}" data-domain="{domain}" data-qtype="{qtype}">'
        f'<div class="q-head"><span class="q-num">{label}</span><span class="q-type {qtype}">{qtype}</span>'
        f'<span class="q-domain">{esc(dom_name)}</span>'
        f'<span class="q-status" data-status-for="{qid}"></span><span class="q-last" data-last-for="{qid}" data-stable="{esc(stable)}"></span><span class="q-next" data-stable="{esc(stable)}"></span></div>'
        f'<div class="q-text">{esc(q["q"])}</div>'
        f'<textarea class="q-answer" placeholder="Recall and type your answer first…" oninput="onAnswerInput(event)"></textarea>'
        f'<button type="button" class="mic-btn" aria-pressed="false" title="Answer by voice" onclick="toggleDictation(this)"><svg class="mic-ico" viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"></path><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M5 11a7 7 0 0 0 14 0M12 18v3"></path></svg><span class="mic-lbl">Speak</span></button>'
        f'<div class="q-confidence"><span class="conf-label">How sure are you?</span>'
        f'<button type="button" class="conf-btn" data-conf="low" onclick="pickConfidence(\'{qid}\',\'low\')">Low</button>'
        f'<button type="button" class="conf-btn" data-conf="med" onclick="pickConfidence(\'{qid}\',\'med\')">Medium</button>'
        f'<button type="button" class="conf-btn" data-conf="high" onclick="pickConfidence(\'{qid}\',\'high\')">High</button></div>'
        f'<div class="q-actions">'
        f'<button type="button" class="btn-reveal" id="revealbtn_{qid}" disabled onclick="revealQ(\'{qid}\')">Reveal answer</button>'
        f'<button type="button" class="btn-idk" onclick="dontKnowQ(\'{qid}\')">I don\'t know</button></div>'
        f'<div class="q-reveal" id="reveal_{qid}"><div class="reveal-label">Answer</div>'
        f'<div class="reveal-body">{esc(q["a"])}</div>{se}'
        f'<div class="q-rate"><div class="rate-label">How did that go? <span class="rate-hint">(this sets when you see it next)</span></div>'
        f'<button type="button" class="rate-btn rate-again" data-grade="1" onclick="rateQ(\'{qid}\',1)">Again<small>&lt;10m</small></button>'
        f'<button type="button" class="rate-btn rate-hard" data-grade="2" onclick="rateQ(\'{qid}\',2)">Hard<small></small></button>'
        f'<button type="button" class="rate-btn rate-good" data-grade="3" onclick="rateQ(\'{qid}\',3)">Good<small></small></button>'
        f'<button type="button" class="rate-btn rate-easy" data-grade="4" onclick="rateQ(\'{qid}\',4)">Easy<small></small></button>'
        f'</div><div class="rate-result"></div></div></div>'
    )


def _interleave(pool):
    """pool: list of dicts with keys topic_id, orig_idx, q, domain. Returns the
    list reordered by exam-weight round-robin so domains appear roughly in
    proportion to NSCA weights and adjacent cards avoid sharing a topic
    (the discrimination practice interleaving buys us)."""
    by_dom = {}
    for it in pool:
        by_dom.setdefault(it["domain"], []).append(it)
    served = {d: 0 for d in by_dom}
    out = []
    last_topic = None
    total = len(pool)
    while len(out) < total:
        best, best_score = None, -1e9
        for d, items in by_dom.items():
            if not items:
                continue
            w = EXAM_WEIGHTS.get(d, 0.1)
            deficit = w - served[d] / max(1, len(out))
            penalty = 0.15 if items[0]["topic_id"] == last_topic else 0.0
            score = deficit - penalty
            if score > best_score:
                best_score, best = score, d
        if best is None:
            break
        it = by_dom[best].pop(0)
        out.append(it)
        served[best] += 1
        last_topic = it["topic_id"]
    return out


def render_practice_section(pool, topic_domain, block_id="px"):
    """Single interleaved practice section (replaces chapter-blocked groups)."""
    if not pool:
        return ""
    ordered = _interleave(pool)
    cards = ""
    for i, it in enumerate(ordered):
        cards += render_q_card(it["topic_id"], it["orig_idx"], it["q"], f"{block_id}_{i}",
                               it["domain"], label=f"Q{i+1}")
    return ('<section class="question-block reveal"><h3>Interleaved practice</h3>'
            '<p class="qs-sub">Mixed across domains by exam weight — this feels harder than drilling one topic, '
            'and that difficulty is the point: it roughly doubles what transfers to test day.</p>'
            f'<div class="qs">{cards}</div></section>')


def render_pretest(topic_id, qs, domain):
    """Errorful-generation pretest: 2 questions BEFORE the lesson. Guessing
    (and being wrong) primes encoding of the upcoming answer."""
    if not qs:
        return ""
    cards = ""
    for i, (orig_idx, q) in enumerate(qs):
        cards += render_q_card(topic_id, orig_idx, q, f"pre_{i}", domain,
                               label="Predict", pretest=True)
    return ('<section class="pretest-section reveal"><div class="pretest-banner">'
            '<span class="pt-icon">&#129504;</span><div><b>Predict first.</b> '
            'Take a guess before you read today\'s lesson. Getting it wrong is fine — '
            'a failed guess primes your brain to remember the right answer when it arrives.</div></div>'
            f'<div class="qs">{cards}</div></section>')



def _archive_dates(meta_start_iso):
    """All ISO dates from start_date through max(today, latest existing daily file)."""
    import datetime as _d
    start = _d.date.fromisoformat(meta_start_iso)
    existing = []
    try:
        for p in OUT.glob("cscs_2*.html"):
            s = p.stem.replace("cscs_", "")
            if s >= meta_start_iso:
                existing.append(s)
    except Exception:
        pass
    last_iso = max(existing) if existing else meta_start_iso
    last = _d.date.fromisoformat(last_iso)
    today_d = _d.date.today()
    end = max(last, today_d)
    out = []
    d = start
    while d <= end:
        out.append(d.isoformat())
        d = d + _d.timedelta(days=1)
    return out

def render_html(today, today_day, today_lesson, deep_review, reviews, questions, meta, topic_domain):
    import json as _json2
    page_date = today.isoformat()
    _all = _archive_dates(meta["start_date"])
    try:
        _i = _all.index(page_date)
    except ValueError:
        _i = -1
    _prev = _all[_i-1] if _i > 0 else None
    _next = _all[_i+1] if _i >= 0 and _i+1 < len(_all) else None
    prev_json = _json2.dumps(_prev)
    next_json = _json2.dumps(_next)

    css = STYLES.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    theme = themes.for_day(today_day)
    theme_css = themes.render_overrides(theme)
    motif = motifs.motif_for(today_lesson["topic_id"])
    motif_css = motifs.render_motif_css(motif) if motif else ""
    badge = "Deep Review" if deep_review else f"Day {today_day} · New lesson"
    badge_class = "badge-review" if deep_review else "badge-new"

    t_topic = today_lesson["topic_id"]
    t_domain = topic_domain.get(t_topic, today_lesson.get("domain", "ES"))

    # ── Pretest (errorful generation) — 2 questions before the lesson ──
    pre_qs = []
    if not deep_review:
        sampled = sample_questions(t_topic, questions, 6, today_day * 7)
        # prefer the harder "applied" items as predictions
        sampled.sort(key=lambda iq: 0 if iq[1].get("type") == "applied" else 1)
        pre_qs = sampled[:2]
    pre_idx = {oi for oi, _ in pre_qs}
    pretest_html = render_pretest(t_topic, pre_qs, t_domain)

    today_card = render_lesson_card(today_lesson, badge, badge_class, True, is_today=True)

    # ── Spaced review lesson cards (full recap incl. the topic animation; questions are pooled) ──
    review_html = ""
    if reviews:
        review_html = ('<div class="review-section">'
                       '<h2 class="rs-title">Spaced review</h2>'
                       '<p class="rs-sub">Concepts you met before, resurfacing at expanding intervals '
                       '(Cepeda et al. 2008). Read the recap, then test yourself in the practice set below.</p>')
        for interval, lesson in reviews:
            label = SPACING_LABELS.get(interval, f"{interval}d review")
            review_html += render_lesson_card(lesson, label, "badge-spaced", True)
        review_html += "</div>"

    # ── Build the interleaved practice pool (exam-weighted, cross-domain) ──
    pool = []
    for oi, q in sample_questions(t_topic, questions, 5, today_day * 7):
        if oi in pre_idx:
            continue
        pool.append({"topic_id": t_topic, "orig_idx": oi, "q": q, "domain": t_domain})
    for interval, lesson in reviews:
        rtopic = lesson["topic_id"]
        rdom = topic_domain.get(rtopic, lesson.get("domain", "ES"))
        for oi, q in sample_questions(rtopic, questions, 2, today_day * 11 + interval):
            pool.append({"topic_id": rtopic, "orig_idx": oi, "q": q, "domain": rdom})
    # cross-domain draws so the queue is never single-domain
    if not deep_review:
        present = {it["topic_id"] for it in pool} | {t_topic}
        others = [t for t in questions if t not in present]
        rng = random.Random(today_day * 13)
        rng.shuffle(others)
        for ot in others[:0]:  # off-lesson cross-domain draws disabled: keep the daily set = today's lesson + due reviews
            ot_qs = sample_questions(ot, questions, 1, today_day * 17 + hash(ot) % 100)
            if ot_qs:
                oi, q = ot_qs[0]
                pool.append({"topic_id": ot, "orig_idx": oi, "q": q,
                             "domain": topic_domain.get(ot, "ES")})
    practice_html = render_practice_section(pool, topic_domain)

    # core question set for the completion-aware resume: a day is 'done'
    # only when ALL of these are graded. Includes pretest + today-topic +
    # review-topic questions; excludes the random cross-domain bonus draws.
    _rtopics = {l['topic_id'] for _i, l in reviews}
    _core = set()
    for _oi, _q in pre_qs:
        _core.add(t_topic + '__' + str(_oi))
    for _it in pool:
        if _it['topic_id'] == t_topic or _it['topic_id'] in _rtopics:
            _core.add(_it['topic_id'] + '__' + str(_it['orig_idx']))
    global LAST_PAGE_QIDS
    LAST_PAGE_QIDS = sorted(_core)

    new_count = len(pre_qs) + len(pool)

    weekday = today.strftime("%A")
    date_str = today.strftime("%B %d, %Y")
    phase = next((p for p in meta["phases"]
                  if int(p["days"].split("-")[0]) <= today_day <= int(p["days"].split("-")[1])), None)
    phase_label = f'Phase {phase["phase"]}: {phase["name"]}' if phase else "Deep review phase — curriculum complete"
    domains_html = " ".join(f'<span class="dchip">{esc(v)}</span>' for v in meta["domains"].values())

    questions_json = json.dumps(questions, ensure_ascii=False)
    domains_json = json.dumps(topic_domain, ensure_ascii=False)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSCS Study — {date_str}</title>
<style>{css}</style>
<style>{theme_css}</style>
<style>{motif_css}</style>
</head>
<body class="{theme["body_class"]}">
<div class="container">
  <header class="top">
    <div class="h-day">CSCS Study · Day {today_day} · {weekday}</div>
    <div class="h-date">{date_str}</div>
    <div class="h-phase">{esc(phase_label)}</div>
    <div class="domains">{domains_html}</div>
    <div class="progress"><div class="bar" style="width: {min(100, today_day / 182 * 100):.1f}%;"></div></div>
    <div class="session-goal">Today: <b id="goal-new">{new_count}</b> new &middot; <b id="goal-due">0</b> due &middot; ~<b id="goal-min">25</b> min <span class="sg-note">— attendance, not a streak</span></div>
  </header>
  <nav class="lesson-nav" aria-label="Lesson navigation"><a class="ln-prev" id="ln-prev" href="#" onclick="return cscsNavPrev();">&larr; Previous lesson</a><span class="ln-here">Day {today_day} &middot; {date_str}</span><a class="ln-next" id="ln-next" href="#" onclick="return cscsNavNext();">Next lesson &rarr;</a></nav>
  <div class="games-cta"><a href="../games.html">&#127918; Drills &amp; Games &mdash; practice with retrieval games</a><a href="../figures.html" style="margin-left:10px">&#128444;&#65039; 5E Figure Library &mdash; every diagram &amp; table</a></div>
  <div class="companion-cta"><span class="cc-label">Official 5th-edition companion &amp; videos:</span>
    <a href="https://us.humankinetics.com/products/essentials-of-strength-training-and-conditioning-5th-edition-with-hkpropel-access" target="_blank" rel="noopener">Human Kinetics HKPropel &mdash; 21 exercise videos + 60 clips + 20 labs</a>
    <a href="https://www.nsca.com/education/nsca-videos/" target="_blank" rel="noopener">NSCA video library</a></div>
  <div class="study-tip">
    <b>How to use this:</b> recall and type an answer <b>before</b> you reveal — the reveal stays locked until you commit.
    After the answer, grade yourself <b>Again / Hard / Good / Easy</b>; that grade schedules the card with
    <b>FSRS</b> (the algorithm behind Anki). Rate <b>confidence first</b> so the dashboard can show where you're
    over- or under-confident. Everything saves in your browser.
    <div style="margin-top: 8px; font-size: 11px; color: var(--text-dim);">
      <span id="lifetime-stats">Lifetime: <b>0</b> tracked · <b>0</b> due now</span> ·
      <a href="#" onclick="exportProgress(); return false;" style="color: var(--theme-accent);">Export progress (JSON)</a> ·
      <label style="cursor: pointer; color: var(--theme-accent);">
        Import <input type="file" accept=".json" style="display:none" onchange="if(this.files[0]) importProgress(this.files[0])">
      </label>
    </div>
  </div>
  <div id="cscs-dashboard"></div>
  <div class="session-summary" id="session-summary">
    <div class="stat"><b>{1 if not deep_review else 0}</b>new lesson{"s" if deep_review else ""}</div>
    <div class="stat"><b>{len(reviews)}</b>spaced reviews</div>
    <div class="stat"><b>{new_count}</b>questions</div>
    <div class="stat"><b id="self-score">0</b>passed today</div>
  </div>
  <button type="button" class="sched-open">&#9201; View full review schedule &mdash; what&rsquo;s coming back &amp; when</button>
  <div id="personal-reviews"></div>
  {pretest_html}
  {today_card}
  {review_html}
  <h2 style="margin: 26px 0 8px; font-size: 20px; font-weight: 700;">Practice questions</h2>
  <p style="font-size: 13px; color: var(--text-dim); margin: 0 0 14px;">Forced retrieval first, then grade yourself. Whatever you miss resurfaces on the FSRS-chosen day.</p>
  {practice_html}
  <footer>
    Source: <i>Essentials of Strength Training and Conditioning</i>, 5th ed. (NSCA) · Scheduling: <b>FSRS</b> (ts-fsrs) · spacing principle: Cepeda et al. 2008<br>
    <code>cscs_{today.isoformat()}.html</code> · also written to <code>cscs_today.html</code> (rolling, for localStorage persistence)
  </footer>
</div>
<script>window.__CSCS_QUESTIONS = {questions_json};</script>
<script>window.__CSCS_DOMAINS = {domains_json};</script>
<script>window.__CSCS_NEWCOUNT = {new_count};</script>
<script>window.__CSCS_PAGE_DATE = "{page_date}";window.__CSCS_PREV = {prev_json}; window.__CSCS_NEXT = {next_json};</script>
{FSRS_MODULE}
<script>{js}</script>
</body>
</html>
'''


def build_index_html(base_html, available, this_iso, dtopic=None):
    """Wrap the day's page as a self-correcting landing page.
    Injects a tiny script that:
      1. Computes *today* in Asia/Manila (viewer's own clock is irrelevant).
      2. Looks at localStorage cscs.state.v1.log to find dates the user has
         already answered questions on (grouped by Manila date).
      3. Redirects to the EARLIEST archive date that is <= today AND has no
         answer activity yet — so missed days resume on the right page rather
         than skipping ahead. If everything up to today is done, goes to today.
      4. On a fresh device (no state yet), defaults to today so a brand-new
         visitor doesn't get sent back to Day 1."""
    days = json.dumps(sorted(available))
    dtopic_json = json.dumps(dtopic or {})
    # Per-day CORE question stable-ids: a day counts as DONE only when the
    # user has graded EVERY one of them. Baked so the redirect can decide
    # completion from graded cards (local UNION remote) with no per-page
    # bookkeeping. Falls back to touchedDays/topic if a day has no set.
    _avail = set(available)
    _dayq = {}
    try:
        _cp = DATA / 'day_completion.json'
        if _cp.exists():
            for _d, _ids in json.loads(_cp.read_text(encoding='utf-8')).items():
                if _d in _avail:
                    _dayq[_d] = _ids
    except Exception:
        _dayq = {}
    dayq_json = json.dumps(_dayq)
    redirect = (
        '<script>(function(){'
        'var DAYS=' + days + ';var DTOPIC=' + dtopic_json + ';var DAYQ=' + dayq_json + ';var THIS="' + this_iso + '";'
        'var GIST="f7cec859cb4ab8ba049297c925c2a959";var GFILE="cscs-progress.json";'
        'function mt(d){try{var p=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Manila",'
        'year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(d||new Date());'
        'var o={};p.forEach(function(x){o[x.type]=x.value;});return o.year+"-"+o.month+"-"+o.day;}'
        'catch(e){return null;}}'
        'var today=mt();if(!today){location.replace("daily/cscs_"+THIS+".html");return;}'
        'function go(t){location.replace("daily/cscs_"+(t||THIS)+".html");}'
        'try{var ov=document.createElement("div");ov.id="sa-resume";'
        'ov.textContent="Finding your place...";'
        'ov.setAttribute("style","position:fixed;inset:0;display:flex;align-items:center;'
        'justify-content:center;background:#0b0e14;color:#9ba3b4;font:14px -apple-system,Segoe UI,sans-serif;z-index:99999");'
        '(document.documentElement||document).appendChild(ov);'
        'setTimeout(function(){var o=document.getElementById("sa-resume");if(o&&o.parentNode)o.parentNode.removeChild(o);},8000);'
        '}catch(e){}'
        'function readLocal(){try{var raw=localStorage.getItem("cscs.state.v1");return raw?JSON.parse(raw):null;}catch(e){return null;}}'
        'function harvest(s,reviewed,engaged,cards){if(!s)return;var tt=s.touchedDays||{};for(var k in tt){if(tt[k])reviewed[k]=true;}'
        'var cc=s.cards||{};for(var ck in cc){engaged[ck.split("__")[0]]=true;cards[ck]=true;}}'
        'function complete(d,reviewed,engaged,cards){var qs=DAYQ[d];'
        'if(qs&&qs.length){for(var i=0;i<qs.length;i++){if(!cards[qs[i]])return false;}return true;}'
        'return reviewed[d]||(DTOPIC[d]&&engaged[DTOPIC[d]]);}'
        'function decide(reviewed,engaged,cards,hasState){var tg=null;'
        'if(hasState){for(var i=0;i<DAYS.length;i++){var d=DAYS[i];if(d>today)break;'
        'if(!complete(d,reviewed,engaged,cards)){tg=d;break;}}'
        'if(!tg){tg=(DAYS.indexOf(today)!==-1)?today:DAYS[DAYS.length-1];}}'
        'else{if(DAYS.indexOf(today)!==-1)tg=today;else if(today>DAYS[DAYS.length-1])tg=DAYS[DAYS.length-1];else tg=DAYS[0];}'
        'return tg||THIS;}'
        'var local=readLocal();var settled=false;'
        'function finish(remote){if(settled)return;settled=true;'
        'var reviewed={},engaged={},cards={};harvest(local,reviewed,engaged,cards);harvest(remote,reviewed,engaged,cards);'
        'var hasState=!!(Object.keys(reviewed).length||Object.keys(engaged).length||Object.keys(cards).length);go(decide(reviewed,engaged,cards,hasState));}'
        'var token="";try{token=localStorage.getItem("cscs.sync.token")||"";}catch(e){}'
        'var to=setTimeout(function(){finish(null);},4500);'
        'try{var hd={"Accept":"application/vnd.github+json"};if(token)hd["Authorization"]="token "+token;'
        'fetch("https://api.github.com/gists/"+GIST,{headers:hd,cache:"no-store"})'
        '.then(function(r){return r.ok?r.json():Promise.reject();})'
        '.then(function(d){var f=d.files&&d.files[GFILE];if(!f)return Promise.reject();'
        'if(f.truncated&&f.raw_url)return fetch(f.raw_url).then(function(x){return x.text();});return f.content;})'
        '.then(function(txt){var p=JSON.parse(txt);clearTimeout(to);finish(p&&p.state?p.state:null);})'
        '.catch(function(){clearTimeout(to);finish(null);});'
        '}catch(e){clearTimeout(to);finish(null);}'
        '})();</script>'
    )
    # The landing page must never be served stale from cache, or an old
    # redirect script (with outdated resume logic) sends the user to the
    # wrong day. GitHub Pages sets max-age=600; these discourage bfcache /
    # heuristic caching so the browser revalidates the index each visit.
    CACHE_META = (
        '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">'
        '<meta http-equiv="Pragma" content="no-cache">'
        '<meta http-equiv="Expires" content="0">'
    )
    # Root landing page lives beside games.html, not inside daily/ — undo
    # the daily-relative prefix for this one output.
    base_html = base_html.replace('href="../games.html"', 'href="games.html"')
    return base_html.replace("<head>", "<head>\n" + CACHE_META + redirect, 1)



def build_gallery_html():
    """Standalone, self-contained browsable gallery of every 5E figure & table."""
    CH_TITLES = {1:"Structure & Function of Body Systems",2:"Biomechanics of Resistance Exercise",3:"Bioenergetics of Exercise & Training",4:"Endocrine Responses to Resistance Training",5:"Adaptations to Anaerobic Training",6:"Adaptations to Aerobic Training",7:"Age-Related Differences",8:"Sex-Related Differences",9:"Psychological Foundations",10:"Basic Nutritional Factors",11:"Nutrition Strategies for Performance",12:"Performance-Enhancing Substances",13:"Test Selection & Administration",14:"Scoring & Interpretation of Tests",15:"Warm-Up, Mobility & Flexibility",16:"Exercise Technique: Free Weight & Machine",17:"Exercise Technique: Alternative Modes",18:"Program Design: Resistance Training",19:"Program Design: Plyometrics",20:"Program Design: Speed & Agility",21:"Program Design: Aerobic & Metabolic",22:"Periodization",23:"Rehabilitation & Reconditioning",24:"Overreaching, Overtraining & Recovery",25:"Facility Design & Layout",26:"Facility Policies & Legal Issues"}
    css = STYLES.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    theme = themes.for_day(1)
    sections = ""
    total = 0
    for ch in sorted(FIGS_BY_CH):
        recs = sorted(FIGS_BY_CH[ch], key=lambda r: (0 if r["kind"] == "FIGURE" else 1,
                      int(r["number"].split(".")[1])))
        cards = ""
        for f in recs:
            total += 1
            url = "figures/" + f["file"]
            cap = f'{f["label"]} — {f["caption"]}' if f.get("caption") else f["label"]
            cards += (f'<figure class="fig-thumb gal" data-full="{esc(url)}" data-cap="{esc(cap)}" '
                      f'data-search="{esc((f["label"]+" "+f.get("caption","")).lower())}" '
                      f'tabindex="0" role="button" aria-label="{esc(cap)}">'
                      f'<img loading="lazy" src="{esc(url)}" alt="{esc(f["label"])}">'
                      f'<figcaption>{esc(f["label"])}<span class="gal-cap">{esc(f.get("caption",""))}</span></figcaption>'
                      f'</figure>')
        sections += (f'<section class="gal-ch" data-ch="{ch}"><h2>Chapter {ch} · {esc(CH_TITLES.get(ch, ""))}</h2>'
                     f'<div class="fig-row gal-row">{cards}</div></section>')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSCS — 5th Edition Figure Library</title>
<style>{css}</style><style>{themes.render_overrides(theme)}</style>
<style>.gal-wrap{{max-width:1200px;margin:0 auto;padding:20px 16px 80px}}
.gal-head h1{{font-size:24px;margin:0 0 4px}}.gal-head p{{color:var(--text-dim);font-size:13px;margin:0 0 16px}}
.gal-search{{width:100%;max-width:420px;padding:10px 14px;border-radius:10px;border:1px solid var(--border);
background:var(--card);color:var(--text);font:inherit;margin-bottom:18px}}
.gal-ch h2{{font-size:16px;margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}}
.gal-row{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
.fig-thumb.gal{{margin:0}}.fig-thumb.gal img{{max-height:150px}}
.gal-cap{{display:block;font-size:10px;color:var(--text-dim);font-weight:400;margin-top:2px;line-height:1.25}}
.gal-empty{{display:none}}</style>
</head><body class="{theme["body_class"]}">
<div class="gal-wrap">
<div class="gal-head"><a href="./" style="color:var(--accent);font-size:12px;text-decoration:none">&larr; Back to today\u2019s study</a>
<h1>5th Edition Figure Library</h1>
<p>{total} figures &amp; tables extracted from <i>Essentials of Strength Training and Conditioning</i>, 5th ed. — tap any image to enlarge. For your personal study reference.</p>
<input class="gal-search" type="search" placeholder="Search figures &amp; tables\u2026 (e.g. fiber, squat, VO2)" oninput="galFilter(this.value)"></div>
{sections}
<div class="gal-empty" id="gal-empty" style="color:var(--text-dim);padding:20px">No matches.</div>
</div>
<script>
function galFilter(q){{q=(q||"").trim().toLowerCase();var any=false;
document.querySelectorAll(".fig-thumb.gal").forEach(function(el){{
var hit=!q||el.dataset.search.indexOf(q)>=0;el.style.display=hit?"":"none";if(hit)any=true;}});
document.querySelectorAll(".gal-ch").forEach(function(s){{
var vis=s.querySelectorAll(".fig-thumb.gal:not([style*=\'none\'])").length;s.style.display=vis?"":"none";}});
document.getElementById("gal-empty").style.display=any?"none":"block";}}
</script>
<script>{js}</script>
</body></html>'''

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, help="Override day_number (e.g. --day 2)")
    parser.add_argument("--date", type=str, help="Pretend today is this ISO date (e.g. --date 2026-05-20)")
    args, _ = parser.parse_known_args()

    curriculum, questions = load_data()
    meta = curriculum["meta"]
    if args.date:
        today = _dt.date.fromisoformat(args.date)
    else:
        today = today_local()
    today_day = args.day if args.day else day_number(meta["start_date"], today)
    if args.day and not args.date:
        # If just --day given, compute synthetic "today" so file naming matches
        today = _dt.date.fromisoformat(meta["start_date"]) + _dt.timedelta(days=args.day - 1)
    if today_day < 1:
        print(f"Today ({today}) is before curriculum start. No file generated.")
        return 1
    lessons = curriculum["lessons"]
    # Map every question topic to its NSCA domain (for interleaving + calibration).
    topic_domain = {l["topic_id"]: l.get("domain", "ES") for l in lessons.values()}
    for t in questions:
        topic_domain.setdefault(t, "ES")
    today_lesson, deep_review = get_today_lesson(today_day, lessons)
    reviews = pick_review_lessons(today_day, lessons, meta.get("seen_through_day", 0))
    html = render_html(today, today_day, today_lesson, deep_review, reviews, questions, meta, topic_domain)
    try:
        _cp = DATA / 'day_completion.json'
        _comp = {}
        if _cp.exists():
            _comp = json.loads(_cp.read_text(encoding='utf-8'))
        _comp[today.isoformat()] = LAST_PAGE_QIDS
        _cp.write_text(json.dumps(_comp, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    dated_path = OUT / f"cscs_{today.isoformat()}.html"
    rolling_path = OUT / "cscs_today.html"
    index_path = ROOT / "index.html"  # GitHub Pages entry point
    dated_path.write_text(html, encoding="utf-8")
    rolling_path.write_text(html, encoding="utf-8")
    # Index is the GitHub Pages entry point: make it self-correct to Manila "today".
    _start = meta["start_date"]
    available = sorted({d for p in OUT.glob("cscs_2*.html") if (d := p.stem.replace("cscs_", "")) >= _start})
    if today.isoformat() not in available:
        available.append(today.isoformat())
        available.sort()
    _sd = _dt.date.fromisoformat(meta["start_date"])
    _lesson_dates = {}
    for _k, _les in lessons.items():
        try:
            _dd = (_sd + _dt.timedelta(days=int(_k) - 1)).isoformat()
            _tid = _les.get("topic_id")
            if _tid:
                _lesson_dates[_dd] = _tid
        except Exception:
            pass
    index_path.write_text(build_index_html(html, available, today.isoformat(), _lesson_dates), encoding="utf-8")
    print(f"Wrote {dated_path}")
    print(f"Wrote {rolling_path} (rolling)")
    gallery_path = ROOT / "figures.html"
    gallery_path.write_text(build_gallery_html(), encoding="utf-8")
    print(f"Wrote {index_path} (GitHub Pages entry)")
    print(f"Wrote {gallery_path} (figure gallery)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
