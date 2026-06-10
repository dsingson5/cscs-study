"""biomech.py — interactive predict-then-check biomechanics widgets (2D SVG).

Design rules (match the cscs-study-site conventions):
  * Self-contained: inline SVG + scoped <style> + an IIFE <script>. No external libs.
  * Reuses the existing .widget / .w-head / .w-title / .w-body / .w-svg CSS so it
    inherits the per-day theme (var(--accent), --good, --warn, --bad, --text...).
  * Every instance is id-namespaced (a unique root id per render) so several
    widgets can coexist on one daily page (today's lesson + spaced reviews).
  * FORCED RETRIEVAL: each widget asks the learner to PREDICT before it reveals
    the answer + a one-line "why". (Same learning-science rule as the games hub.)
  * Kept fully SEPARATE from FSRS: these widgets NEVER touch localStorage /
    cscs.state.v1. They are ephemeral lesson scaffolding, not graded cards.

Public API:
  render(topic_id) -> str   # concatenated widget HTML for that topic ("" if none)
"""
from __future__ import annotations

import random as _random

_CTR = 0


def _uid(prefix: str = "bm") -> str:
    global _CTR
    _CTR += 1
    return f"{prefix}{_CTR}{_random.randint(1000, 9999)}"


def _shell(uid: str, title: str, inner: str, icon: str = "\U0001f9b4") -> str:
    """Wrap a widget body in the standard .widget chrome (bone emoji default)."""
    return (
        f'<div class="widget bm-w" id="{uid}">'
        f'<div class="w-head"><span class="w-icon">{icon}</span>'
        f'<span class="w-title">{title}</span></div>'
        f'<div class="w-body">{inner.replace("__UID__", uid)}</div>'
        f"</div>"
    )


# Shared, id-scoped CSS for the predict-then-check chrome. Emitted once per widget
# (cheap, and keeps each widget independent / copy-safe).
_PREDICT_CSS = """
<style>
#__UID__ .bm-q{font-size:13px;font-weight:600;color:var(--text);margin:10px 0 8px}
#__UID__ .bm-opts{display:flex;flex-direction:column;gap:7px;margin-bottom:8px}
#__UID__ .bm-opt{appearance:none;text-align:left;cursor:pointer;font-size:13px;
  padding:9px 12px;border-radius:9px;border:1px solid var(--border-2,#2d3548);
  background:var(--surface-2,rgba(255,255,255,.03));color:var(--text);
  transition:border-color .15s,background .15s,transform .1s;line-height:1.35}
#__UID__ .bm-opt:hover:not(:disabled){border-color:var(--accent);transform:translateX(2px)}
#__UID__ .bm-opt:disabled{cursor:default}
#__UID__ .bm-opt.is-correct{border-color:var(--good);background:rgba(103,232,176,.12);color:var(--good)}
#__UID__ .bm-opt.is-wrong{border-color:var(--bad);background:rgba(255,122,122,.10);color:var(--bad)}
#__UID__ .bm-opt .bm-tag{font-weight:700;margin-right:6px}
#__UID__ .bm-reveal{display:none;margin-top:10px;padding:10px 13px;border-radius:9px;
  background:rgba(94,200,255,.07);border-left:3px solid var(--accent);font-size:12.5px;
  color:var(--text-dim,#9ba3b4);line-height:1.5}
#__UID__ .bm-reveal.show{display:block;animation:bmfade .35s ease}
#__UID__ .bm-reveal b{color:var(--text)}
#__UID__ .bm-reveal .bm-why{color:var(--warn)}
#__UID__ .bm-controls{margin-top:10px}
#__UID__ .bm-controls label{font-size:12px;color:var(--text-dim,#9ba3b4);display:block;margin-top:6px}
#__UID__ .bm-controls label b{color:var(--text)}
#__UID__ .bm-slider{width:100%;-webkit-appearance:none;appearance:none;height:4px;
  background:var(--surface-3,#2d3548);border-radius:999px;outline:none;cursor:pointer;margin-top:4px}
#__UID__ .bm-slider::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;
  border-radius:50%;background:var(--accent);cursor:pointer;box-shadow:0 0 8px var(--accent)}
#__UID__ .bm-slider::-moz-range-thumb{width:16px;height:16px;border-radius:50%;
  background:var(--accent);border:none;cursor:pointer}
#__UID__ .bm-toggle{display:inline-flex;gap:6px;margin-top:10px}
#__UID__ .bm-tbtn{cursor:pointer;font-size:12px;padding:6px 12px;border-radius:999px;
  border:1px solid var(--border-2,#2d3548);background:transparent;color:var(--text-dim,#9ba3b4)}
#__UID__ .bm-tbtn.active{border-color:var(--accent);color:var(--accent);background:rgba(94,200,255,.08)}
#__UID__ .bm-read{margin-top:8px;font-size:12.5px;color:var(--text)}
#__UID__ .bm-read b{color:var(--accent);font-variant-numeric:tabular-nums}
@keyframes bmfade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
</style>
"""


