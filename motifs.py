"""
Topic motifs — each lesson topic gets its own visual identity that reflects
the subject matter. The motif drives the primary palette, background pattern,
hero banner illustration, and typography hint. The procedural theme generator
still adds daily variation, but the motif establishes the topical tone.

Today's lesson on muscle architecture should LOOK like an anatomy textbook,
not a generic neon UI.
"""
from __future__ import annotations


# Each motif provides:
#   name: human-readable label
#   primary_hex: primary topical color
#   secondary_hex / tertiary_hex: harmonized accents
#   bg_overlay: SVG/CSS background pattern as a data URL fragment or "none"
#   font_stack: font family appropriate to the topic
#   hero_svg: inline SVG illustration shown at the top of the lesson card
#   accent_label: small caption next to the hero
#
# Topic categories share visual languages — anatomy uses striated reds,
# cardio uses pulse motifs, biomechanics uses blueprint blue, etc.


def _stripes_pattern(color: str, opacity: float = 0.06, angle: int = 90, width: int = 14) -> str:
    """A subtle repeating-linear-gradient stripe pattern — looks like muscle striations or paper rule."""
    return (
        f"repeating-linear-gradient({angle}deg, "
        f"transparent 0px, transparent {width - 1}px, "
        f"rgba({_hex_to_rgb(color)}, {opacity}) {width - 1}px, "
        f"rgba({_hex_to_rgb(color)}, {opacity}) {width}px)"
    )


def _grid_pattern(color: str, opacity: float = 0.05, size: int = 40) -> str:
    """A blueprint-style square grid."""
    rgba = f"rgba({_hex_to_rgb(color)}, {opacity})"
    return (
        f"linear-gradient({rgba} 1px, transparent 1px) 0 0 / {size}px {size}px, "
        f"linear-gradient(90deg, {rgba} 1px, transparent 1px) 0 0 / {size}px {size}px"
    )


def _dots_pattern(color: str, opacity: float = 0.10, size: int = 24) -> str:
    """Polka-dot pattern — molecular feel."""
    rgba = f"rgba({_hex_to_rgb(color)}, {opacity})"
    return f"radial-gradient(circle at 50% 50%, {rgba} 1.4px, transparent 2px) 0 0 / {size}px {size}px"


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


# ─────────────────── HERO SVGs ───────────────────

def _hero_muscle_fiber() -> str:
    """Striated muscle fiber bundle — parallel banded cylinders."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="fiberGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#5a1a26" stop-opacity="0.0"/>
      <stop offset="20%" stop-color="#a33344" stop-opacity="0.9"/>
      <stop offset="80%" stop-color="#a33344" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#5a1a26" stop-opacity="0.0"/>
    </linearGradient>
    <pattern id="striations" x="0" y="0" width="14" height="40" patternUnits="userSpaceOnUse">
      <rect width="14" height="40" fill="url(#fiberGrad)"/>
      <line x1="0" y1="20" x2="14" y2="20" stroke="#3a0d18" stroke-width="0.6" opacity="0.6"/>
      <line x1="0" y1="8" x2="14" y2="8" stroke="#ffe0d5" stroke-width="0.3" opacity="0.5"/>
      <line x1="0" y1="32" x2="14" y2="32" stroke="#ffe0d5" stroke-width="0.3" opacity="0.5"/>
    </pattern>
  </defs>
  <rect x="0" y="20" width="600" height="22" fill="url(#striations)" rx="3"/>
  <rect x="0" y="46" width="600" height="22" fill="url(#striations)" rx="3" opacity="0.95"/>
  <rect x="0" y="72" width="600" height="22" fill="url(#striations)" rx="3" opacity="0.9"/>
  <rect x="0" y="98" width="600" height="22" fill="url(#striations)" rx="3" opacity="0.85"/>
</svg>'''


def _hero_neuron() -> str:
    """Branching neuron / motor unit network."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <defs>
    <radialGradient id="cellG" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#7fe5ff"/><stop offset="100%" stop-color="#2a87b8"/></radialGradient>
  </defs>
  <g stroke="#7fe5ff" stroke-width="1.4" fill="none" opacity="0.8">
    <path d="M 80 70 Q 140 30 200 60 T 320 50 T 460 80"/>
    <path d="M 80 70 Q 130 110 200 95 T 340 105 T 500 70"/>
    <path d="M 200 60 Q 220 30 250 25 M 200 60 Q 215 20 240 10"/>
    <path d="M 320 50 Q 340 20 370 18 M 320 50 Q 355 35 390 30"/>
    <path d="M 200 95 Q 220 120 250 130 M 200 95 Q 225 125 260 135"/>
    <path d="M 340 105 Q 360 130 395 135"/>
  </g>
  <circle cx="80" cy="70" r="14" fill="url(#cellG)" stroke="#fff" stroke-width="1.5"/>
  <circle cx="200" cy="60" r="6" fill="#7fe5ff"/>
  <circle cx="200" cy="95" r="6" fill="#7fe5ff"/>
  <circle cx="320" cy="50" r="6" fill="#7fe5ff"/>
  <circle cx="340" cy="105" r="6" fill="#7fe5ff"/>
  <circle cx="460" cy="80" r="6" fill="#7fe5ff"/>
  <circle cx="500" cy="70" r="6" fill="#7fe5ff"/>
  <g opacity="0.9">
    <circle cx="250" cy="25" r="2.5" fill="#5ec8ff"/>
    <circle cx="240" cy="10" r="2.5" fill="#5ec8ff"/>
    <circle cx="370" cy="18" r="2.5" fill="#5ec8ff"/>
    <circle cx="390" cy="30" r="2.5" fill="#5ec8ff"/>
    <circle cx="250" cy="130" r="2.5" fill="#5ec8ff"/>
    <circle cx="260" cy="135" r="2.5" fill="#5ec8ff"/>
    <circle cx="395" cy="135" r="2.5" fill="#5ec8ff"/>
  </g>
