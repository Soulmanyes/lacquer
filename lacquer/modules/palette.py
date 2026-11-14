"""Colors: who makes the palette and which one.

`engine` says who writes the colors:

- "noctalia": Noctalia builds the palette (`source`: builtin, wallpaper,
  community or custom) and its templates color the apps.
- "lacquer": Lacquer builds it from `seed` (palettegen.py) and writes it to
  every color target (colortargets/). This works without Noctalia. With
  Noctalia running, the shell gets the palette as a custom palette file and
  its templates still color what Lacquer has no target for (terminals, ...).

Keys of the `lacquer` engine:

- `seed`: "#rrggbb", "wallpaper" (Noctalia's current wallpaper) or an image
  file. Colors from an image are taken when the palette is written, not when
  the image changes later.
- `base`: name of a Noctalia custom palette whose colors are used as they are;
  the seed then only fills in what that palette lacks.
- `dark.<name>` / `light.<name>` (`dark.primary`, `light.terminal.red`): one
  hand-picked color. Unset it to get the derived color back.

`seed`, `base` and the picked colors are remembered while the engine is
"noctalia", so switching back and forth loses nothing.

Everything the engine holds lives in one file (ENGINE), which is a place like
any other: a revert puts back the file and every target exactly.
"""
import json
import os

from .. import (
	color,
	colortargets,
	gsettings,
	noctalia,
	noctaliapalette,
	palettegen,
	paths,
	places,
	state,
	wallcolor,
)
from ..colortargets.shell import NAME as SHELL_PALETTE
from ..values import Invalid, Key, LacquerError, same

ENGINES = ("noctalia", "lacquer")
ENGINE = os.path.join(paths.STATE, "palette-engine.json")
MODES = palettegen.MODES
FALLBACK_SEED = "#7aa2f7"
# Noctalia keys that say which palette Noctalia uses. While the engine is
# `lacquer` they point at Lacquer's palette, so a value set for them is held
# back until the engine is `noctalia` again.
HELD = ("source", "custom_palette")
# `applied`: the mode the targets were last written for (sync() compares it).
BLANK = {"engine": "noctalia", "seed": None, "seed_default": True, "color": None, "base": "", "mode": "dark", "applied": None, "overrides": {}, "handover": {}}
# Noctalia runs these commands after a dark/light switch (a list of shell
# commands in its config).
MODE_HOOK = "hooks.theme_mode_changed"
SYNC_COMMAND = f"{paths.USER_BIN} sync"


def _is_color_key(key):
	return key.split(".", 1)[0] in MODES


def load():
	"""What the engine holds (BLANK before its first use)."""
	text = paths.read_text(ENGINE)
	return {**json.loads(json.dumps(BLANK)), **(json.loads(text) if text else {})}


def _base_colors(name):
	if not name:
		return {}
	text = paths.read_text(noctaliapalette.path(name))
	if text is None:
		raise LacquerError(f"base: no Noctalia palette {name!r} in {noctaliapalette.FOLDER}")
	return noctaliapalette.loads(text)


def palette_of(held):
	"""The palette the engine's seed, base and picked colors give, or None
	before a seed color is known."""
	if not held["color"]:
		return None
	return palettegen.generate(held["color"], {**_base_colors(held["base"]), **held["overrides"]})


