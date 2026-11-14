"""Noctalia's palette file format (~/.config/noctalia/palettes/<name>.json).

Lacquer's names are snake_case (`on_primary`, `terminal.bright_red`);
Noctalia's are `mOnPrimary` and a nested `terminal` table.
"""
import json
import os

from . import paths
from .palettegen import ANSI, MODES, ROLES

FOLDER = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(paths.HOME, ".config"), "noctalia", "palettes")

SIMPLE = {"foreground": "foreground", "background": "background", "selection_fg": "selectionFg", "selection_bg": "selectionBg", "cursor_text": "cursorText", "cursor": "cursor"}


def path(name):
	return os.path.join(FOLDER, f"{name}.json")


def names():
	try:
		return sorted(f[:-5] for f in os.listdir(FOLDER) if f.endswith(".json"))
	except FileNotFoundError:
		return []


def _role(name):
	return "m" + "".join(part.capitalize() for part in name.split("_"))


def dumps(palette):
	"""A Lacquer palette as the text of a Noctalia palette file."""
	out = {}
	for mode in MODES:
		colors = palette[mode]
		out[mode] = {_role(r): colors[r] for r in ROLES}
		out[mode]["terminal"] = {
			**{theirs: colors[f"terminal.{ours}"] for ours, theirs in SIMPLE.items()},
			"normal": {c: colors[f"terminal.{c}"] for c in ANSI},
			"bright": {c: colors[f"terminal.bright_{c}"] for c in ANSI},
		}
	return json.dumps(out, indent=2) + "\n"


def loads(text):
	"""A Noctalia palette file as {"dark.primary": "#..", ...}: every color it
	has, in the form `generate()` takes as overrides."""
	data = json.loads(text)
	out = {}
	for mode in MODES:
		colors = data.get(mode, {})
		terminal = colors.get("terminal", {})
		found = {r: colors.get(_role(r)) for r in ROLES}
		found.update({f"terminal.{ours}": terminal.get(theirs) for ours, theirs in SIMPLE.items()})
		found.update({f"terminal.{c}": terminal.get("normal", {}).get(c) for c in ANSI})
		found.update({f"terminal.bright_{c}": terminal.get("bright", {}).get(c) for c in ANSI})
		out.update({f"{mode}.{k}": v.lower() for k, v in found.items() if isinstance(v, str)})
	return out