# Reusable predict-then-check JS. Wired by class under the widget root. Options
# carry data-correct ("1") and data-why (the per-option reason). Reveals the
# .bm-reveal box once any option is chosen.
_PREDICT_JS = """
<script>(function(){
  var root=document.getElementById("__UID__");if(!root)return;
  var opts=root.querySelectorAll(".bm-opt");
  var rev=root.querySelector(".bm-reveal");
  var answered=false;
  opts.forEach(function(b){
    b.addEventListener("click",function(){
      if(answered)return;answered=true;
      opts.forEach(function(o){
        o.disabled=true;
        if(o.getAttribute("data-correct")==="1")o.classList.add("is-correct");
      });
      if(b.getAttribute("data-correct")!=="1")b.classList.add("is-wrong");
      if(rev)rev.classList.add("show");
      var hook=root.querySelector("[data-after-answer]");
      if(hook&&window["__UID__after"])window["__UID__after"]();
    });
  });
})();</script>
"""


def _predict_block(question: str, options, reveal_html: str) -> str:
    """options: list of (label, is_correct_bool)."""
    opt_html = []
    for i, (label, correct) in enumerate(options):
        tag = "ABCDEF"[i]
        opt_html.append(
            f'<button class="bm-opt" data-correct="{"1" if correct else "0"}">'
            f'<span class="bm-tag">{tag}</span>{label}</button>'
        )
    return (
        _PREDICT_CSS
        + f'<div class="bm-q">{question}</div>'
        + '<div class="bm-opts">' + "".join(opt_html) + "</div>"
        + f'<div class="bm-reveal">{reveal_html}</div>'
        + _PREDICT_JS
    )


# ───────────────────────── 1. LEVER CLASSIFIER ─────────────────────────

def lever_classifier() -> str:
    uid = _uid("lev")
    svg = r'''
<svg viewBox="0 0 460 150" class="w-svg" xmlns="http://www.w3.org/2000/svg" style="max-height:160px">
  <!-- the lever beam -->
  <line x1="40" y1="80" x2="420" y2="80" stroke="var(--text-dim,#9ba3b4)" stroke-width="5" stroke-linecap="round"/>
  <!-- fulcrum (triangle) -->
  <path d="M 110 80 L 96 104 L 124 104 Z" fill="var(--warn,#ffb86b)"/>
  <text x="110" y="120" fill="var(--warn,#ffb86b)" font-size="10" text-anchor="middle">Fulcrum (joint)</text>
  <!-- effort arrow (muscle) -->
  <g>
    <line x1="250" y1="80" x2="250" y2="32" stroke="var(--good,#67e8b0)" stroke-width="2.5"/>
    <path d="M 250 30 L 244 42 L 256 42 Z" fill="var(--good,#67e8b0)"/>
    <text x="250" y="24" fill="var(--good,#67e8b0)" font-size="10" text-anchor="middle">Effort (muscle)</text>
  </g>
  <!-- load arrow -->
  <g>
    <line x1="395" y1="80" x2="395" y2="120" stroke="var(--bad,#ff7a7a)" stroke-width="2.5"/>
    <path d="M 395 122 L 389 110 L 401 110 Z" fill="var(--bad,#ff7a7a)"/>
    <text x="395" y="138" fill="var(--bad,#ff7a7a)" font-size="10" text-anchor="middle">Load</text>
  </g>
  <text x="230" y="14" fill="var(--text-dim,#9ba3b4)" font-size="10" text-anchor="middle">Effort between fulcrum &amp; load &rarr; effort arm is SHORT</text>
</svg>'''
    reveal = (
        "<b>Most human limbs are 3rd-class levers.</b> Order along the bone: "
        "fulcrum (joint) → effort (muscle inserting close to the joint) → load "
        "(weight far out in the hand/foot). "
        "<span class='bm-why'>Why it matters:</span> a short effort arm vs a long load arm "
        "means the muscle must generate <b>several times</b> the external load in force — "
        "a force <i>disadvantage</i> traded for a <b>speed &amp; range-of-motion advantage</b> "
        "at the hand/foot. That trade is exactly why a small range of muscle shortening "
        "produces a large, fast limb movement (your sprint stride, your sled drive)."
    )
    body = (
        svg
        + _predict_block(
            "The diagram shows a biceps curl: elbow = fulcrum, biceps = effort, "
            "dumbbell in the hand = load. <b>Which lever class is this?</b>",
            [
                ("1st class — fulcrum in the middle (e.g. neck extension, triceps)", False),
                ("2nd class — load in the middle (e.g. standing calf raise)", False),
                ("3rd class — effort in the middle (most limb muscles)", True),
            ],
            reveal,
        )
    )
    return _shell(uid, "Lever classifier — predict the class", body)


