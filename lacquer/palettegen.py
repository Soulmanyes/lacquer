"""Lacquer's own palette generator: one seed color to every role.

Works in OKLCH (see color.py): the seed gives the hue and how colorful the
palette is, each role gets a fixed lightness. The scheme follows Material's
"tonal spot": secondary is the seed's hue with less color, tertiary is 60
degrees on. Swapping the generator means replacing `generate()`.

A palette is {"dark": {name: "#rrggbb"}, "light": {...}}; names are NAMES.
"""
from . import color

ROLES = (
	"primary", "on_primary", "secondary", "on_secondary", "tertiary", "on_tertiary", "error", "on_error",
	"surface", "on_surface", "surface_variant", "on_surface_variant", "outline", "shadow", "hover", "on_hover",
)
ANSI = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
TERMINAL = ("foreground", "background", "selection_fg", "selection_bg", "cursor_text", "cursor", *ANSI, *(f"bright_{c}" for c in ANSI))
NAMES = ROLES + tuple(f"terminal.{t}" for t in TERMINAL)
MODES = ("dark", "light")

ERROR_HUE = 20
ANSI_HUES = {"red": 22, "green": 145, "yellow": 95, "blue": 260, "magenta": 320, "cyan": 200}

# Lightness of each role, and its chroma as (share of the accent chroma, share
# of the neutral chroma).
TONES = {
	"dark": {
		"primary": 0.76, "secondary": 0.76, "tertiary": 0.76, "error": 0.72, "hover": 0.68, "on_accent": 0.16,
		"surface": 0.15, "surface_variant": 0.21, "on_surface": 0.92, "on_surface_variant": 0.80, "outline": 0.42,
		"ansi": 0.74, "ansi_bright": 0.83, "black": 0.28, "bright_black": 0.62, "white": 0.83, "bright_white": 0.96,
	},
	"light": {
		"primary": 0.48, "secondary": 0.50, "tertiary": 0.50, "error": 0.52, "hover": 0.42, "on_accent": 0.98,
		"surface": 0.975, "surface_variant": 0.92, "on_surface": 0.22, "on_surface_variant": 0.38, "outline": 0.62,
		"ansi": 0.50, "ansi_bright": 0.42, "black": 0.35, "bright_black": 0.22, "white": 0.87, "bright_white": 1.0,
	},
}


def _roles(seed, mode):
	_, chroma, hue = color.to_oklch(seed)
	# A gray seed gives a gray palette; any other seed is kept inside a range
	# that reads as an accent without glowing.
	accent = chroma if chroma < 0.03 else max(0.08, min(0.16, chroma))
	neutral = min(1.0, chroma / 0.03)
	t = TONES[mode]

	def tone(name, c, h=hue):
		return color.from_oklch(t[name], c, h)

	on_accent = tone("on_accent", 0.015 * neutral)
	return {
		"primary": tone("primary", accent),
		"on_primary": on_accent,
		"secondary": tone("secondary", accent * 0.5),
		"on_secondary": on_accent,
		"tertiary": tone("tertiary", accent * 0.7, hue + 60),
		"on_tertiary": on_accent,
		"error": tone("error", 0.15, ERROR_HUE),
		"on_error": on_accent,
		"surface": tone("surface", 0.015 * neutral),
		"on_surface": tone("on_surface", 0.012 * neutral),
		"surface_variant": tone("surface_variant", 0.022 * neutral),
		"on_surface_variant": tone("on_surface_variant", 0.025 * neutral),
		"outline": tone("outline", 0.035 * neutral),
		"shadow": "#000000",
		"hover": tone("hover", accent),
		"on_hover": on_accent,
	}


def _terminal(seed, mode, roles):
	"""Terminal colors that sit on this palette's surface."""
	_, chroma, hue = color.to_oklch(seed)
	neutral = min(1.0, chroma / 0.03)
	t = TONES[mode]
	out = {
		"foreground": roles["on_surface"], "background": roles["surface"],
		"selection_fg": roles["on_primary"], "selection_bg": roles["primary"],
		"cursor_text": roles["surface"], "cursor": roles["on_surface"],
	}
	for name in ("black", "white"):
		out[name] = color.from_oklch(t[name], 0.02 * neutral, hue)
		out[f"bright_{name}"] = color.from_oklch(t[f"bright_{name}"], 0.02 * neutral, hue)
	for name, h in ANSI_HUES.items():
		out[name] = color.from_oklch(t["ansi"], 0.12, h)
		out[f"bright_{name}"] = color.from_oklch(t["ansi_bright"], 0.12, h)
	return out


def generate(seed, overrides=None):
	"""Returns the palette for a seed. `overrides` is {"dark.primary": "#..",
	"light.terminal.red": "#.."}: hand-picked colors that replace derived ones.
	The terminal colors follow overridden roles (background = surface)."""
	overrides = overrides or {}
	palette = {}
	for mode in MODES:
		picked = {k[len(mode) + 1:]: v for k, v in overrides.items() if k.startswith(f"{mode}.") and v}
		roles = _roles(seed, mode)
		roles.update({k: v for k, v in picked.items() if k in ROLES})
		terminal = {f"terminal.{k}": v for k, v in _terminal(seed, mode, roles).items()}
		terminal.update({k: v for k, v in picked.items() if k in terminal})
		palette[mode] = {**roles, **terminal}
	return palette
