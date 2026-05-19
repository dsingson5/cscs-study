"""
Topic-specific interactive widgets for CSCS daily study HTML.

Each function returns a self-contained HTML fragment (SVG + CSS + JS) themed to
the lesson's topic. The generator calls `render(topic_id)` to inject the right
widget into a lesson card.
"""
from __future__ import annotations


def _wrap(widget_id: str, title: str, body: str, hint: str = "") -> str:
    hint_html = f'<div class="w-hint">{hint}</div>' if hint else ""
    return f'''
<div class="widget" id="{widget_id}">
  <div class="w-head"><span class="w-icon">⚡</span><span class="w-title">{title}</span></div>
  <div class="w-body">{body}</div>
  {hint_html}
</div>
'''


# ────────── EXERCISE SCIENCE WIDGETS ──────────

def sarcomere_animation() -> str:
    # Anatomy:
    #   Sarcomere = Z-disc to Z-disc
    #   Thin filaments (actin) are RIGIDLY anchored at Z-discs and project inward
    #   Thick filament (myosin) is centered, anchored at M-line (does not move)
    #   During contraction: Z-discs move SYMMETRICALLY toward center; thin filaments
    #     move WITH their Z-disc, increasing overlap with myosin.
    #
    # Resting layout (viewBox 600 wide):
    #   Left Z-disc at x=100, right Z-disc at x=500 → sarcomere length 400 units
    #   Myosin: x=220 to x=380 (centered, width 160)
    #   Thin filament: 200 wide, anchored at each Z-disc, extending inward
    #   Resting overlap each side: (300 - 220) = 80 units... let's compute properly:
    #     thinLeft spans 100→300 (width 200), overlaps myosin 220→300 = 80
    #     thinRight spans 300→500 (width 200), overlaps myosin 300→380 = 80
    #     Total overlap = 160 = full myosin? Actually no: at rest, partial overlap.
    #   Maximum contraction: Z-discs at x=180 and x=420 (shift = 80 each)
    #     thinLeft spans 180→380, thinRight spans 220→420 → both fully overlap myosin
    body = '''
<svg viewBox="0 0 600 200" class="w-svg sarcomere-svg" id="sarcomereSvg" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sgrad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#3a2030" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#1a0a18" stop-opacity="0.1"/>
    </linearGradient>
  </defs>

  <!-- Reference baseline (visual frame for the sarcomere) -->
  <rect x="80" y="58" width="440" height="84" fill="url(#sgrad)" rx="6"/>

  <!-- M-line (center of myosin, anatomic anchor) -->
  <line x1="300" y1="62" x2="300" y2="138" stroke="#7a4a6a" stroke-width="1" stroke-dasharray="2 3" opacity="0.5"/>
  <text x="300" y="56" fill="#a87a98" font-size="9" text-anchor="middle" opacity="0.7">M-line</text>

  <!-- Z-discs (rigid; thin filaments are rigidly attached) -->
  <line id="zLeft" x1="100" y1="58" x2="100" y2="142" stroke="#ff5e5e" stroke-width="5" stroke-linecap="round"/>
  <text id="zLeftLbl" x="100" y="50" fill="#ff5e5e" font-size="11" text-anchor="middle" font-weight="600">Z</text>
  <line id="zRight" x1="500" y1="58" x2="500" y2="142" stroke="#ff5e5e" stroke-width="5" stroke-linecap="round"/>
  <text id="zRightLbl" x="500" y="50" fill="#ff5e5e" font-size="11" text-anchor="middle" font-weight="600">Z</text>

  <!-- Thin filaments (actin) — anchored at Z-discs, projecting toward center -->
  <g id="thinLeft">
    <rect x="100" y="93" width="200" height="3" fill="#67e8b0" rx="1.5"/>
    <rect x="100" y="104" width="200" height="3" fill="#67e8b0" rx="1.5"/>
    <circle cx="300" cy="94" r="2" fill="#67e8b0"/>
    <circle cx="300" cy="106" r="2" fill="#67e8b0"/>
  </g>
  <g id="thinRight">
    <rect x="300" y="93" width="200" height="3" fill="#67e8b0" rx="1.5"/>
    <rect x="300" y="104" width="200" height="3" fill="#67e8b0" rx="1.5"/>
    <circle cx="300" cy="94" r="2" fill="#67e8b0"/>
    <circle cx="300" cy="106" r="2" fill="#67e8b0"/>
  </g>

  <!-- Thick filament (myosin) — centered, anchored at M-line, does not translate -->
  <g id="thickFil">
    <rect x="220" y="85" width="160" height="30" fill="#5ec8ff" rx="3" opacity="0.85"/>
    <g id="crossBridges" stroke="#ffb86b" stroke-width="1.5" stroke-linecap="round">
      <line x1="232" y1="85" x2="232" y2="78"/><line x1="248" y1="85" x2="248" y2="78"/>
      <line x1="264" y1="85" x2="264" y2="78"/><line x1="280" y1="85" x2="280" y2="78"/>
      <line x1="320" y1="85" x2="320" y2="78"/><line x1="336" y1="85" x2="336" y2="78"/>
      <line x1="352" y1="85" x2="352" y2="78"/><line x1="368" y1="85" x2="368" y2="78"/>
      <line x1="232" y1="115" x2="232" y2="122"/><line x1="248" y1="115" x2="248" y2="122"/>
      <line x1="264" y1="115" x2="264" y2="122"/><line x1="280" y1="115" x2="280" y2="122"/>
      <line x1="320" y1="115" x2="320" y2="122"/><line x1="336" y1="115" x2="336" y2="122"/>
      <line x1="352" y1="115" x2="352" y2="122"/><line x1="368" y1="115" x2="368" y2="122"/>
    </g>
  </g>

  <!-- Legend -->
  <g font-size="10">
    <rect x="100" y="160" width="14" height="3" fill="#67e8b0" rx="1.5"/>
    <text x="120" y="164" fill="#67e8b0">actin (thin)</text>
    <rect x="220" y="158" width="14" height="7" fill="#5ec8ff" rx="1.5" opacity="0.85"/>
    <text x="240" y="164" fill="#5ec8ff">myosin (thick)</text>
    <line x1="360" y1="158" x2="360" y2="165" stroke="#ff5e5e" stroke-width="3"/>
    <text x="370" y="164" fill="#ff5e5e">Z-disc</text>
    <line x1="430" y1="160" x2="438" y2="160" stroke="#ffb86b" stroke-width="2"/>
    <text x="446" y="164" fill="#ffb86b">cross-bridge</text>
  </g>
</svg>
<div class="w-controls">
  <button onclick="sarcomereToggle()" id="sarcoBtn">▶ Animate contraction</button>
  <span class="w-stat">Sarcomere length: <b id="sarcoLen">400 units</b> · Overlap: <b id="sarcoOverlap">80</b></span>
</div>
<script>
(function(){
  // shift = how far EACH Z-disc moves toward the M-line (center is x=300)
  // Resting: shift=0   → Z at 100 and 500, sarcomere length 400
  // Max contraction: shift=80 → Z at 180 and 420, sarcomere length 240
  let playing = false, t = 0, dir = 1;
  function step(){
    if(!playing) return;
    t += dir * 0.010;
    if(t > 1){ t = 1; dir = -1; }
    if(t < 0){ t = 0; dir = 1; }
    const shift = t * 80;
    // Move BOTH Z-discs symmetrically toward center
    const zL = 100 + shift, zR = 500 - shift;
    const zLeft = document.getElementById('zLeft');
    const zRight = document.getElementById('zRight');
    zLeft.setAttribute('x1', zL); zLeft.setAttribute('x2', zL);
    zRight.setAttribute('x1', zR); zRight.setAttribute('x2', zR);
    document.getElementById('zLeftLbl').setAttribute('x', zL);
    document.getElementById('zRightLbl').setAttribute('x', zR);
    // Thin filaments translate WITH their Z-disc (rigidly attached)
    document.getElementById('thinLeft').setAttribute('transform', `translate(${shift}, 0)`);
    document.getElementById('thinRight').setAttribute('transform', `translate(${-shift}, 0)`);
    // Cross-bridges pulse to indicate active cycling
    const cb = document.getElementById('crossBridges');
    cb.style.opacity = 0.5 + Math.abs(Math.sin(t * Math.PI * 5)) * 0.5;
    // Readouts
    const sLen = 400 - 2 * shift;
    document.getElementById('sarcoLen').textContent = Math.round(sLen) + ' units';
    // Overlap on each side = thin filament tip position minus myosin start
    // tip of thinLeft at rest = 300; with shift it's at 300+shift; overlap = (300+shift) - 220 = 80 + shift
    const overlap = 80 + shift;
    document.getElementById('sarcoOverlap').textContent = Math.round(overlap) + ' units';
    requestAnimationFrame(step);
  }
  window.sarcomereToggle = function(){
    playing = !playing;
    document.getElementById('sarcoBtn').textContent = playing ? '⏸ Pause' : '▶ Animate contraction';
    if(playing) requestAnimationFrame(step);
  };
})();
</script>
'''
    return _wrap(
        "sarcomere-widget",
        "Sliding-filament animation",
        body,
        "Z-discs pull together as actin slides along myosin via cross-bridge cycling.",
    )