# ───────────────────────── 2. TORQUE / MOMENT-ARM EXPLORER ─────────────

def torque_explorer() -> str:
    uid = _uid("tq")
    # forearm pivots about the elbow; phi = angle from straight-down (0=extended
    # hanging, 90=horizontal "sticking point", 180=fully flexed up).
    svg = r'''
<svg viewBox="0 0 320 230" class="w-svg" id="__UID__-svg" xmlns="http://www.w3.org/2000/svg" style="max-height:240px">
  <!-- upper arm (fixed, vertical) -->
  <line x1="90" y1="40" x2="90" y2="120" stroke="var(--text-dim,#9ba3b4)" stroke-width="6" stroke-linecap="round"/>
  <text x="74" y="80" fill="var(--text-dim,#9ba3b4)" font-size="9" text-anchor="end">upper arm</text>
  <!-- elbow (fulcrum) -->
  <circle cx="90" cy="120" r="6" fill="var(--warn,#ffb86b)"/>
  <text x="90" y="142" fill="var(--warn,#ffb86b)" font-size="9" text-anchor="middle">elbow</text>
  <!-- moment-arm bracket (horizontal dist elbow->weight) -->
  <line id="__UID__-arm" x1="90" y1="190" x2="90" y2="190" stroke="var(--accent,#5ec8ff)" stroke-width="1.5" stroke-dasharray="4 3"/>
  <text id="__UID__-armlbl" x="90" y="204" fill="var(--accent,#5ec8ff)" font-size="9" text-anchor="middle">moment arm</text>
  <!-- forearm (rotates) -->
  <line id="__UID__-fore" x1="90" y1="120" x2="90" y2="200" stroke="var(--good,#67e8b0)" stroke-width="6" stroke-linecap="round"/>
  <!-- weight at hand -->
  <g id="__UID__-hand">
    <rect x="-9" y="-9" width="18" height="18" rx="3" fill="var(--bad,#ff7a7a)"/>
    <line x1="0" y1="9" x2="0" y2="34" stroke="var(--bad,#ff7a7a)" stroke-width="2"/>
    <path d="M 0 36 L -5 26 L 5 26 Z" fill="var(--bad,#ff7a7a)"/>
  </g>
</svg>'''
    controls = (
        '<div class="bm-controls">'
        '<label>Elbow position: <b id="__UID__-anglbl">extended (hanging)</b></label>'
        '<input type="range" min="0" max="180" step="2" value="20" id="__UID__-sl" class="bm-slider">'
        '<div class="bm-read">Resistance torque on the elbow: '
        '<b id="__UID__-tq">low</b> &nbsp;|&nbsp; moment arm = <b id="__UID__-mm">short</b></div>'
        "</div>"
    )
    reveal = (
        "<b>Greatest at ~90° (forearm horizontal).</b> Torque = force × "
        "<b>perpendicular</b> moment arm. Gravity always pulls straight down, so the "
        "moment arm is the <i>horizontal</i> distance from the elbow to the weight — "
        "longest when the forearm is horizontal, near-zero when it points straight down or "
        "straight up. "
        "<span class='bm-why'>Why it matters:</span> that horizontal point is your "
        "<b>sticking point</b> — where the resistance curve peaks. Drag the slider to watch "
        "the moment arm (blue) and torque grow to a max mid-rep, then fall off. It's also why "
        "accommodating resistance (bands/chains) and exercise selection are built around where "
        "torque demand is highest."
    )
    after_js = r'''
<script>(function(){
  var root=document.getElementById("__UID__");if(!root)return;
  var sl=root.querySelector("#__UID__-sl"),
      fore=root.querySelector("#__UID__-fore"),
      hand=root.querySelector("#__UID__-hand"),
      arm=root.querySelector("#__UID__-arm"),
      armlbl=root.querySelector("#__UID__-armlbl"),
      ex=90,ey=120,L=80;
  function up(){
    var phi=+sl.value*Math.PI/180;
    var hx=ex+L*Math.sin(phi), hy=ey+L*Math.cos(phi);
    fore.setAttribute("x2",hx);fore.setAttribute("y2",hy);
    hand.setAttribute("transform","translate("+hx+","+hy+")");
    // moment arm = horizontal distance elbow->hand, drawn near bottom
    var ax=Math.min(ex,hx), bx=Math.max(ex,hx), ay=hy+44;
    arm.setAttribute("x1",ax);arm.setAttribute("x2",bx);
    arm.setAttribute("y1",ay);arm.setAttribute("y2",ay);
    armlbl.setAttribute("x",(ax+bx)/2);armlbl.setAttribute("y",ay+14);
    var ratio=Math.abs(Math.sin(phi)); // 0..1, 1 at horizontal
    var pct=Math.round(ratio*100);
    root.querySelector("#__UID__-tq").textContent=pct+"% of max";
    root.querySelector("#__UID__-mm").textContent=Math.round(L*Math.abs(Math.sin(phi)))+" units";
    var deg=+sl.value, name;
    if(deg<25)name="extended (hanging)";
    else if(deg<70)name="mid-range (rising)";
    else if(deg<110)name="~horizontal — STICKING POINT";
    else if(deg<150)name="past horizontal (easing)";
    else name="fully flexed (top)";
    root.querySelector("#__UID__-anglbl").textContent=name;
  }
  sl.addEventListener("input",up);up();
})();</script>'''
    body = svg + controls + _predict_block(
        "Before you touch the slider — <b>at which elbow angle is the dumbbell's "
        "resistance torque the GREATEST?</b>",
        [
            ("Fully extended (forearm hanging straight down)", False),
            ("About 90° (forearm horizontal)", True),
            ("Fully flexed (forearm pointing up at the top)", False),
        ],
        reveal,
    ) + after_js
    return _shell(uid, "Torque &amp; moment arm — find the sticking point", body, icon="⚖️")