</svg>'''


def _hero_heart() -> str:
    """ECG line with heart silhouette."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <path d="M 0 80 L 100 80 L 130 80 L 145 40 L 160 120 L 175 70 L 190 75 L 220 80 L 360 80 L 380 80 L 395 40 L 410 120 L 425 70 L 440 75 L 470 80 L 600 80" fill="none" stroke="#ff5e5e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.85">
    <animate attributeName="stroke-dasharray" from="0 1200" to="1200 0" dur="3s" begin="0s" fill="freeze"/>
  </path>
  <g transform="translate(500, 60)">
    <path d="M 0 30 C -20 15 -25 0 -15 -10 C -5 -18 5 -10 10 0 C 15 -10 25 -18 35 -10 C 45 0 40 15 20 30 Z" fill="#ff5e5e" stroke="#7a1a26" stroke-width="1.5">
      <animateTransform attributeName="transform" type="scale" values="1;1.08;1" dur="0.9s" repeatCount="indefinite" additive="sum"/>
    </path>
  </g>
</svg>'''


def _hero_lungs() -> str:
    """Lung silhouette with airy gradient."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <defs>
    <radialGradient id="lungG" cx="50%" cy="50%" r="60%"><stop offset="0%" stop-color="#a8d8ff" stop-opacity="0.8"/><stop offset="100%" stop-color="#3a78b0" stop-opacity="0.3"/></radialGradient>
  </defs>
  <line x1="300" y1="20" x2="300" y2="80" stroke="#7fa6cf" stroke-width="3" stroke-linecap="round"/>
  <path d="M 285 60 Q 200 50 180 90 Q 165 130 220 130 Q 270 130 290 100 Z" fill="url(#lungG)" stroke="#5a8ab8" stroke-width="1.5"/>
  <path d="M 315 60 Q 400 50 420 90 Q 435 130 380 130 Q 330 130 310 100 Z" fill="url(#lungG)" stroke="#5a8ab8" stroke-width="1.5"/>
  <g stroke="#7fa6cf" stroke-width="1.2" fill="none" opacity="0.6">
    <path d="M 250 90 Q 230 100 220 115"/><path d="M 250 75 Q 220 80 210 95"/>
    <path d="M 350 90 Q 370 100 380 115"/><path d="M 350 75 Q 380 80 390 95"/>
  </g>
</svg>'''


def _hero_molecule() -> str:
    """Hexagonal molecular pattern — glucose / metabolic."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <defs>
    <pattern id="hexG" x="0" y="0" width="60" height="52" patternUnits="userSpaceOnUse">
      <polygon points="30,4 56,18 56,46 30,60 4,46 4,18" fill="none" stroke="#ffcc4a" stroke-width="1.2" opacity="0.55"/>
      <circle cx="30" cy="32" r="2" fill="#ffcc4a" opacity="0.7"/>
    </pattern>
  </defs>
  <rect width="600" height="140" fill="url(#hexG)"/>
  <g transform="translate(280, 50)">
    <polygon points="30,4 56,18 56,46 30,60 4,46 4,18" fill="#ffcc4a" stroke="#a37a1f" stroke-width="2" opacity="0.85"/>
    <text x="30" y="38" text-anchor="middle" fill="#3a2a08" font-size="13" font-weight="700">ATP</text>
  </g>
