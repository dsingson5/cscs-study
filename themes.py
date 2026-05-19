"""
Procedural daily-theme generator for CSCS study HTML.

Each day_number produces a unique theme — deterministic but never repeating.
The base hue rotates by the golden angle (≈137.508°) so consecutive days are
perceptually maximally distinct. All other parameters are seeded random.

A 26-week curriculum produces 182 themes; the golden-angle rotation means
no two days share the same hue, and the seeded random ensures fonts,
layouts, accents, and decorative effects all vary.
"""
from __future__ import annotations

import colorsys
import random


# Hue rotation by golden angle yields maximally spread, never-repeating hues
GOLDEN_ANGLE = 137.50776405003785

# Font stacks — varied serif/sans/mono families
FONT_STACKS = [
    '-apple-system, BlinkMacSystemFont, "Inter", "SF Pro Text", "Segoe UI", Helvetica, Arial, sans-serif',
    '"Georgia", "Iowan Old Style", "Times New Roman", serif',
    '"Charter", "Bitstream Charter", "Sitka Text", "Georgia", serif',
    '"Helvetica Neue", "Inter", -apple-system, sans-serif',
    '"JetBrains Mono", "SF Mono", "Menlo", Consolas, monospace',
    '"Palatino", "Palatino Linotype", "Book Antiqua", Georgia, serif',
    '"Optima", "Segoe UI", "Helvetica Neue", sans-serif',
    '"Avenir Next", "Avenir", "Helvetica Neue", sans-serif',
    '"Cochin", "Times New Roman", Times, serif',
    '"Lucida Console", "Monaco", Consolas, monospace',
    '"Trebuchet MS", "Lucida Grande", Tahoma, sans-serif',
    '"Garamond", "EB Garamond", "Adobe Garamond Pro", serif',
    '"Verdana", "Tahoma", "Geneva", sans-serif',
    '"Hoefler Text", "Baskerville", "Georgia", serif',
    'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    '"Futura", "Trebuchet MS", "Inter", sans-serif',
]

# Card accent styles
ACCENT_STYLES = [
    "left-stripe",
    "top-stripe",
    "no-stripe",
    "border-only",
    "left-thick",
    "double-border",
    "left-glow",
]

# Adjectives + nouns for procedurally generated theme names
ADJECTIVES = [
    "Velvet", "Glacial", "Ember", "Tidal", "Solar", "Lunar", "Twilight", "Dawn",
    "Cobalt", "Amber", "Crimson", "Verdant", "Slate", "Quartz", "Obsidian",
    "Iron", "Copper", "Indigo", "Saffron", "Onyx", "Rust", "Sage", "Plum",
    "Cinder", "Mist", "Frost", "Aurora", "Tundra", "Magma", "Coral", "Jade",
    "Argent", "Bronze", "Vermilion", "Cerulean", "Ochre", "Pewter", "Garnet",
    "Citrine", "Heather", "Storm", "Marble", "Linen", "Granite", "Birch",
    "Cedar", "Maple", "Walnut", "Ash", "Spruce", "Pine", "Oak",
]
NOUNS = [
    "Atrium", "Pavilion", "Forge", "Lattice", "Meridian", "Prism", "Cipher",
    "Compass", "Helix", "Quill", "Sextant", "Codex", "Threshold", "Marquee",
    "Beacon", "Anchor", "Crucible", "Reverie", "Cascade", "Vector", "Folio",
    "Atlas", "Echo", "Loom", "Lantern", "Fathom", "Pinnacle", "Vault", "Galleria",
    "Stratum", "Foundry", "Spire", "Mesa", "Reach", "Drift", "Field", "Span",
    "Halo", "Vista", "Channel", "Citadel", "Belvedere", "Lyceum", "Rotunda",
    "Bazaar", "Promenade", "Veranda", "Conservatory", "Gallery", "Cloister",
]


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """h in [0, 360), s/l in [0, 100]. Returns #rrggbb."""
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert #rrggbb to rgba(r, g, b, a)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _name_for(day: int) -> str:
    """Procedurally derived theme name. Enumerates the full (ADJ × NOUN) product
    shuffled with a fixed seed, then picks deterministically by day_number — so
    no two days share a name across the full ~2,500-combination space."""
    import itertools
    combos = list(itertools.product(ADJECTIVES, NOUNS))
    random.Random(20260519).shuffle(combos)
    adj, noun = combos[(day - 1) % len(combos)]
    return f"{adj} {noun}"