# ───────────────────────── 3. FREE-BODY: SQUAT GRF ─────────────────────

def free_body_squat() -> str:
    uid = _uid("fb")
    svg = r'''
<svg viewBox="0 0 360 240" class="w-svg" id="__UID__-svg" xmlns="http://www.w3.org/2000/svg" style="max-height:250px">
  <!-- floor -->
  <line x1="20" y1="210" x2="340" y2="210" stroke="var(--text-dim,#9ba3b4)" stroke-width="2"/>
  <!-- foot -->
  <line x1="150" y1="210" x2="210" y2="210" stroke="var(--text)" stroke-width="5" stroke-linecap="round"/>
  <text x="150" y="226" fill="var(--text-dim,#9ba3b4)" font-size="9">heel</text>
  <text x="208" y="226" fill="var(--text-dim,#9ba3b4)" font-size="9" text-anchor="end">toes</text>
  <!-- midfoot marker -->
  <circle cx="180" cy="210" r="3" fill="var(--good,#67e8b0)"/>
  <text x="180" y="200" fill="var(--good,#67e8b0)" font-size="9" text-anchor="middle">midfoot</text>
  <!-- stick lifter: ankle(180,210) knee hip shoulder + bar -->
  <g stroke="var(--accent,#5ec8ff)" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <polyline id="__UID__-leg" points="180,210 150,160 178,120 172,70"/>
  </g>
  <circle id="__UID__-knee" cx="150" cy="160" r="4" fill="var(--accent,#5ec8ff)"/>
  <circle id="__UID__-hip" cx="178" cy="120" r="4" fill="var(--accent,#5ec8ff)"/>
  <!-- barbell on the back / over a point -->
  <circle id="__UID__-bar" cx="180" cy="78" r="8" fill="var(--warn,#ffb86b)"/>
  <text id="__UID__-barlbl" x="196" y="74" fill="var(--warn,#ffb86b)" font-size="9">bar</text>
  <!-- GRF / load vertical line -->
  <line id="__UID__-grf" x1="180" y1="210" x2="180" y2="60" stroke="var(--bad,#ff7a7a)" stroke-width="1.5" stroke-dasharray="5 4"/>
  <text x="270" y="120" fill="var(--bad,#ff7a7a)" font-size="9" text-anchor="middle">load line</text>
  <text x="270" y="133" fill="var(--bad,#ff7a7a)" font-size="9" text-anchor="middle">(stays vertical)</text>
</svg>'''
    toggle = (
        '<div class="bm-toggle" data-after-answer>'
        '<button class="bm-tbtn active" id="__UID__-good">Bar over midfoot</button>'
        '<button class="bm-tbtn" id="__UID__-drift">Bar drifts forward</button>'
        "</div>"
        '<div class="bm-read" id="__UID__-msg">Balanced: the load line falls through the '
        "midfoot — knee &amp; hip moment arms stay modest and sharable.</div>"
    )
    reveal = (
        "<b>Over the midfoot.</b> Gravity on the bar acts in a straight vertical line. "
        "If that line falls through the midfoot, the whole system is balanced and the "
        "knee- and hip-extensor moment arms (horizontal distance from each joint to the "
        "line) stay moderate. "
        "<span class='bm-why'>Why it matters:</span> let the bar drift toward the toes and "
        "the <b>knee</b> moment arm balloons — quad torque demand spikes and you fight to "
        "stay balanced. Toggle the buttons to see the load line and joint distances shift. "
        "Same rule governs the deadlift (bar over midfoot, against the shins) and your sled "
        "drive (keep the resultant force line efficient)."
    )
    after_js = r'''
<script>(function(){
  var root=document.getElementById("__UID__");if(!root)return;
  var grf=root.querySelector("#__UID__-grf"),
      bar=root.querySelector("#__UID__-bar"),
      barlbl=root.querySelector("#__UID__-barlbl"),
      msg=root.querySelector("#__UID__-msg"),
      gb=root.querySelector("#__UID__-good"),
      db=root.querySelector("#__UID__-drift"),
      leg=root.querySelector("#__UID__-leg");
  function set(mode){
    if(mode==="good"){
      gb.classList.add("active");db.classList.remove("active");
      grf.setAttribute("x1",180);grf.setAttribute("x2",180);
      bar.setAttribute("cx",180);barlbl.setAttribute("x",196);
      bar.setAttribute("fill","var(--good,#67e8b0)");
      leg.setAttribute("points","180,210 150,160 178,120 172,70");
      msg.innerHTML="Balanced: the load line falls through the midfoot — knee &amp; hip moment arms stay modest and sharable.";
    }else{
      db.classList.add("active");gb.classList.remove("active");
      grf.setAttribute("x1",214);grf.setAttribute("x2",214);
      bar.setAttribute("cx",214);barlbl.setAttribute("x",230);
      bar.setAttribute("fill","var(--bad,#ff7a7a)");
      leg.setAttribute("points","180,210 138,160 178,120 196,72");
      msg.innerHTML="Drifted to the toes: the load line is now forward of the knee — the <b>knee moment arm balloons</b>, quad torque spikes, and balance is lost.";
    }
  }
  gb.addEventListener("click",function(){set("good");});
  db.addEventListener("click",function(){set("drift");});
})();</script>'''
    body = svg + _predict_block(
        "Side view of a squat. For the most efficient, balanced lift, the barbell should "
        "stay vertically aligned over which point of the foot?",
        [
            ("The toes / ball of the foot", False),
            ("The midfoot", True),
            ("The heel", False),
        ],
        reveal,
    ) + toggle + after_js
    return _shell(uid, "Free-body diagram — where does the load line fall?", body, icon="\U0001f4d0")