</svg>'''


def _hero_blueprint() -> str:
    """Engineering blueprint — lever with torque vectors."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <defs>
    <pattern id="bpGrid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#3a78b0" stroke-width="0.4" opacity="0.4"/>
    </pattern>
  </defs>
  <rect width="600" height="140" fill="url(#bpGrid)"/>
  <line x1="80" y1="80" x2="520" y2="80" stroke="#7fc4ff" stroke-width="5" stroke-linecap="round"/>
  <circle cx="140" cy="80" r="9" fill="#ffcc4a" stroke="#7fc4ff" stroke-width="2"/>
  <rect x="460" y="58" width="40" height="44" fill="none" stroke="#7fc4ff" stroke-width="2"/>
  <line x1="280" y1="80" x2="280" y2="30" stroke="#a8e1ff" stroke-width="2" stroke-dasharray="4 3"/>
  <polygon points="280,30 274,40 286,40" fill="#a8e1ff"/>
  <text x="296" y="38" fill="#a8e1ff" font-family="monospace" font-size="11">F · d = τ</text>
  <text x="140" y="108" fill="#a8e1ff" font-family="monospace" font-size="10" text-anchor="middle">fulcrum</text>
  <text x="480" y="124" fill="#a8e1ff" font-family="monospace" font-size="10" text-anchor="middle">load</text>
</svg>'''


def _hero_hormone() -> str:
    """Endocrine — hormone vials with droplet."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g opacity="0.85">
    <g transform="translate(180, 30)">
      <path d="M -12 0 L -12 4 L -8 6 L -8 60 Q -8 78 0 80 Q 8 78 8 60 L 8 6 L 12 4 L 12 0 Z" fill="rgba(255, 184, 74, 0.25)" stroke="#ffb84a" stroke-width="1.5"/>
      <rect x="-8" y="50" width="16" height="28" fill="#ffb84a" opacity="0.55"/>
    </g>
    <g transform="translate(300, 30)">
      <path d="M -12 0 L -12 4 L -8 6 L -8 60 Q -8 78 0 80 Q 8 78 8 60 L 8 6 L 12 4 L 12 0 Z" fill="rgba(255, 184, 74, 0.25)" stroke="#ffb84a" stroke-width="1.5"/>
      <rect x="-8" y="30" width="16" height="48" fill="#ffb84a" opacity="0.75"/>
    </g>
    <g transform="translate(420, 30)">
      <path d="M -12 0 L -12 4 L -8 6 L -8 60 Q -8 78 0 80 Q 8 78 8 60 L 8 6 L 12 4 L 12 0 Z" fill="rgba(255, 184, 74, 0.25)" stroke="#ffb84a" stroke-width="1.5"/>
      <rect x="-8" y="40" width="16" height="38" fill="#ffb84a" opacity="0.65"/>
    </g>
  </g>
  <text x="180" y="125" fill="#ffb84a" font-size="10" text-anchor="middle" font-family="monospace">Testosterone</text>
  <text x="300" y="125" fill="#ffb84a" font-size="10" text-anchor="middle" font-family="monospace">GH</text>
  <text x="420" y="125" fill="#ffb84a" font-size="10" text-anchor="middle" font-family="monospace">Cortisol</text>
</svg>'''


def _hero_growth() -> str:
    """Adaptations — ascending arrow with bar growth."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <line x1="40" y1="120" x2="560" y2="120" stroke="#558e5e" stroke-width="1.5"/>
  <g fill="#7fcf8e" opacity="0.85">
    <rect x="80" y="100" width="36" height="20" rx="2"/>
    <rect x="140" y="80" width="36" height="40" rx="2"/>
    <rect x="200" y="60" width="36" height="60" rx="2"/>
    <rect x="260" y="50" width="36" height="70" rx="2"/>
    <rect x="320" y="38" width="36" height="82" rx="2"/>
    <rect x="380" y="30" width="36" height="90" rx="2"/>
    <rect x="440" y="24" width="36" height="96" rx="2"/>
    <rect x="500" y="20" width="36" height="100" rx="2"/>
  </g>
  <path d="M 90 110 Q 250 80 540 25" fill="none" stroke="#a8efb8" stroke-width="2.5"/>
</svg>'''


def _hero_squat() -> str:
    """Strength — barbell with plates silhouette."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <line x1="40" y1="70" x2="560" y2="70" stroke="#c9c9c9" stroke-width="6" stroke-linecap="round"/>
  <g fill="#404040" stroke="#c9c9c9" stroke-width="1.5">
    <rect x="60" y="40" width="22" height="60" rx="3"/>
    <rect x="88" y="30" width="22" height="80" rx="3"/>
    <rect x="116" y="20" width="22" height="100" rx="3"/>
    <rect x="461" y="20" width="22" height="100" rx="3"/>
    <rect x="489" y="30" width="22" height="80" rx="3"/>
    <rect x="517" y="40" width="22" height="60" rx="3"/>
  </g>
  <line x1="40" y1="118" x2="560" y2="118" stroke="#666" stroke-width="1" stroke-dasharray="6 4"/>
</svg>'''


