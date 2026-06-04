"""
Animated visual step-throughs for the CSCS daily study site.

Each sequential process (a lift, a metabolic pathway, a physiological cascade)
gets a `_stepper(...)` widget: one bespoke SVG *scene* per step that cross-fades
on navigation, with internal entrance + looping animations that replay every
time a scene becomes active. Controls: Prev / Next / Auto-play + clickable dots.

The generator calls `render(topic_id)`; widgets.render() prefers a stepper when
one exists and still appends any existing calculator/chart widget after it.

Design notes
------------
* viewBox is a constant 440 x 240 so every scene shares one coordinate space.
* Colours come from the per-topic motif via CSS vars (--accent, --accent-2),
  with hard fallbacks so the SVG also looks right in isolation.
* No f-strings around JS — %-formatting + json.dumps keep braces/quotes safe.
"""
from __future__ import annotations

import json

VB = "0 0 440 240"
GROUND_Y = 206

# Palette helpers (CSS vars w/ fallbacks)
AC = "var(--accent,#5ec8ff)"
A2 = "var(--accent-2,#c08fff)"
INK = "var(--text,#e8ebf2)"
DIM = "var(--text-dim,#9ba3b4)"
GOOD = "var(--good,#67e8b0)"
WARN = "var(--warn,#ffb86b)"
BAD = "var(--bad,#ff7a7a)"


def _wrap(widget_id: str, title: str, body: str, hint: str = "") -> str:
    hint_html = '<div class="w-hint">%s</div>' % hint if hint else ""
    return (
        '\n<div class="widget" id="%s">\n'
        '  <div class="w-head"><span class="w-icon">&#9654;</span>'
        '<span class="w-title">%s</span></div>\n'
        '  <div class="w-body">%s</div>\n  %s\n</div>\n'
    ) % (widget_id, title, body, hint_html)