# ───────────────────────── 4. BAR-PATH TRACER ──────────────────────────

def bar_path_tracer() -> str:
    uid = _uid("bp")
    svg = r'''
<svg viewBox="0 0 360 220" class="w-svg" xmlns="http://www.w3.org/2000/svg" style="max-height:230px">
  <line x1="40" y1="200" x2="320" y2="200" stroke="var(--text-dim,#9ba3b4)" stroke-width="2"/>
  <text x="180" y="216" fill="var(--text-dim,#9ba3b4)" font-size="9" text-anchor="middle">midfoot reference (dotted = ideal vertical path)</text>
  <line x1="120" y1="40" x2="120" y2="200" stroke="var(--text-dim,#9ba3b4)" stroke-width="1" stroke-dasharray="3 4"/>
  <line x1="240" y1="40" x2="240" y2="200" stroke="var(--text-dim,#9ba3b4)" stroke-width="1" stroke-dasharray="3 4"/>
  <!-- PATH A: efficient vertical -->
  <path d="M 120 190 L 120 50" fill="none" stroke="var(--good,#67e8b0)" stroke-width="3"/>
  <circle cx="120" cy="50" r="6" fill="var(--good,#67e8b0)"/>
  <text x="120" y="32" fill="var(--good,#67e8b0)" font-size="11" text-anchor="middle" font-weight="700">A</text>
  <!-- PATH B: forward drift S-curve -->
  <path d="M 240 190 C 200 150 285 120 240 50" fill="none" stroke="var(--bad,#ff7a7a)" stroke-width="3"/>
  <circle cx="240" cy="50" r="6" fill="var(--bad,#ff7a7a)"/>
  <text x="240" y="32" fill="var(--bad,#ff7a7a)" font-size="11" text-anchor="middle" font-weight="700">B</text>
  <text x="300" y="120" fill="var(--bad,#ff7a7a)" font-size="9" text-anchor="middle">wasted</text>
  <text x="300" y="132" fill="var(--bad,#ff7a7a)" font-size="9" text-anchor="middle">horizontal</text>
</svg>'''
    reveal = (
        "<b>Path A (the straight vertical line).</b> The most mechanically efficient bar "
        "path is as close to vertical over the midfoot as the lift allows. "
        "<span class='bm-why'>Why it matters:</span> every centimetre the bar travels "
        "horizontally is work that doesn't raise the load and that lengthens a joint moment "
        "arm — more torque demand, more energy cost, more chance of missing the lift. "
        "Path B's forward loop wastes horizontal travel and spikes joint torque mid-pull. "
        "(In the deadlift the bar still tracks the shins; “vertical” means over the "
        "midfoot, not literally grazing a plumb line.)"
    )
    body = svg + _predict_block(
        "Two bar paths from the floor to lockout. <b>Which one is more mechanically "
        "efficient?</b>",
        [
            ("Path A — the straight vertical line over the midfoot", True),
            ("Path B — the forward-looping curve", False),
            ("Both cost the same; only the weight matters", False),
        ],
        reveal,
    )
    return _shell(uid, "Bar-path tracer — pick the efficient path", body, icon="\U0001f3cb️")


# ───────────────────────── REGISTRY + RENDER ───────────────────────────

# topic_id -> ordered list of widget builders. Designed so no single daily page
# gets more than two heavy SVG widgets (today's lesson + spaced reviews stack).
BIOMECH = {
    "biomech_levers": [lever_classifier, torque_explorer],
    "force_velocity_length_tension": [torque_explorer],
    "ex_squat": [free_body_squat, bar_path_tracer],
    "ex_deadlift": [bar_path_tracer],
    "ex_press": [bar_path_tracer],
}


def render(topic_id: str) -> str:
    fns = BIOMECH.get(topic_id)
    if not fns:
        return ""
    return "\n".join(fn() for fn in fns)