def motor_unit_recruitment() -> str:
    body = '''
<div class="mu-container">
  <div class="mu-bars">
    <div class="mu-bar" data-thresh="20" data-type="I"><div class="mu-fill"></div><span>Type I · low threshold</span></div>
    <div class="mu-bar" data-thresh="35" data-type="I"><div class="mu-fill"></div><span>Type I · low threshold</span></div>
    <div class="mu-bar" data-thresh="50" data-type="IIa"><div class="mu-fill"></div><span>Type IIa · moderate</span></div>
    <div class="mu-bar" data-thresh="65" data-type="IIa"><div class="mu-fill"></div><span>Type IIa · moderate</span></div>
    <div class="mu-bar" data-thresh="80" data-type="IIx"><div class="mu-fill"></div><span>Type IIx · high threshold</span></div>
    <div class="mu-bar" data-thresh="92" data-type="IIx"><div class="mu-fill"></div><span>Type IIx · highest threshold</span></div>
  </div>
  <div class="w-controls">
    <label>Force demand: <b id="muIntensityLbl">0%</b></label>
    <input type="range" min="0" max="100" value="0" id="muIntensity" class="w-slider">
  </div>
  <div class="mu-readout" id="muReadout">Drag the slider — recruitment follows Henneman's Size Principle (smallest first).</div>
</div>
<script>
(function(){
  const slider = document.getElementById('muIntensity');
  const lbl = document.getElementById('muIntensityLbl');
  const readout = document.getElementById('muReadout');
  const bars = document.querySelectorAll('.mu-bar');
  slider.addEventListener('input', e => {
    const v = +e.target.value;
    lbl.textContent = v + '%';
    let recruited = {I:0, IIa:0, IIx:0};
    bars.forEach(b => {
      const t = +b.dataset.thresh;
      const fill = b.querySelector('.mu-fill');
      if(v >= t){
        b.classList.add('active');
        fill.style.width = '100%';
        recruited[b.dataset.type]++;
      } else {
        b.classList.remove('active');
        fill.style.width = '0%';
      }
    });
    let msg;
    if(v < 20) msg = 'Sub-threshold — no motor units recruited.';
    else if(v < 50) msg = `Recruiting Type I (oxidative). ${recruited.I} units active.`;
    else if(v < 80) msg = `Type I + Type IIa now active. Approaching MLSS intensity.`;
    else msg = `Type IIx recruited — high-force/sprint range. ${recruited.IIx} IIx units online.`;
    readout.textContent = msg;
  });
})();
</script>
'''
    return _wrap(
        "mu-widget",
        "Motor unit recruitment slider",
        body,
        "Henneman's Size Principle: smaller (Type I) units fire first, larger (Type IIx) last.",
    )


def ec_coupling_steps() -> str:
    steps = [
        ("Action potential travels down motoneuron", "An electrical signal races down the axon toward the neuromuscular junction."),
        ("ACh released into synaptic cleft", "Vesicles fuse with axon terminal, dumping acetylcholine."),
        ("ACh binds nicotinic receptors on sarcolemma", "Receptor opening lets Na⁺ in — sarcolemma depolarizes."),
        ("AP propagates down T-tubules", "Depolarization spreads into the muscle fiber via T-tubule network."),
        ("Sarcoplasmic reticulum releases Ca²⁺", "Ryanodine receptors open. Ca²⁺ floods the cytosol."),
        ("Ca²⁺ binds troponin C → tropomyosin shifts", "Myosin-binding sites on actin exposed."),
        ("Cross-bridge cycle begins — CONTRACTION", "Myosin pulls actin. ATP required for both attachment AND detachment."),
    ]
    items = ""
    for i, (label, desc) in enumerate(steps):
        items += f'''
<div class="ec-step" data-step="{i}">
  <div class="ec-num">{i + 1}</div>
  <div class="ec-content">
    <div class="ec-label">{label}</div>
    <div class="ec-desc">{desc}</div>
  </div>
</div>'''
    body_prefix = '''
<div class="ec-container">
  <div class="ec-track">'''
    body_suffix = '''</div>
  <div class="w-controls">
    <button onclick="ecStep(-1)">◀ Prev</button>
    <button onclick="ecStep(1)" id="ecNext">Next ▶</button>
    <button onclick="ecAuto()" id="ecAutoBtn">⏵ Auto-play</button>
  </div>
</div>
<script>
(function(){
  let cur = -1, auto = null;
  const steps = document.querySelectorAll('.ec-step');
  function show(i){
    cur = Math.max(-1, Math.min(steps.length - 1, i));
    steps.forEach((s, idx) => {
      s.classList.toggle('active', idx === cur);
      s.classList.toggle('past', idx < cur);
    });
  }
  window.ecStep = function(delta){
    if(auto){ clearInterval(auto); auto = null; document.getElementById('ecAutoBtn').textContent = '⏵ Auto-play'; }
    show(cur + delta);
  };
  window.ecAuto = function(){
    const btn = document.getElementById('ecAutoBtn');
    if(auto){ clearInterval(auto); auto = null; btn.textContent = '⏵ Auto-play'; return; }
    btn.textContent = '⏸ Pause';
    cur = -1;
    auto = setInterval(() => {
      if(cur >= steps.length - 1){ clearInterval(auto); auto = null; btn.textContent = '⏵ Auto-play'; return; }
      show(cur + 1);
    }, 1400);
    show(0);
  };
})();
</script>
'''
    body = body_prefix + items + body_suffix
    return _wrap(
        "ec-widget",
        "Excitation-contraction coupling — step through",
        body,
        "Click Next or Auto-play to walk through the cascade from nerve signal to cross-bridge cycling.",
    )