# Defined once per page; whichever stepper renders first installs the engine.
ENGINE = r"""
<script>
/* ============================================================
   SAEngine v2  (SA_V2)  — offline-first animated step engine.
   New over v1:
     - continuous joint TWEENING for figure steppers (Rive-style
       state blending) so the athlete moves instead of jumping;
     - drag-to-scrub on the stage + a range slider (GSAP-scrub idea);
     - smoother eased cross-fade for diagram steppers;
     - Sagittal <-> Frontal plane toggle for the lifts;
     - progressive Three.js 3D view (CDN when online, graceful
       offline fallback) for the lifts.
   Figure keyframes are auto-extracted from the rendered SVG
   (data-joints on .sa-fig), so the python step builders stay
   untouched. Any failure degrades to the old discrete behaviour.
   ============================================================ */
if (!window.SAEngine) {
  var SVGNS = "http://www.w3.org/2000/svg";
  function saEl(tag, attrs) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) { e.setAttribute(k, attrs[k]); }
    return e;
  }
  function saVar(el, name, fb) {
    try { var v = getComputedStyle(el).getPropertyValue(name).trim(); return v || fb; }
    catch (e) { return fb; }
  }
  function saRGB(c) {
    c = (c || "").trim();
    if (c.charAt(0) === "#") {
      if (c.length === 4) { return [parseInt(c[1] + c[1], 16), parseInt(c[2] + c[2], 16), parseInt(c[3] + c[3], 16)]; }
      return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
    }
    var m = c.match(/(\d+\.?\d*)/g);
    if (m && m.length >= 3) { return [+m[0], +m[1], +m[2]]; }
    return [94, 200, 255];
  }
  function saMix(a, b, t) {
    var A = saRGB(a), B = saRGB(b);
    return "rgb(" + Math.round(A[0] + (B[0] - A[0]) * t) + "," + Math.round(A[1] + (B[1] - A[1]) * t) + "," + Math.round(A[2] + (B[2] - A[2]) * t) + ")";
  }
  function saEase(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function lp(a, b, f) { return a + (b - a) * f; }
  function lpt(a, b, f) { return [lp(a[0], b[0], f), lp(a[1], b[1], f)]; }

  /* read sagittal keyframes straight out of the rendered scenes */
  function extractFrames(scenes) {
    var out = [], any = false;
    for (var k = 0; k < scenes.length; k++) {
      var fig = scenes[k].querySelector(".sa-fig[data-joints]");
      if (!fig) { out.push(null); continue; }
      any = true;
      var fr = { c: fig.getAttribute("data-c") || "ac", bar: null };
      try { fr.j = JSON.parse(fig.getAttribute("data-joints")); } catch (e) { return null; }
      var db = fig.getAttribute("data-bar");
      if (db) { var p = db.split(","); fr.bar = [+p[0], +p[1]]; }
      else { var pl = scenes[k].querySelector(".sa-plate[data-bar]"); if (pl) { var pp = pl.getAttribute("data-bar").split(","); fr.bar = [+pp[0], +pp[1]]; } }
      out.push(fr);
    }
    if (!any) return null;
    var last = null;            // carry a frame across any annotation-only scene
    for (var i = 0; i < out.length; i++) { if (out[i]) last = out[i]; else if (last) out[i] = last; }
    for (var j2 = 0, seed = null; j2 < out.length; j2++) { if (!out[j2]) { if (!seed) { for (var z = 0; z < out.length; z++) { if (out[z]) { seed = out[z]; break; } } } out[j2] = seed; } }
    return out;
  }

  /* ---------- side-view skeleton (mirrors python _figure) ---------- */
  function buildSkelSide(svg, inkCol) {
    var g = saEl("g", { "class": "sa-skel sa-skel-side" });
    var la = { fill: "none", "stroke-width": 7, "stroke-linecap": "round", "stroke-linejoin": "round" };
    var lines = {};
    ["nh", "hk", "ka", "at", "se", "eh"].forEach(function (id) { var ln = saEl("line", la); lines[id] = ln; g.appendChild(ln); });
    var head = saEl("circle", {}); g.appendChild(head);
    var barG = saEl("g", { "class": "sa-bar" });
    var barLine = saEl("line", { "stroke-width": 5, "stroke-linecap": "round", stroke: inkCol });
    var plL = saEl("circle", { r: 14 }), plR = saEl("circle", { r: 14 });
    var hubL = saEl("circle", { r: 5, fill: inkCol }), hubR = saEl("circle", { r: 5, fill: inkCol });
    barG.appendChild(barLine); barG.appendChild(plL); barG.appendChild(plR); barG.appendChild(hubL); barG.appendChild(hubR);
    g.appendChild(barG); svg.appendChild(g);
    return { g: g, lines: lines, head: head, barG: barG, barLine: barLine, plL: plL, plR: plR, hubL: hubL, hubR: hubR };
  }
  function drawSide(r, A, B, f, color, a2) {
    var ja = A.j, jb = B.j;
    function J(key) { return lpt(ja[key], jb[key], f); }
    var neck = J("neck"), hip = J("hip"), knee = J("knee"), ankle = J("ankle"), toe = J("toe"), sh = J("shoulder"), elb = J("elbow"), hand = J("hand");
    function set(ln, p, q) { ln.setAttribute("x1", p[0]); ln.setAttribute("y1", p[1]); ln.setAttribute("x2", q[0]); ln.setAttribute("y2", q[1]); ln.setAttribute("stroke", color); }
    set(r.lines.nh, neck, hip); set(r.lines.hk, hip, knee); set(r.lines.ka, knee, ankle); set(r.lines.at, ankle, toe); set(r.lines.se, sh, elb); set(r.lines.eh, elb, hand);
    var hx = lp(ja.head[0], jb.head[0], f), hy = lp(ja.head[1], jb.head[1], f), hr = lp(ja.head[2], jb.head[2], f);
    r.head.setAttribute("cx", hx); r.head.setAttribute("cy", hy); r.head.setAttribute("r", hr); r.head.setAttribute("fill", color);
    if (A.bar || B.bar) {
      var ba = A.bar || B.bar, bb = B.bar || A.bar;
      var bx = lp(ba[0], bb[0], f), by = lp(ba[1], bb[1], f);
      r.barG.style.opacity = (A.bar && B.bar) ? 1 : (A.bar ? (1 - f) : f);
      r.barLine.setAttribute("x1", bx - 62); r.barLine.setAttribute("y1", by); r.barLine.setAttribute("x2", bx + 62); r.barLine.setAttribute("y2", by);
      r.plL.setAttribute("cx", bx - 62); r.plL.setAttribute("cy", by); r.plL.setAttribute("fill", a2);
      r.plR.setAttribute("cx", bx + 62); r.plR.setAttribute("cy", by); r.plR.setAttribute("fill", a2);
      r.hubL.setAttribute("cx", bx - 62); r.hubL.setAttribute("cy", by); r.hubR.setAttribute("cx", bx + 62); r.hubR.setAttribute("cy", by);
    } else { r.barG.style.opacity = 0; }
  }

  /* ---------- frontal-view skeleton (symmetric) ---------- */
  function buildSkelFront(svg, inkCol) {
    var g = saEl("g", { "class": "sa-skel sa-skel-front" });
    g.style.display = "none";
    var la = { fill: "none", "stroke-width": 7, "stroke-linecap": "round", "stroke-linejoin": "round" };
    var lines = {};
    ["torso", "legLU", "legLD", "legRU", "legRD", "armL", "armR"].forEach(function (id) { var ln = saEl("line", la); lines[id] = ln; g.appendChild(ln); });
    var head = saEl("circle", {}); g.appendChild(head);
    var barG = saEl("g", { "class": "sa-bar" });
    var barLine = saEl("line", { "stroke-width": 5, "stroke-linecap": "round", stroke: inkCol });
    var plL = saEl("circle", { r: 13 }), plR = saEl("circle", { r: 13 });
    barG.appendChild(barLine); barG.appendChild(plL); barG.appendChild(plR); g.appendChild(barG);
    var cue = saEl("text", { "class": "sa-cue-lbl", "text-anchor": "middle", "font-size": 11, "font-weight": 700 });
    g.appendChild(cue); svg.appendChild(g);
    return { g: g, lines: lines, head: head, barG: barG, barLine: barLine, plL: plL, plR: plR, cue: cue };
  }
  function drawFront(r, A, B, f, color, a2, accent) {
    var ja = A.j, jb = B.j;
    function J(key) { return lpt(ja[key], jb[key], f); }
    var neck = J("neck"), hipC = J("hipC"), shL = J("shL"), shR = J("shR"), handL = J("handL"), handR = J("handR"), kneeL = J("kneeL"), kneeR = J("kneeR"), ankleL = J("ankleL"), ankleR = J("ankleR");
    function set(ln, p, q) { ln.setAttribute("x1", p[0]); ln.setAttribute("y1", p[1]); ln.setAttribute("x2", q[0]); ln.setAttribute("y2", q[1]); ln.setAttribute("stroke", color); }
    set(r.lines.torso, neck, hipC); set(r.lines.legLU, hipC, kneeL); set(r.lines.legLD, kneeL, ankleL); set(r.lines.legRU, hipC, kneeR); set(r.lines.legRD, kneeR, ankleR); set(r.lines.armL, shL, handL); set(r.lines.armR, shR, handR);
    var hx = lp(ja.head[0], jb.head[0], f), hy = lp(ja.head[1], jb.head[1], f), hr = lp(ja.head[2], jb.head[2], f);
    r.head.setAttribute("cx", hx); r.head.setAttribute("cy", hy); r.head.setAttribute("r", hr); r.head.setAttribute("fill", color);
    if (A.bar || B.bar) {
      var ba = A.bar || B.bar, bb = B.bar || A.bar;
      var bx = lp(ba[0], bb[0], f), by = lp(ba[1], bb[1], f);
      r.barG.style.opacity = (A.bar && B.bar) ? 1 : (A.bar ? (1 - f) : f);
      r.barLine.setAttribute("x1", bx - 52); r.barLine.setAttribute("y1", by); r.barLine.setAttribute("x2", bx + 52); r.barLine.setAttribute("y2", by);
      r.plL.setAttribute("cx", bx - 52); r.plL.setAttribute("cy", by); r.plL.setAttribute("fill", a2);
      r.plR.setAttribute("cx", bx + 52); r.plR.setAttribute("cy", by); r.plR.setAttribute("fill", a2);
    } else { r.barG.style.opacity = 0; }
    var cueTxt = (f < 0.5 ? A.cue : B.cue) || "";
    r.cue.textContent = cueTxt; r.cue.setAttribute("x", 220); r.cue.setAttribute("y", 226); r.cue.setAttribute("fill", accent); r.cue.style.opacity = cueTxt ? 0.92 : 0;
  }

  window.SA = {};
  window.SAEngine = {
    init: function (sid, steps, opts) {
      try { this._init(sid, steps, opts || {}); }
      catch (err) { try { this._fallback(sid, steps); } catch (e2) {} }
    },
    _fallback: function (sid, steps) {
      var _fr0 = document.getElementById(sid); if (_fr0) _fr0.classList.remove("sa-figure-mode");
      var root = document.getElementById(sid); if (!root) return;
      var scenes = root.querySelectorAll(".sa-scene"), dots = root.querySelectorAll(".sa-dot");
      var bar = document.getElementById(sid + "-bar"), curEl = document.getElementById(sid + "-cur");
      var labEl = document.getElementById(sid + "-label"), desEl = document.getElementById(sid + "-desc");
      var n = steps.length, cur = 0;
      function show(i) {
        cur = ((i % n) + n) % n;
        for (var k = 0; k < scenes.length; k++) { scenes[k].classList.toggle("active", k === cur); scenes[k].style.opacity = ""; }
        for (var d = 0; d < dots.length; d++) { dots[d].classList.toggle("active", d === cur); dots[d].classList.toggle("past", d < cur); }
        if (bar) bar.style.width = ((cur + 1) / n * 100) + "%";
        if (curEl) curEl.textContent = cur + 1;
        if (labEl) labEl.textContent = steps[cur][0];
        if (desEl) desEl.textContent = steps[cur][1];
      }
      window.SA[sid] = { next: function () { show(cur + 1); }, prev: function () { show(cur - 1); }, go: function (i) { show(i); }, auto: function () {}, plane: function () {}, three: function () {} };
      for (var j = 0; j < dots.length; j++) { (function (b) { b.addEventListener("click", function () { show(parseInt(b.getAttribute("data-i"))); }); })(dots[j]); }
      show(0);
    },
    _init: function (sid, steps, opts) {
      var root = document.getElementById(sid); if (!root) return;
      var stage = root.querySelector(".sa-stage");
      var svg = root.querySelector(".sa-svg");
      var scenes = root.querySelectorAll(".sa-scene");
      var dots = root.querySelectorAll(".sa-dot");
      var bar = document.getElementById(sid + "-bar");
      var curEl = document.getElementById(sid + "-cur");
      var labEl = document.getElementById(sid + "-label");
      var desEl = document.getElementById(sid + "-desc");
      var aBtn = document.getElementById(sid + "-autobtn");
      var slider = document.getElementById(sid + "-scrub");
      var cap = root.querySelector(".sa-caption");
      var n = steps.length;
      var framesS = extractFrames(scenes);
      var framesF = opts.framesF || null;
      var lift = !!opts.lift;
      var t = 0, raf = null, playing = false, plane = "side";
      var pal = { ac: saVar(stage, "--accent", "#5ec8ff"), a2: saVar(stage, "--accent-2", "#c08fff"), good: saVar(stage, "--good", "#67e8b0"), warn: saVar(stage, "--warn", "#ffb86b"), bad: saVar(stage, "--bad", "#ff7a7a") };
      var ink = saVar(stage, "--text", "#e8ebf2");
      function col(key) { return pal[key] || pal.ac; }
      var skelS = null, skelF = null;
      if (framesS) {
        root.classList.add("sa-figure-mode");
        skelS = buildSkelSide(svg, ink);
        if (framesF) skelF = buildSkelFront(svg, ink);
      }
      function curFrames() { return (plane === "front" && framesF) ? framesF : framesS; }
      function drawFig(tt) {
        var F = curFrames(); if (!F) return;
        var span = F.length - 1;
        var u = (n > 1) ? (tt / (n - 1)) * span : 0;
        var i = Math.max(0, Math.min(span, Math.floor(u)));
        var j = Math.min(span, i + 1);
        var f = saEase(u - i);
        var A = F[i], B = F[j];
        var c = saMix(col(A.c), col(B.c), f);
        if (plane === "front" && skelF) { skelS.g.style.display = "none"; skelF.g.style.display = ""; drawFront(skelF, A, B, f, c, pal.a2, pal.good); }
        else { if (skelF) skelF.g.style.display = "none"; skelS.g.style.display = ""; drawSide(skelS, A, B, f, c, pal.a2); }
      }
      function setScenes(tt, settle) {
        if (scenes.length === 0) return;
        if (plane === "front") { for (var q = 0; q < scenes.length; q++) { scenes[q].classList.remove("active"); scenes[q].style.opacity = "0"; } return; }
        var near = Math.round(tt);
        for (var k = 0; k < scenes.length; k++) {
          var sc = scenes[k];
          if (settle) { sc.classList.toggle("active", k === near); sc.style.opacity = ""; }
          else { sc.classList.remove("active"); var d = Math.abs(k - tt); sc.style.opacity = d < 1 ? (1 - d).toFixed(3) : "0"; }
        }
      }
      function updMeta(idx) {
        if (bar) bar.style.width = ((idx + 1) / n * 100) + "%";
        if (curEl) curEl.textContent = idx + 1;
        if (labEl) labEl.textContent = steps[idx][0];
        if (desEl) desEl.textContent = steps[idx][1];
        for (var d = 0; d < dots.length; d++) { dots[d].classList.toggle("active", d === idx); dots[d].classList.toggle("past", d < idx); }
        if (cap) { cap.classList.remove("flash"); void cap.offsetWidth; cap.classList.add("flash"); }
      }
      function render(tt, settle) {
        t = Math.max(0, Math.min(n - 1, tt));
        if (framesS) drawFig(t);
        setScenes(t, settle);
        if (slider && document.activeElement !== slider) slider.value = String(Math.round(t / (n - 1) * 1000));
        if (settle) updMeta(Math.round(t));
      }
      function animateT(from, to, dur, done) {
        if (raf) cancelAnimationFrame(raf);
        var st = performance.now();
        function loop(now) { var p = Math.min(1, (now - st) / dur), e = saEase(p); render(from + (to - from) * e, false); if (p < 1) raf = requestAnimationFrame(loop); else { raf = null; if (done) done(); } }
        raf = requestAnimationFrame(loop);
      }
      function settleTo(target) { stopPlay(); animateT(t, target, 360, function () { render(target, true); }); }
      function startPlay() {
        playing = true; if (aBtn) aBtn.innerHTML = "&#9208; Pause";
        var seq = (Math.round(t) >= n - 1) ? 0 : Math.round(t);
        render(seq, true);
        function stepNext() { if (!playing) return; if (seq >= n - 1) { stopPlay(); return; } animateT(seq, seq + 1, 900, function () { render(seq + 1, true); seq++; setTimeout(stepNext, 620); }); }
        setTimeout(stepNext, 300);
      }
      function stopPlay() { playing = false; if (raf) { cancelAnimationFrame(raf); raf = null; } if (aBtn) aBtn.innerHTML = "&#9205; Auto-play"; }
      function updPlaneBtn() { var pb = document.getElementById(sid + "-planebtn"); if (pb) { pb.innerHTML = (plane === "side" ? "&#8634; Front view" : "&#8634; Side view"); pb.classList.toggle("on", plane === "front"); } }
      var api = {
        next: function () { settleTo(Math.min(n - 1, Math.round(t) + 1)); },
        prev: function () { settleTo(Math.max(0, Math.round(t) - 1)); },
        go: function (i) { settleTo(Math.max(0, Math.min(n - 1, i))); },
        auto: function () { if (playing) stopPlay(); else startPlay(); },
        plane: function () { if (!framesF) return; plane = (plane === "side") ? "front" : "side"; root.setAttribute("data-plane", plane); updPlaneBtn(); render(t, true); },
        three: function () { SAEngine._three(sid, framesS, pal, ink); }
      };
      if (slider) {
        slider.addEventListener("input", function () { stopPlay(); render(slider.value / 1000 * (n - 1), false); });
        slider.addEventListener("change", function () { settleTo(Math.round(t)); });
      }
      var dragging = false;
      function px2t(clientX) { var rc = stage.getBoundingClientRect(); var x = (clientX - rc.left) / rc.width; return Math.max(0, Math.min(1, x)) * (n - 1); }
      stage.addEventListener("pointerdown", function (e) { if (e.target.closest && e.target.closest("button")) return; dragging = true; try { stage.setPointerCapture(e.pointerId); } catch (x) {} stopPlay(); stage.classList.add("sa-grabbing"); render(px2t(e.clientX), false); });
      stage.addEventListener("pointermove", function (e) { if (dragging) render(px2t(e.clientX), false); });
      function endDrag() { if (!dragging) return; dragging = false; stage.classList.remove("sa-grabbing"); settleTo(Math.round(t)); }
      stage.addEventListener("pointerup", endDrag); stage.addEventListener("pointercancel", endDrag); stage.addEventListener("pointerleave", endDrag);
      for (var jx = 0; jx < dots.length; jx++) { (function (b) { b.addEventListener("click", function () { api.go(parseInt(b.getAttribute("data-i"))); }); })(dots[jx]); }
      window.SA[sid] = api;
      updPlaneBtn();
      render(0, true);
    },
    _three: function (sid, frames, pal, ink) {
      var host = document.getElementById(sid + "-3d");
      var btn = document.getElementById(sid + "-3dbtn");
      if (!host || !frames) return;
      if (host.getAttribute("data-on") === "1") {
        host.setAttribute("data-on", "0"); host.style.display = "none";
        if (host._stop) { host._stop(); host._stop = null; }
        host.innerHTML = ""; if (btn) btn.innerHTML = "&#9673; 3D view"; return;
      }
      host.setAttribute("data-on", "1"); host.style.display = "block";
      host.innerHTML = '<div class="sa-3d-msg">Loading 3D&hellip;</div>';
      if (btn) btn.innerHTML = "&#9673; Loading&hellip;";
      import("https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js")
        .then(function (THREE) { host.innerHTML = ""; SAEngine._build3D(THREE, host, frames, pal, ink); if (btn) btn.innerHTML = "&#9673; Hide 3D"; })
        .catch(function () { host.innerHTML = '<div class="sa-3d-msg">3D view needs an internet connection &mdash; the side &amp; front views above work offline.</div>'; if (btn) btn.innerHTML = "&#9673; 3D view"; });
    },
    _build3D: function (THREE, host, frames, pal, ink) {
      function rgbHex(c) { var r = saRGB(c); return (r[0] << 16) + (r[1] << 8) + r[2]; }
      var W = host.clientWidth || 460, H = 280;
      var scene = new THREE.Scene();
      var cam = new THREE.PerspectiveCamera(42, W / H, 0.1, 100); cam.position.set(0, 1.2, 11);
      var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); renderer.setSize(W, H); host.appendChild(renderer.domElement);
      scene.add(new THREE.AmbientLight(0xffffff, 0.75));
      var dl = new THREE.DirectionalLight(0xffffff, 0.9); dl.position.set(4, 8, 6); scene.add(dl);
      var grid = new THREE.GridHelper(14, 14, 0x44506a, 0x2a3245); grid.position.y = -3.4; scene.add(grid);
      var group = new THREE.Group(); scene.add(group);
      var mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(rgbHex(pal.ac)), roughness: 0.5, metalness: 0.1 });
      var barMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(rgbHex(ink)), roughness: 0.4 });
      var plMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(rgbHex(pal.a2)), roughness: 0.5 });
      function V(j) { return new THREE.Vector3((j[0] - 220) / 26, (206 - j[1]) / 26, 0); }
      var joints = {}, bones = [], jointKeys = ["head", "neck", "shoulder", "elbow", "hand", "hip", "knee", "ankle", "toe"];
      jointKeys.forEach(function (k) { var s = new THREE.Mesh(new THREE.SphereGeometry(k === "head" ? 0.62 : 0.26, 16, 16), mat); group.add(s); joints[k] = s; });
      var boneDefs = [["neck", "hip"], ["hip", "knee"], ["knee", "ankle"], ["ankle", "toe"], ["shoulder", "elbow"], ["elbow", "hand"]];
      boneDefs.forEach(function () { var cylL = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 1, 12), mat); var cylR = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 1, 12), mat); group.add(cylL); group.add(cylR); bones.push([cylL, cylR]); });
      var ZOFF = 0.55, YUP = new THREE.Vector3(0, 1, 0);
      function place(cyl, a, b, z) { var av = a.clone(), bv = b.clone(); av.z = z; bv.z = z; var mid = av.clone().add(bv).multiplyScalar(0.5); cyl.position.copy(mid); var dir = bv.clone().sub(av); var len = dir.length(); cyl.scale.set(1, Math.max(0.001, len), 1); cyl.quaternion.setFromUnitVectors(YUP, dir.normalize()); }
      var barShaft = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 4.6, 12), barMat); barShaft.rotation.z = Math.PI / 2;
      var plate1 = new THREE.Mesh(new THREE.CylinderGeometry(0.95, 0.95, 0.18, 20), plMat); var plate2 = new THREE.Mesh(new THREE.CylinderGeometry(0.95, 0.95, 0.18, 20), plMat);
      plate1.rotation.z = Math.PI / 2; plate2.rotation.z = Math.PI / 2;
      var barGroup = new THREE.Group(); barGroup.add(barShaft); barGroup.add(plate1); barGroup.add(plate2); plate1.position.x = -2.3; plate2.position.x = 2.3; group.add(barGroup);
      function frameVerts(F) { var o = {}; jointKeys.forEach(function (k) { o[k] = V(F.j[k]); }); o.bar = F.bar ? V(F.bar) : null; return o; }
      function applyFrame(va, vb, f) {
        jointKeys.forEach(function (k) { var p = va[k].clone().lerp(vb[k], f); joints[k].position.set(p.x, p.y, 0); });
        boneDefs.forEach(function (d, i) { var a = va[d[0]].clone().lerp(vb[d[0]], f); var b = va[d[1]].clone().lerp(vb[d[1]], f); place(bones[i][0], a, b, ZOFF); place(bones[i][1], a, b, -ZOFF); });
        if (va.bar || vb.bar) { var ba = va.bar || vb.bar, bb = vb.bar || va.bar; var p = ba.clone().lerp(bb, f); barGroup.visible = true; barGroup.position.set(0, p.y, 0); } else { barGroup.visible = false; }
      }
      var verts = frames.map(frameVerts), nF = verts.length;
      var rotY = 0.5, rotX = 0.05, down = false, lx = 0, ly = 0;
      renderer.domElement.style.cursor = "grab";
      renderer.domElement.addEventListener("pointerdown", function (e) { down = true; lx = e.clientX; ly = e.clientY; renderer.domElement.style.cursor = "grabbing"; });
      window.addEventListener("pointermove", function (e) { if (!down) return; rotY += (e.clientX - lx) * 0.01; rotX += (e.clientY - ly) * 0.008; rotX = Math.max(-0.8, Math.min(0.8, rotX)); lx = e.clientX; ly = e.clientY; });
      window.addEventListener("pointerup", function () { down = false; renderer.domElement.style.cursor = "grab"; });
      var stopped = false, clock = 0, last = performance.now();
      function frame(now) {
        if (stopped) return;
        var dt = Math.min(0.05, (now - last) / 1000); last = now; clock += dt * 0.55;
        var phase = nF > 1 ? (clock % nF) : 0; var i = Math.floor(phase), j = (i + 1) % nF, f = saEase(phase - i);
        applyFrame(verts[i], verts[j], f);
        if (!down) rotY += dt * 0.25; group.rotation.y = rotY; group.rotation.x = rotX;
        renderer.render(scene, cam); requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
      host._stop = function () { stopped = true; try { renderer.dispose(); } catch (e) {} if (renderer.domElement && renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement); };
      window.addEventListener("resize", function () { var w = host.clientWidth || W; renderer.setSize(w, H); cam.aspect = w / H; cam.updateProjectionMatrix(); });
    }
  };
}
</script>
"""


