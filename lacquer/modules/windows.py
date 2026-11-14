"""Hyprland look: gaps, borders, rounding, opacity, blur, shadow, glow, groups.

Preview is `hyprctl eval` (live only), revert is `hyprctl reload`, keep writes
~/.config/hypr/config/lacquer.lua. Keys are Hyprland option names with dots:
`decoration:blur:passes` is `decoration.blur.passes`.
"""
import os
import re
import shutil

from .. import hypr, hyprconf, lua, paths, tomlio
from ..values import Key, LacquerError, same
from .base import Module

MAIN_LUA = hyprconf.MAIN_LUA
LACQUER_LUA = hyprconf.config_file("lacquer")
DASHBOARD_LUA = hyprconf.config_file("dashboard_options")
REQUIRE = 'require("config.lacquer")'
DEFAULT_REVERT_BIND = "SUPER + BackSpace"
MODMASK = {"SHIFT": 1, "CTRL": 4, "CONTROL": 4, "ALT": 8, "SUPER": 64}

# Which Hyprland options count as "look". Everything else belongs elsewhere.
LOOK = re.compile(
	r"general:(gaps_in|gaps_out|float_gaps|gaps_workspaces|border_size|col\..+)$"
	r"|decoration:"
	r"|group:col\."
	r"|group:groupbar:"
	r"|animations:enabled$"
)

# (key, test, why): values that can leave you unable to see or click Revert,
# or that have hung the iGPU before. These get the auto-revert timer.
RISKY = [
	("decoration.screen_shader", lambda v: v != "", "a shader can black out the screen"),
	("decoration.active_opacity", lambda v: v < 0.3, "windows become nearly invisible"),
	("decoration.inactive_opacity", lambda v: v < 0.3, "windows become nearly invisible"),
	("decoration.fullscreen_opacity", lambda v: v < 0.3, "windows become nearly invisible"),
	("decoration.dim_strength", lambda v: v > 0.8, "dimmed windows become nearly black"),
	("decoration.dim_around", lambda v: v > 0.8, "the screen around a window becomes nearly black"),
	("decoration.blur.passes", lambda v: v > 3, "heavy blur has hung the GPU before"),
	("decoration.blur.size", lambda v: v > 12, "heavy blur has hung the GPU before"),
	("decoration.blur.variant", lambda v: v != 0, "blur variants are heavier on the GPU"),
	("decoration.shadow.range", lambda v: v > 30, "large shadows are heavy on the GPU"),
	("decoration.glow.range", lambda v: v > 30, "large glow is heavy on the GPU"),
	("decoration.motion_blur.enabled", lambda v: v, "motion blur is heavy on the GPU"),
	("decoration.motion_blur.samples", lambda v: v > 32, "motion blur is heavy on the GPU"),
]

# The blur variant whose settings sit in decoration.blur.<table> is the one
# named like the table. These tables are read by other variants (checked in
# Hyprland 0.57.1, src/render/gl/blur/).
BLUR_VARIANT = "decoration.blur.variant"
BLUR_TABLE_VARIANTS = {"glass": ("frost", "drops", "prism", "heat_shimmer", "aurora")}

HEADER = """\
-- Written by Lacquer (~/claude/lacquer). Do not edit by hand: `lacquer keep`
-- rewrites this whole file from ~/.config/lacquer/current.toml.
"""


def _hex(aarrggbb):
	"""Hyprland's aarrggbb to the theme's #rrggbb[aa]."""
	alpha, rgb = aarrggbb[:2], aarrggbb[2:]
	return f"#{rgb}" if alpha == "ff" else f"#{rgb}{alpha}"


def _from_hypr(kind, raw):
	"""Turns a getoption/descriptions value into the theme file's form."""
	if kind == "gaps":
		sides = [int(n) for n in raw.split()] if isinstance(raw, str) else [raw] * 4
		return sides[0] if len(set(sides)) == 1 else dict(zip(("top", "right", "bottom", "left"), sides))
	if kind == "gradient":
		parts = raw.split()
		angle = int(parts.pop()[:-3]) if parts[-1].endswith("deg") else 0
		colors = [_hex(p) for p in parts]
		return colors[0] if len(colors) == 1 and angle == 0 else {"colors": colors, "angle": angle}
	if kind == "color":
		if isinstance(raw, str):
			return None if raw.startswith("-") else _hex(raw)
		return None if raw < 0 else _hex(f"{raw:08x}")
	if kind == "str":
		return "" if raw == "[[EMPTY]]" else raw
	if kind == "float":
		return round(float(raw), 6)
	return raw