def heart_calculator() -> str:
    body = '''
<div class="hc-container">
  <div class="hc-heart-wrap">
    <svg viewBox="0 0 200 220" class="heart-svg" id="heartSvg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="heartG" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stop-color="#ff9999"/>
          <stop offset="100%" stop-color="#cc3344"/>
        </radialGradient>
      </defs>
      <path id="heartPath" d="M100 200 C 30 150 10 100 30 60 C 50 20 90 30 100 70 C 110 30 150 20 170 60 C 190 100 170 150 100 200 Z" fill="url(#heartG)" stroke="#7a1a26" stroke-width="2"/>
    </svg>
    <div class="hc-rate" id="hcRate">60 bpm</div>
  </div>
  <div class="hc-controls">
    <label>Heart rate: <b id="hcHrLbl">60</b> bpm</label>
    <input type="range" min="40" max="200" value="60" id="hcHr" class="w-slider">
    <label>Stroke volume: <b id="hcSvLbl">80</b> mL</label>
    <input type="range" min="50" max="180" value="80" id="hcSv" class="w-slider">
    <div class="hc-output">
      <div class="hc-line">Q = HR × SV</div>
      <div class="hc-line big">Q = <b id="hcQ">4.8</b> L/min</div>
      <div class="hc-context" id="hcContext">Resting cardiac output — normal range.</div>
    </div>
  </div>
</div>
<script>
(function(){
  const hr = document.getElementById('hcHr');
  const sv = document.getElementById('hcSv');
  const hrLbl = document.getElementById('hcHrLbl');
  const svLbl = document.getElementById('hcSvLbl');
  const q = document.getElementById('hcQ');
  const ctx = document.getElementById('hcContext');
  const rate = document.getElementById('hcRate');
  const path = document.getElementById('heartPath');
  let beat = null;
  function update(){
    const h = +hr.value, s = +sv.value;
    hrLbl.textContent = h;
    svLbl.textContent = s;
    rate.textContent = h + ' bpm';
    const Q = (h * s / 1000);
    q.textContent = Q.toFixed(1);
    let ctxMsg;
    if(h < 60) ctxMsg = 'Trained-athlete resting HR. Lower HR maintained by higher SV.';
    else if(h < 100 && Q < 6) ctxMsg = 'Resting range. Normal cardiac output ~5 L/min.';
    else if(Q < 15) ctxMsg = 'Submax exercise — SV plateaus ~40-60% VO₂max; HR drives further Q increases.';
    else ctxMsg = `Near-maximal Q = ${Q.toFixed(0)} L/min. Elite endurance athletes can hit 35-40 L/min.`;
    ctx.textContent = ctxMsg;
    const dur = 60 / h;
    path.style.animation = 'none';
    void path.offsetWidth;
    path.style.animation = `heartbeat ${dur}s ease-in-out infinite`;
  }
  hr.addEventListener('input', update);
  sv.addEventListener('input', update);
  update();
})();
</script>
'''
    return _wrap(
        "hc-widget",
        "Q = HR × SV — interactive calculator",
        body,
        "Slide HR and SV to see how cardiac output scales. Watch the heart rate visually.",
    )


def bohr_curve() -> str:
    body = '''
<svg viewBox="0 0 360 240" class="w-svg bohr-svg" id="bohrSvg" xmlns="http://www.w3.org/2000/svg">
  <line x1="40" y1="200" x2="340" y2="200" stroke="#2d3548" stroke-width="1"/>
  <line x1="40" y1="200" x2="40" y2="30" stroke="#2d3548" stroke-width="1"/>
  <text x="190" y="225" fill="#9ba3b4" font-size="11" text-anchor="middle">PO₂ (mmHg)</text>
  <text x="15" y="115" fill="#9ba3b4" font-size="11" text-anchor="middle" transform="rotate(-90, 15, 115)">% O₂ saturation</text>
  <g stroke="#3a4358" stroke-width="0.5">
    <line x1="40" y1="50" x2="340" y2="50"/>
    <line x1="40" y1="125" x2="340" y2="125"/>
  </g>
  <text x="32" y="55" fill="#5a6378" font-size="9" text-anchor="end">100</text>
  <text x="32" y="130" fill="#5a6378" font-size="9" text-anchor="end">50</text>
  <path id="bohrPath" d="" fill="none" stroke="#5ec8ff" stroke-width="2.5"/>
  <path id="bohrPathOrig" d="" fill="none" stroke="#5ec8ff" stroke-width="1" stroke-dasharray="4 4" opacity="0.4"/>
  <circle id="bohrDot" cx="200" cy="80" r="5" fill="#ffb86b"/>
  <text x="305" y="50" fill="#5ec8ff" font-size="10">Current curve</text>
  <text x="305" y="64" fill="#5ec8ff" font-size="10" opacity="0.5">Resting</text>
</svg>
<div class="w-controls">
  <label>pH (lower = more acidic working muscle): <b id="bohrPhLbl">7.4</b></label>
  <input type="range" min="6.8" max="7.6" step="0.05" value="7.4" id="bohrPh" class="w-slider">
  <label>Temperature: <b id="bohrTempLbl">37°C</b></label>
  <input type="range" min="35" max="42" step="0.1" value="37" id="bohrTemp" class="w-slider">
</div>
<div class="bohr-readout" id="bohrReadout">Normal resting conditions. Working muscle shifts curve RIGHT — unloads O₂.</div>
<script>
(function(){
  const phS = document.getElementById('bohrPh');
  const tS = document.getElementById('bohrTemp');
  const phL = document.getElementById('bohrPhLbl');
  const tL = document.getElementById('bohrTempLbl');
  const path = document.getElementById('bohrPath');
  const orig = document.getElementById('bohrPathOrig');
  const dot = document.getElementById('bohrDot');
  const out = document.getElementById('bohrReadout');
  function curve(p50){
    let d = '';
    for(let po2 = 0; po2 <= 100; po2 += 2){
      const sat = 100 * Math.pow(po2, 2.7) / (Math.pow(p50, 2.7) + Math.pow(po2, 2.7));
      const x = 40 + po2 * 3;
      const y = 200 - sat * 1.5;
      d += (po2 === 0 ? 'M' : 'L') + x + ',' + y + ' ';
    }
    return d;
  }
  orig.setAttribute('d', curve(26));
  function update(){
    const ph = +phS.value, temp = +tS.value;
    phL.textContent = ph.toFixed(2);
    tL.textContent = temp.toFixed(1) + '°C';
    const p50 = 26 + (7.4 - ph) * 18 + (temp - 37) * 2;
    path.setAttribute('d', curve(p50));
    const tissueSat = 100 * Math.pow(40, 2.7) / (Math.pow(p50, 2.7) + Math.pow(40, 2.7));
    dot.setAttribute('cx', 40 + 40 * 3);
    dot.setAttribute('cy', 200 - tissueSat * 1.5);
    let msg;
    if(ph >= 7.35 && temp <= 37.5) msg = 'Resting conditions. ~75% saturation at tissue (PO₂ 40).';
    else if(ph < 7.2 || temp > 39) msg = `Working muscle: pH ↓, temp ↑ → Bohr right-shift. ${tissueSat.toFixed(0)}% sat at tissue — more O₂ unloaded.`;
    else msg = `Moderate work. ${tissueSat.toFixed(0)}% sat at tissue PO₂ 40 mmHg.`;
    out.textContent = msg;
  }
  phS.addEventListener('input', update);
  tS.addEventListener('input', update);
  update();
})();
</script>
'''
    return _wrap(
        "bohr-widget",
        "Bohr effect — O₂-hemoglobin dissociation curve",
        body,
        "Drag pH or temperature to see the curve shift. Right-shift = more O₂ released to working muscle.",
    )