FRONTAL = {
    "ex_squat": [
        {"c": "ac", "bar": [220, 82], "cue": "stance set", "j": {"head": [220, 58, 13], "neck": [220, 78], "hipC": [220, 138], "shL": [200, 88], "shR": [240, 88], "handL": [196, 80], "handR": [244, 80], "kneeL": [208, 170], "kneeR": [232, 170], "ankleL": [208, 205], "ankleR": [232, 205]}},
        {"c": "a2", "bar": [220, 120], "cue": "knees track out — not caving in", "j": {"head": [220, 98, 13], "neck": [220, 116], "hipC": [220, 176], "shL": [200, 124], "shR": [240, 124], "handL": [196, 118], "handR": [244, 118], "kneeL": [196, 178], "kneeR": [244, 178], "ankleL": [208, 205], "ankleR": [232, 205]}},
        {"c": "good", "bar": [220, 82], "cue": "stand tall, locked", "j": {"head": [220, 58, 13], "neck": [220, 78], "hipC": [220, 138], "shL": [200, 88], "shR": [240, 88], "handL": [196, 80], "handR": [244, 80], "kneeL": [208, 170], "kneeR": [232, 170], "ankleL": [208, 205], "ankleR": [232, 205]}},
    ],
    "ex_deadlift": [
        {"c": "ac", "bar": [220, 182], "cue": "grip just outside the knees", "j": {"head": [220, 86, 13], "neck": [220, 104], "hipC": [220, 150], "shL": [202, 112], "shR": [238, 112], "handL": [206, 180], "handR": [234, 180], "kneeL": [206, 172], "kneeR": [234, 172], "ankleL": [206, 206], "ankleR": [234, 206]}},
        {"c": "ac", "bar": [220, 150], "cue": "bar stays centered, hips square", "j": {"head": [220, 72, 13], "neck": [220, 90], "hipC": [220, 138], "shL": [204, 98], "shR": [236, 98], "handL": [208, 150], "handR": [232, 150], "kneeL": [210, 168], "kneeR": [230, 168], "ankleL": [208, 206], "ankleR": [232, 206]}},
        {"c": "good", "bar": [220, 128], "cue": "hips & shoulders level", "j": {"head": [220, 58, 13], "neck": [220, 76], "hipC": [220, 128], "shL": [206, 84], "shR": [234, 84], "handL": [208, 128], "handR": [232, 128], "kneeL": [212, 168], "kneeR": [228, 168], "ankleL": [210, 206], "ankleR": [230, 206]}},
    ],
    "ex_press": [
        {"c": "ac", "bar": [220, 80], "cue": "bar on the front delts", "j": {"head": [220, 60, 13], "neck": [220, 80], "hipC": [220, 140], "shL": [200, 88], "shR": [240, 88], "handL": [204, 82], "handR": [236, 82], "kneeL": [210, 172], "kneeR": [230, 172], "ankleL": [210, 205], "ankleR": [230, 205]}},
        {"c": "ac", "bar": [220, 50], "cue": "press straight up past the face", "j": {"head": [220, 64, 13], "neck": [220, 82], "hipC": [220, 140], "shL": [202, 90], "shR": [238, 90], "handL": [208, 52], "handR": [232, 52], "kneeL": [210, 172], "kneeR": [230, 172], "ankleL": [210, 205], "ankleR": [230, 205]}},
        {"c": "good", "bar": [220, 28], "cue": "stacked overhead, even", "j": {"head": [220, 64, 13], "neck": [220, 82], "hipC": [220, 140], "shL": [204, 90], "shR": [236, 90], "handL": [212, 28], "handR": [228, 28], "kneeL": [210, 172], "kneeR": [230, 172], "ankleL": [210, 205], "ankleR": [230, 205]}},
    ],
    "ex_clean": [
        {"c": "ac", "bar": [220, 180], "cue": "pull the bar in close", "j": {"head": [220, 86, 13], "neck": [220, 104], "hipC": [220, 150], "shL": [202, 112], "shR": [238, 112], "handL": [206, 180], "handR": [234, 180], "kneeL": [206, 172], "kneeR": [234, 172], "ankleL": [206, 206], "ankleR": [234, 206]}},
        {"c": "good", "bar": [220, 116], "cue": "triple extension — explode up", "j": {"head": [220, 54, 13], "neck": [220, 72], "hipC": [220, 120], "shL": [206, 80], "shR": [234, 80], "handL": [210, 118], "handR": [230, 118], "kneeL": [212, 162], "kneeR": [228, 162], "ankleL": [212, 206], "ankleR": [228, 206]}},
        {"c": "a2", "bar": [220, 82], "cue": "catch: elbows high, knees out", "j": {"head": [220, 72, 13], "neck": [220, 90], "hipC": [220, 150], "shL": [202, 98], "shR": [238, 98], "handL": [206, 86], "handR": [234, 86], "kneeL": [200, 176], "kneeR": [240, 176], "ankleL": [208, 206], "ankleR": [232, 206]}},
    ],
}


def _stepper(sid: str, title: str, steps: list, hint: str = "") -> str:
    """steps: list of dicts with keys label, desc, svg (inner SVG markup)."""
    scenes = "".join(
        '<g class="sa-scene" data-step="%d">%s</g>' % (i, s["svg"])
        for i, s in enumerate(steps)
    )
    dots = "".join(
        '<button class="sa-dot" data-i="%d">%d</button>' % (i, i + 1)
        for i in range(len(steps))
    )
    meta = json.dumps([[s["label"], s["desc"]] for s in steps], ensure_ascii=False)
    _fr = FRONTAL.get(sid)
    _opts = {"framesF": _fr, "lift": True} if _fr else {}
    _opts_json = json.dumps(_opts, ensure_ascii=False)
    if _fr:
        _extra_btns = (
            '    <button class="sa-plane-btn" id="%s-planebtn" onclick="SA[\'%s\'].plane()">&#8634; Front view</button>\n'
            '    <button class="sa-3d-btn" id="%s-3dbtn" onclick="SA[\'%s\'].three()">&#9673; 3D view</button>\n'
        ) % (sid, sid, sid, sid)
        _extra_html = '  <div class="sa-3d" id="%s-3d" data-on="0" style="display:none"></div>\n' % sid
    else:
        _extra_btns = ""
        _extra_html = ""
    body = ENGINE + (
        '<div class="step-anim" id="%s">\n'
        '  <div class="sa-stage"><svg viewBox="%s" class="sa-svg" '
        'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">%s</svg>'
        '<div class="sa-scrubhint">drag to scrub &#8596;</div></div>\n'
        '  <input type="range" class="sa-scrub" id="%s-scrub" min="0" max="1000" value="0" aria-label="Scrub the movement">\n'
        '  <div class="sa-progress"><div class="sa-bar" id="%s-bar"></div></div>\n'
        '  <div class="sa-dots">%s</div>\n'
        '  <div class="sa-caption">\n'
        '    <div class="sa-step-num">Step <span id="%s-cur">1</span> of %d</div>\n'
        '    <div class="sa-label" id="%s-label"></div>\n'
        '    <div class="sa-desc" id="%s-desc"></div>\n'
        '  </div>\n'
        '  <div class="w-controls">\n'
        '    <button onclick="SA[\'%s\'].prev()">&#9664; Prev</button>\n'
        '    <button onclick="SA[\'%s\'].next()">Next &#9654;</button>\n'
        '    <button onclick="SA[\'%s\'].auto()" id="%s-autobtn">&#9205; Auto-play</button>\n'
        '%s'
        '  </div>\n'
        '%s'
        '</div>\n'
        '<script>SAEngine.init("%s", %s, %s);</script>\n'
    ) % (sid, VB, scenes, sid, sid, dots, sid, len(steps), sid, sid,
         sid, sid, sid, sid, _extra_btns, _extra_html, sid, meta, _opts_json)
    return _wrap(sid + "-stepper", title, body, hint)