def _to_lua(kind, value):
	"""Turns a theme value into what hl.config() takes."""
	def color(c):
		return f"rgb({c[1:]})" if len(c) == 7 else f"rgba({c[1:]})"
	if kind == "color" or (kind == "gradient" and isinstance(value, str)):
		return color(value)
	if kind == "gradient":
		return {"colors": [color(c) for c in value["colors"]], "angle": value["angle"]}
	if kind == "str" and value == "":
		return "[[EMPTY]]"
	return value


def _option(key):
	"""`general.col.active_border` back to Hyprland's `general:col.active_border`."""
	return key.replace(".", ":").replace(":col:", ":col.")


def _lua_leaves(text):
	"""Lists the option paths set in a generated hl.config({...}) file."""
	stack, leaves = [], []
	for line in text.splitlines():
		line = line.strip()
		if m := re.match(r"(\w+)\s*=\s*\{$", line):
			stack.append(m.group(1))
		elif line in ("}", "},") and stack:
			stack.pop()
		elif m := re.match(r"(\w+)\s*=", line):
			leaves.append(".".join(stack + [m.group(1)]))
	return leaves


class Windows(Module):
	name = "windows"
	title = "Windows"
	order = 20

	def __init__(self):
		self._schema = None

	def detect(self):
		return hypr.running() and shutil.which("hyprctl") is not None

	def schema(self):
		if self._schema is None:
			self._schema = {}
			for d in hypr.hyprctl_json("descriptions"):
				if not LOOK.match(d["name"]):
					continue
				option = hypr.get_option(d["name"])
				if option is None:
					continue
				kind = "gaps" if option[0] == "css" else option[0]
				# Plain colors are reported as int but described as hex text.
				if kind == "int" and isinstance(d["default"], str):
					kind = "color"
				name = d["name"].replace(":", ".")
				self._schema[name] = Key(
					name=name, type=kind, default=_from_hypr(kind, d["default"]),
					min=d.get("min"), max=d.get("max"),
					choices={k: v for pair in d.get("map") or [] for k, v in pair.items()} or None,
					description=d["description"],
				)
		return self._schema

	def needs(self, key, schema):
		needs = super().needs(key, schema)
		parts = key.split(".")
		variant = schema.get(BLUR_VARIANT)
		if len(parts) == 4 and key.startswith("decoration.blur.") and variant and variant.choices:
			# A variant this Hyprland does not know hides nothing.
			names = BLUR_TABLE_VARIANTS.get(parts[2], (parts[2],))
			allowed = [variant.choices[n] for n in names if n in variant.choices]
			if allowed:
				needs[BLUR_VARIANT] = allowed
		return needs

	def read(self, keys=None):
		schema = self.schema()
		out = {}
		for key in schema if keys is None else keys:
			option = hypr.get_option(_option(key))
			if option is not None:
				out[key] = _from_hypr(schema[key].type, option[1])
		return out

	def risk(self, key, value):
		for name, test, why in RISKY:
			if name == key and test(value):
				return why
		return None

	def preview(self, changes):
		if changes:
			hypr.eval_lua(f"hl.config({lua.emit(self._nest(changes), pretty=False)})")

	def keep(self, section):
		old = paths.read_text(LACQUER_LUA)
		paths.atomic_write(LACQUER_LUA, self._render(section))
		hypr.reload()
		errors = hypr.config_errors()
		if errors:
			if old is None:
				os.remove(LACQUER_LUA)
			else:
				paths.atomic_write(LACQUER_LUA, old)
			hypr.reload()
			raise LacquerError("Hyprland reported config errors, the old file is back: " + "; ".join(errors))
		if not self._hooked():
			return [f"{MAIN_LUA} does not load config.lacquer yet: run `lacquer install`"]
		return [f"windows.{k} is overridden by a later config file ({why})" for k, why in self._overridden(section).items()]

	def revert(self):
		hypr.reload()

	def unchanged(self, changes):
		# Setting the old values is enough, and spares a reload (which also
		# drops what other tools set at runtime).
		self.preview(changes)

	def doctor(self, section):
		out = []

		def add(level, check, detail):
			out.append({"level": level, "check": check, "detail": detail})

		text = paths.read_text(MAIN_LUA) or ""
		if REQUIRE not in text:
			add("error", "windows.hooked", f"{MAIN_LUA} does not load config.lacquer: run `lacquer install`")
		else:
			pos = text.index(REQUIRE)
			theme, dash = text.find("apply_theme()"), text.find('require("config.dashboard_options")')
			if theme > pos:
				add("warn", "windows.order", "config.lacquer loads before the Noctalia theme, so Noctalia's border colors win")
			elif dash != -1 and dash < pos:
				add("warn", "windows.order", "config.lacquer loads after dashboard_options")
			else:
				add("ok", "windows.hooked", "hyprland.lua loads config.lacquer in the right place")

		# Hyprland does not report a bind's command, so match on the key.
		*mods, key = [part.strip() for part in self._revert_bind().split("+")]
		mask = sum(MODMASK.get(m.upper(), 0) for m in mods)
		binds = [b for b in hypr.hyprctl_json("binds") if b["key"].lower() == key.lower() and b["modmask"] == mask]
		if len(binds) == 1:
			add("ok", "windows.revert_bind", f"revert key is bound ({self._revert_bind()})")
		elif binds:
			add("error", "windows.revert_bind", f"{self._revert_bind()} is bound {len(binds)} times, so another bind shares the revert key")
		else:
			add("error", "windows.revert_bind", f"{self._revert_bind()} is not bound: run `lacquer keep` or `lacquer install`")

		dashboard = sorted(k for k in _lua_leaves(paths.read_text(DASHBOARD_LUA) or "") if k in self.schema())
		clash = [k for k in dashboard if k in section]
		if clash:
			add("warn", "windows.dashboard_overlap", "hypr-dashboard also sets these and loads later, so it wins: " + ", ".join(clash))
		if dashboard:
			add("ok", "windows.dashboard_sets", "look options hypr-dashboard sets (keeping them in Lacquer has no effect): " + ", ".join(dashboard))
		for key, why in self._overridden(section).items():
			add("warn", "windows.overridden", f"windows.{key}: {why}")
		return out

	def install(self, section):
		done = []
		if paths.read_text(LACQUER_LUA) is None:
			paths.atomic_write(LACQUER_LUA, self._render(section))
			done.append(f"wrote {LACQUER_LUA}")
		return done + hyprconf.hook(REQUIRE, [
			"-- Look options kept by Lacquer (~/claude/lacquer). After the Noctalia theme",
			"-- so they win over it, before dashboard_options.",
		])

	# -- helpers --

	def _nest(self, flat):
		tree = {}
		for key, value in flat.items():
			node = tree
			*parents, leaf = key.split(".")
			for p in parents:
				node = node.setdefault(p, {})
			node[leaf] = _to_lua(self.schema()[key].type, value)
		return tree

	def _revert_bind(self):
		return tomlio.load(paths.SETTINGS).get("revert", {}).get("bind", DEFAULT_REVERT_BIND)

	def _render(self, section):
		command = paths.USER_BIN if os.path.exists(paths.USER_BIN) else paths.LAUNCHER
		text = HEADER + "\n-- Undoes a Lacquer preview you can't see or click away.\n"
		text += f"hl.bind({lua.emit(self._revert_bind())}, hl.dsp.exec_cmd({lua.emit(command + ' revert')}))\n"
		if section:
			text += f"\nhl.config({lua.emit(self._nest(section))})\n"
		return text

	def _hooked(self):
		return hyprconf.hooked(REQUIRE)

	def _overridden(self, section):
		"""Saved keys whose live value differs. Only meaningful with no preview."""
		live = self.read(section)
		return {k: f"saved {v!r}, live {live.get(k)!r}" for k, v in section.items() if not same(live.get(k), v)}


MODULE = Windows()