def energy_systems_timeline() -> str:
    body = '''
<div class="es-container">
  <svg viewBox="0 0 600 180" class="w-svg" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="esATP" x1="0" x2="1"><stop offset="0%" stop-color="#ff7a7a"/><stop offset="100%" stop-color="#ff7a7a" stop-opacity="0.2"/></linearGradient>
      <linearGradient id="esGly" x1="0" x2="1"><stop offset="0%" stop-color="#ffb86b" stop-opacity="0.2"/><stop offset="40%" stop-color="#ffb86b"/><stop offset="100%" stop-color="#ffb86b" stop-opacity="0.2"/></linearGradient>
      <linearGradient id="esOx" x1="0" x2="1"><stop offset="0%" stop-color="#67e8b0" stop-opacity="0.2"/><stop offset="100%" stop-color="#67e8b0"/></linearGradient>
    </defs>
    <rect x="40" y="40" width="520" height="22" fill="url(#esATP)" rx="4"/>
    <rect x="40" y="70" width="520" height="22" fill="url(#esGly)" rx="4"/>
    <rect x="40" y="100" width="520" height="22" fill="url(#esOx)" rx="4"/>
    <text x="35" y="56" text-anchor="end" fill="#ff7a7a" font-size="11">ATP-PCr</text>
    <text x="35" y="86" text-anchor="end" fill="#ffb86b" font-size="11">Glycolysis</text>
    <text x="35" y="116" text-anchor="end" fill="#67e8b0" font-size="11">Oxidative</text>
    <line id="esMarker" x1="60" x2="60" y1="32" y2="135" stroke="#5ec8ff" stroke-width="2"/>
    <circle id="esDot" cx="60" cy="32" r="5" fill="#5ec8ff"/>
    <text x="40" y="155" fill="#9ba3b4" font-size="10">0s</text>
    <text x="160" y="155" fill="#9ba3b4" font-size="10">10s</text>
    <text x="280" y="155" fill="#9ba3b4" font-size="10">2min</text>
    <text x="400" y="155" fill="#9ba3b4" font-size="10">30min</text>
    <text x="540" y="155" fill="#9ba3b4" font-size="10">3hr+</text>
  </svg>
  <div class="w-controls">
    <label>Duration: <b id="esDur">0 sec</b></label>
    <input type="range" min="0" max="100" value="0" id="esSlider" class="w-slider">
  </div>
  <div class="es-readout" id="esReadout">At rest. Drag slider to explore which energy system dominates by duration.</div>
</div>
<script>
(function(){
  const slider = document.getElementById('esSlider');
  const dur = document.getElementById('esDur');
  const out = document.getElementById('esReadout');
  const marker = document.getElementById('esMarker');
  const dot = document.getElementById('esDot');
  function durFromV(v){
    if(v < 20) return v * 0.5;
    if(v < 40) return 10 + (v - 20) * 5.5;
    if(v < 70) return 120 + (v - 40) * 56;
    return 1800 + (v - 70) * 240;
  }
  function fmt(s){
    if(s < 60) return s.toFixed(0) + ' sec';
    if(s < 3600) return (s/60).toFixed(1) + ' min';
    return (s/3600).toFixed(1) + ' hr';
  }
  slider.addEventListener('input', e => {
    const v = +e.target.value;
    const x = 40 + (v / 100) * 520;
    marker.setAttribute('x1', x); marker.setAttribute('x2', x);
    dot.setAttribute('cx', x);
    const seconds = durFromV(v);
    dur.textContent = fmt(seconds);
    let msg;
    if(seconds < 10) msg = `${fmt(seconds)} → ATP-PCr dominant. Phosphagen system. Max power output.`;
    else if(seconds < 120) msg = `${fmt(seconds)} → Fast glycolysis dominant. Lactate accumulates above MLSS.`;
    else if(seconds < 1800) msg = `${fmt(seconds)} → Oxidative dominant, carb fuel. LT2 region.`;
    else msg = `${fmt(seconds)} → Oxidative dominant, increasing fat contribution. Sub-Z2.`;
    out.textContent = msg;
  });
})();
</script>
'''
    return _wrap(
        "es-widget",
        "Energy systems by duration",
        body,
        "All three systems are always active — proportions shift with intensity and duration.",
    )


def lactate_curve() -> str:
    body = '''
<svg viewBox="0 0 400 240" class="w-svg" id="lacSvg" xmlns="http://www.w3.org/2000/svg">
  <line x1="50" y1="200" x2="380" y2="200" stroke="#2d3548"/>
  <line x1="50" y1="200" x2="50" y2="30" stroke="#2d3548"/>
  <text x="215" y="225" fill="#9ba3b4" font-size="11" text-anchor="middle">Heart rate (bpm)</text>
  <text x="20" y="115" fill="#9ba3b4" font-size="11" text-anchor="middle" transform="rotate(-90, 20, 115)">Lactate (mmol/L)</text>
  <line x1="50" y1="170" x2="380" y2="170" stroke="#3a4358" stroke-dasharray="3 3" stroke-width="0.5"/>
  <text x="45" y="175" fill="#5a6378" font-size="9" text-anchor="end">2</text>
  <line x1="50" y1="130" x2="380" y2="130" stroke="#3a4358" stroke-dasharray="3 3" stroke-width="0.5"/>
  <text x="45" y="135" fill="#5a6378" font-size="9" text-anchor="end">4</text>
  <line x1="50" y1="60" x2="380" y2="60" stroke="#3a4358" stroke-dasharray="3 3" stroke-width="0.5"/>
  <text x="45" y="65" fill="#5a6378" font-size="9" text-anchor="end">10</text>
  <path d="M 50 192 L 130 188 L 180 180 L 220 165 L 245 150 L 270 125 L 295 95 L 320 65 L 350 45 L 380 38"
        fill="none" stroke="#ffb86b" stroke-width="2.5"/>
  <line x1="180" y1="200" x2="180" y2="170" stroke="#67e8b0" stroke-width="2"/>
  <text x="180" y="215" fill="#67e8b0" font-size="10" text-anchor="middle">LT1 (147)</text>
  <text x="195" y="183" fill="#67e8b0" font-size="9">~2 mmol</text>
  <line x1="245" y1="200" x2="245" y2="130" stroke="#ff7a7a" stroke-width="2"/>
  <text x="245" y="215" fill="#ff7a7a" font-size="10" text-anchor="middle">LT2 (158)</text>
  <text x="260" y="143" fill="#ff7a7a" font-size="9">~4 mmol</text>
  <line x1="300" y1="200" x2="300" y2="100" stroke="#5ec8ff" stroke-width="2"/>
  <text x="300" y="215" fill="#5ec8ff" font-size="10" text-anchor="middle">Your 4×8 (172)</text>
  <text x="315" y="103" fill="#5ec8ff" font-size="9">~7-10 mmol</text>
</svg>
<div class="w-controls">
  <button onclick="lacPulse()">Show: where your work sits</button>
</div>
<div class="lac-readout" id="lacReadout">Your individual zones: LT1=147 (Z2 ceiling), LT2=158 (MLSS). 4×8 at 172 is supra-MLSS — lactate accumulates.</div>
<script>
function lacPulse(){
  const svg = document.getElementById('lacSvg');
  const lines = svg.querySelectorAll('line[stroke="#5ec8ff"]');
  lines.forEach(l => {
    l.style.animation = 'none';
    void l.getBBox();
    l.style.animation = 'pulse 1s ease-in-out 3';
  });
}
</script>
'''
    return _wrap(
        "lac-widget",
        "Your lactate curve — LT1, LT2, and 4×8 work",
        body,
        "Lactate threshold zones anchored to your indoor data. Above LT2 = supra-MLSS.",
    )