# ───────────────────────── shared SVG builders ─────────────────────────

def _ground(label=""):
    g = ('<line x1="40" y1="%d" x2="400" y2="%d" stroke="%s" stroke-width="2" '
         'opacity="0.5"/>') % (GROUND_Y, GROUND_Y, DIM)
    if label:
        g += '<text x="220" y="232" fill="%s" font-size="11" text-anchor="middle">%s</text>' % (DIM, label)
    return g


def _figure(p, cls="sa-pop", color=None, bar=None):
    """Side-view athlete from a joints dict. Wrapped in one .sa-fig group that
    carries data-joints / data-c / data-bar so the JS engine can extract the
    keyframe and tween a live skeleton. The static group is hidden in
    figure-mode and only revealed if the engine fails to start."""
    c = color or AC
    sym = "ac"
    if color == A2:
        sym = "a2"
    elif color == GOOD:
        sym = "good"
    elif color == WARN:
        sym = "warn"
    elif color == BAD:
        sym = "bad"
    L = lambda a, b: '<line x1="%g" y1="%g" x2="%g" y2="%g"/>' % (p[a][0], p[a][1], p[b][0], p[b][1])
    limbs = '<g fill="none" stroke="%s" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">' % c
    limbs += L("neck", "hip") + L("hip", "knee") + L("knee", "ankle") + L("ankle", "toe")
    limbs += L("shoulder", "elbow") + L("elbow", "hand")
    limbs += "</g>"
    head = '<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % (p["head"][0], p["head"][1], p["head"][2], c)
    barbell = ""
    if bar:
        bx, by = bar
        barbell = (
            '<g>'
            '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="5" stroke-linecap="round"/>'
            '<circle cx="%g" cy="%g" r="14" fill="%s"/>'
            '<circle cx="%g" cy="%g" r="14" fill="%s"/>'
            '</g>'
        ) % (bx - 62, by, bx + 62, by, INK, bx - 62, by, A2, bx + 62, by, A2)
    _jk = ("head", "neck", "shoulder", "elbow", "hand", "hip", "knee", "ankle", "toe")
    _joints = {k: [round(float(v), 1) for v in p[k]] for k in _jk}
    _dj = json.dumps(_joints, separators=(",", ":"))
    _barattr = ' data-bar="%g,%g"' % (bar[0], bar[1]) if bar else ""
    return '<g class="%s sa-fig" data-joints=\'%s\' data-c="%s"%s>%s%s%s</g>' % (
        cls, _dj, sym, _barattr, limbs, head, barbell)


def _arrow(x1, y1, x2, y2, color=None, cls="sa-draw", w=4):
    """A motion arrow with arrowhead (animated draw)."""
    c = color or A2
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 10
    p1x, p1y = x2 - ah * math.cos(ang - 0.5), y2 - ah * math.sin(ang - 0.5)
    p2x, p2y = x2 - ah * math.cos(ang + 0.5), y2 - ah * math.sin(ang + 0.5)
    return (
        '<g class="%s" stroke="%s" stroke-width="%d" fill="none" stroke-linecap="round">'
        '<line x1="%g" y1="%g" x2="%g" y2="%g"/>'
        '<polyline points="%g,%g %g,%g %g,%g" stroke-linejoin="round"/>'
        '</g>'
    ) % (cls, c, w, x1, y1, x2, y2, p1x, p1y, x2, y2, p2x, p2y)


def _chip(x, y, text, color=None, cls="sa-pop", w=None):
    c = color or AC
    w = w or max(46, 9 + len(text) * 7)
    return (
        '<g class="%s">'
        '<rect x="%g" y="%g" width="%g" height="24" rx="12" fill="%s" opacity="0.16"/>'
        '<rect x="%g" y="%g" width="%g" height="24" rx="12" fill="none" stroke="%s" stroke-width="1.4"/>'
        '<text x="%g" y="%g" fill="%s" font-size="12" font-weight="700" text-anchor="middle">%s</text>'
        '</g>'
    ) % (cls, x, y, w, c, x, y, w, c, x + w / 2, y + 16, c, text)


def _mol(cx, cy, r, text, color=None, cls="sa-pop", tcolor=None):
    c = color or AC
    tc = tcolor or INK
    return (
        '<g class="%s">'
        '<circle cx="%g" cy="%g" r="%g" fill="%s" opacity="0.2"/>'
        '<circle cx="%g" cy="%g" r="%g" fill="none" stroke="%s" stroke-width="2"/>'
        '<text x="%g" y="%g" fill="%s" font-size="%g" font-weight="700" text-anchor="middle">%s</text>'
        '</g>'
    ) % (cls, cx, cy, r, c, cx, cy, r, c, cx, cy + r * 0.32, tc, max(10, r * 0.7), text)


def _title(text, color=None):
    c = color or DIM
    return ('<text x="220" y="26" fill="%s" font-size="13" font-weight="700" '
            'text-anchor="middle" letter-spacing="0.5">%s</text>') % (c, text)


# ───────────────────────── EXERCISE TECHNIQUE: the lifts ─────────────────────────

def _plate(cx, cy, cls="sa-pop"):
    return (
        '<g class="%s sa-plate sa-fig" data-bar="%g,%g">'
        '<circle cx="%g" cy="%g" r="20" fill="%s" opacity="0.25"/>'
        '<circle cx="%g" cy="%g" r="20" fill="none" stroke="%s" stroke-width="3"/>'
        '<circle cx="%g" cy="%g" r="6" fill="%s"/>'
        '</g>'
    ) % (cls, cx, cy, cx, cy, A2, cx, cy, A2, cx, cy, INK)


def _guide(x, y1=40, y2=206):
    return ('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.5" '
            'stroke-dasharray="4 5" opacity="0.35"/>') % (x, y1, x, y2, DIM)


def s_squat():
    standing = dict(head=(206, 58, 13), neck=(206, 75), shoulder=(206, 82), hip=(206, 132),
                    knee=(206, 168), ankle=(206, 202), toe=(224, 206), elbow=(190, 92), hand=(192, 80))
    quarter = dict(head=(212, 66, 13), neck=(212, 82), shoulder=(212, 90), hip=(198, 146),
                   knee=(216, 176), ankle=(206, 202), toe=(224, 206), elbow=(196, 100), hand=(200, 90))
    bottom = dict(head=(220, 84, 13), neck=(220, 100), shoulder=(220, 108), hip=(196, 180),
                  knee=(232, 176), ankle=(206, 202), toe=(224, 206), elbow=(204, 118), hand=(210, 108))
    drive = dict(head=(214, 70, 13), neck=(214, 86), shoulder=(214, 94), hip=(200, 150),
                 knee=(218, 178), ankle=(206, 202), toe=(224, 206), elbow=(198, 104), hand=(202, 94))
    steps = [
        dict(label="Set up & brace",
             desc="Bar on the upper traps, feet about shoulder-width, toes slightly out. Big breath into the belly, brace the core, neutral spine.",
             svg=_title("SET-UP") + _guide(206) + _ground("weight over mid-foot") + _figure(standing, bar=(206, 80)) + _chip(296, 64, "BRACE", GOOD)),
        dict(label="Descend — hips & knees together",
             desc="Break at the hips and knees at the same time and sit between the heels. Knees track over the toes; chest stays up.",
             svg=_title("DESCENT") + _guide(206) + _ground() + _figure(quarter, bar=(212, 88)) + _arrow(150, 118, 150, 168, A2) + _chip(286, 150, "hips back", AC)),
        dict(label="Hit depth — hip crease below knee",
             desc="Reach full depth: the hip crease drops below the top of the knee. Keep tension — no bouncing or collapsing forward.",
             svg=_title("BOTTOM") + _guide(206) + _ground() + _figure(bottom, bar=(220, 106), color=A2) + _chip(300, 150, "DEPTH", GOOD) +
                 '<line x1="188" y1="180" x2="246" y2="180" stroke="%s" stroke-width="1.5" stroke-dasharray="3 4" opacity="0.8"/>' % GOOD),
        dict(label="Drive up — lead with the chest",
             desc="Push the floor away and drive hips and shoulders up together so the bar travels straight up. Keep the chest tall.",
             svg=_title("ASCENT") + _guide(206) + _ground() + _figure(drive, bar=(214, 92)) + _arrow(150, 168, 150, 108, GOOD) + _chip(286, 116, "drive!", GOOD)),
        dict(label="Lockout & reset",
             desc="Stand fully tall — hips and knees extended, glutes squeezed. Reset the breath and brace before the next rep.",
             svg=_title("LOCKOUT") + _guide(206) + _ground() + _figure(standing, bar=(206, 80), color=GOOD) + _arrow(150, 150, 150, 92, GOOD) + _chip(296, 64, "TALL", GOOD)),
    ]
    return _stepper("ex_squat", "Back squat — phase by phase", steps,
                    "Hips and knees move together; the bar stays stacked over mid-foot the whole way.")


def s_deadlift():
    plate_y = lambda by: _plate(206, by)
    setup = dict(head=(170, 100, 12), neck=(176, 112), shoulder=(182, 120), hip=(150, 152),
                 knee=(198, 170), ankle=(206, 202), toe=(228, 206), elbow=(194, 152), hand=(206, 178))
    breaks = dict(head=(178, 92, 12), neck=(184, 104), shoulder=(190, 112), hip=(158, 140),
                  knee=(202, 162), ankle=(206, 202), toe=(228, 206), elbow=(200, 140), hand=(206, 156))
    knees = dict(head=(192, 78, 12), neck=(196, 92), shoulder=(200, 100), hip=(176, 126),
                 knee=(206, 162), ankle=(206, 202), toe=(226, 206), elbow=(204, 116), hand=(206, 132))
    lock = dict(head=(206, 60, 13), neck=(206, 77), shoulder=(206, 84), hip=(206, 128),
                knee=(206, 166), ankle=(206, 202), toe=(224, 206), elbow=(206, 104), hand=(206, 118))
    steps = [
        dict(label="Set up over the bar",
             desc="Bar over mid-foot, shins close. Hinge to grip just outside the knees. Hips higher than knees, shoulders just ahead of the bar, lats tight, flat back.",
             svg=_title("SET-UP") + _guide(206) + _ground("bar over mid-foot") + _figure(setup) + plate_y(178) + _chip(290, 88, "flat back", AC)),
        dict(label="Break from the floor — push the legs",
             desc="Drive the floor away with the legs to break the bar from the ground. The bar stays glued to the shins; hips and shoulders rise at the same rate.",
             svg=_title("FIRST PULL") + _guide(206) + _ground() + _figure(breaks) + plate_y(156) + _arrow(150, 168, 150, 138, A2) + _chip(286, 100, "leg drive", AC)),
        dict(label="Bar passes the knees",
             desc="Once past the knees, drive the hips forward toward the bar. Keep it close — don't let it swing out or round the back.",
             svg=_title("PAST KNEES") + _guide(206) + _ground() + _figure(knees) + plate_y(132) + _arrow(150, 150, 178, 120, A2) + _chip(286, 92, "hips in", AC)),
        dict(label="Lockout — stand tall, hips through",
             desc="Finish by squeezing the glutes and standing fully erect. Shoulders back, knees and hips locked. No leaning back or over-extending the spine.",
             svg=_title("LOCKOUT") + _guide(206) + _ground() + _figure(lock, color=GOOD) + _plate(206, 118, "sa-pop") + _arrow(150, 150, 150, 100, GOOD) + _chip(296, 70, "GLUTES", GOOD)),
    ]
    return _stepper("ex_deadlift", "Conventional deadlift — pull sequence", steps,
                    "Bar travels in a straight vertical line, glued to the body. Hips and shoulders rise together off the floor.")