def for_day(day: int) -> dict:
    """Generate a deterministic-but-unique theme for the given day number (1-indexed)."""
    rng = random.Random(day)

    # Base hue rotates by golden angle for maximal visual spread between consecutive days
    base_hue = (day * GOLDEN_ANGLE) % 360
    # Mode: ~85% dark themes, ~15% light themes for variety
    is_light = rng.random() < 0.15

    # Build accent triad — base + harmony from a randomly chosen scheme
    scheme = rng.choice(["complementary", "split-complementary", "triadic", "analogous", "tetradic"])
    if scheme == "complementary":
        accents = [base_hue, (base_hue + 180) % 360, (base_hue + 30) % 360]
    elif scheme == "split-complementary":
        accents = [base_hue, (base_hue + 150) % 360, (base_hue + 210) % 360]
    elif scheme == "triadic":
        accents = [base_hue, (base_hue + 120) % 360, (base_hue + 240) % 360]
    elif scheme == "tetradic":
        accents = [base_hue, (base_hue + 90) % 360, (base_hue + 180) % 360]
    else:  # analogous
        accents = [base_hue, (base_hue + 30) % 360, (base_hue - 30) % 360]

    # Background tinting — very low sat, very dark (or very light for light mode)
    bg_sat = rng.uniform(8, 22)
    if is_light:
        bg_lightness = rng.uniform(92, 97)
        surface_l = bg_lightness - rng.uniform(3, 6)
        surface_2_l = surface_l - rng.uniform(2, 4)
        surface_3_l = surface_2_l - rng.uniform(3, 6)
        border_l = surface_3_l - rng.uniform(5, 10)
        border_2_l = border_l - rng.uniform(8, 14)
        text_l = rng.uniform(10, 18)
        text_dim_l = text_l + rng.uniform(20, 28)
        text_dimmer_l = text_dim_l + rng.uniform(12, 18)
    else:
        bg_lightness = rng.uniform(3, 8)
        surface_l = bg_lightness + rng.uniform(3, 6)
        surface_2_l = surface_l + rng.uniform(2, 4)
        surface_3_l = surface_2_l + rng.uniform(3, 6)
        border_l = surface_3_l + rng.uniform(5, 10)
        border_2_l = border_l + rng.uniform(8, 14)
        text_l = rng.uniform(88, 96)
        text_dim_l = text_l - rng.uniform(25, 35)
        text_dimmer_l = text_dim_l - rng.uniform(15, 22)

    bg = _hsl_to_hex(base_hue, bg_sat, bg_lightness)
    bg_2 = _hsl_to_hex(base_hue, bg_sat - 2, bg_lightness + (1 if not is_light else -1))
    surface = _hsl_to_hex(base_hue, bg_sat + 2, surface_l)
    surface_2 = _hsl_to_hex(base_hue, bg_sat + 4, surface_2_l)
    surface_3 = _hsl_to_hex(base_hue, bg_sat + 6, surface_3_l)
    border = _hsl_to_hex(base_hue, bg_sat + 4, border_l)
    border_2 = _hsl_to_hex(base_hue, bg_sat + 2, border_2_l)
    text = _hsl_to_hex(base_hue, 8 if not is_light else 18, text_l)
    text_dim = _hsl_to_hex(base_hue, 12, text_dim_l)
    text_dimmer = _hsl_to_hex(base_hue, 10, text_dimmer_l)

    # Vivid accents
    accent_sat = rng.uniform(60, 88)
    accent_light = rng.uniform(60, 72) if not is_light else rng.uniform(38, 52)
    accent = _hsl_to_hex(accents[0], accent_sat, accent_light)
    secondary = _hsl_to_hex(accents[1], accent_sat - rng.uniform(0, 12), accent_light + rng.uniform(-5, 5))
    tertiary = _hsl_to_hex(accents[2], accent_sat - rng.uniform(0, 15), accent_light + rng.uniform(-5, 5))

    # Status colors — derive from base hue but force into recognizable semantic ranges
    good = _hsl_to_hex(rng.uniform(135, 165), 55, 60 if not is_light else 40)
    warn = _hsl_to_hex(rng.uniform(32, 48), 75, 62 if not is_light else 50)
    bad = _hsl_to_hex(rng.uniform(355, 365) % 360, 75, 64 if not is_light else 48)

    # Background gradient — pick 1-3 radial spots at random positions
    spots = rng.randint(2, 4)
    grad_parts = []
    for _ in range(spots):
        x = rng.choice([0, 25, 50, 75, 100])
        y = rng.choice([0, 25, 50, 75, 100])
        hue = rng.choice(accents)
        opacity = rng.uniform(0.04, 0.10)
        spread = rng.uniform(45, 65)
        rgba = _hex_to_rgba(_hsl_to_hex(hue, accent_sat, accent_light), opacity)
        grad_parts.append(f"radial-gradient(at {x}% {y}%, {rgba} 0px, transparent {spread:.0f}%)")
    bg_grad = ", ".join(grad_parts)

    # Card properties
    accent_style = rng.choice(ACCENT_STYLES)
    card_radius = f"{rng.choice([0, 4, 6, 8, 10, 12, 14, 16, 18, 22])}px"
    font_stack = rng.choice(FONT_STACKS)
    is_mono = "Mono" in font_stack or "Consolas" in font_stack or "Console" in font_stack
    is_serif = any(s in font_stack for s in ["Georgia", "serif", "Charter", "Palatino", "Garamond", "Cochin", "Hoefler", "Baskerville"])

    # Decorative effects — pick 0-2 random ones
    available_effects = ["drift", "glow", "uppercase", "italic-headings", "tighter", "wider",
                         "thick-border", "subtle-shadow", "no-shadow", "soft-radius"]
    n_effects = rng.randint(1, 3)
    effects = rng.sample(available_effects, k=n_effects)

    # Header alignment
    header_align = rng.choice(["left", "left", "center"])  # weighted toward left

    return {
        "name": _name_for(day),
        "tagline": _tagline(scheme, is_light, is_mono, is_serif, rng),
        "is_light": is_light,
        "base_hue": base_hue,
        "scheme": scheme,
        "bg": bg, "bg_2": bg_2,
        "surface": surface, "surface_2": surface_2, "surface_3": surface_3,
        "border": border, "border_2": border_2,
        "text": text, "text_dim": text_dim, "text_dimmer": text_dimmer,
        "accent": accent, "secondary": secondary, "tertiary": tertiary,
        "good": good, "warn": warn, "bad": bad,
        "bg_grad": bg_grad,
        "body_class": f"theme-day-{day}",
        "card_radius": card_radius,
        "accent_style": accent_style,
        "font_stack": font_stack,
        "is_mono": is_mono,
        "is_serif": is_serif,
        "effects": effects,
        "header_align": header_align,
    }