def _hero_chart() -> str:
    """Force-velocity / testing — scientific scatter with curve."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <line x1="50" y1="120" x2="550" y2="120" stroke="#4a5b78" stroke-width="1"/>
  <line x1="50" y1="20" x2="50" y2="120" stroke="#4a5b78" stroke-width="1"/>
  <path d="M 50 30 Q 150 50 250 70 T 450 105 L 540 115" fill="none" stroke="#7fdcff" stroke-width="2.5"/>
  <g fill="#7fdcff">
    <circle cx="80" cy="42" r="3"/><circle cx="120" cy="50" r="3"/>
    <circle cx="180" cy="62" r="3"/><circle cx="240" cy="72" r="3"/>
    <circle cx="320" cy="88" r="3"/><circle cx="400" cy="100" r="3"/>
    <circle cx="480" cy="112" r="3"/>
  </g>
  <text x="296" y="138" fill="#4a5b78" font-size="9" text-anchor="middle" font-family="monospace">velocity →</text>
</svg>'''


def _hero_leaf() -> str:
    """Nutrition — stylized leaf with grain."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(170, 20)">
    <path d="M 0 100 Q 30 -10 130 10 Q 100 90 0 100 Z" fill="#7ed68a" stroke="#3a8a4a" stroke-width="1.5" opacity="0.9"/>
    <path d="M 0 100 Q 30 80 60 60 Q 90 40 130 10" fill="none" stroke="#3a8a4a" stroke-width="1.5"/>
    <path d="M 30 80 Q 50 75 70 70" fill="none" stroke="#3a8a4a" stroke-width="0.9"/>
    <path d="M 50 65 Q 70 60 90 55" fill="none" stroke="#3a8a4a" stroke-width="0.9"/>
  </g>
  <g transform="translate(370, 30)">
    <circle cx="40" cy="50" r="40" fill="#ffb84a" opacity="0.8"/>
    <text x="40" y="55" text-anchor="middle" fill="#3a2008" font-size="14" font-weight="700">4 kcal/g</text>
  </g>
</svg>'''


def _hero_calendar() -> str:
    """Program design / periodization — calendar grid."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g fill="none" stroke="#b88fff" stroke-width="1.2">
    <rect x="50" y="20" width="500" height="100" rx="4"/>
    <line x1="50" y1="46" x2="550" y2="46"/>
    <line x1="120" y1="20" x2="120" y2="120"/>
    <line x1="190" y1="20" x2="190" y2="120"/>
    <line x1="260" y1="20" x2="260" y2="120"/>
    <line x1="330" y1="20" x2="330" y2="120"/>
    <line x1="400" y1="20" x2="400" y2="120"/>
    <line x1="470" y1="20" x2="470" y2="120"/>
  </g>
  <g fill="#b88fff" opacity="0.7">
    <rect x="55" y="52" width="60" height="22" rx="2"/>
    <rect x="125" y="80" width="60" height="22" rx="2" opacity="0.5"/>
    <rect x="195" y="52" width="60" height="22" rx="2"/>
    <rect x="265" y="80" width="60" height="22" rx="2" opacity="0.5"/>
    <rect x="335" y="52" width="60" height="22" rx="2"/>
    <rect x="405" y="80" width="60" height="22" rx="2" opacity="0.5"/>
    <rect x="475" y="52" width="60" height="22" rx="2"/>
  </g>
  <text x="55" y="38" fill="#d4b8ff" font-size="10" font-family="monospace">M  T  W  T  F  S  S</text>
</svg>'''


def _hero_brain() -> str:
    """Sport psych — brain silhouette."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(260, 10)">
    <path d="M 40 5 C 15 5 0 25 5 50 C -5 65 5 85 25 90 C 30 105 50 115 75 110 C 100 115 120 105 125 90 C 145 85 155 65 145 50 C 150 25 135 5 110 5 Q 90 -5 75 5 Q 60 -5 40 5 Z"
          fill="rgba(140, 200, 140, 0.25)" stroke="#7fc48e" stroke-width="1.8"/>
    <path d="M 25 90 Q 40 75 50 60 M 50 60 Q 70 50 75 30 M 75 30 Q 85 50 100 60 M 100 60 Q 110 75 125 90 M 75 30 L 75 110" fill="none" stroke="#7fc48e" stroke-width="1.2" opacity="0.7"/>
  </g>
</svg>'''


def _hero_lightning() -> str:
    """Power / plyometrics — lightning bolt with motion lines."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(270, 20)">
    <path d="M 30 0 L 10 60 L 28 60 L 18 100 L 50 40 L 32 40 L 42 0 Z" fill="#ffd84a" stroke="#a37a08" stroke-width="2"/>
  </g>
  <g stroke="#ffd84a" stroke-width="2" opacity="0.5" stroke-linecap="round">
    <line x1="120" y1="40" x2="220" y2="40"/>
    <line x1="100" y1="70" x2="200" y2="70"/>
    <line x1="120" y1="100" x2="220" y2="100"/>
    <line x1="380" y1="40" x2="480" y2="40"/>
    <line x1="400" y1="70" x2="500" y2="70"/>
    <line x1="380" y1="100" x2="480" y2="100"/>
  </g>