def s_press():
    rack = dict(head=(206, 60, 13), neck=(206, 77), shoulder=(206, 86), hip=(206, 140),
                knee=(206, 172), ankle=(206, 204), toe=(224, 206), elbow=(186, 92), hand=(198, 76))
    mid = dict(head=(200, 64, 13), neck=(204, 80), shoulder=(206, 88), hip=(206, 140),
               knee=(206, 172), ankle=(206, 204), toe=(224, 206), elbow=(198, 70), hand=(204, 52))
    past = dict(head=(206, 64, 13), neck=(206, 80), shoulder=(206, 88), hip=(206, 140),
                knee=(206, 172), ankle=(206, 204), toe=(224, 206), elbow=(204, 60), hand=(206, 40))
    lock = dict(head=(206, 64, 13), neck=(206, 80), shoulder=(206, 88), hip=(206, 140),
                knee=(206, 172), ankle=(206, 204), toe=(224, 206), elbow=(206, 56), hand=(206, 30))
    steps = [
        dict(label="Front-rack start",
             desc="Bar on the front delts, elbows slightly ahead, forearms vertical. Glutes and abs braced, ribs down — a rigid column from floor to bar.",
             svg=_title("RACK") + _guide(206) + _ground("stacked: bar over mid-foot") + _figure(rack, bar=(206, 74)) + _chip(290, 70, "brace", AC)),
        dict(label="Press & move the head back",
             desc="Drive the bar straight up. As it clears the chin, shift the head and torso slightly back so the bar can travel vertically past the face.",
             svg=_title("DRIVE") + _guide(206) + _ground() + _figure(mid, bar=(206, 50)) + _arrow(150, 150, 150, 90, A2) + _chip(286, 110, "bar up", AC)),
        dict(label="Bar passes the forehead",
             desc="Once the bar is above the head, push the head back through 'the window' so the bar finishes over the mid-foot, not out front.",
             svg=_title("THROUGH") + _guide(206) + _ground() + _figure(past, bar=(206, 38)) + _arrow(150, 120, 150, 70, A2) + _chip(286, 86, "head through", AC)),
        dict(label="Overhead lockout",
             desc="Elbows locked, biceps by the ears, bar stacked over the shoulders, hips and ankles. Shrug the shoulders up to finish actively.",
             svg=_title("LOCKOUT") + _guide(206) + _ground() + _figure(lock, bar=(206, 26), color=GOOD) + _chip(290, 60, "STACKED", GOOD)),
    ]
    return _stepper("ex_press", "Overhead press — bar path", steps,
                    "The bar travels in a straight vertical line; the head moves back then forward so nothing blocks the path. (Bench press mirrors this stack horizontally.)")


def s_clean():
    floor = dict(head=(170, 102, 12), neck=(176, 114), shoulder=(182, 122), hip=(152, 154),
                 knee=(198, 172), ankle=(206, 202), toe=(228, 206), elbow=(194, 154), hand=(206, 180))
    pull1 = dict(head=(184, 88, 12), neck=(190, 100), shoulder=(196, 108), hip=(166, 138),
                 knee=(204, 164), ankle=(206, 202), toe=(226, 206), elbow=(202, 134), hand=(206, 156))
    scoop = dict(head=(200, 76, 12), neck=(204, 90), shoulder=(206, 98), hip=(190, 124),
                 knee=(214, 158), ankle=(206, 202), toe=(226, 206), elbow=(204, 116), hand=(206, 134))
    ext = dict(head=(208, 50, 12), neck=(208, 64), shoulder=(208, 72), hip=(208, 116),
               knee=(208, 158), ankle=(206, 202), toe=(220, 206), elbow=(206, 92), hand=(206, 108))
    catch = dict(head=(206, 70, 13), neck=(206, 86), shoulder=(206, 94), hip=(196, 150),
                 knee=(220, 176), ankle=(206, 202), toe=(224, 206), elbow=(192, 84), hand=(200, 78))
    stand = dict(head=(206, 60, 13), neck=(206, 77), shoulder=(206, 86), hip=(206, 138),
                 knee=(206, 172), ankle=(206, 204), toe=(224, 206), elbow=(188, 90), hand=(198, 78))
    steps = [
        dict(label="Start position",
             desc="Bar over mid-foot, hook grip just outside the knees. Hips higher than the knees, shoulders over or just in front of the bar, back flat and braced.",
             svg=_title("START") + _guide(206) + _ground("bar over mid-foot") + _figure(floor) + _plate(206, 180) + _chip(290, 92, "flat back", AC)),
        dict(label="First pull — floor to knee",
             desc="Push the floor away to lift the bar smoothly to knee height. Keep the back angle constant and the bar close; this is patient, not explosive yet.",
             svg=_title("FIRST PULL") + _guide(206) + _ground() + _figure(pull1) + _plate(206, 156) + _arrow(150, 170, 150, 142, A2) + _chip(286, 96, "patient", AC)),
        dict(label="Scoop / transition (double-knee bend)",
             desc="As the bar passes the knees, the knees re-bend under the bar and the torso becomes vertical — loading the legs to explode (the 'power position').",
             svg=_title("SCOOP") + _guide(206) + _ground() + _figure(scoop) + _plate(206, 134) + _chip(286, 100, "power position", A2, w=120)),
        dict(label="Second pull — triple extension",
             desc="Violently extend ankles, knees and hips and shrug — the jump that launches the bar upward. This is the explosive heart of the lift.",
             svg=_title("EXPLODE") + _ground() + _figure(ext, color=GOOD) + _plate(206, 108, "sa-rise") + _arrow(150, 170, 150, 70, GOOD, w=5) + _chip(286, 70, "triple ext!", GOOD, w=110)),
        dict(label="Catch in the front rack",
             desc="Pull the body under the bar and whip the elbows around fast, catching the bar on the front delts in a quarter-squat. Elbows high.",
             svg=_title("CATCH") + _guide(206) + _ground() + _figure(catch, bar=(206, 78)) + _arrow(150, 90, 150, 140, A2) + _chip(286, 96, "elbows up", AC)),
        dict(label="Recover to standing",
             desc="Stand up out of the quarter-squat to finish tall with the bar racked. Controlled — the hard work was the pull and the catch.",
             svg=_title("RECOVER") + _guide(206) + _ground() + _figure(stand, bar=(206, 76), color=GOOD) + _chip(290, 62, "stand tall", GOOD)),
    ]
    return _stepper("ex_clean", "Power clean — six positions", steps,
                    "The bar accelerates: a patient first pull, a scoop that loads the legs, then an explosive triple extension before you drop under to catch.")


# ───────────────────────── EXERCISE SCIENCE: cascades & pathways ─────────────────────────

def _membrane(y, x1=70, x2=370, color=None):
    c = color or DIM
    return ('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="3" opacity="0.7"/>'
            '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="3" opacity="0.7"/>'
            ) % (x1, y, x2, y, c, x1, y + 9, x2, y + 9, c)


def s_ec_coupling():
    axon = ('<rect x="60" y="58" width="240" height="28" rx="14" fill="%s" opacity="0.14"/>'
            '<rect x="60" y="58" width="240" height="28" rx="14" fill="none" stroke="%s" stroke-width="2"/>'
            '<text x="80" y="50" fill="%s" font-size="11">motoneuron</text>') % (AC, AC, DIM)
    cleft = _membrane(150) + '<text x="380" y="150" fill="%s" font-size="10" text-anchor="end">sarcolemma</text>' % DIM
    ca_burst = "".join(_mol(150 + i * 26, 150 + (i % 2) * 18, 9, "Ca", GOOD, "sa-pop sa-d%d" % (1 + i % 4), GOOD) for i in range(7))
    steps = [
        dict(label="Action potential races down the motoneuron",
             desc="An electrical impulse travels along the axon toward the neuromuscular junction at the muscle fiber.",
             svg=_title("1 · NERVE IMPULSE") + axon + _arrow(110, 72, 285, 72, A2, "sa-draw", 5) + _mol(96, 72, 13, "AP", AC, "sa-inR", AC)),
        dict(label="ACh released into the synaptic cleft",
             desc="The impulse triggers vesicles at the axon terminal to fuse and dump acetylcholine (ACh) into the gap between nerve and muscle.",
             svg=_title("2 · ACh RELEASE") + _membrane(150) +
                 '<path d="M150 70 q40 0 60 40" fill="none" stroke="%s" stroke-width="2" class="sa-draw"/>' % AC +
                 _mol(150, 70, 16, "ves", AC, "sa-pop", AC) +
                 "".join(_mol(180 + i * 22, 120 + (i % 2) * 16, 8, "ACh", A2, "sa-rise sa-d%d" % (1 + i), A2) for i in range(4))),
        dict(label="ACh binds receptors → sarcolemma depolarizes",
             desc="ACh opens nicotinic receptors. Na⁺ rushes in and the muscle membrane depolarizes, firing its own action potential.",
             svg=_title("3 · DEPOLARIZE") + cleft + _mol(160, 130, 9, "ACh", A2, "sa-pop", A2) +
                 _arrow(220, 110, 220, 168, GOOD, "sa-draw", 4) + _mol(220, 100, 11, "Na+", GOOD, "sa-inR", GOOD) + _chip(280, 170, "depolarized", GOOD, w=104)),
        dict(label="AP spreads down the T-tubules",
             desc="The depolarization dives into the fiber along the T-tubule network so the signal reaches deep inside the cell at once.",
             svg=_title("4 · T-TUBULE") + _membrane(110) +
                 '<rect x="206" y="119" width="20" height="80" rx="6" fill="%s" opacity="0.16"/>'
                 '<rect x="206" y="119" width="20" height="80" rx="6" fill="none" stroke="%s" stroke-width="2"/>' % (AC, AC) +
                 _arrow(216, 124, 216, 190, A2, "sa-draw", 4) + _mol(216, 110, 11, "AP", AC, "sa-pop", AC) + _chip(250, 150, "T-tubule", AC)),
        dict(label="Sarcoplasmic reticulum releases Ca²⁺",
             desc="The signal opens ryanodine receptors on the SR. Stored calcium floods out into the cytosol — the trigger for contraction.",
             svg=_title("5 · Ca²⁺ FLOOD") +
                 '<rect x="120" y="70" width="200" height="34" rx="16" fill="%s" opacity="0.14"/>'
                 '<rect x="120" y="70" width="200" height="34" rx="16" fill="none" stroke="%s" stroke-width="2"/>'
                 '<text x="220" y="64" fill="%s" font-size="10" text-anchor="middle">sarcoplasmic reticulum</text>' % (GOOD, GOOD, DIM) +
                 ca_burst),
        dict(label="Ca²⁺ binds troponin → tropomyosin shifts",
             desc="Calcium binds troponin C, which pulls tropomyosin off the actin strand — exposing the myosin-binding sites.",
             svg=_title("6 · SITES EXPOSED") +
                 '<rect x="70" y="150" width="300" height="14" rx="7" fill="%s" opacity="0.3"/>' % DIM +
                 '<text x="70" y="142" fill="%s" font-size="10">actin</text>' % DIM +
                 '<path class="sa-draw" d="M80 150 q150 -26 290 0" fill="none" stroke="%s" stroke-width="4"/>' % WARN +
                 _mol(150, 120, 11, "Ca", GOOD, "sa-pop", GOOD) + _mol(150, 150, 9, "Tn", WARN, "sa-pop", WARN) +
                 _arrow(190, 150, 190, 124, A2, "sa-draw", 3) + _chip(250, 116, "sites open", GOOD, w=96)),
        dict(label="Cross-bridge cycling — CONTRACTION",
             desc="Myosin heads grab actin and pull (the power stroke). ATP is needed both to detach the head and to re-cock it for the next pull.",
             svg=_title("7 · CONTRACTION") +
                 '<rect x="70" y="156" width="300" height="14" rx="7" fill="%s" opacity="0.3"/>' % DIM +
                 '<line x1="120" y1="120" x2="120" y2="150" stroke="%s" stroke-width="6" stroke-linecap="round"/>' % A2 +
                 '<line x1="200" y1="120" x2="200" y2="150" stroke="%s" stroke-width="6" stroke-linecap="round"/>' % A2 +
                 '<line x1="280" y1="120" x2="280" y2="150" stroke="%s" stroke-width="6" stroke-linecap="round"/>' % A2 +
                 '<text x="220" y="112" fill="%s" font-size="10" text-anchor="middle">myosin heads</text>' % DIM +
                 _arrow(300, 163, 200, 163, GOOD, "sa-draw", 5) + _mol(330, 120, 12, "ATP", WARN, "sa-pulseS", WARN) + _chip(150, 188, "POWER STROKE", GOOD, w=128)),
    ]
    return _stepper("ec_coupling", "Excitation–contraction coupling", steps,
                    "Walk the cascade from nerve impulse to cross-bridge cycling. Calcium is the trigger; ATP powers both the pull and the release.")