def _tagline(scheme: str, light: bool, mono: bool, serif: bool, rng) -> str:
    mode_word = "light" if light else "dark"
    font_word = "monospace" if mono else ("serif" if serif else "sans")
    fragments = [
        f"{scheme.replace('-', ' ')} palette",
        f"{font_word} typography",
        f"{mode_word} mode",
        rng.choice([
            "fresh today only",
            "procedurally generated",
            "never repeated",
            "unique morning",
            "today's instance",
            "ephemeral design",
            "one-day edition",
        ]),
    ]
    rng.shuffle(fragments)
    return " · ".join(fragments[:3])


def render_overrides(theme: dict) -> str:
    """Render a CSS override block based on the theme dict."""
    # Card accent stripe variation
    if theme["accent_style"] == "top-stripe":
        card_accent = ".lesson-card { border-left: 1px solid var(--border); border-top: 3px solid var(--theme-accent); }"
    elif theme["accent_style"] == "no-stripe":
        card_accent = ".lesson-card { border-left: 1px solid var(--border); }"
    elif theme["accent_style"] == "border-only":
        card_accent = ".lesson-card { border: 2px solid var(--theme-accent); border-left: 2px solid var(--theme-accent); }"
    elif theme["accent_style"] == "left-thick":
        card_accent = ".lesson-card { border-left: 6px solid var(--theme-accent); }"
    elif theme["accent_style"] == "double-border":
        card_accent = ".lesson-card { border: 1px double var(--border-2); border-left: 3px double var(--theme-accent); padding: 24px; }"
    elif theme["accent_style"] == "left-glow":
        card_accent = ".lesson-card { border-left: 3px solid var(--theme-accent); box-shadow: -2px 0 12px " + _hex_to_rgba(theme["accent"], 0.25) + "; }"
    else:  # left-stripe (default)
        card_accent = ".lesson-card { border-left: 3px solid var(--theme-accent); }"

    # Light mode adjustments — invert various foreground/background relationships
    light_extras = ""
    if theme["is_light"]:
        accent = theme["accent"]
        light_extras = f"""
.h-date {{ background: linear-gradient(135deg, {theme['text']} 0%, {theme['text_dim']} 100%); -webkit-background-clip: text; background-clip: text; }}
.stat b {{ background: linear-gradient(135deg, {accent}, {theme['secondary']}); -webkit-background-clip: text; background-clip: text; }}
.progress .bar {{ background: linear-gradient(90deg, {accent}, {theme['secondary']}, {theme['tertiary']}); box-shadow: 0 0 6px {_hex_to_rgba(accent, 0.3)}; }}
.q-answer {{ background: {theme['bg_2']}; color: {theme['text']}; }}
button[data-self="correct"].active {{ background: {theme['good']}; color: #fff; border-color: {theme['good']}; }}
button[data-self="partial"].active {{ background: {theme['warn']}; color: #fff; border-color: {theme['warn']}; }}
button[data-self="missed"].active {{ background: {theme['bad']}; color: #fff; border-color: {theme['bad']}; }}
"""

    # Effect-based decorative tweaks
    decor = ""
    if "drift" in theme["effects"]:
        decor += '\nbody::before { content: ""; position: fixed; inset: 0; background: linear-gradient(135deg, transparent 40%, var(--theme-secondary-rgba) 60%, transparent 80%); pointer-events: none; z-index: 0; animation: themeDrift 16s ease-in-out infinite alternate; opacity: 0.6; }\n@keyframes themeDrift { 0% { transform: translateX(-8%) translateY(-2%); } 100% { transform: translateX(8%) translateY(2%); } }\n'
    if "glow" in theme["effects"]:
        decor += '\n.lesson-card { box-shadow: 0 0 32px var(--theme-glow-soft); }\n.badge-new { box-shadow: 0 0 16px var(--theme-glow-soft); }\n'
    if "uppercase" in theme["effects"]:
        decor += '\n.lesson-card h2 { text-transform: uppercase; letter-spacing: -0.01em; }\n.h-date { text-transform: uppercase; letter-spacing: 0.02em; }\n'
    if "italic-headings" in theme["effects"]:
        decor += '\n.lesson-card h2 { font-style: italic; }\n'
    if "tighter" in theme["effects"]:
        decor += '\n.container { max-width: 760px; }\n'
    if "wider" in theme["effects"]:
        decor += '\n.container { max-width: 1040px; }\n'
    if "thick-border" in theme["effects"]:
        decor += '\n.lesson-card, .question-block, .widget { border-width: 2px; }\n'
    if "subtle-shadow" in theme["effects"]:
        decor += '\n.lesson-card { box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25); }\n'
    if "no-shadow" in theme["effects"]:
        decor += '\n.lesson-card { box-shadow: none !important; }\n.lesson-card:hover { box-shadow: none !important; transform: none !important; }\n'
    if "soft-radius" in theme["effects"]:
        decor += '\n.q, .widget, .facts, .training-link, .media-link { border-radius: 14px; }\n'
    if theme["is_mono"]:
        decor += '\nbutton { font-family: monospace; text-transform: uppercase; letter-spacing: 0.05em; font-size: 11px; }\n.badge, .q-type { font-family: monospace; }\n'

    accent_rgba_soft = _hex_to_rgba(theme["accent"], 0.18)
    accent_rgba_glow = _hex_to_rgba(theme["accent"], 0.45)
    secondary_rgba = _hex_to_rgba(theme["secondary"], 0.05)
    accent_rgba_focus = _hex_to_rgba(theme["accent"], 0.15)
    header_align_css = ""
    if theme["header_align"] == "center":
        header_align_css = "header.top { text-align: center; } header.top .domains { justify-content: center; }"

    css = (
        ":root {\n"
        f"  --bg: {theme['bg']};\n"
        f"  --bg-2: {theme['bg_2']};\n"
        f"  --surface: {theme['surface']};\n"
        f"  --surface-2: {theme['surface_2']};\n"
        f"  --surface-3: {theme['surface_3']};\n"
        f"  --border: {theme['border']};\n"
        f"  --border-2: {theme['border_2']};\n"
        f"  --text: {theme['text']};\n"
        f"  --text-dim: {theme['text_dim']};\n"
        f"  --text-dimmer: {theme['text_dimmer']};\n"
        f"  --good: {theme['good']};\n"
        f"  --warn: {theme['warn']};\n"
        f"  --bad: {theme['bad']};\n"
        f"  --theme-accent: {theme['accent']};\n"
        f"  --theme-secondary: {theme['secondary']};\n"
        f"  --theme-tertiary: {theme['tertiary']};\n"
        f"  --theme-glow-soft: {accent_rgba_soft};\n"
        f"  --theme-glow-strong: {accent_rgba_glow};\n"
        f"  --theme-secondary-rgba: {secondary_rgba};\n"
        "}\n"
        "body {\n"
        f"  font-family: {theme['font_stack']};\n"
        f"  background-image: {theme['bg_grad']};\n"
        "}\n"
        f".lesson-card, .question-block, .widget {{ border-radius: {theme['card_radius']}; }}\n"
        f".q-answer:focus {{ box-shadow: 0 0 0 3px {accent_rgba_focus}; border-color: var(--theme-accent); }}\n"
        f"{card_accent}\n"
        f"{light_extras}\n"
        f"{decor}\n"
        f"{header_align_css}\n"
        ".theme-banner {\n"
        "  display: inline-flex;\n"
        "  align-items: center;\n"
        "  gap: 8px;\n"
        "  padding: 4px 12px;\n"
        "  margin-top: 6px;\n"
        "  border-radius: 999px;\n"
        f"  background: {_hex_to_rgba(theme['accent'], 0.08)};\n"
        f"  border: 1px solid {_hex_to_rgba(theme['accent'], 0.30)};\n"
        "  font-size: 11px;\n"
        "  color: var(--text-dim);\n"
        "  letter-spacing: 0.04em;\n"
        "}\n"
        ".theme-banner .tb-name { color: var(--theme-accent); font-weight: 700; text-transform: uppercase; }\n"
        '.theme-swatch { display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: var(--theme-accent); box-shadow: 0 0 6px var(--theme-glow-strong); }\n'
        '.h-date { color: var(--text); }\n'
    )
    return css
