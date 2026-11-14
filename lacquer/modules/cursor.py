"""Mouse cursor: theme and size.

Preview is `hyprctl setcursor` plus gsettings (GTK apps draw their own cursor
from it). Keep also writes what a new login needs: the env vars in
~/.config/hypr/config/lacquer_cursor.lua, ~/.icons/default (X11 apps) and
GTK's settings.ini. Never `hl.env` in a preview: an env var can't be unset by
a reload.
"""
import os

from .. import gsettings, gtk, hypr, hyprconf, installed, lua, paths, places
from ..values import Key, LacquerError

CURSOR_LUA = hyprconf.config_file("lacquer_cursor")
REQUIRE = 'require("config.lacquer_cursor")'
THEME, SIZE = "gsettings:cursor-theme", "gsettings:cursor-size"
SMALL, HUGE = 16, 96

HEADER = """\
-- Written by Lacquer (~/claude/lacquer). Do not edit by hand: `lacquer keep`
-- rewrites this whole file from ~/.config/lacquer/current.toml.
-- Cursor for apps started from now on. Taking a line out does not unset the
-- variable until the next login.
"""


class Cursor(places.Placed):
	name = "cursor"
	title = "Cursor"
	order = 70

	def detect(self):
		return hypr.running() and gsettings.available()

	def schema(self):
		return {
			"theme": Key(name="theme", type="str", choices={n: n for n in installed.cursor_themes()}, description="cursor theme"),
			"size": Key(name="size", type="int", min=1, max=256, description="cursor size in pixels"),
		}

	def risk(self, key, value):
		if key == "theme" and value not in installed.cursor_themes():
			return f"cursor theme {value!r} is not installed, the cursor may vanish"
		if key == "size" and value < SMALL:
			return "a cursor this small is hard to find"
		if key == "size" and value > HUGE:
			return "a cursor this large covers what you click"
		return None

	def read(self, keys=None):
		theme = places.get(THEME)
		if theme == "default":
			theme = installed.default_cursor() or theme
		live = {"theme": theme, "size": places.get(SIZE)}
		return live if keys is None else {k: live[k] for k in keys if k in live}

	def touched(self, changes):
		return [THEME, SIZE]

	def write(self, changes):
		now = {**self.read(), **changes}
		hypr.set_cursor(now["theme"], now["size"])
		places.put(THEME, now["theme"])
		places.put(SIZE, now["size"])

	def restored(self):
		live = self.read()
		hypr.set_cursor(live["theme"], live["size"])

	def keep(self, section):
		theme, size = section.get("theme"), section.get("size")
		self._write_env(theme, size)
		ini = {}
		if theme:
			paths.backup_once(installed.USER_DEFAULT_CURSOR)
			paths.atomic_write(installed.USER_DEFAULT_CURSOR, f"[Icon Theme]\nName=Default\nComment=Default Cursor Theme\nInherits={theme}\n")
			ini["gtk-cursor-theme-name"] = theme
		if size:
			ini["gtk-cursor-theme-size"] = size
		gtk.mirror(ini)
		return super().keep(section)

	def install(self, section):
		if not section or hyprconf.hooked(REQUIRE):
			return []
		self._write_env(section.get("theme"), section.get("size"))
		return [f"wrote {CURSOR_LUA}"]

	def doctor(self, section):
		out = []
		live = self.read()
		if live["theme"] not in installed.cursor_themes():
			out.append({"level": "warn", "check": "cursor.theme", "detail": f"cursor theme {live['theme']!r} is set but not installed"})
		if section and not hyprconf.hooked(REQUIRE):
			out.append({"level": "error", "check": "cursor.hooked", "detail": f"{hyprconf.MAIN_LUA} does not load config.lacquer_cursor: run `lacquer install`"})
		ini = {"gtk-cursor-theme-name": section.get("theme"), "gtk-cursor-theme-size": section.get("size")}
		for path, key, found in gtk.stale({k: v for k, v in ini.items() if v}):
			out.append({"level": "warn", "check": "cursor.settings_ini", "detail": f"{path} has {key}={found}, not the kept value"})
		if not out:
			out.append({"level": "ok", "check": "cursor.theme", "detail": f"cursor is {live['theme']} at {live['size']}"})
		return out

	# -- helpers --

	def _write_env(self, theme, size):
		"""Writes the env file and hooks it into hyprland.lua. With nothing
		kept and no file yet, there is nothing to do."""
		old = paths.read_text(CURSOR_LUA)
		if old is None and not theme and not size:
			return
		text = HEADER
		for name, value in (("XCURSOR_THEME", theme), ("HYPRCURSOR_THEME", theme), ("XCURSOR_SIZE", size), ("HYPRCURSOR_SIZE", size)):
			if value:
				text += f"hl.env({lua.emit(name)}, {lua.emit(str(value))})\n"
		paths.atomic_write(CURSOR_LUA, text)
		try:
			if hyprconf.hooked(REQUIRE):
				hypr.reload()
				errors = hypr.config_errors()
				if errors:
					raise LacquerError("Hyprland reported config errors, the old cursor file is back: " + "; ".join(errors))
			else:
				hyprconf.hook(REQUIRE, ["-- Cursor env vars kept by Lacquer (~/claude/lacquer)."])
		except LacquerError:
			if old is None:
				os.remove(CURSOR_LUA)
			else:
				paths.atomic_write(CURSOR_LUA, old)
			hypr.reload()
			raise


MODULE = Cursor()