def s_glycolysis():
    def coin(x, y, t, cls="sa-pop"):
        return ('<g class="%s"><circle cx="%g" cy="%g" r="13" fill="%s" opacity="0.2"/>'
                '<circle cx="%g" cy="%g" r="13" fill="none" stroke="%s" stroke-width="2"/>'
                '<text x="%g" y="%g" fill="%s" font-size="10" font-weight="700" text-anchor="middle">%s</text></g>'
                ) % (cls, x, y, WARN, x, y, WARN, x, y + 4, WARN, t)
    steps = [
        dict(label="Glucose is trapped as glucose-6-phosphate",
             desc="A 6-carbon glucose enters the cell. Hexokinase spends 1 ATP to phosphorylate it, locking it inside as G6P.",
             svg=_title("1 · TRAP THE SUGAR") + _ground() * 0 + _mol(110, 120, 26, "Glucose", AC, "sa-inR") +
                 _arrow(150, 120, 250, 120, A2, "sa-draw", 4) + coin(200, 86, "-1 ATP") + _mol(300, 120, 26, "G6P", AC, "sa-pop")),
        dict(label="Invest a 2nd ATP → fructose-1,6-bisphosphate",
             desc="PFK (the rate-limiting enzyme) spends a second ATP. The energy investment phase is now complete: 2 ATP spent.",
             svg=_title("2 · INVEST (PFK)") + _mol(110, 120, 26, "G6P", AC, "sa-inR") +
                 _arrow(150, 120, 250, 120, A2, "sa-draw", 4) + coin(200, 86, "-1 ATP") + _mol(305, 120, 30, "F1,6BP", AC, "sa-pop") + _chip(150, 168, "rate-limiter", WARN, w=104)),
        dict(label="Split into two 3-carbon sugars (G3P)",
             desc="The 6-carbon molecule is cleaved into two 3-carbon G3P. From here, everything happens twice — once per half.",
             svg=_title("3 · SPLIT") + _mol(110, 120, 28, "F1,6BP", AC, "sa-inR") +
                 _arrow(150, 120, 230, 90, A2, "sa-draw", 3) + _arrow(150, 120, 230, 150, A2, "sa-draw", 3) +
                 _mol(280, 86, 22, "G3P", A2, "sa-rise sa-d1") + _mol(280, 154, 22, "G3P", A2, "sa-rise sa-d2")),
        dict(label="Payoff: pyruvate + ATP + NADH",
             desc="Each G3P is oxidized to pyruvate, generating 4 ATP and 2 NADH total. Net gain = 2 ATP and 2 NADH per glucose.",
             svg=_title("4 · PAYOFF") + _mol(96, 120, 22, "2 G3P", A2, "sa-inR") +
                 _arrow(130, 120, 240, 120, GOOD, "sa-draw", 5) + coin(170, 86, "+4 ATP") + _mol(180, 156, 14, "NADH", GOOD, "sa-pop") +
                 _mol(300, 120, 26, "2 Pyr", GOOD, "sa-pop") + _chip(150, 196, "net +2 ATP", GOOD, w=96)),
        dict(label="Fast glycolysis → lactate",
             desc="When demand outpaces oxygen, pyruvate is reduced to lactate. This regenerates NAD⁺ so glycolysis can keep firing at high rates.",
             svg=_title("5 · FAST (no O₂)") + _mol(110, 120, 26, "Pyruvate", AC, "sa-inR") +
                 _arrow(150, 120, 250, 120, BAD, "sa-draw", 4) + _mol(180, 86, 13, "NAD+", GOOD, "sa-pop") + _mol(300, 120, 26, "Lactate", BAD, "sa-pop", BAD) + _chip(150, 168, "high intensity", BAD, w=110)),
        dict(label="Slow glycolysis → mitochondria",
             desc="With enough oxygen, pyruvate instead enters the mitochondrion for full oxidation — far more ATP, but slower.",
             svg=_title("6 · SLOW (O₂ present)") + _mol(110, 120, 26, "Pyruvate", AC, "sa-inR") +
                 _arrow(150, 120, 250, 120, GOOD, "sa-draw", 4) +
                 '<ellipse cx="320" cy="120" rx="46" ry="34" fill="%s" opacity="0.15"/>'
                 '<ellipse cx="320" cy="120" rx="46" ry="34" fill="none" stroke="%s" stroke-width="2" class="sa-pop"/>'
                 '<text x="320" y="124" fill="%s" font-size="11" font-weight="700" text-anchor="middle">mito</text>' % (GOOD, GOOD, GOOD)),
    ]
    return _stepper("glycolysis", "Glycolysis — splitting sugar for energy", steps,
                    "Two ATP are invested up front; four come back. Net +2 ATP, +2 NADH, and pyruvate — which becomes lactate (fast) or fuels the mitochondria (slow).")


def s_oxidative():
    def mito(cls="sa-pop"):
        return ('<g class="%s"><ellipse cx="220" cy="130" rx="150" ry="74" fill="%s" opacity="0.1"/>'
                '<ellipse cx="220" cy="130" rx="150" ry="74" fill="none" stroke="%s" stroke-width="2"/>'
                '<path d="M110 130 q22 -30 44 0 q22 30 44 0 q22 -30 44 0 q22 30 44 0 q22 -30 44 0" '
                'fill="none" stroke="%s" stroke-width="2" opacity="0.5"/></g>') % (cls, GOOD, GOOD, GOOD)
    steps = [
        dict(label="Pyruvate enters as acetyl-CoA",
             desc="Inside the mitochondrion, pyruvate is converted to acetyl-CoA — the fuel that feeds the Krebs cycle.",
             svg=_title("1 · FUEL IN") + mito("sa-pop") + _mol(100, 130, 20, "Pyr", AC, "sa-inR") +
                 _arrow(124, 130, 180, 130, A2, "sa-draw", 4) + _mol(220, 130, 24, "Ac-CoA", AC, "sa-pop")),
        dict(label="Krebs cycle strips out electrons",
             desc="The citric acid cycle spins, releasing CO₂ and loading electron carriers: lots of NADH and FADH₂ (plus a little GTP/ATP).",
             svg=_title("2 · KREBS CYCLE") + mito() +
                 '<circle cx="220" cy="130" r="42" fill="none" stroke="%s" stroke-width="3" stroke-dasharray="8 7" class="sa-spin"/>' % WARN +
                 _mol(220, 130, 16, "TCA", WARN, "sa-pop", WARN) + _mol(300, 96, 14, "NADH", GOOD, "sa-rise sa-d1") + _mol(316, 150, 12, "FADH₂", GOOD, "sa-rise sa-d2") + _mol(150, 92, 12, "CO₂", DIM, "sa-rise sa-d3", DIM)),
        dict(label="Electrons drive the transport chain",
             desc="NADH and FADH₂ drop their electrons into the electron transport chain on the inner membrane, which pumps H⁺ to one side.",
             svg=_title("3 · ELECTRON TRANSPORT") + mito() +
                 _membrane(130, 150, 300, GOOD) +
                 "".join(_mol(160 + i * 34, 110, 11, "H+", WARN, "sa-rise sa-d%d" % (1 + i % 4), WARN) for i in range(5)) +
                 _arrow(170, 150, 170, 116, A2, "sa-draw", 3) + _arrow(240, 150, 240, 116, A2, "sa-draw", 3)),
        dict(label="ATP synthase makes the ATP",
             desc="H⁺ floods back through ATP synthase like water through a turbine, spinning it to forge the bulk of the cell's ATP.",
             svg=_title("4 · ATP SYNTHASE") + mito() + _membrane(130, 150, 300, GOOD) +
                 '<circle cx="230" cy="150" r="18" fill="%s" opacity="0.2"/>'
                 '<circle cx="230" cy="150" r="18" fill="none" stroke="%s" stroke-width="3" stroke-dasharray="6 5" class="sa-spin"/>' % (WARN, WARN) +
                 _arrow(230, 110, 230, 144, A2, "sa-draw", 4) + _mol(300, 160, 16, "ATP", WARN, "sa-pop", WARN) + _chip(120, 96, "most ATP here", GOOD, w=120)),
        dict(label="Oxygen is the final acceptor → water",
             desc="O₂ grabs the spent electrons and H⁺ to form water — the reason this system needs oxygen. Slow, but by far the biggest ATP yield.",
             svg=_title("5 · O₂ → H₂O") + mito() + _mol(150, 120, 16, "O₂", AC, "sa-inR", AC) +
                 _arrow(174, 124, 240, 134, A2, "sa-draw", 4) + _mol(280, 134, 18, "H₂O", AC, "sa-pop", AC) + _chip(120, 188, "endurance fuel", GOOD, w=120)),
    ]
    return _stepper("oxidative", "Oxidative phosphorylation", steps,
                    "Krebs strips electrons; the transport chain pumps H⁺; ATP synthase cashes the gradient in for ATP; oxygen closes the loop as water.")


