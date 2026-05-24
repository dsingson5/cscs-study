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

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "daily"
STYLES = ROOT / "styles.css"
APP_JS = ROOT / "app.js"

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


def pick_review_lessons(today_day, lessons):
    out = []
    for s in SPACING_DAYS:
        t = today_day - s
        if t < 1:
            continue
        if str(t) in lessons:
            out.append((s, lessons[str(t)]))
    return out


def get_today_lesson(today_day, lessons):
    if str(today_day) in lessons:
        return lessons[str(today_day)], False
    rng = random.Random(today_day)
    return rng.choice(list(lessons.values())), True


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
                      f'<div class="gloss-svg">{g["svg"]}</div>'
                      f'<div class="gloss-text"><div class="gloss-term">{esc(g["term"])}</div>'
                      f'<div class="gloss-def">{esc(g["def"])}</div></div></div>')
        glossary_html = (f'<div class="glossary"><div class="gloss-title">Visual glossary</div>'
                         f'<div class="gloss-grid">{items}</div></div>')

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
        f'<span class="q-status" data-status-for="{qid}"></span></div>'
        f'<div class="q-text">{esc(q["q"])}</div>'
        f'<textarea class="q-answer" placeholder="Recall and type your answer first…" oninput="onAnswerInput(event)"></textarea>'
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


def render_html(today, today_day, today_lesson, deep_review, reviews, questions, meta, topic_domain):
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

    # ── Spaced review lesson cards (content recap only; questions are pooled) ──
    review_html = ""
    if reviews:
        review_html = ('<div class="review-section">'
                       '<h2 class="rs-title">Spaced review</h2>'
                       '<p class="rs-sub">Concepts you met before, resurfacing at expanding intervals '
                       '(Cepeda et al. 2008). Read the recap, then test yourself in the practice set below.</p>')
        for interval, lesson in reviews:
            label = SPACING_LABELS.get(interval, f"{interval}d review")
            review_html += render_lesson_card(lesson, label, "badge-spaced", False)
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
        for ot in others[:2]:
            ot_qs = sample_questions(ot, questions, 1, today_day * 17 + hash(ot) % 100)
            if ot_qs:
                oi, q = ot_qs[0]
                pool.append({"topic_id": ot, "orig_idx": oi, "q": q,
                             "domain": topic_domain.get(ot, "ES")})
    practice_html = render_practice_section(pool, topic_domain)

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
  <div class="session-summary">
    <div class="stat"><b>{1 if not deep_review else 0}</b>new lesson{"s" if deep_review else ""}</div>
    <div class="stat"><b>{len(reviews)}</b>spaced reviews</div>
    <div class="stat"><b>{new_count}</b>questions</div>
    <div class="stat"><b id="self-score">0</b>passed today</div>
  </div>
  <div id="personal-reviews"></div>
  {pretest_html}
  {today_card}
  {review_html}
  <h2 style="margin: 26px 0 8px; font-size: 20px; font-weight: 700;">Practice questions</h2>
  <p style="font-size: 13px; color: var(--text-dim); margin: 0 0 14px;">Forced retrieval first, then grade yourself. Whatever you miss resurfaces on the FSRS-chosen day.</p>
  {practice_html}
  <footer>
    Source: <i>Essentials of Strength Training and Conditioning</i> · Scheduling: <b>FSRS</b> (ts-fsrs) · spacing principle: Cepeda et al. 2008<br>
    <code>cscs_{today.isoformat()}.html</code> · also written to <code>cscs_today.html</code> (rolling, for localStorage persistence)
  </footer>
</div>
<script>window.__CSCS_QUESTIONS = {questions_json};</script>
<script>window.__CSCS_DOMAINS = {domains_json};</script>
<script>window.__CSCS_NEWCOUNT = {new_count};</script>
{FSRS_MODULE}
<script>{js}</script>
</body>
</html>
'''


def build_index_html(base_html, available, this_iso):
    """Wrap the day's page as a self-correcting landing page.
    Injects a tiny script that computes *today* in Asia/Manila (the viewer's
    own clock/timezone is irrelevant) and redirects to the matching daily
    archive page. Keeps the root URL from ever showing a stale date even if
    the generator hasn't run for a few days."""
    days = json.dumps(sorted(available))
    redirect = (
        '<script>(function(){var DAYS=' + days + ';var THIS="' + this_iso + '";'
        'function mt(){try{var p=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Manila",'
        'year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());'
        'var o={};p.forEach(function(x){o[x.type]=x.value;});return o.year+"-"+o.month+"-"+o.day;}'
        'catch(e){return null;}}'
        'var t=mt();if(!t)return;var tg=null;'
        'if(DAYS.indexOf(t)!==-1)tg=t;else if(t>DAYS[DAYS.length-1])tg=DAYS[DAYS.length-1];'
        'if(tg&&tg!==THIS){location.replace("daily/cscs_"+tg+".html");}})();</script>'
    )
    return base_html.replace("<head>", "<head>\n" + redirect, 1)


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
    reviews = pick_review_lessons(today_day, lessons)
    html = render_html(today, today_day, today_lesson, deep_review, reviews, questions, meta, topic_domain)
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
    index_path.write_text(build_index_html(html, available, today.isoformat()), encoding="utf-8")
    print(f"Wrote {dated_path}")
    print(f"Wrote {rolling_path} (rolling)")
    print(f"Wrote {index_path} (GitHub Pages entry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