class Palette(places.Placed):
	name = "palette"
	title = "Palette"
	order = 10

	def __init__(self):
		self._schema = None
		self._targets = None

	def detect(self):
		return True

	def targets(self):
		if self._targets is None:
			self._targets = colortargets.discover()
		return self._targets

	# -- keys --

	def _theirs(self):
		"""Noctalia's own theme keys (not the template lists)."""
		if not noctalia.running():
			return {}
		return noctalia.scalars(noctalia.config_get("theme"), lambda key: "." not in key)

	def schema(self):
		if self._schema is None:
			keys = [
				Key(name="engine", type="str", default="noctalia", choices={e: e for e in ENGINES}, description="who writes the colors"),
				Key(name="seed", type="str", description='lacquer engine: "#rrggbb", "wallpaper" or an image file to take the main color from'),
				Key(name="base", type="str", default="", description="lacquer engine: a Noctalia custom palette to start from (its colors win over the seed)"),
			]
			if noctalia.running():
				keys += [Key(name=k, type=noctalia.TYPES[type(v)]) for k, v in self._theirs().items()]
			else:
				keys.append(Key(name="mode", type="str", default="dark", choices={m: m for m in MODES}, description="lacquer engine: dark or light"))
			keys += [
				Key(name=f"{mode}.{name}", type="color", description="lacquer engine: this color picked by hand (unset = derived from the seed)")
				for mode in MODES for name in palettegen.NAMES
			]
			self._schema = {k.name: k for k in keys}
		return self._schema

	def validate(self, key, value):
		value = super().validate(key, value)
		if key == "engine" and value not in ENGINES:
			raise Invalid(f"engine: pick one of {', '.join(ENGINES)}, got {value!r}")
		if key == "mode" and not noctalia.running() and value not in MODES:
			raise Invalid(f"mode: pick one of {', '.join(MODES)}, got {value!r}")
		if key == "seed":
			return self._seed(value)
		if key == "base" and value and not os.path.isfile(noctaliapalette.path(value)):
			raise Invalid(f"base: no Noctalia palette {value!r} (have: {', '.join(noctaliapalette.names()) or 'none'})")
		if _is_color_key(key) and len(value) != 7:
			raise Invalid(f"{key}: palette colors have no alpha part, give \"#rrggbb\"")
		return value

	def _seed(self, value):
		if value.startswith("#"):
			if len(value) != 7:
				raise Invalid(f"seed: {value!r} is not \"#rrggbb\"")
			try:
				color.parse(value)
			except ValueError as e:
				raise Invalid(f"seed: {value!r} is not \"#rrggbb\"") from e
			return value.lower()
		if value == "wallpaper":
			if not noctalia.running():
				raise Invalid("seed: \"wallpaper\" needs Noctalia running, give an image file instead")
		else:
			value = os.path.abspath(os.path.expanduser(value))
			if not os.path.isfile(value):
				raise Invalid(f"seed: needs \"#rrggbb\", \"wallpaper\" or an image file, and there is no file {value}")
		if not wallcolor.available():
			raise Invalid("seed: taking the color from an image needs ImageMagick (`magick`), which is not installed")
		return value

	def read(self, keys=None):
		held = load()
		live = {"engine": held["engine"], "base": held["base"]}
		if held["seed"]:
			live["seed"] = held["seed"]
		theirs = self._theirs()
		if theirs:
			live.update(theirs)
			if held["engine"] == "lacquer":
				# What Noctalia goes back to, not Lacquer's own palette file.
				back = held["handover"].get("shell", {})
				live.update({k: back[k] for k in HELD if back.get(k) is not None})
		else:
			live["mode"] = held["mode"]
		palette = palette_of(held)
		if palette:
			live.update({f"{mode}.{name}": value for mode in MODES for name, value in palette[mode].items()})
		return live if keys is None else {k: live[k] for k in keys if k in live}

	# -- the engine --

	def _default_seed(self):
		"""The seed for a first switch to `lacquer`: stay close to what is on
		screen now."""
		if noctalia.running():
			if noctalia.get("theme.source") == "custom":
				text = paths.read_text(noctaliapalette.path(noctalia.get("theme.custom_palette") or ""))
				primary = noctaliapalette.loads(text).get(f"{self._mode({}, {})}.primary") if text else None
				if primary:
					return primary
			if wallcolor.available():
				return "wallpaper"
		return FALLBACK_SEED

	def _seed_color(self, seed):
		if seed.startswith("#"):
			return seed
		return wallcolor.seed(noctalia.msg("wallpaper-get") if seed == "wallpaper" else seed)

	def _mode(self, held, theirs):
		if not noctalia.running():
			return held["mode"]
		mode = theirs.get("mode") or noctalia.msg("theme-mode-get")
		if mode in MODES:
			return mode
		return "light" if gsettings.available() and gsettings.get("color-scheme") == "prefer-light" else "dark"

	def _merged(self, changes):
		"""The engine's state after `changes`, and the Noctalia keys in them."""
		held, theirs = load(), {}
		for key, value in changes.items():
			if _is_color_key(key):
				held["overrides"][key] = value
			elif key in ("engine", "base") or (key == "mode" and not noctalia.running()):
				held[key] = value
			elif key == "seed":
				held.update(seed=value, seed_default=False)
			else:
				theirs[key] = value
		return held, theirs

	def _plan(self, held, theirs, reseed=True):
		"""Returns ({place: value} in writing order, calls to make after) that
		bring the system to the engine state `held` and set the Noctalia keys
		`theirs`. reseed=False keeps the color taken from the seed before
		(an image is not read again)."""
		was = load()
		written, after = {}, []
		if held["engine"] == "lacquer":
			if held["seed"] is None:
				held.update(seed=self._default_seed(), seed_default=True)
			if reseed or not held["color"]:
				held["color"] = self._seed_color(held["seed"])
			held["applied"] = self._mode(held, theirs)
			look = colortargets.Look(
				mode=held["applied"], seed=held["color"], palette=palette_of(held),
				templates=tuple(t for target in self.targets() for t in target.templates), handover=held["handover"],
			)
			for target in self.targets():
				written.update(target.render(look))
			after = [lambda t=t: t.live(look) for t in self.targets()]
			if "shell" in held["handover"]:
				held["handover"]["shell"].update({k: v for k, v in theirs.items() if k in HELD})
				theirs = {k: v for k, v in theirs.items() if k not in HELD}
		elif was["engine"] == "lacquer":
			for target in self.targets():
				written.update(target.release(was["handover"]))
			after = [lambda t=t: t.live(None) for t in self.targets()]
			held["handover"] = {}
		# The Noctalia keys after a release, so they win over what it puts back.
		for key, value in theirs.items():
			written.pop(f"noctalia:theme.{key}", None)
			written[f"noctalia:theme.{key}"] = value
		return {f"file:{ENGINE}": json.dumps(held, indent=1) + "\n", **written}, after

	def _run(self, written, after):
		for place, value in written.items():
			places.put(place, value)
		for call in after:
			call()

	def preview(self, changes):
		if not changes:
			return
		written, after = self._plan(*self._merged(changes))
		old = state.old_load(self.name)
		fresh = {p: places.get(p) for p in written if p not in old}
		if fresh:
			old.update(fresh)
			state.old_save(self.name, old)
		self._run(written, after)
		self.check(changes)

	def restored(self):
		for target in self.targets():
			target.reverted()

	def keep(self, section):
		# The section decides what the engine holds: a key that was unset goes
		# back to its default (a color to the derived one).
		held = load()
		want = {
			"engine": section.get("engine", "noctalia"), "base": section.get("base", ""),
			"overrides": {k: v for k, v in section.items() if _is_color_key(k)},
		}
		if "seed" in section:
			want.update(seed=section["seed"], seed_default=False)
		elif not held["seed_default"]:
			want.update(seed=None, seed_default=True)
		if any(not same(held[k], v) for k, v in want.items()):
			self._run(*self._plan({**held, **want}, {}))
		warnings = []
		for target in self.targets():
			warnings += target.keep(want["engine"] == "lacquer")
		state.old_clear(self.name)
		return warnings

	def sync(self):
		# Noctalia's dark/light switch only recolors the shell and what its
		# templates write; Lacquer's own targets still hold the other mode.
		held = load()
		if held["engine"] != "lacquer":
			return []
		mode = self._mode(held, {})
		# Also what stops a loop: writing the targets makes Noctalia reload.
		if mode == held["applied"]:
			return []
		self._run(*self._plan(held, {}, reseed=False))
		for target in self.targets():
			target.keep(True)
		return [f"palette: targets written for {mode} mode"]

	def _hooked(self):
		return SYNC_COMMAND in (noctalia.get(MODE_HOOK) or [])

	def install(self, section):
		if not noctalia.running() or self._hooked():
			return []
		noctalia.config_set(MODE_HOOK, [*(noctalia.get(MODE_HOOK) or []), SYNC_COMMAND])
		return [f"added `{SYNC_COMMAND}` to Noctalia's {MODE_HOOK}"]

	def doctor(self, section):
		held = load()
		if held["engine"] != "lacquer":
			return [{"level": "ok", "check": "palette.engine", "detail": "Noctalia writes the colors"}]
		names = ", ".join(t.name for t in self.targets())
		out = [{"level": "ok", "check": "palette.engine", "detail": f"Lacquer writes the colors from seed {held['seed']} ({held['color']}) to: {names}"}]
		if noctalia.running() and (noctalia.get("theme.source"), noctalia.get("theme.custom_palette")) != ("custom", SHELL_PALETTE):
			out.append({"level": "warn", "check": "palette.shell", "detail": "Noctalia's palette was changed outside Lacquer, so the shell and the apps disagree: set `palette.engine` again (\"lacquer\" to take over, \"noctalia\" to hand back)"})
		if noctalia.running() and not self._hooked():
			out.append({"level": "warn", "check": "palette.mode_hook", "detail": "a dark/light switch made in Noctalia is not followed by GTK, Qt and Hyprland colors: run `lacquer install`"})
		if held["seed"] and not held["seed"].startswith("#") and not wallcolor.available():
			out.append({"level": "warn", "check": "palette.seed", "detail": "the seed is an image but ImageMagick (`magick`) is not installed"})
		return out


MODULE = Palette()
