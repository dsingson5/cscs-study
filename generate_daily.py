#!/usr/bin/env python3
"""CSCS Daily Study Generator — Interactive Edition.

Reads curriculum.json + questions.json, picks today's lesson, stacks
spaced-repetition reviews at 1/3/7/14/30/90-day intervals (Cepeda et al. 2008),
injects topic-specific interactive widgets, and writes a self-contained
interactive HTML to ./daily/cscs_YYYY-MM-DD.html.
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


def render_question_block(topic_id, label, qs, block_id):
    """qs is a list of (orig_index, question_dict) tuples — orig_index becomes
    part of the stable ID so localStorage tracks the same question across days."""
    if not qs:
        return ""
    items = ""
    for i, (orig_idx, q) in enumerate(qs):
        qid = f"{block_id}_{i}"
        stable = f"{topic_id}__{orig_idx}"
        qtype = q.get("type", "recall")
        items += (
            f'<div class="q" data-qid="{qid}" data-stable="{esc(stable)}">'
            f'<div class="q-head"><span class="q-num">Q{i+1}</span><span class="q-type {qtype}">{qtype}</span></div>'
            f'<div class="q-text">{esc(q["q"])}</div>'
            f'<textarea class="q-answer" placeholder="Type your answer here (try recall before revealing)…" oninput="onAnswerInput(event)"></textarea>'
            f'<div class="q-actions">'
            f'<button type="button" class="btn-reveal" onclick="toggleAnswer(\'{qid}\')">Reveal answer</button>'
            f'<button type="button" class="btn-self" data-self="correct" onclick="markSelf(\'{qid}\', \'correct\')">I got it</button>'
            f'<button type="button" class="btn-self" data-self="partial" onclick="markSelf(\'{qid}\', \'partial\')">Close</button>'
            f'<button type="button" class="btn-self" data-self="missed" onclick="markSelf(\'{qid}\', \'missed\')">Missed</button>'
            f'<span class="q-save-status" data-status-for="{qid}">auto-saving as you type</span>'
            f'</div>'
            f'<div class="q-reveal" id="reveal_{qid}"><div class="reveal-label">Answer</div>'
            f'<div class="reveal-body">{esc(q["a"])}</div></div></div>'
        )
    return f'<section class="question-block reveal"><h3>{esc(label)}</h3><div class="qs">{items}</div></section>'


def render_html(today, today_day, today_lesson, deep_review, reviews, questions, meta):
    css = STYLES.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    theme = themes.for_day(today_day)
    theme_css = themes.render_overrides(theme)
    motif = motifs.motif_for(today_lesson["topic_id"])
    motif_css = motifs.render_motif_css(motif) if motif else ""
    badge = "Deep Review" if deep_review else f"Day {today_day} · New lesson"
    badge_class = "badge-review" if deep_review else "badge-new"
    today_card = render_lesson_card(today_lesson, badge, badge_class, True, is_today=True)
    today_qs = sample_questions(today_lesson["topic_id"], questions, 4, today_day * 7)
    today_q_block = render_question_block(today_lesson["topic_id"], "Today's questions", today_qs, "today")

    review_html = ""; review_q_html = ""
    if reviews:
        review_html = ('<div class="review-section">'
                       '<h2 class="rs-title">Spaced repetition reviews</h2>'
                       '<p class="rs-sub">Research-validated spacing intervals (Cepeda et al. 2008) — concepts resurface at 1d, 3d, 7d, 14d, 30d, 90d for long-term retention.</p>')
        for interval, lesson in reviews:
            label = SPACING_LABELS.get(interval, f"{interval}d review")
            review_html += render_lesson_card(lesson, label, "badge-spaced", False)
            qs = sample_questions(lesson["topic_id"], questions, 2, today_day * 11 + interval)
            review_q_html += render_question_block(lesson["topic_id"], f"{label} — {lesson['title']}", qs, f"r{interval}")
        review_html += "</div>"

    off_topic_html = ""
    if not deep_review:
        others = [t for t in questions if t != today_lesson["topic_id"]]
        if others:
            ot = random.Random(today_day * 13).choice(others)
            ot_qs = sample_questions(ot, questions, 1, today_day * 17)
            if ot_qs:
                off_topic_html = render_question_block(ot, "Bonus cross-domain question", ot_qs, "bonus")

    weekday = today.strftime("%A")
    date_str = today.strftime("%B %d, %Y")
    phase = next((p for p in meta["phases"]
                  if int(p["days"].split("-")[0]) <= today_day <= int(p["days"].split("-")[1])), None)
    phase_label = f'Phase {phase["phase"]}: {phase["name"]}' if phase else "Deep review phase — curriculum complete"
    domains_html = " ".join(f'<span class="dchip">{esc(v)}</span>' for v in meta["domains"].values())
    total_qs = len(today_qs) + sum(2 for _ in reviews) + (1 if off_topic_html else 0)

    # Embed full question bank so JS can build the personal review queue
    questions_json = json.dumps(questions, ensure_ascii=False)
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
  </header>
  <div class="study-tip">
    <b>Today's study protocol:</b> Try active recall before revealing. Self-mark honestly.
    Answers and marks are <b>saved in your browser</b> — your "Personal review queue" below
    surfaces questions you missed or got partial credit on, with adaptive (SM-2) spacing.
    <div style="margin-top: 8px; font-size: 11px; color: var(--text-dim);">
      <span id="lifetime-stats">Lifetime: <b>0</b> tracked · <b>0</b> due now</span> ·
      <a href="#" onclick="exportProgress(); return false;" style="color: var(--theme-accent);">Export progress (JSON)</a> ·
      <label style="cursor: pointer; color: var(--theme-accent);">
        Import <input type="file" accept=".json" style="display:none" onchange="if(this.files[0]) importProgress(this.files[0])">
      </label>
    </div>
  </div>
  <div class="session-summary">
    <div class="stat"><b>{1 if not deep_review else 0}</b>new lesson{"s" if deep_review else ""}</div>
    <div class="stat"><b>{len(reviews)}</b>spaced reviews</div>
    <div class="stat"><b>{total_qs}</b>questions</div>
    <div class="stat"><b id="self-score">0</b>self-marked correct</div>
  </div>
  <div id="personal-reviews"></div>
  {today_card}
  {review_html}
  <h2 style="margin: 26px 0 8px; font-size: 20px; font-weight: 700;">Practice questions</h2>
  <p style="font-size: 13px; color: var(--text-dim); margin: 0 0 14px;">Active recall — write your answer, THEN reveal. Mistakes here resurface in your queue tomorrow.</p>
  {today_q_block}{review_q_html}{off_topic_html}
  <footer>
    Source: <i>Essentials of Strength Training and Conditioning</i> (4th ed.) · Adaptive spacing: SM-2 / Cepeda et al. 2008<br>
    <code>cscs_{today.isoformat()}.html</code> · also written to <code>cscs_today.html</code> (rolling, for localStorage persistence)
  </footer>
</div>
<script>window.__CSCS_QUESTIONS = {questions_json};</script>
<script>{js}</script>
</body>
</html>
'''


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
    today_lesson, deep_review = get_today_lesson(today_day, lessons)
    reviews = pick_review_lessons(today_day, lessons)
    html = render_html(today, today_day, today_lesson, deep_review, reviews, questions, meta)
    OUT.mkdir(parents=True, exist_ok=True)
    dated_path = OUT / f"cscs_{today.isoformat()}.html"
    rolling_path = OUT / "cscs_today.html"
    index_path = ROOT / "index.html"  # GitHub Pages entry point
    dated_path.write_text(html, encoding="utf-8")
    rolling_path.write_text(html, encoding="utf-8")
    index_path.write_text(html, encoding="utf-8")
    print(f"Wrote {dated_path}")
    print(f"Wrote {rolling_path} (rolling)")
    print(f"Wrote {index_path} (GitHub Pages entry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
