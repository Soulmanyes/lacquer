"""Hyprland animations: on/off, speed, curve and style of the main leaves.

Only the leaf families are here (`windows`, not `windowsIn`); the sub-leaves
and a curve editor are hypr-dashboard's Animations page. Preview is
`hyprctl eval` (live only), revert is `hyprctl reload`, keep writes
~/.config/hypr/config/lacquer_motion.lua, loaded after the other animation
config so a kept leaf wins.

Hyprland takes a leaf only whole (`enabled` plus a curve, checked in 0.57.1),
so a leaf with one kept key is written with its other values as they are
without Lacquer's file.
"""
import glob
import os
import re

from .. import hypr, hyprconf, lua, paths
from ..values import Key, LacquerError
from .base import Module

MOTION_LUA = hyprconf.config_file("lacquer_motion")
REQUIRE = 'require("config.lacquer_motion")'
SPRING = "spring:"
SLOW = 20

# Leaf: what it moves. A leaf that is not set takes its parent's values.
LEAVES = {
	"global": "every animation that has no values of its own",
	"windows": "windows opening, closing and moving",
	"layers": "layers (bar, panels, launcher) opening and closing",
	"fade": "fades (opening, closing, dim, shadow)",
	"border": "border color changes",
	"workspaces": "switching workspace",
	"specialWorkspace": "the special workspace opening and closing",
}
PARENT = {"specialWorkspace": "workspaces"}
FIELDS = ("enabled", "speed", "curve", "style")
# Leaves named like a family that are not its sub-leaves.
NOT_SUB = {"border": ("borderangle",)}

SLIDE = ["slide", "slide top", "slide bottom", "slide left", "slide right"]
WORKSPACE_STYLES = ["slide", "slidevert", "fade", "slidefade", "slidefade 20%", "slidefadevert", "slidefadevert 20%"]
# Styles Hyprland accepts per leaf (list from hypr-dashboard, same owner).
STYLES = {
	"windows": SLIDE + ["popin", "popin 80%", "gnomed"],
	"layers": SLIDE + ["popin", "popin 80%", "fade"],
	"workspaces": WORKSPACE_STYLES,
	"specialWorkspace": WORKSPACE_STYLES,
}

# Curves Lacquer brings itself, so a theme does not depend on the curves of
# one PC. Stored name: what hl.curve() takes.
PRESETS = {
	"lacquer_smooth": {"type": "bezier", "points": [[0.25, 0.1], [0.25, 1]]},
	"lacquer_gentle": {"type": "bezier", "points": [[0.4, 0], [0.2, 1]]},
	"lacquer_snappy": {"type": "bezier", "points": [[0.2, 0], [0, 1]]},
	"lacquer_bounce": {"type": "bezier", "points": [[0.34, 1.56], [0.64, 1]]},
	"lacquer_linear": {"type": "bezier", "points": [[0, 0], [1, 1]]},
	SPRING + "lacquer_spring": {"type": "spring", "mass": 1, "stiffness": 70, "dampening": 16},
	SPRING + "lacquer_wobble": {"type": "spring", "mass": 1, "stiffness": 70, "dampening": 10},
}
SPRING_DEF = re.compile(r'hl\.curve\(\s*"([^"]+)"\s*,\s*\{\s*type\s*=\s*"spring"')

HEADER = """\
-- Written by Lacquer. Do not edit by hand: `lacquer keep`
-- rewrites this whole file from ~/.config/lacquer/current.toml.
-- A leaf set here wins over the same leaf in animations.lua.
"""


def _curve_name(curve):
	return curve.removeprefix(SPRING)


def _curve_lua(curve):
	return f"hl.curve({lua.emit(_curve_name(curve))}, {lua.emit(PRESETS[curve], pretty=False)})"


def _animation_lua(leaf, values):
	"""One whole leaf as an hl.animation() call."""
	curve = values["curve"]
	call = {"leaf": leaf, "enabled": values["enabled"], "speed": values["speed"]}
	call["spring" if curve.startswith(SPRING) else "bezier"] = _curve_name(curve)
	if values.get("style"):
		call["style"] = values["style"]
	return f"hl.animation({lua.emit(call, pretty=False)})"


