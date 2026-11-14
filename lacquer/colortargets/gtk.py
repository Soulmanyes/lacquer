"""GTK 3 and 4 apps (and libadwaita): named colors in `lacquer.css`, pulled in
by the first line of the user's `gtk.css`.

GTK reads `gtk.css` once when an app starts, so running apps keep their old
colors until they are restarted.
"""
import os
import re

from .. import color, gsettings, noctalia, paths
from . import Target

CONFIG = os.environ.get("XDG_CONFIG_HOME") or os.path.join(paths.HOME, ".config")
DIRS = {3: os.path.join(CONFIG, "gtk-3.0"), 4: os.path.join(CONFIG, "gtk-4.0")}
IMPORT = re.compile(r'^@import url\("(?:noctalia|lacquer)\.css"\);\n?', re.MULTILINE)
# Noctalia keeps the GTK parts of its community templates in this file.
EXTENSIONS = "noctalia-extensions.css"


def _pointed(text, name):
	"""gtk.css with its palette import set to `<name>.css` (None: no import)."""
	line = f'@import url("{name}.css");\n' if name else ""
	rest = IMPORT.sub("", text or "")
	return line + rest


def _css(c, version, extensions):
	headerbar = c["surface_variant"] if version == 3 else c["surface"]
	named = {
		"accent_color": c["primary"], "accent_bg_color": c["primary"], "accent_fg_color": c["on_primary"],
		"destructive_bg_color": c["error"], "destructive_fg_color": c["on_error"],
		"error_bg_color": c["error"], "error_fg_color": c["on_error"],
		"window_bg_color": c["surface"], "window_fg_color": c["on_surface"],
		"view_bg_color": c["surface"], "view_fg_color": c["on_surface"],
		"headerbar_bg_color": headerbar, "headerbar_fg_color": c["on_surface"], "headerbar_backdrop_color": "@window_bg_color",
		"popover_bg_color": c["surface_variant"], "popover_fg_color": c["on_surface"],
		"card_bg_color": c["surface_variant"], "card_fg_color": c["on_surface"],
		"dialog_bg_color": c["surface"], "dialog_fg_color": c["on_surface"],
		"overview_bg_color": c["surface_variant"], "overview_fg_color": c["on_surface"],
		"sidebar_bg_color": c["surface_variant"], "sidebar_fg_color": c["on_surface"],
		"sidebar_backdrop_color": "@window_bg_color", "sidebar_border_color": "@window_bg_color",
		"secondary_sidebar_bg_color": c["surface"], "secondary_sidebar_fg_color": c["on_surface"],
		"theme_selected_bg_color": "@accent_bg_color", "theme_selected_fg_color": "@accent_fg_color",
		"theme_unfocused_fg_color": "@window_fg_color", "theme_unfocused_text_color": "@view_fg_color",
		"theme_unfocused_bg_color": "@window_bg_color", "theme_unfocused_base_color": "@window_bg_color",
		"theme_unfocused_selected_bg_color": "@accent_bg_color", "theme_unfocused_selected_fg_color": "@accent_fg_color",
	}
	text = f"/* GTK {version} colors. Written by Lacquer (~/claude/lacquer): do not edit by hand. */\n"
	if extensions:
		text += f'@import url("{EXTENSIONS}");\n'
	text += "\n" + "".join(f"@define-color {name} {value};\n" for name, value in named.items())
	if version == 4:
		# libadwaita reads these as CSS variables.
		variables = {name.replace("_", "-"): value for name, value in named.items() if not name.startswith("theme_") and not name.startswith("secondary_")}
		variables.update({
			"error-color": c["error"],
			"warning-bg-color": color.mix(c["surface"], c["tertiary"], 0.3), "warning-fg-color": c["tertiary"], "warning-color": c["tertiary"],
			"success-bg-color": color.mix(c["surface"], c["secondary"], 0.3), "success-fg-color": c["secondary"], "success-color": c["secondary"],
			"shade-color": "rgba(0, 0, 0, 0.36)",
		})
		text += "\n:root {\n" + "".join(f"\t--{name}: {value};\n" for name, value in variables.items()) + "}\n"
	return text


class Gtk(Target):
	name = "gtk"
	templates = ("gtk3", "gtk4")

	def render(self, look):
		places = {}
		for version, folder in DIRS.items():
			extensions = os.path.isfile(os.path.join(folder, EXTENSIONS))
			places[f"file:{os.path.join(folder, 'lacquer.css')}"] = _css(look.colors, version, extensions)
			places[f"file:{os.path.join(folder, 'gtk.css')}"] = _pointed(paths.read_text(os.path.join(folder, "gtk.css")), "lacquer")
		# Noctalia sets dark/light for apps itself; without it Lacquer does.
		if not noctalia.running() and gsettings.available():
			places["gsettings:color-scheme"] = "prefer-light" if look.mode == "light" else "prefer-dark"
		return places

	def release(self, handover):
		places = {}
		for folder in DIRS.values():
			back = "noctalia" if os.path.isfile(os.path.join(folder, "noctalia.css")) else None
			places[f"file:{os.path.join(folder, 'gtk.css')}"] = _pointed(paths.read_text(os.path.join(folder, "gtk.css")), back) or None
			places[f"file:{os.path.join(folder, 'lacquer.css')}"] = None
		return places


TARGET = Gtk()