def lever_calculator() -> str:
    body = '''
<div class="lc-container">
  <svg viewBox="0 0 500 200" class="w-svg" xmlns="http://www.w3.org/2000/svg">
    <line x1="50" y1="120" x2="450" y2="120" stroke="#5ec8ff" stroke-width="6" stroke-linecap="round" id="lcBar"/>
    <circle id="lcFulcrum" cx="100" cy="120" r="10" fill="#ffb86b"/>
    <text x="100" y="155" fill="#ffb86b" font-size="11" text-anchor="middle">Fulcrum (joint)</text>
    <g id="lcLoad" transform="translate(400, 95)">
      <rect x="-12" y="-12" width="24" height="24" fill="#ff7a7a" rx="3"/>
      <text x="0" y="40" fill="#ff7a7a" font-size="11" text-anchor="middle">Load</text>
    </g>
    <g id="lcEffort" transform="translate(250, 50)">
      <path d="M 0 0 L -8 -15 L 8 -15 Z" fill="#67e8b0"/>
      <line x1="0" y1="0" x2="0" y2="70" stroke="#67e8b0" stroke-width="2"/>
      <text x="0" y="-22" fill="#67e8b0" font-size="11" text-anchor="middle">Effort (muscle)</text>
    </g>
  </svg>
  <div class="w-controls">
    <label>Load weight: <b id="lcLoadLbl">100</b> lb</label>
    <input type="range" min="10" max="500" step="10" value="100" id="lcLoad_s" class="w-slider">
    <label>Effort moment arm: <b id="lcEffortLbl">15</b> cm</label>
    <input type="range" min="3" max="20" step="1" value="15" id="lcEffort_s" class="w-slider">
    <label>Load moment arm: <b id="lcLoadArm_s_lbl">35</b> cm</label>
    <input type="range" min="10" max="50" step="1" value="35" id="lcLoadArm_s" class="w-slider">
  </div>
  <div class="lc-output">
    <div>Torque on load side = <b id="lcLoadTq">35 N·m equivalent</b></div>
    <div>Force muscle must produce = <b id="lcMuscleF">2.3×</b> the load</div>
    <div class="lc-context" id="lcContext">Most human joints are 3rd-class levers — muscle works at mechanical disadvantage for FORCE, advantage for SPEED.</div>
  </div>
</div>
<script>
(function(){
  const loadS = document.getElementById('lcLoad_s');
  const effortS = document.getElementById('lcEffort_s');
  const loadArmS = document.getElementById('lcLoadArm_s');
  function update(){
    const L = +loadS.value, eA = +effortS.value, lA = +loadArmS.value;
    document.getElementById('lcLoadLbl').textContent = L;
    document.getElementById('lcEffortLbl').textContent = eA;
    document.getElementById('lcLoadArm_s_lbl').textContent = lA;
    const ratio = lA / eA;
    document.getElementById('lcLoadTq').textContent = (L * lA / 10).toFixed(0) + ' arbitrary units';
    document.getElementById('lcMuscleF').textContent = ratio.toFixed(2) + '× the load';
    const ctx = document.getElementById('lcContext');
    if(ratio > 5) ctx.textContent = `Long limbs / extreme leverage — muscle force demand is ${ratio.toFixed(1)}× the load. Brutal.`;
    else if(ratio > 2) ctx.textContent = `Typical 3rd-class lever — mechanical disadvantage for force (~${ratio.toFixed(1)}×) but advantage for range and speed.`;
    else ctx.textContent = `Favorable leverage — close to 1:1 or better. Rare in human joints.`;
    // Move SVG load
    const newX = 100 + lA * 7;
    document.getElementById('lcLoad').setAttribute('transform', `translate(${newX}, 95)`);
    document.getElementById('lcEffort').setAttribute('transform', `translate(${100 + eA * 7}, 50)`);
  }
  loadS.addEventListener('input', update);
  effortS.addEventListener('input', update);
  loadArmS.addEventListener('input', update);
  update();
})();
</script>
'''
    return _wrap(
        "lc-widget",
        "Torque & lever calculator",
        body,
        "Drag the moment arms to see why long limbs create force disadvantage at the joint.",
    )