def s_cardiovascular():
    def heart(cls="sa-pop"):
        return ('<g class="%s">'
                '<rect x="150" y="70" width="64" height="58" rx="10" fill="%s" opacity="0.16"/>'
                '<rect x="150" y="128" width="64" height="64" rx="10" fill="%s" opacity="0.16"/>'
                '<rect x="226" y="70" width="64" height="58" rx="10" fill="%s" opacity="0.16"/>'
                '<rect x="226" y="128" width="64" height="64" rx="10" fill="%s" opacity="0.16"/>'
                '<rect x="150" y="70" width="140" height="122" rx="12" fill="none" stroke="%s" stroke-width="2"/>'
                '<line x1="220" y1="70" x2="220" y2="192" stroke="%s" stroke-width="1.5" opacity="0.5"/>'
                '<text x="182" y="64" fill="%s" font-size="9" text-anchor="middle">RIGHT</text>'
                '<text x="258" y="64" fill="%s" font-size="9" text-anchor="middle">LEFT</text>'
                '</g>') % (cls, AC, AC, BAD, BAD, DIM, DIM, AC, BAD)
    label = lambda x, y, t, c: '<text x="%g" y="%g" fill="%s" font-size="10" font-weight="700" text-anchor="middle">%s</text>' % (x, y, c, t)
    steps = [
        dict(label="Deoxygenated blood returns to the right atrium",
             desc="Oxygen-poor blood from the body empties through the vena cava into the right atrium (RA).",
             svg=_title("1 · RIGHT ATRIUM") + heart() + label(182, 102, "RA", AC) +
                 _arrow(70, 100, 148, 100, AC, "sa-flow", 5) + _chip(40, 150, "from body", AC, w=86)),
        dict(label="Right atrium → right ventricle",
             desc="Blood drops through the tricuspid valve into the right ventricle (RV), the pump for the lungs.",
             svg=_title("2 · RIGHT VENTRICLE") + heart() + label(182, 102, "RA", AC) + label(182, 162, "RV", AC) +
                 _arrow(182, 124, 182, 150, A2, "sa-draw", 4)),
        dict(label="Right ventricle → lungs",
             desc="The RV pumps blood out the pulmonary artery to the lungs, where it dumps CO₂ and picks up oxygen.",
             svg=_title("3 · TO THE LUNGS") + heart() + label(182, 162, "RV", AC) +
                 _arrow(180, 128, 120, 60, AC, "sa-flow", 4) +
                 '<ellipse cx="96" cy="54" rx="34" ry="22" fill="%s" opacity="0.14"/>'
                 '<ellipse cx="96" cy="54" rx="34" ry="22" fill="none" stroke="%s" stroke-width="2" class="sa-pop"/>'
                 '<text x="96" y="58" fill="%s" font-size="10" text-anchor="middle">lungs</text>' % (GOOD, GOOD, GOOD) +
                 _mol(150, 40, 11, "O₂", GOOD, "sa-rise", GOOD)),
        dict(label="Oxygenated blood → left atrium",
             desc="Freshly oxygenated blood returns via the pulmonary veins into the left atrium (LA).",
             svg=_title("4 · LEFT ATRIUM") + heart() + label(258, 102, "LA", BAD) +
                 _arrow(120, 60, 250, 78, BAD, "sa-flow", 4)),
        dict(label="Left atrium → left ventricle",
             desc="Blood passes the mitral valve into the left ventricle (LV) — the thick, powerful chamber.",
             svg=_title("5 · LEFT VENTRICLE") + heart() + label(258, 102, "LA", BAD) + label(258, 162, "LV", BAD) +
                 _arrow(258, 124, 258, 150, A2, "sa-draw", 4) + _chip(150, 200, "thickest wall", BAD, w=104)),
        dict(label="Left ventricle → aorta → whole body",
             desc="The LV ejects blood into the aorta at the highest pressure in the system, delivering oxygen to every tissue. The loop repeats.",
             svg=_title("6 · OUT TO THE BODY") + heart() + label(258, 162, "LV", BAD) +
                 _arrow(290, 150, 380, 150, BAD, "sa-flow", 5) + _chip(316, 100, "highest BP", BAD, w=92)),
    ]
    return _stepper("cardiovascular", "Blood flow through the heart", steps,
                    "Follow one drop of blood: body → right side → lungs → left side → body. Right side is blue (deoxygenated); left side is red and runs at the highest pressure.")