</svg>'''


def _hero_zones() -> str:
    """Endurance zones — stacked colored bars."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g rx="3">
    <rect x="60" y="20" width="480" height="18" fill="#7fe1c9" opacity="0.85" rx="2"/>
    <rect x="60" y="42" width="380" height="18" fill="#a8e187" opacity="0.85" rx="2"/>
    <rect x="60" y="64" width="280" height="18" fill="#ffd84a" opacity="0.85" rx="2"/>
    <rect x="60" y="86" width="180" height="18" fill="#ffa84a" opacity="0.85" rx="2"/>
    <rect x="60" y="108" width="80" height="18" fill="#ff5e5e" opacity="0.85" rx="2"/>
  </g>
  <g fill="#7a6f55" font-family="monospace" font-size="10">
    <text x="50" y="33" text-anchor="end">Z1</text>
    <text x="50" y="55" text-anchor="end">Z2</text>
    <text x="50" y="77" text-anchor="end">Z3</text>
    <text x="50" y="99" text-anchor="end">Z4</text>
    <text x="50" y="121" text-anchor="end">Z5</text>
  </g>
</svg>'''


def _hero_floorplan() -> str:
    """Facility — architectural floor plan."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g stroke="#7fc4ff" stroke-width="2" fill="none">
    <rect x="40" y="20" width="520" height="100"/>
    <line x1="200" y1="20" x2="200" y2="120"/>
    <line x1="400" y1="20" x2="400" y2="120"/>
    <line x1="200" y1="70" x2="400" y2="70"/>
  </g>
  <g fill="#a8e1ff" opacity="0.6" font-family="monospace" font-size="9" text-anchor="middle">
    <text x="120" y="75">FREE WT</text>
    <text x="300" y="50">RACKS</text>
    <text x="300" y="100">PLATFORMS</text>
    <text x="480" y="75">CARDIO</text>
  </g>
  <g fill="#7fc4ff">
    <circle cx="120" cy="40" r="3"/><circle cx="160" cy="50" r="3"/>
    <circle cx="80" cy="100" r="3"/><circle cx="140" cy="105" r="3"/>
  </g>
</svg>'''


def _hero_warmup() -> str:
    """Warm-up — ramping flame."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="rampG" x1="0" x2="1"><stop offset="0%" stop-color="#3a78b0"/><stop offset="50%" stop-color="#ffb84a"/><stop offset="100%" stop-color="#ff5e3a"/></linearGradient>
  </defs>
  <path d="M 40 120 L 560 30 L 560 120 Z" fill="url(#rampG)" opacity="0.75"/>
  <g fill="#fff" font-family="monospace" font-size="10" opacity="0.9">
    <text x="80" y="115" text-anchor="middle">R</text>
    <text x="200" y="100" text-anchor="middle">A</text>
    <text x="320" y="80" text-anchor="middle">M</text>
    <text x="440" y="55" text-anchor="middle">P</text>
  </g>
  <g fill="#fff" font-family="monospace" font-size="8" opacity="0.7">
    <text x="80" y="128" text-anchor="middle">Raise</text>
    <text x="200" y="128" text-anchor="middle">Activate</text>
    <text x="320" y="128" text-anchor="middle">Mobilize</text>
    <text x="440" y="128" text-anchor="middle">Potentiate</text>
  </g>
</svg>'''


def _hero_shield() -> str:
    """PEDs — warning shield."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(280, 20)">
    <path d="M 40 0 L 80 12 L 80 50 Q 80 90 40 100 Q 0 90 0 50 L 0 12 Z" fill="rgba(255, 94, 94, 0.25)" stroke="#ff5e5e" stroke-width="2.5"/>
    <text x="40" y="62" text-anchor="middle" fill="#ff5e5e" font-size="36" font-weight="800">!</text>
  </g>
  <g stroke="#ff5e5e" stroke-width="1.5" fill="none" opacity="0.6" stroke-dasharray="5 4">
    <line x1="120" y1="30" x2="240" y2="30"/>
    <line x1="120" y1="110" x2="240" y2="110"/>
    <line x1="380" y1="30" x2="500" y2="30"/>
    <line x1="380" y1="110" x2="500" y2="110"/>
  </g>
  <g fill="#ff5e5e" font-family="monospace" font-size="9" opacity="0.7" text-anchor="middle">
    <text x="180" y="70">WADA</text>
    <text x="440" y="70">BANNED</text>
  </g>
</svg>'''


