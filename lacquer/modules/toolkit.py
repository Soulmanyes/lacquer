"""GTK and Qt look: GTK theme, icon theme, Qt widget style. Not colors: those
come from the palette.

Preview writes gsettings and qt6ct.conf (running apps follow both at once).
Keep also copies the values into GTK's settings.ini files, which XWayland and
some sandboxed apps read.
"""
from .. import gsettings, gtk, installed, places, qt6ct
from ..values import Invalid, Key

# key: (description, places written on preview, settings.ini key, installed names)
KEYS = {
	"gtk_theme": ("GTK theme (GTK3 apps; libadwaita apps keep their own)", ["gsettings:gtk-theme"], "gtk-theme-name", installed.gtk_themes),
	"icon_theme": ("icon theme for GTK and Qt apps", ["gsettings:icon-theme", "qt6ct:Appearance/icon_theme"], "gtk-icon-theme-name", installed.icon_themes),
	"qt_style": ("Qt widget style, for example Fusion, Breeze, Oxygen", ["qt6ct:Appearance/style"], None, None),
}


def _usable(place):
	return qt6ct.installed() if place.startswith("qt6ct:") else True


class Toolkit(places.Placed):
	name = "toolkit"
	title = "Apps (GTK and Qt)"
	order = 60

	def __init__(self):
		self._schema = None

	def detect(self):
		return gsettings.available()

	def _places(self, key):
		return [p for p in KEYS[key][1] if _usable(p)]

	def schema(self):
		if self._schema is None:
			self._schema = {}
			for key, (description, _, _, names) in KEYS.items():
				if self._places(key):
					choices = {n: n for n in names()} if names else None
					self._schema[key] = Key(name=key, type="str", choices=choices, description=description)
		return self._schema

	def validate(self, key, value):
		value = super().validate(key, value)
		if not value:
			raise Invalid(f"{key}: needs a name")
		if key == "icon_theme" and value not in installed.icon_themes():
			raise Invalid(f"{key}: icon theme {value!r} is not installed (have: {', '.join(installed.icon_themes())})")
		return value

	def risk(self, key, value):
		if key == "gtk_theme" and value not in installed.gtk_themes():
			return f"GTK theme {value!r} is not installed, apps may become unreadable"
		return None

	def read(self, keys=None):
		return {k: places.get(self._places(k)[0]) for k in (self.schema() if keys is None else keys) if k in self.schema()}

	def touched(self, changes):
		return [p for k in changes for p in self._places(k)]

	def write(self, changes):
		for key, value in changes.items():
			for place in self._places(key):
				places.put(place, value)

	def _ini(self, section):
		return {KEYS[k][2]: v for k, v in section.items() if KEYS[k][2]}

	def keep(self, section):
		gtk.mirror(self._ini(section))
		return super().keep(section)

	def doctor(self, section):
		out = []
		live = self.read()
		for key, value in live.items():
			names = KEYS[key][3]
			if names and value not in names():
				out.append({"level": "warn", "check": f"toolkit.{key}", "detail": f"{value!r} is set but not installed, so apps fall back to a default"})
			for place in self._places(key)[1:]:
				other = places.get(place)
				if other != value:
					out.append({"level": "warn", "check": f"toolkit.{key}", "detail": f"{place} says {other!r}, GTK apps use {value!r}: `lacquer set toolkit.{key} <name>` makes them agree"})
		for path, ini_key, found in gtk.stale(self._ini({k: v for k, v in live.items() if k in section})):
			out.append({"level": "warn", "check": "toolkit.settings_ini", "detail": f"{path} has {ini_key}={found}, not the kept value: `lacquer keep` after any toolkit preview rewrites it"})
		if not out:
			out.append({"level": "ok", "check": "toolkit.agree", "detail": "GTK and Qt settings agree and the themes are installed"})
		return out


MODULE = Toolkit()