def s_respiratory():
    def alveolus(cls="sa-pop"):
        return ('<g class="%s"><circle cx="130" cy="120" r="56" fill="%s" opacity="0.12"/>'
                '<circle cx="130" cy="120" r="56" fill="none" stroke="%s" stroke-width="2"/>'
                '<text x="130" y="124" fill="%s" font-size="11" text-anchor="middle">alveolus</text></g>') % (cls, AC, AC, DIM)
    def cap(cls="sa-pop"):
        return ('<g class="%s"><rect x="206" y="92" width="150" height="56" rx="28" fill="%s" opacity="0.12"/>'
                '<rect x="206" y="92" width="150" height="56" rx="28" fill="none" stroke="%s" stroke-width="2"/>'
                '<text x="288" y="170" fill="%s" font-size="10" text-anchor="middle">capillary</text></g>') % (cls, BAD, BAD, DIM)
    steps = [
        dict(label="Inhale — fresh air fills the alveoli",
             desc="Breathing in floods the alveoli with air that is high in O₂ and low in CO₂, setting up the gradients for exchange.",
             svg=_title("1 · INHALE") + alveolus() + _arrow(60, 80, 110, 104, AC, "sa-draw", 4) +
                 "".join(_mol(110 + (i % 3) * 22, 110 + (i // 3) * 24, 9, "O₂", AC, "sa-pop sa-d%d" % (1 + i % 4), AC) for i in range(4))),
        dict(label="O₂ diffuses into the blood",
             desc="Oxygen moves down its pressure gradient across the thin alveolar wall into the capillary — no pump needed, just diffusion.",
             svg=_title("2 · DIFFUSION") + alveolus() + cap() +
                 _arrow(176, 120, 240, 120, GOOD, "sa-draw", 5) + _mol(150, 120, 11, "O₂", AC, "sa-pop", AC) + _chip(150, 188, "high → low", GOOD, w=88)),
        dict(label="O₂ loads onto hemoglobin",
             desc="In the cool, less-acidic lung, hemoglobin grabs O₂ readily — the left-shifted (loading) end of the Bohr relationship.",
             svg=_title("3 · LOADING") + cap() + _mol(248, 120, 17, "Hb", BAD, "sa-pop", BAD) +
                 _mol(300, 120, 12, "O₂", AC, "sa-inL", AC) + _arrow(284, 120, 266, 120, GOOD, "sa-draw", 3) + _chip(206, 70, "Hb saturates", GOOD, w=104)),
        dict(label="At the muscle — Bohr shift unloads O₂",
             desc="Working muscle is warm, acidic and CO₂-rich. That right-shifts the curve, so hemoglobin releases O₂ right where it's needed.",
             svg=_title("4 · UNLOADING") +
                 '<rect x="60" y="80" width="120" height="80" rx="12" fill="%s" opacity="0.12"/>'
                 '<rect x="60" y="80" width="120" height="80" rx="12" fill="none" stroke="%s" stroke-width="2" class="sa-pop"/>'
                 '<text x="120" y="124" fill="%s" font-size="11" text-anchor="middle">muscle</text>' % (WARN, WARN, DIM) +
                 _mol(240, 120, 17, "Hb", BAD, "sa-pop", BAD) + _arrow(224, 120, 170, 120, WARN, "sa-draw", 4) +
                 _mol(150, 120, 11, "O₂", AC, "sa-pop", AC) + _chip(220, 70, "warm + acidic", WARN, w=110)),
        dict(label="CO₂ carried back, then exhaled",
             desc="The blood picks up CO₂ from the muscle and carries it back to the lungs, where it diffuses out and is breathed away.",
             svg=_title("5 · CO₂ OUT") + alveolus() + cap() +
                 _arrow(240, 130, 176, 130, DIM, "sa-draw", 4) + _mol(280, 120, 11, "CO₂", DIM, "sa-pop", DIM) + _arrow(110, 100, 60, 76, DIM, "sa-draw", 4)),
    ]
    return _stepper("respiratory", "Gas exchange & the Bohr shift", steps,
                    "Oxygen diffuses from alveoli into blood and loads onto hemoglobin in the cool lung; warmth, acid and CO₂ at the muscle flip the switch so it unloads.")


# ───────────────────────── POWER, SPEED, WARM-UP, DESIGN, REHAB ─────────────────────────

def _coil(x, top, bottom, turns=5, w=16, cls="sa-pop", color=None):
    c = color or A2
    step = (bottom - top) / turns
    pts = ["%g,%g" % (x, top)]
    for i in range(turns + 1):
        yy = top + i * step
        xx = x + (w if i % 2 else -w)
        pts.append("%g,%g" % (xx, yy))
    pts.append("%g,%g" % (x, bottom))
    return ('<polyline class="%s" points="%s" fill="none" stroke="%s" stroke-width="4" '
            'stroke-linecap="round" stroke-linejoin="round"/>') % (cls, " ".join(pts), c)


def s_plyometrics():
    stand = dict(head=(150, 70, 13), neck=(150, 86), shoulder=(150, 94), hip=(150, 140),
                 knee=(150, 174), ankle=(150, 204), toe=(168, 206), elbow=(136, 110), hand=(134, 126))
    dip = dict(head=(154, 92, 13), neck=(154, 108), shoulder=(154, 116), hip=(146, 152),
               knee=(166, 178), ankle=(150, 204), toe=(168, 206), elbow=(170, 126), hand=(184, 118))
    fly = dict(head=(150, 50, 13), neck=(150, 66), shoulder=(150, 74), hip=(150, 120),
               knee=(150, 156), ankle=(150, 186), toe=(166, 192), elbow=(140, 46), hand=(140, 30))
    steps = [
        dict(label="Eccentric — load the spring",
             desc="Landing or dipping rapidly lengthens the muscle-tendon unit under tension, storing elastic energy like compressing a spring.",
             svg=_title("1 · ECCENTRIC (load)") + _ground() + _figure(dip, color=AC) +
                 _coil(300, 96, 168, 5, 16, "sa-pop", AC) + _arrow(340, 110, 340, 160, A2, "sa-draw", 4) + _chip(250, 70, "store energy", AC, w=104)),
        dict(label="Amortization — keep it brief",
             desc="The split-second between lengthening and shortening. Keep it SHORT — a long pause lets the stored elastic energy leak away as heat.",
             svg=_title("2 · AMORTIZATION") + _ground() + _figure(dip, cls="sa-pulseS", color=WARN) +
                 _coil(300, 96, 168, 5, 16, "sa-pop", WARN) + _chip(240, 70, "milliseconds!", WARN, w=120) +
                 '<text x="300" y="200" fill="%s" font-size="10" text-anchor="middle">don’t pause</text>' % WARN),
        dict(label="Concentric — release + stretch reflex",
             desc="The muscle shortens explosively. Stored elastic energy plus the stretch reflex add to the contraction, so the jump is far more powerful.",
             svg=_title("3 · CONCENTRIC (release)") + _ground() + _figure(fly, color=GOOD) +
                 _coil(300, 60, 150, 4, 12, "sa-rise", GOOD) + _arrow(150, 180, 150, 50, GOOD, "sa-draw", 5) + _chip(250, 60, "EXPLODE", GOOD, w=92)),
    ]
    return _stepper("plyometrics", "The stretch-shortening cycle", steps,
                    "Load (eccentric) → a brief amortization → explosive release (concentric). The shorter the middle phase, the more stored energy survives into the jump.")


def s_speed():
    drive = dict(head=(120, 70, 12), neck=(128, 84), shoulder=(136, 92), hip=(108, 128),
                 knee=(150, 150), ankle=(180, 176), toe=(196, 178), elbow=(150, 96), hand=(168, 84))
    build = dict(head=(160, 64, 12), neck=(162, 80), shoulder=(164, 88), hip=(150, 130),
                 knee=(180, 156), ankle=(200, 188), toe=(214, 190), elbow=(178, 96), hand=(192, 84))
    maxv = dict(head=(206, 56, 12), neck=(206, 72), shoulder=(206, 80), hip=(206, 124),
                knee=(232, 150), ankle=(214, 188), toe=(228, 190), elbow=(186, 88), hand=(168, 78))
    decel = dict(head=(214, 78, 12), neck=(210, 94), shoulder=(206, 102), hip=(196, 144),
                 knee=(176, 172), ankle=(158, 196), toe=(150, 198), elbow=(220, 110), hand=(232, 124))
    steps = [
        dict(label="Acceleration — drive phase",
             desc="Out of the start, a big forward lean and powerful triple extension push the body forward. Ground contacts are long and forceful.",
             svg=_title("1 · DRIVE") + _ground() + _figure(drive, color=AC) + _arrow(150, 110, 230, 96, A2, "sa-draw", 5) + _chip(280, 80, "lean + push", AC, w=104)),
        dict(label="Transition — posture rises",
             desc="As speed builds over the first several strides, the body gradually stands taller and stride length increases.",
             svg=_title("2 · TRANSITION") + _ground() + _figure(build, color=AC) + _arrow(190, 96, 250, 84, A2, "sa-draw", 4) + _chip(286, 80, "rising", AC, w=78)),
        dict(label="Max velocity — front-side mechanics",
             desc="Tall posture, high knee drive, and a quick downward 'paw-back' of the foot. Ground contact is brief; the goal is to apply force fast, straight down.",
             svg=_title("3 · MAX VELOCITY") + _ground() + _figure(maxv, color=GOOD) + _arrow(232, 150, 214, 188, GOOD, "sa-draw", 4) + _chip(120, 70, "tall + fast", GOOD, w=96)),
        dict(label="Deceleration & change of direction",
             desc="To cut, lower the center of mass, take gather steps, and plant hard. Eccentric strength absorbs the brake before re-accelerating a new way.",
             svg=_title("4 · CUT / DECELERATE") + _ground() + _figure(decel, color=WARN) + _arrow(180, 150, 150, 188, WARN, "sa-draw", 4) + _chip(286, 80, "sink + plant", WARN, w=104)),
    ]
    return _stepper("speed_agility", "Sprint mechanics — start to cut", steps,
                    "Acceleration is a forward-lean push; max velocity is tall with brief, straight-down ground force; agility is a controlled sink-and-plant to redirect.")


def s_warmup():
    def ramp(active, labels):
        bars = ""
        for i in range(4):
            h = 30 + i * 36
            y = 196 - h
            on = (i <= active)
            col = AC if on else DIM
            op = "0.85" if i == active else ("0.4" if on else "0.18")
            cls = "sa-rise sa-d%d" % (1 + i) if on else ""
            bars += ('<rect class="%s" x="%g" y="%g" width="56" height="%g" rx="6" fill="%s" opacity="%s"/>'
                     '<text x="%g" y="212" fill="%s" font-size="10" text-anchor="middle" font-weight="700">%s</text>'
                     ) % (cls, 90 + i * 70, y, h, col, op, 90 + i * 70 + 28, col, labels[i])
        return bars
    L = ["Raise", "Activate", "Mobilise", "Potentiate"]
    steps = [
        dict(label="Raise — body temperature & blood flow",
             desc="Start with low-intensity movement to raise heart rate, core temperature, blood flow and joint fluid. The body literally warms up.",
             svg=_title("R · RAISE") + _ground() + ramp(0, L) + _chip(150, 50, "↑ HR & temp", AC, w=104)),
        dict(label="Activate — switch on key muscles",
             desc="Fire up the muscles the session depends on — glutes, core, scapular stabilisers — so they're recruited well under load.",
             svg=_title("A · ACTIVATE") + _ground() + ramp(1, L) + _chip(150, 50, "glutes + core", AC, w=110)),
        dict(label="Mobilise — dynamic range of motion",
             desc="Move the joints through sport-relevant ranges with dynamic (not long static) stretches to prep mobility without dulling power.",
             svg=_title("M · MOBILISE") + _ground() + ramp(2, L) + _chip(150, 50, "dynamic ROM", AC, w=108)),
        dict(label="Potentiate — ramp to competition speed",
             desc="Finish with progressively faster, sport-specific efforts (build-up sprints, ramping loads) so you start the session primed, not flat.",
             svg=_title("P · POTENTIATE") + _ground() + ramp(3, L) + _chip(150, 50, "near max", GOOD, w=86)),
    ]
    return _stepper("warmup", "RAMP warm-up protocol", steps,
                    "Raise → Activate → Mobilise → Potentiate. Intensity climbs across the four stages so you finish primed for the work ahead.")


def s_needs():
    def card(x, y, t, c, cls="sa-pop"):
        return ('<g class="%s"><rect x="%g" y="%g" width="150" height="40" rx="9" fill="%s" opacity="0.14"/>'
                '<rect x="%g" y="%g" width="150" height="40" rx="9" fill="none" stroke="%s" stroke-width="1.6"/>'
                '<text x="%g" y="%g" fill="%s" font-size="12" font-weight="700" text-anchor="middle">%s</text></g>'
                ) % (cls, x, y, c, x, y, c, x + 75, y + 25, c, t)
    steps = [
        dict(label="Evaluate the sport — movement demands",
             desc="What does the sport actually require? Map the key movement patterns, the muscles and joints involved, and the common injury sites.",
             svg=_title("1 · SPORT — MOVEMENT") + card(145, 60, "Movement patterns", AC) + card(145, 110, "Joints / muscles", AC, "sa-pop sa-d1") + card(145, 160, "Injury sites", AC, "sa-pop sa-d2")),
        dict(label="Evaluate the sport — energy demands",
             desc="Which energy systems power it? A 100m sprint and a marathon need very different training. Match work-to-rest and intensity to the sport.",
             svg=_title("2 · SPORT — ENERGY") + card(60, 110, "Phosphagen", WARN) + card(220, 110, "Glycolytic", AC, "sa-pop sa-d1") + card(140, 160, "Oxidative", GOOD, "sa-pop sa-d2") + _chip(150, 60, "which system?", DIM, w=120)),
        dict(label="Assess the athlete",
             desc="Now profile the individual: training age, test results, injury history and the training calendar. The plan must fit this athlete, not a generic one.",
             svg=_title("3 · THE ATHLETE") + card(145, 56, "Training age", A2) + card(145, 104, "Test results", A2, "sa-pop sa-d1") + card(145, 152, "Injury history", A2, "sa-pop sa-d2")),
        dict(label="Translate into program variables",
             desc="Sport demands + athlete profile drive every choice: exercise selection, intensity, volume, rest and frequency. Needs analysis is the foundation.",
             svg=_title("4 · → THE PROGRAM") + card(40, 110, "Sport", AC) + card(250, 110, "Athlete", A2, "sa-pop sa-d1") +
                 _arrow(196, 130, 248, 130, GOOD, "sa-draw", 4) + _arrow(244, 130, 196, 130, GOOD, "sa-draw", 4) +
                 _chip(150, 170, "exercise · load · volume · rest", GOOD, w=210)),
    ]
    return _stepper("needs_analysis", "Needs analysis — sport then athlete", steps,
                    "Two questions first: what does the SPORT demand (movement + energy), and what does this ATHLETE bring? Those answers set every program variable.")


def s_rehab():
    def node(x, on, t):
        c = GOOD if on else DIM
        cls = "sa-pop" if on else ""
        return ('<g class="%s"><circle cx="%g" cy="120" r="16" fill="%s" opacity="0.18"/>'
                '<circle cx="%g" cy="120" r="16" fill="none" stroke="%s" stroke-width="2.5"/></g>'
                '<text x="%g" y="160" fill="%s" font-size="10" text-anchor="middle" font-weight="700">%s</text>'
                ) % (cls, x, c, x, c, x, c, t)
    line = '<line x1="80" y1="120" x2="360" y2="120" stroke="%s" stroke-width="2" opacity="0.4"/>' % DIM
    xs = [80, 173, 266, 360]
    names = ["Acute", "Repair", "Remodel", "Return"]
    def stage(active):
        return line + "".join(node(xs[i], i <= active, names[i]) for i in range(4))
    steps = [
        dict(label="Acute / inflammation — protect",
             desc="Right after injury: control pain and swelling and protect the tissue (the PRICE idea). Gentle, pain-free movement only.",
             svg=_title("1 · ACUTE") + stage(0) + _chip(150, 70, "protect + de-swell", AC, w=132)),
        dict(label="Repair / proliferation — load lightly",
             desc="New tissue is laid down. Introduce controlled, progressive loading and restore range of motion so it heals aligned and strong.",
             svg=_title("2 · REPAIR") + stage(1) + _chip(150, 70, "restore ROM", AC, w=96)),
        dict(label="Remodeling — rebuild strength",
             desc="The tissue matures and re-organises along lines of stress. Progressive overload now rebuilds real strength and capacity.",
             svg=_title("3 · REMODEL") + stage(2) + _arrow(140, 92, 240, 80, GOOD, "sa-draw", 4) + _chip(250, 70, "overload", GOOD, w=84)),
        dict(label="Return to sport — criteria-based",
             desc="Progress to sport-specific demands and clear objective criteria (strength, control, confidence) — not just the calendar — before full return.",
             svg=_title("4 · RETURN") + stage(3) + _chip(150, 70, "meet the criteria", GOOD, w=124)),
    ]
    return _stepper("rehab", "Rehab — tissue healing stages", steps,
                    "Acute → Repair → Remodel → Return. Load is reintroduced gradually and the jump back to sport is earned by criteria, not by the calendar alone.")


def s_review():
    def domain(x, t, c, on, cls="sa-pop"):
        op = "0.85" if on else "0.2"
        return ('<g class="%s"><rect x="%g" y="96" width="74" height="74" rx="12" fill="%s" opacity="%s"/>'
                '<rect x="%g" y="96" width="74" height="74" rx="12" fill="none" stroke="%s" stroke-width="2"/>'
                '<text x="%g" y="138" fill="%s" font-size="13" font-weight="800" text-anchor="middle">%s</text></g>'
                ) % (cls, x, c, op, x, c, x + 37, INK if on else DIM, t)
    xs = [44, 142, 240, 338]
    cols = [AC, GOOD, A2, WARN]
    tags = ["ES", "NT", "EX", "PD"]
    def row(active):
        return "".join(domain(xs[i], tags[i], cols[i], i <= active) for i in range(4))
    steps = [
        dict(label="Exercise Science — how force is made",
             desc="Muscles, motor units, the energy systems and biomechanics: the science of how the body produces force and fuels it. (~25% of the exam.)",
             svg=_title("DOMAIN 1") + row(0) + _chip(80, 60, "how the body works", AC, w=150)),
        dict(label="Nutrition — fuel the systems",
             desc="Macronutrients, hydration and timing — supplying the substrates the energy systems burn. Smaller slice, but easy points. (~10%.)",
             svg=_title("DOMAIN 2") + row(1) + _chip(110, 60, "fuel in", GOOD, w=72)),
        dict(label="Exercise Technique — apply force safely",
             desc="The lifts, Olympic variations and alternative modes: how to express that force with sound, coachable technique. (~25%.)",
             svg=_title("DOMAIN 3") + row(2) + _chip(150, 60, "the lifts", A2, w=80)),
        dict(label="Program Design & Testing — put it together",
             desc="Needs analysis, periodization and testing tie everything into a plan and measure it. The biggest domain — where it all integrates. (~40%.)",
             svg=_title("DOMAIN 4") + row(3) + _arrow(118, 200, 338, 200, GOOD, "sa-draw", 3) + _chip(150, 58, "the whole plan", WARN, w=116)),
    ]
    return _stepper("phase1_review", "The four CSCS domains, assembled", steps,
                    "Science explains force, nutrition fuels it, technique applies it, and program design organises and tests it. Phase 1 connects all four.")


# ───────────────────────── dispatch ─────────────────────────

STEPPERS = {
    "ec_coupling": s_ec_coupling,
    "glycolysis": s_glycolysis,
    "oxidative": s_oxidative,
    "cardiovascular": s_cardiovascular,
    "respiratory": s_respiratory,
    "ex_squat": s_squat,
    "ex_deadlift": s_deadlift,
    "ex_press": s_press,
    "ex_clean": s_clean,
    "plyometrics": s_plyometrics,
    "speed_agility": s_speed,
    "warmup": s_warmup,
    "needs_analysis": s_needs,
    "rehab": s_rehab,
    "phase1_review": s_review,
}


def render(topic_id: str) -> str:
    fn = STEPPERS.get(topic_id)
    return fn() if fn else ""