def force_velocity_curve() -> str:
    body = '''
<svg viewBox="0 0 400 240" class="w-svg" id="fvSvg" xmlns="http://www.w3.org/2000/svg">
  <line x1="50" y1="200" x2="380" y2="200" stroke="#2d3548"/>
  <line x1="50" y1="200" x2="50" y2="30" stroke="#2d3548"/>
  <text x="215" y="225" fill="#9ba3b4" font-size="11" text-anchor="middle">Velocity →</text>
  <text x="20" y="115" fill="#9ba3b4" font-size="11" text-anchor="middle" transform="rotate(-90, 20, 115)">Force</text>
  <path d="M 50 50 L 70 55 L 100 65 L 140 80 L 200 110 L 260 145 L 320 175 L 370 195"
        fill="none" stroke="#5ec8ff" stroke-width="2.5"/>
  <path d="M 50 50 L 70 35 L 100 25 L 130 22 L 160 30 L 200 50 L 260 100 L 320 165 L 370 200"
        fill="none" stroke="#ffb86b" stroke-width="2" stroke-dasharray="5 3"/>
  <text x="105" y="20" fill="#ffb86b" font-size="10">Power = F × V</text>
  <text x="330" y="50" fill="#5ec8ff" font-size="10">Force curve</text>
  <circle id="fvDot" cx="140" cy="80" r="6" fill="#67e8b0" stroke="#fff" stroke-width="2"/>
  <line x1="50" y1="200" x2="50" y2="200" id="fvForceLine" stroke="#5ec8ff" stroke-width="2" stroke-dasharray="3 3"/>
  <line x1="50" y1="200" x2="50" y2="200" id="fvVelLine" stroke="#5ec8ff" stroke-width="2" stroke-dasharray="3 3"/>
</svg>
<div class="w-controls">
  <label>Movement velocity: <b id="fvVel">low (heavy lift)</b></label>
  <input type="range" min="0" max="100" value="25" id="fvSlider" class="w-slider">
</div>
<div class="fv-output">
  <div>Force: <b id="fvForce">85%</b> of max</div>
  <div>Power: <b id="fvPower">21%</b> of max</div>
  <div class="lc-context" id="fvContext">Heavy slow lifts — high force, low velocity, low power. Strength training territory.</div>
</div>
<script>
(function(){
  const slider = document.getElementById('fvSlider');
  const dot = document.getElementById('fvDot');
  const fLine = document.getElementById('fvForceLine');
  const vLine = document.getElementById('fvVelLine');
  function force(v){ return 100 * Math.exp(-v / 50); }
  slider.addEventListener('input', e => {
    const v = +e.target.value;
    const x = 50 + v * 3.3;
    const f = force(v);
    const y = 200 - f * 1.5;
    const power = (f * v) / 100;
    dot.setAttribute('cx', x);
    dot.setAttribute('cy', y);
    fLine.setAttribute('x1', 50); fLine.setAttribute('x2', x);
    fLine.setAttribute('y1', y); fLine.setAttribute('y2', y);
    vLine.setAttribute('x1', x); vLine.setAttribute('x2', x);
    vLine.setAttribute('y1', y); vLine.setAttribute('y2', 200);
    document.getElementById('fvForce').textContent = Math.round(f) + '%';
    document.getElementById('fvPower').textContent = Math.round(power) + '%';
    document.getElementById('fvVel').textContent = v < 20 ? 'low (heavy lift)' : v < 50 ? 'moderate' : v < 80 ? 'high (jump/throw)' : 'maximal';
    const c = document.getElementById('fvContext');
    if(v < 20) c.textContent = 'Heavy slow lifts — high force, low velocity, low power. Strength training.';
    else if(v < 40) c.textContent = `Peak power region begins (~30% max force). Olympic lifts and explosive work.`;
    else if(v < 70) c.textContent = 'High velocity — power continues high, force drops. Ballistic movements.';
    else c.textContent = 'Maximal velocity — very low force, low power. Sprint/unloaded.';
  });
  slider.dispatchEvent(new Event('input'));
})();
</script>
'''
    return _wrap(
        "fv-widget",
        "Force-velocity-power curve",
        body,
        "Drag the dot along the curve. Peak power lives at ~30% max isometric force — the F-V intersection.",
    )


def hormone_response_compare() -> str:
    body = '''
<div class="hr-container">
  <div class="hr-protocol" data-protocol="A">
    <div class="hr-name">Protocol A: 3×5 squats @ 90%, 3 min rest</div>
    <div class="hr-bars">
      <div class="hr-row"><span>Testosterone</span><div class="hr-bar"><div class="hr-fill" style="width: 30%; background: #5ec8ff;"></div></div><b>+30%</b></div>
      <div class="hr-row"><span>GH</span><div class="hr-bar"><div class="hr-fill" style="width: 25%; background: #67e8b0;"></div></div><b>+25%</b></div>
      <div class="hr-row"><span>Cortisol</span><div class="hr-bar"><div class="hr-fill" style="width: 40%; background: #ffb86b;"></div></div><b>+40%</b></div>
    </div>
  </div>
  <div class="hr-protocol active" data-protocol="B">
    <div class="hr-name">Protocol B: 4×10 squats @ 75%, 60s rest</div>
    <div class="hr-bars">
      <div class="hr-row"><span>Testosterone</span><div class="hr-bar"><div class="hr-fill" style="width: 65%; background: #5ec8ff;"></div></div><b>+65%</b></div>
      <div class="hr-row"><span>GH</span><div class="hr-bar"><div class="hr-fill" style="width: 90%; background: #67e8b0;"></div></div><b>+90%</b></div>
      <div class="hr-row"><span>Cortisol</span><div class="hr-bar"><div class="hr-fill" style="width: 75%; background: #ffb86b;"></div></div><b>+75%</b></div>
    </div>
  </div>
  <div class="hr-context">
    Higher total volume + larger muscle mass + shorter rest = bigger acute anabolic spike.
    Protocol B's GH response is roughly 3× larger. This is why classic hypertrophy parameters
    are 6-12 reps with short rest.
  </div>
</div>
'''
    return _wrap(
        "hr-widget",
        "Acute hormonal response — protocol comparison",
        body,
        "Same lift, different parameters → very different endocrine response.",
    )


def adaptation_timeline() -> str:
    body = '''
<svg viewBox="0 0 500 220" class="w-svg" xmlns="http://www.w3.org/2000/svg">
  <line x1="40" y1="180" x2="470" y2="180" stroke="#2d3548"/>
  <line x1="40" y1="180" x2="40" y2="30" stroke="#2d3548"/>
  <text x="255" y="205" fill="#9ba3b4" font-size="11" text-anchor="middle">Weeks of training</text>
  <text x="20" y="105" fill="#9ba3b4" font-size="11" text-anchor="middle" transform="rotate(-90, 20, 105)">Contribution</text>
  <path d="M 40 50 Q 100 60 160 90 Q 220 130 280 160 Q 340 173 470 175" fill="rgba(94, 200, 255, 0.15)" stroke="#5ec8ff" stroke-width="2.5"/>
  <text x="50" y="45" fill="#5ec8ff" font-size="11">Neural adaptation (dominant 0-4 wk)</text>
  <path d="M 40 175 Q 130 160 200 110 Q 280 70 360 55 Q 420 48 470 45" fill="rgba(255, 184, 107, 0.15)" stroke="#ffb86b" stroke-width="2.5"/>
  <text x="280" y="60" fill="#ffb86b" font-size="11">Hypertrophy (dominant 6+ wk)</text>
  <g>
    <text x="40" y="195" fill="#5a6378" font-size="9">0</text>
    <text x="125" y="195" fill="#5a6378" font-size="9">4</text>
    <text x="210" y="195" fill="#5a6378" font-size="9">8</text>
    <text x="295" y="195" fill="#5a6378" font-size="9">12</text>
    <text x="380" y="195" fill="#5a6378" font-size="9">16</text>
    <text x="465" y="195" fill="#5a6378" font-size="9">20+</text>
  </g>
</svg>
<div class="w-controls">
  <button onclick="adapPulse('neural')">Highlight neural</button>
  <button onclick="adapPulse('hyper')">Highlight hypertrophy</button>
</div>
<div class="lc-context">
  First 4 weeks: gains are mostly NEURAL (recruitment, rate coding, reduced inhibition).
  Hypertrophy starts contributing ~4-6 weeks, becomes dominant after 8.
  Connective tissue adapts SLOWER — this is the injury-risk window when load is jumped.
</div>
'''
    return _wrap(
        "adap-widget",
        "Anaerobic training adaptation timeline",
        body,
        "Neural-first, hypertrophy-second. Beginner 'newbie gains' are real and mostly neurological.",
    )