def _by_leaf(flat):
	"""{"windows.speed": 3} to {"windows": {"speed": 3}}."""
	out = {}
	for key, value in flat.items():
		leaf, field = key.split(".")
		out.setdefault(leaf, {})[field] = value
	return out


def _config_springs():
	"""Springs defined in the Hyprland config (Hyprland does not list them)."""
	names = []
	for path in sorted(glob.glob(os.path.join(hyprconf.HYPR_DIR, "config", "*.lua"))):
		if path != MOTION_LUA:
			names += SPRING_DEF.findall(paths.read_text(path) or "")
	return names


class Motion(Module):
	name = "motion"
	title = "Motion"
	order = 25

	def detect(self):
		return hypr.running()

	def schema(self):
		curves = self._curves()
		out = {}
		for leaf, what in LEAVES.items():
			out[f"{leaf}.enabled"] = Key(name=f"{leaf}.enabled", type="bool", description=f"animate {what}")
			out[f"{leaf}.speed"] = Key(
				name=f"{leaf}.speed", type="float", min=0.1, max=100,
				description="how long it takes, in tenths of a second (higher is slower)",
			)
			out[f"{leaf}.curve"] = Key(name=f"{leaf}.curve", type="str", choices=curves, description="curve the movement follows")
			if leaf in STYLES:
				choices = {"default": "", **{s: s for s in STYLES[leaf]}}
				out[f"{leaf}.style"] = Key(name=f"{leaf}.style", type="str", choices=choices, description="kind of movement; a percentage is how far it goes")
		return out

	def needs(self, key, schema):
		needs = super().needs(key, schema)
		leaf, _, field = key.partition(".")
		curve = schema.get(f"{leaf}.curve")
		if field == "speed" and curve and curve.choices:
			# A spring takes its duration from its own mass, stiffness and
			# dampening; Hyprland ignores the speed (seen in 0.57.1).
			needs[f"{leaf}.curve"] = [c for c in curve.choices.values() if not c.startswith(SPRING)]
		return needs

	def read(self, keys=None):
		live = self._live()
		out = {}
		for leaf in LEAVES:
			for field, value in self._effective(live, leaf).items():
				if field != "style" or leaf in STYLES:
					out[f"{leaf}.{field}"] = value
		return out if keys is None else {k: out[k] for k in keys if k in out}

	def risk(self, key, value):
		if key.endswith(".speed") and value > SLOW:
			return f"animations longer than {SLOW // 10} seconds make the desktop feel frozen"
		return None

	def preview(self, changes):
		live = self._live()
		for leaf, fields in _by_leaf(changes).items():
			values = {**self._effective(live, leaf), **fields}
			if values["curve"] in PRESETS:
				hypr.eval_lua(_curve_lua(values["curve"]))
			hypr.eval_lua(_animation_lua(leaf, values))

	def keep(self, section):
		old = paths.read_text(MOTION_LUA)
		if old is None and not section:
			return []
		leaves = _by_leaf(section)
		if any(set(FIELDS[:3]) - set(fields) for fields in leaves.values()):
			# A leaf with a field Lacquer does not keep: that field is
			# what the other config files give, so look without our file.
			if old is not None:
				paths.atomic_write(MOTION_LUA, HEADER)
			hypr.reload()
			live = self._live()
			leaves = {leaf: {**self._effective(live, leaf), **fields} for leaf, fields in leaves.items()}
		self._write(self._render(leaves), old)
		return [f"motion.{leaf}: {why}" for leaf, why in self._shadowed(leaves).items()]

	def revert(self):
		hypr.reload()

	def unchanged(self, changes):
		# Setting the old values is enough, and spares a reload (which also
		# drops what other tools set at runtime).
		self.preview(changes)

	def owns(self):
		return {"hyprland": {"animations": {leaf: f"{self.name}.{leaf}" for leaf in LEAVES}}}

	def doctor(self, section):
		out = []
		if not section:
			return out
		if not hyprconf.hooked(REQUIRE):
			out.append({"level": "error", "check": "motion.hooked", "detail": f"{hyprconf.MAIN_LUA} does not load config.lacquer_motion: run `lacquer install`"})
		leaves = _by_leaf(section)
		for leaf, why in self._shadowed(leaves).items():
			out.append({"level": "warn", "check": "motion.shadowed", "detail": f"motion.{leaf}: {why}"})
		live = self.read(section)
		for key, value in section.items():
			if live.get(key) != value:
				out.append({"level": "warn", "check": "motion.overridden", "detail": f"motion.{key}: saved {value!r}, live {live.get(key)!r}"})
		if not out:
			out.append({"level": "ok", "check": "motion.hooked", "detail": "kept animations are live: " + ", ".join(sorted(leaves))})
		return out

	def install(self, section):
		if not section or hyprconf.hooked(REQUIRE):
			return []
		self.keep(section)
		return [f"wrote {MOTION_LUA}"]

	# -- helpers --

	def _live(self):
		return {a["name"]: a for a in hypr.hyprctl_json("animations")[0]}

	def _effective(self, live, leaf):
		"""The values a leaf runs with: its own, or its nearest set parent's."""
		node = leaf
		while not live[node]["overridden"] and node != "global":
			node = PARENT.get(node, "global")
		a = live[node]
		style = a["style"] if node == leaf or node != "global" else ""
		return {"enabled": a["enabled"], "speed": round(float(a["speed"]), 3), "curve": a["bezier"], "style": style}

	def _curves(self):
		"""{shown name: stored name}: Lacquer's own, then what this PC has.
		A spring is stored as `spring:<name>`."""
		beziers = [b["name"] for b in hypr.hyprctl_json("animations")[1]]
		springs = [SPRING + n for n in _config_springs()]
		springs += [a["bezier"] for a in self._live().values() if a["bezier"].startswith(SPRING)]
		names = list(PRESETS)
		for name in beziers + springs:
			# A lacquer_ curve that is no preset is a leftover of an older run.
			if name not in names and not _curve_name(name).startswith("lacquer_"):
				names.append(name)
		return {n.replace(SPRING, "spring ").replace("lacquer_", "Lacquer "): n for n in names}

	def _render(self, leaves):
		text = HEADER
		curves = sorted({v["curve"] for v in leaves.values() if v["curve"] in PRESETS})
		if curves:
			text += "\n" + "".join(_curve_lua(c) + "\n" for c in curves)
		if leaves:
			# Parents first, so the file reads top-down like the leaf tree.
			text += "\n" + "".join(_animation_lua(leaf, leaves[leaf]) + "\n" for leaf in LEAVES if leaf in leaves)
		return text

	def _write(self, text, old):
		"""Writes the file and hooks it into hyprland.lua; `old` comes back
		if Hyprland reports config errors."""
		paths.atomic_write(MOTION_LUA, text)
		try:
			if hyprconf.hooked(REQUIRE):
				hypr.reload()
				errors = hypr.config_errors()
				if errors:
					raise LacquerError("Hyprland reported config errors, the old animations file is back: " + "; ".join(errors))
			else:
				hyprconf.hook(REQUIRE, [
					"-- Animations kept by Lacquer. After config.animations",
					"-- so a leaf kept here wins.",
				])
		except LacquerError:
			if old is None:
				os.remove(MOTION_LUA)
			else:
				paths.atomic_write(MOTION_LUA, old)
			hypr.reload()
			raise

	def _shadowed(self, leaves):
		"""Kept leaves whose sub-leaves are set elsewhere and so still win."""
		live = self._live()
		out = {}
		for leaf in leaves:
			if leaf == "global":
				continue
			subs = sorted(
				n for n, a in live.items()
				if n.startswith(leaf) and n != leaf and n not in NOT_SUB.get(leaf, ()) and a["overridden"]
			)
			if subs:
				out[leaf] = f"{', '.join(subs)} set in another config file still win (change them in hypr-dashboard)"
		return out


MODULE = Motion()
