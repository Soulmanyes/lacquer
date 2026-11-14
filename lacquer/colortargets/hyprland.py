"""Hyprland: border, group, groupbar and glow colors.

Live through `hyprctl eval`; saved in ~/.config/hypr/config/lacquer_palette.lua,
which hyprland.lua loads after the Noctalia theme and before config.lacquer,
so a border color kept in the `windows` section still wins.

Noctalia's own `hyprland` template stays on. Turning it off makes Noctalia
delete ~/.config/hypr/noctalia.lua and its require line in hyprland.lua, which
breaks any config that reads `require("noctalia").colors`, and turning it back
on appends the require at the end of hyprland.lua, after the files that must
win over it. Both write the same palette; Lacquer's file is loaded later.
"""
from .. import hypr, hyprconf, lua, paths
from ..values import LacquerError
from . import Target

FILE = hyprconf.config_file("lacquer_palette")
REQUIRE = 'require("config.lacquer_palette")'
HEADER = """\
-- Written by Lacquer. Do not edit by hand: the palette
-- engine rewrites this whole file.
"""
IDLE = HEADER + "-- The palette engine is not `lacquer`, so no colors are set here.\n"


def _config(c):
	def rgb(name, alpha=""):
		return f"rgba({c[name][1:]}{alpha})" if alpha else f"rgb({c[name][1:]})"
	return {
		"general": {"col": {"active_border": rgb("primary"), "inactive_border": rgb("surface")}},
		"group": {
			"col": {
				"border_active": rgb("secondary"), "border_inactive": rgb("surface"),
				"border_locked_active": rgb("error"), "border_locked_inactive": rgb("surface"),
			},
			"groupbar": {
				"col": {"active": rgb("secondary"), "inactive": rgb("surface"), "locked_active": rgb("error"), "locked_inactive": rgb("surface")},
				"text_color": rgb("on_secondary"), "text_color_inactive": rgb("on_surface"),
				"text_color_locked_active": rgb("on_error"), "text_color_locked_inactive": rgb("on_surface"),
			},
		},
		"decoration": {"glow": {"color": rgb("primary", "ee"), "color_inactive": rgb("secondary", "55")}},
	}


class Hyprland(Target):
	name = "hyprland"

	def detect(self):
		return hypr.running()

	def render(self, look):
		return {f"file:{FILE}": HEADER + f"\nhl.config({lua.emit(_config(look.colors))})\n"}

	def release(self, handover):
		# hyprland.lua may load the file, so it stays, empty.
		return {f"file:{FILE}": IDLE} if paths.read_text(FILE) is not None else {}

	def live(self, look):
		if look is None:
			hypr.reload()
		else:
			hypr.eval_lua(f"hl.config({lua.emit(_config(look.colors), pretty=False)})")

	def reverted(self):
		hypr.reload()

	def keep(self, active):
		if not hyprconf.hooked(REQUIRE):
			if active:
				hyprconf.hook(REQUIRE, ["-- Palette colors from Lacquer's own engine."], before='require("config.lacquer")')
			return []
		# The saved file now decides, in the right order with config.lacquer.
		hypr.reload()
		errors = hypr.config_errors()
		if errors:
			raise LacquerError("Hyprland reported config errors after the palette change: " + "; ".join(errors))
		return []


TARGET = Hyprland()