def polarized_donut() -> str:
    body = '''
<div class="pd-container">
  <div class="pd-side">
    <h4>Polarized (Seiler 80/20)</h4>
    <svg viewBox="0 0 200 200" class="w-svg" xmlns="http://www.w3.org/2000/svg">
      <circle cx="100" cy="100" r="80" fill="none" stroke="#67e8b0" stroke-width="36" stroke-dasharray="402 502" transform="rotate(-90 100 100)"/>
      <circle cx="100" cy="100" r="80" fill="none" stroke="#ff7a7a" stroke-width="36" stroke-dasharray="100 502" stroke-dashoffset="-402" transform="rotate(-90 100 100)"/>
      <text x="100" y="98" fill="#fff" font-size="14" text-anchor="middle" font-weight="600">80%</text>
      <text x="100" y="118" fill="#9ba3b4" font-size="11" text-anchor="middle">Z1-Z2</text>
    </svg>
    <div class="pd-legend"><span class="pd-dot" style="background: #67e8b0"></span>Z1-Z2 (≤LT1) · 80%</div>
    <div class="pd-legend"><span class="pd-dot" style="background: #ff7a7a"></span>Z3+ (≥LT2) · 20%</div>
  </div>
  <div class="pd-side">
    <h4>Pyramidal (alternative)</h4>
    <svg viewBox="0 0 200 200" class="w-svg" xmlns="http://www.w3.org/2000/svg">
      <circle cx="100" cy="100" r="80" fill="none" stroke="#67e8b0" stroke-width="36" stroke-dasharray="302 502" transform="rotate(-90 100 100)"/>
      <circle cx="100" cy="100" r="80" fill="none" stroke="#ffb86b" stroke-width="36" stroke-dasharray="125 502" stroke-dashoffset="-302" transform="rotate(-90 100 100)"/>
      <circle cx="100" cy="100" r="80" fill="none" stroke="#ff7a7a" stroke-width="36" stroke-dasharray="75 502" stroke-dashoffset="-427" transform="rotate(-90 100 100)"/>
      <text x="100" y="98" fill="#fff" font-size="14" text-anchor="middle" font-weight="600">60/25/15</text>
    </svg>
    <div class="pd-legend"><span class="pd-dot" style="background: #67e8b0"></span>Z1-Z2 · 60%</div>
    <div class="pd-legend"><span class="pd-dot" style="background: #ffb86b"></span>Z3 (gray) · 25%</div>
    <div class="pd-legend"><span class="pd-dot" style="background: #ff7a7a"></span>Z4+ · 15%</div>
  </div>
</div>
<div class="lc-context">
  Seiler's polarized model: ~80% sessions in easy zone, ~20% in hard zone, minimize the middle "gray zone."
  Measured by SESSION COUNT, not minutes. Your block follows this — 4×8 and 10×1000m are the polar Z3+ sessions.
</div>
'''
    return _wrap(
        "pd-widget",
        "Polarized vs Pyramidal — session distribution",
        body,
        "Two valid distributions of endurance training intensity.",
    )


def squat_form_visualizer() -> str:
    body = '''
<div class="sf-container">
  <svg viewBox="0 0 300 380" class="w-svg" xmlns="http://www.w3.org/2000/svg">
    <line x1="40" y1="370" x2="260" y2="370" stroke="#3a4358" stroke-width="2"/>
    <g id="squatFig">
      <line x1="150" y1="60" x2="150" y2="155" stroke="#e6e9ef" stroke-width="6" stroke-linecap="round"/>
      <circle cx="150" cy="40" r="20" fill="#e6e9ef"/>
      <line x1="105" y1="80" x2="195" y2="80" stroke="#5ec8ff" stroke-width="6" stroke-linecap="round"/>
      <rect x="95" y="73" width="110" height="14" fill="none" stroke="#5ec8ff" stroke-width="1.5" rx="3"/>
      <line id="lThigh" x1="150" y1="160" x2="130" y2="240" stroke="#e6e9ef" stroke-width="6" stroke-linecap="round"/>
      <line id="lShin" x1="130" y1="240" x2="135" y2="350" stroke="#e6e9ef" stroke-width="6" stroke-linecap="round"/>
      <line id="rThigh" x1="150" y1="160" x2="170" y2="240" stroke="#e6e9ef" stroke-width="6" stroke-linecap="round"/>
      <line id="rShin" x1="170" y1="240" x2="165" y2="350" stroke="#e6e9ef" stroke-width="6" stroke-linecap="round"/>
    </g>
    <g class="sf-cues" id="sfCues">
      <g class="sf-cue" data-cue="chest" transform="translate(220, 90)">
        <circle r="11" fill="#5ec8ff"/><text y="4" text-anchor="middle" fill="#0f1419" font-size="11" font-weight="600">1</text>
      </g>
      <g class="sf-cue" data-cue="knee" transform="translate(105, 220)">
        <circle r="11" fill="#67e8b0"/><text y="4" text-anchor="middle" fill="#0f1419" font-size="11" font-weight="600">2</text>
      </g>
      <g class="sf-cue" data-cue="depth" transform="translate(210, 200)">
        <circle r="11" fill="#ffb86b"/><text y="4" text-anchor="middle" fill="#0f1419" font-size="11" font-weight="600">3</text>
      </g>
      <g class="sf-cue" data-cue="foot" transform="translate(115, 360)">
        <circle r="11" fill="#ff7a7a"/><text y="4" text-anchor="middle" fill="#0f1419" font-size="11" font-weight="600">4</text>
      </g>
    </g>
  </svg>
  <div class="sf-info">
    <h4>Click a numbered cue</h4>
    <div id="sfCueText" class="sf-cue-text">Click a numbered marker on the figure to see the coaching cue.</div>
    <div class="w-controls">
      <button onclick="sfAnim()" id="sfBtn">▶ Animate descent</button>
    </div>
  </div>
</div>
<script>
(function(){
  const cues = {
    chest: { title: 'Chest up', text: 'Maintain neutral spine. Cue: "chest tall" or "proud chest." Prevents forward lean and lumbar flexion.' },
    knee: { title: 'Knees track over toes', text: 'Knee valgus (caving in) is the most common fault. Cue: "knees out" or "spread the floor."' },
    depth: { title: 'Depth: parallel or below', text: 'Femur parallel to floor at minimum. Hip crease at or below top of knee. Don\\'t butt-wink.' },
    foot: { title: 'Whole-foot contact', text: 'Drive through midfoot. Big toe, pinky toe, heel — all stay grounded. Tripod foot.' }
  };
  document.querySelectorAll('.sf-cue').forEach(c => {
    c.addEventListener('click', () => {
      const k = c.dataset.cue;
      const txt = document.getElementById('sfCueText');
      txt.innerHTML = '<b>' + cues[k].title + '</b><br>' + cues[k].text;
      document.querySelectorAll('.sf-cue circle').forEach(ci => ci.setAttribute('r', '11'));
      c.querySelector('circle').setAttribute('r', '14');
    });
  });
  let anim = null;
  window.sfAnim = function(){
    const btn = document.getElementById('sfBtn');
    if(anim){ clearInterval(anim); anim = null; btn.textContent = '▶ Animate descent'; resetFig(); return; }
    btn.textContent = '⏸ Pause';
    let t = 0, dir = 1;
    anim = setInterval(() => {
      t += dir * 0.04;
      if(t > 1){ t = 1; dir = -1; }
      if(t < 0){ t = 0; dir = 1; }
      const hipDrop = t * 80;
      const lThigh = document.getElementById('lThigh');
      const rThigh = document.getElementById('rThigh');
      const lShin = document.getElementById('lShin');
      const rShin = document.getElementById('rShin');
      lThigh.setAttribute('y1', 160 + hipDrop);
      rThigh.setAttribute('y1', 160 + hipDrop);
      lShin.setAttribute('y1', 240 + hipDrop * 0.3);
      rShin.setAttribute('y1', 240 + hipDrop * 0.3);
    }, 40);
  };
  function resetFig(){
    document.getElementById('lThigh').setAttribute('y1', 160);
    document.getElementById('rThigh').setAttribute('y1', 160);
    document.getElementById('lShin').setAttribute('y1', 240);
    document.getElementById('rShin').setAttribute('y1', 240);
  }
})();
</script>
'''
    return _wrap(
        "sf-widget",
        "Squat form — interactive cues",
        body,
        "Click numbered markers for technique points. Press play to animate the descent.",
    )