def _hero_recovery() -> str:
    """Rehab — medical cross with timeline."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(280, 30)" fill="#a8e1c0">
    <rect x="14" y="0" width="12" height="40" rx="2"/>
    <rect x="0" y="14" width="40" height="12" rx="2"/>
  </g>
  <line x1="40" y1="110" x2="560" y2="110" stroke="#7fc4a0" stroke-width="2"/>
  <g fill="#7fc4a0" font-family="monospace" font-size="9" text-anchor="middle">
    <circle cx="100" cy="110" r="4"/><text x="100" y="128">acute</text>
    <circle cx="240" cy="110" r="4"/><text x="240" y="128">prolif</text>
    <circle cx="380" cy="110" r="4"/><text x="380" y="128">remodel</text>
    <circle cx="520" cy="110" r="4"/><text x="520" y="128">RTS</text>
  </g>
</svg>'''


def _hero_kaleidoscope() -> str:
    """Synthesis / review — multicolor geometric burst."""
    return '''<svg viewBox="0 0 600 140" class="hero-svg" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(300, 70)">
    <polygon points="0,-50 14,-15 50,-15 22,8 32,42 0,22 -32,42 -22,8 -50,-15 -14,-15" fill="#ff5e5e" opacity="0.45"/>
    <polygon points="0,-50 14,-15 50,-15 22,8 32,42 0,22 -32,42 -22,8 -50,-15 -14,-15" transform="rotate(36)" fill="#5ec8ff" opacity="0.45"/>
    <polygon points="0,-50 14,-15 50,-15 22,8 32,42 0,22 -32,42 -22,8 -50,-15 -14,-15" transform="rotate(72)" fill="#7fcf8e" opacity="0.45"/>
    <polygon points="0,-50 14,-15 50,-15 22,8 32,42 0,22 -32,42 -22,8 -50,-15 -14,-15" transform="rotate(108)" fill="#ffd84a" opacity="0.45"/>
    <polygon points="0,-50 14,-15 50,-15 22,8 32,42 0,22 -32,42 -22,8 -50,-15 -14,-15" transform="rotate(144)" fill="#c08fff" opacity="0.45"/>
  </g>
</svg>'''


# ─────────────────── MOTIF DEFINITIONS ───────────────────

MOTIFS = {
    # ANATOMY — striated reds, anatomical serif
    "anatomy": {
        "name": "Anatomy",
        "primary": "#a33344", "secondary": "#5a1a26", "tertiary": "#ffe0d5",
        "bg_overlay": lambda: _stripes_pattern("#a33344", 0.05, 90, 18),
        "font_stack": '"Charter", "Iowan Old Style", "Georgia", "Hoefler Text", serif',
        "hero_fn": _hero_muscle_fiber,
        "accent_label": "Histology · anatomy",
    },
    "neural": {
        "name": "Neural",
        "primary": "#5ec8ff", "secondary": "#88e0ff", "tertiary": "#a8d6ff",
        "bg_overlay": lambda: _dots_pattern("#5ec8ff", 0.08, 32),
        "font_stack": '"Inter", -apple-system, "Helvetica Neue", sans-serif',
        "hero_fn": _hero_neuron,
        "accent_label": "Neuroscience",
    },
    "cardio": {
        "name": "Cardiac",
        "primary": "#ff5e5e", "secondary": "#ff8a8a", "tertiary": "#a8d8ff",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_heart,
        "accent_label": "Cardiology",
    },
    "respiratory": {
        "name": "Respiratory",
        "primary": "#7fc4ff", "secondary": "#a8d8ff", "tertiary": "#88e0d8",
        "bg_overlay": lambda: _dots_pattern("#a8d8ff", 0.06, 40),
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_lungs,
        "accent_label": "Pulmonary physiology",
    },
    "metabolic": {
        "name": "Metabolic",
        "primary": "#ffcc4a", "secondary": "#ffa84a", "tertiary": "#a37a08",
        "bg_overlay": lambda: "none",
        "font_stack": '"JetBrains Mono", "SF Mono", monospace',
        "hero_fn": _hero_molecule,
        "accent_label": "Bioenergetics",
    },
    "biomech": {
        "name": "Biomechanics",
        "primary": "#7fc4ff", "secondary": "#a8e1ff", "tertiary": "#ffcc4a",
        "bg_overlay": lambda: _grid_pattern("#7fc4ff", 0.05, 40),
        "font_stack": '"JetBrains Mono", "SF Mono", "Menlo", monospace',
        "hero_fn": _hero_blueprint,
        "accent_label": "Engineering · biomechanics",
    },
    "endocrine": {
        "name": "Endocrine",
        "primary": "#ffb84a", "secondary": "#ffa84a", "tertiary": "#a37a08",
        "bg_overlay": lambda: "none",
        "font_stack": '"Charter", "Georgia", serif',
        "hero_fn": _hero_hormone,
        "accent_label": "Endocrinology · lab",
    },
    "growth": {
        "name": "Adaptation",
        "primary": "#7fcf8e", "secondary": "#a8efb8", "tertiary": "#ffd84a",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_growth,
        "accent_label": "Adaptation · longitudinal",
    },
    "psych": {
        "name": "Psychology",
        "primary": "#7fc48e", "secondary": "#a8d8c0", "tertiary": "#b8a8d8",
        "bg_overlay": lambda: "none",
        "font_stack": '"Palatino", "Iowan Old Style", "Georgia", serif',
        "hero_fn": _hero_brain,
        "accent_label": "Sport psychology",
    },
    "nutrition": {
        "name": "Nutrition",
        "primary": "#7ed68a", "secondary": "#ffb84a", "tertiary": "#3a8a4a",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_leaf,
        "accent_label": "Sports nutrition",
    },
    "peds": {
        "name": "Anti-Doping",
        "primary": "#ff5e5e", "secondary": "#ff8a3a", "tertiary": "#ffcc4a",
        "bg_overlay": lambda: _stripes_pattern("#ff5e5e", 0.04, 45, 22),
        "font_stack": '"JetBrains Mono", monospace',
        "hero_fn": _hero_shield,
        "accent_label": "WADA · banned substances",
    },
    "testing": {
        "name": "Testing & Data",
        "primary": "#7fdcff", "secondary": "#88a8d8", "tertiary": "#ffd84a",
        "bg_overlay": lambda: _grid_pattern("#7fdcff", 0.04, 30),
        "font_stack": '"JetBrains Mono", "SF Mono", monospace',
        "hero_fn": _hero_chart,
        "accent_label": "Assessment · norms",
    },
    "warmup": {
        "name": "Warm-up",
        "primary": "#ffb84a", "secondary": "#ff5e3a", "tertiary": "#3a78b0",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", "Helvetica Neue", sans-serif',
        "hero_fn": _hero_warmup,
        "accent_label": "RAMP protocol",
    },
    "strength": {
        "name": "Strength Technique",
        "primary": "#c9c9c9", "secondary": "#666666", "tertiary": "#ffcc4a",
        "bg_overlay": lambda: _stripes_pattern("#c9c9c9", 0.03, 45, 12),
        "font_stack": '"Inter", "Helvetica Neue", -apple-system, sans-serif',
        "hero_fn": _hero_squat,
        "accent_label": "Iron · technique",
    },
    "program": {
        "name": "Program Design",
        "primary": "#b88fff", "secondary": "#d8b8ff", "tertiary": "#7fc4ff",
        "bg_overlay": lambda: _grid_pattern("#b88fff", 0.04, 36),
        "font_stack": '"Inter", -apple-system, "Helvetica Neue", sans-serif',
        "hero_fn": _hero_calendar,
        "accent_label": "Periodization",
    },
    "power": {
        "name": "Power & Speed",
        "primary": "#ffd84a", "secondary": "#ffa84a", "tertiary": "#a37a08",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", "Helvetica Neue", sans-serif',
        "hero_fn": _hero_lightning,
        "accent_label": "Stretch-shortening cycle",
    },
    "endurance": {
        "name": "Aerobic Endurance",
        "primary": "#7fe1c9", "secondary": "#ffd84a", "tertiary": "#ff5e5e",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_zones,
        "accent_label": "Polarized training",
    },
    "rehab": {
        "name": "Rehabilitation",
        "primary": "#a8e1c0", "secondary": "#7fc4a0", "tertiary": "#7fc4ff",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_recovery,
        "accent_label": "Return-to-sport",
    },
    "facility": {
        "name": "Facility & Operations",
        "primary": "#7fc4ff", "secondary": "#a8e1ff", "tertiary": "#7fcf8e",
        "bg_overlay": lambda: _grid_pattern("#7fc4ff", 0.06, 24),
        "font_stack": '"JetBrains Mono", monospace',
        "hero_fn": _hero_floorplan,
        "accent_label": "Architecture · operations",
    },
    "review": {
        "name": "Synthesis Review",
        "primary": "#c08fff", "secondary": "#5ec8ff", "tertiary": "#7fcf8e",
        "bg_overlay": lambda: "none",
        "font_stack": '"Inter", -apple-system, sans-serif',
        "hero_fn": _hero_kaleidoscope,
        "accent_label": "Integration · phase review",
    },
}


# Topic → motif mapping
TOPIC_TO_MOTIF = {
    "muscle_fiber_types": "anatomy",
    "motor_units": "neural",
    "ec_coupling": "neural",
    "cardiovascular": "cardio",
    "respiratory": "respiratory",
    "atp_pcr": "metabolic",
    "glycolysis": "metabolic",
    "oxidative": "metabolic",
    "energy_system_interaction": "metabolic",
    "biomech_levers": "biomech",
    "force_velocity_length_tension": "biomech",
    "anabolic_hormones": "endocrine",
    "catabolic_hormones": "endocrine",
    "anaerobic_adaptations": "growth",
    "aerobic_adaptations": "growth",
    "age_sex": "growth",
    "sport_psych": "psych",
    "macros": "nutrition",
    "nutrient_timing": "nutrition",
    "peds": "peds",
    "test_principles": "testing",
    "test_admin_strength": "testing",
    "test_admin_endurance": "testing",
    "warmup": "warmup",
    "ex_squat": "strength",
    "ex_deadlift": "strength",
    "ex_press": "strength",
    "ex_clean": "strength",
    "ex_alt_modes": "strength",
    "needs_analysis": "program",
    "exercise_selection": "program",
    "intensity_volume": "program",
    "rest_frequency": "program",
    "plyometrics": "power",
    "speed_agility": "power",
    "aerobic_programming": "endurance",
    "periodization_models": "program",
    "periodization_structure": "program",
    "rehab": "rehab",
    "facility_design": "facility",
    "facility_legal": "facility",
    "phase1_review": "review",
}


def motif_for(topic_id: str) -> dict | None:
    key = TOPIC_TO_MOTIF.get(topic_id)
    if key is None:
        return None
    return MOTIFS.get(key)


def render_motif_hero(motif: dict) -> str:
    """Render the hero banner SVG + label for a motif."""
    if not motif:
        return ""
    return (
        '<div class="motif-hero">'
        + motif["hero_fn"]()
        + f'<div class="motif-label">{motif["accent_label"]}</div>'
        + '</div>'
    )


def render_motif_css(motif: dict) -> str:
    """Return CSS overrides that re-paint the page in the motif's palette."""
    if not motif:
        return ""
    primary = motif["primary"]
    secondary = motif["secondary"]
    tertiary = motif["tertiary"]
    pattern = motif["bg_overlay"]()
    pr, pg, pb = _hex_to_rgb(primary).split(", ")

    # Background pattern is layered ABOVE the existing radial gradients
    pattern_decl = ""
    if pattern and pattern != "none":
        pattern_decl = f"body {{ background-image: {pattern}, var(--theme-bg-grad, none); }}"

    return f"""
/* Topic motif: {motif['name']} */
:root {{
  --theme-accent: {primary};
  --theme-secondary: {secondary};
  --theme-tertiary: {tertiary};
  --motif-primary: {primary};
  --motif-secondary: {secondary};
  --motif-tertiary: {tertiary};
  --motif-glow: rgba({pr}, {pg}, {pb}, 0.25);
  --motif-soft: rgba({pr}, {pg}, {pb}, 0.10);
}}
body {{ font-family: {motif['font_stack']}; }}
{pattern_decl}
.motif-hero {{
  position: relative;
  margin: -22px -24px 18px -24px;
  border-radius: 14px 14px 0 0;
  overflow: hidden;
  background: linear-gradient(135deg, rgba({pr}, {pg}, {pb}, 0.06), rgba({pr}, {pg}, {pb}, 0.18));
  border-bottom: 1px solid rgba({pr}, {pg}, {pb}, 0.30);
}}
.motif-hero .hero-svg {{ display: block; width: 100%; height: 140px; }}
.motif-hero .motif-label {{
  position: absolute;
  top: 12px; left: 18px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: {primary};
  background: rgba(0, 0, 0, 0.35);
  padding: 4px 10px;
  border-radius: 999px;
  backdrop-filter: blur(4px);
  font-weight: 700;
}}
.lesson-card.has-motif {{ border-left-color: {primary} !important; }}
.lesson-card.has-motif h2 {{ color: {primary}; }}
.facts-title {{ color: {primary} !important; }}
.training-link {{ border-left-color: {primary} !important; background: linear-gradient(135deg, rgba({pr}, {pg}, {pb}, 0.08), transparent) !important; }}
.training-link .tl-label {{ color: {primary} !important; }}
.badge-new {{ background: rgba({pr}, {pg}, {pb}, 0.20); color: {primary}; border-color: rgba({pr}, {pg}, {pb}, 0.5); box-shadow: 0 0 16px rgba({pr}, {pg}, {pb}, 0.20); }}
.h-date {{ background: linear-gradient(135deg, {primary} 0%, {secondary} 100%); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }}
.progress .bar {{ background: linear-gradient(90deg, {primary}, {secondary}, {tertiary}); box-shadow: 0 0 8px rgba({pr}, {pg}, {pb}, 0.4); }}
.stat b {{ background: linear-gradient(135deg, {primary}, {secondary}); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }}
.theme-banner {{ background: rgba({pr}, {pg}, {pb}, 0.10); border-color: rgba({pr}, {pg}, {pb}, 0.35); }}
.theme-banner .tb-name {{ color: {primary}; }}
"""