def macro_calculator() -> str:
    body = '''
<div class="mc-container">
  <div class="mc-inputs">
    <label>Body weight (kg): <b id="mcWt">75</b></label>
    <input type="range" min="40" max="130" value="75" id="mcWtS" class="w-slider">
    <label>Training focus:</label>
    <div class="mc-focus">
      <button class="mc-fbtn active" data-focus="endurance" onclick="mcFocus('endurance')">Endurance</button>
      <button class="mc-fbtn" data-focus="hybrid" onclick="mcFocus('hybrid')">Hybrid</button>
      <button class="mc-fbtn" data-focus="hypertrophy" onclick="mcFocus('hypertrophy')">Hypertrophy</button>
    </div>
  </div>
  <div class="mc-output">
    <div class="mc-macro"><span class="mc-l">Carbohydrate</span><b id="mcCho">450 g</b><span class="mc-r">(<span id="mcChoR">6</span> g/kg)</span></div>
    <div class="mc-macro"><span class="mc-l">Protein</span><b id="mcPro">120 g</b><span class="mc-r">(<span id="mcProR">1.6</span> g/kg)</span></div>
    <div class="mc-macro"><span class="mc-l">Fat</span><b id="mcFat">75 g</b><span class="mc-r">(≥20% kcal)</span></div>
    <div class="mc-total">~<b id="mcKcal">3000</b> kcal/day</div>
  </div>
</div>
<script>
(function(){
  let focus = 'endurance';
  const ratios = {
    endurance:  { c: 7,   p: 1.6, f: 1.0 },
    hybrid:     { c: 6,   p: 1.8, f: 1.0 },
    hypertrophy:{ c: 5,   p: 2.0, f: 1.0 }
  };
  function update(){
    const w = +document.getElementById('mcWtS').value;
    const r = ratios[focus];
    const c = w * r.c, p = w * r.p, f = w * r.f;
    document.getElementById('mcWt').textContent = w;
    document.getElementById('mcCho').textContent = c.toFixed(0) + ' g';
    document.getElementById('mcChoR').textContent = r.c;
    document.getElementById('mcPro').textContent = p.toFixed(0) + ' g';
    document.getElementById('mcProR').textContent = r.p;
    document.getElementById('mcFat').textContent = f.toFixed(0) + ' g';
    document.getElementById('mcKcal').textContent = (c*4 + p*4 + f*9).toFixed(0);
  }
  window.mcFocus = function(k){
    focus = k;
    document.querySelectorAll('.mc-fbtn').forEach(b => b.classList.toggle('active', b.dataset.focus === k));
    update();
  };
  document.getElementById('mcWtS').addEventListener('input', update);
  update();
})();
</script>
'''
    return _wrap(
        "mc-widget",
        "Macro calculator",
        body,
        "Slide your weight and pick a focus. Numbers from CSCS / ISSN guidelines.",
    )


def inverted_u() -> str:
    body = (
        '<svg viewBox="0 0 400 240" class="w-svg" xmlns="http://www.w3.org/2000/svg">'
        '<line x1="40" y1="200" x2="380" y2="200" stroke="#2d3548"/>'
        '<line x1="40" y1="200" x2="40" y2="30" stroke="#2d3548"/>'
        '<text x="210" y="225" fill="#9ba3b4" font-size="11" text-anchor="middle">Arousal level</text>'
        '<text x="20" y="115" fill="#9ba3b4" font-size="11" text-anchor="middle" transform="rotate(-90, 20, 115)">Performance</text>'
        '<path d="M 40 195 Q 90 180 130 150 Q 180 100 210 80 Q 250 95 290 140 Q 330 170 380 195" fill="none" stroke="#ffb86b" stroke-width="3"/>'
        '<circle id="iuDot" cx="100" cy="170" r="7" fill="#5ec8ff" stroke="#fff" stroke-width="2"/>'
        '</svg>'
        '<div class="w-controls">'
        '<label>Arousal: <b id="iuLbl">low</b></label>'
        '<input type="range" min="0" max="100" value="20" id="iuS" class="w-slider">'
        '</div>'
        '<div class="lc-context" id="iuCtx">Under-aroused. Need to elevate state.</div>'
        '<script>'
        '(function(){'
        'const s = document.getElementById("iuS"), dot = document.getElementById("iuDot");'
        'function perf(a){ return 80 + 95 * Math.exp(-Math.pow((a-50)/22, 2)); }'
        's.addEventListener("input", e => {'
        'const a = +e.target.value;'
        'const x = 40 + a * 3.4;'
        'const y = 200 - (perf(a) - 80);'
        'dot.setAttribute("cx", x); dot.setAttribute("cy", y);'
        'const lbl = document.getElementById("iuLbl"), ctx = document.getElementById("iuCtx");'
        'if(a < 25){ lbl.textContent = "low"; ctx.textContent = "Under-aroused. Need to elevate state."; }'
        'else if(a < 45){ lbl.textContent = "rising"; ctx.textContent = "Approaching optimal. Cognitive focus building."; }'
        'else if(a < 65){ lbl.textContent = "optimal"; ctx.textContent = "Peak performance zone. IZOF range."; }'
        'else if(a < 85){ lbl.textContent = "high"; ctx.textContent = "Over-aroused. Tightness reduces skilled performance."; }'
        'else { lbl.textContent = "panic"; ctx.textContent = "Choking territory. Attentional control compromised."; }'
        '});'
        '})();'
        '</script>'
    )
    return _wrap("iu-widget", "Inverted-U arousal curve", body, "Drag the slider. Performance peaks at moderate arousal.")


WIDGETS = {
    "muscle_fiber_types": sarcomere_animation,
    "motor_units": motor_unit_recruitment,
    "ec_coupling": ec_coupling_steps,
    "cardiovascular": heart_calculator,
    "respiratory": bohr_curve,
    "atp_pcr": energy_systems_timeline,
    "glycolysis": lactate_curve,
    "oxidative": energy_systems_timeline,
    "energy_system_interaction": energy_systems_timeline,
    "biomech_levers": lever_calculator,
    "force_velocity_length_tension": force_velocity_curve,
    "anabolic_hormones": hormone_response_compare,
    "catabolic_hormones": hormone_response_compare,
    "anaerobic_adaptations": adaptation_timeline,
    "aerobic_adaptations": polarized_donut,
    "sport_psych": inverted_u,
    "macros": macro_calculator,
    "nutrient_timing": macro_calculator,
    "ex_squat": squat_form_visualizer,
    "aerobic_programming": polarized_donut,
    "phase1_review": energy_systems_timeline,
}


def render(topic_id: str) -> str:
    fn = WIDGETS.get(topic_id)
    if fn:
        return fn()
    return ""
