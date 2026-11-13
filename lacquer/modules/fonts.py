"""Fonts of GTK and Qt apps: interface, document and monospace, each a family
and a size in points. Terminals and the bar have their own font settings.

Preview writes gsettings and qt6ct.conf. Keep also copies the interface font
into GTK's settings.ini files.
"""
import difflib
import re

from .. import gsettings, gtk, installed, places, qt6ct
from ..values import Invalid, Key

# role: (description, gsettings key, qt6ct key or None, settings.ini key or None)
ROLES = {
	"interface": ("font of menus, buttons and labels", "font-name", "Fonts/general", "gtk-font-name"),
	"document": ("font of document text", "document-font-name", None, None),
	"monospace": ("fixed-width font of GTK and Qt apps", "monospace-font-name", "Fonts/fixed", None),
}
TINY, HUGE = 6, 24

# Style words that may end a family name, as Qt's weight.
WEIGHTS = {"thin": 100, "light": 300, "regular": 400, "medium": 500, "semibold": 600, "semi-bold": 600, "bold": 700, "extrabold": 800, "black": 900}
SLANTS = ("italic", "oblique")
DESCRIPTION = re.compile(r"(.*?)[,\s]+(\d+(?:\.\d+)?)$")


def parse(text):
	"""`Noto Sans  10` to ("Noto Sans", 10)."""
	found = DESCRIPTION.match(text.strip())
	if not found:
		return text.strip(), 10
	return found.group(1).strip(" ,"), round(float(found.group(2)))


def split_style(family):
	"""`Noto Sans Bold Italic` to ("Noto Sans", 700, True)."""
	words = family.split()
	weight, italic = 400, False
	while len(words) > 1 and words[-1].lower() in (*WEIGHTS, *SLANTS):
		word = words.pop().lower()
		if word in SLANTS:
			italic = True
		else:
			weight = WEIGHTS[word]
	return " ".join(words), weight, italic


def qt_font(family, size):
	"""The form Qt stores a font in (QFont::toString)."""
	name, weight, italic = split_style(family)
	return f"{name},{size},-1,5,{weight},{int(italic)},0,0,0,0,0,0,0,0,0,1"


def _role(key):
	return key.removesuffix("_size")


class Fonts(places.Placed):
	name = "fonts"

	def detect(self):
		return gsettings.available()

	def schema(self):
		out = {}
		for role, (description, *_) in ROLES.items():
			out[role] = Key(name=role, type="str", description=f"{description}: family, may end in a style (Bold, Italic)")
			out[f"{role}_size"] = Key(name=f"{role}_size", type="int", min=1, max=200, description=f"{description}: size in points")
		return out

	def validate(self, key, value):
		value = super().validate(key, value)
		if key in ROLES:
			value = " ".join(value.split())
			name = split_style(value)[0]
			families = {f.lower() for f in installed.font_families()}
			if families and name.lower() not in families:
				near = difflib.get_close_matches(name, installed.font_families(), n=3)
				raise Invalid(f"{key}: font {name!r} is not installed" + (f" (did you mean {', '.join(near)}?)" if near else ""))
		return value

	def risk(self, key, value):
		if key.endswith("_size") and value < TINY:
			return "text this small is unreadable"
		if key.endswith("_size") and value > HUGE:
			return "text this large pushes buttons off the window"
		return None

	def read(self, keys=None):
		live = {}
		for role, (_, setting, _, _) in ROLES.items():
			live[role], live[f"{role}_size"] = parse(gsettings.get(setting))
		return live if keys is None else {k: live[k] for k in keys if k in live}

	def _places(self, role):
		_, setting, qt, _ = ROLES[role]
		return [f"gsettings:{setting}"] + ([f"qt6ct:{qt}"] if qt and qt6ct.installed() else [])

	def touched(self, changes):
		return [p for role in dict.fromkeys(map(_role, changes)) for p in self._places(role)]

	def write(self, changes):
		now = {**self.read(), **changes}
		for role in dict.fromkeys(map(_role, changes)):
			family, size = now[role], now[f"{role}_size"]
			for place in self._places(role):
				places.put(place, qt_font(family, size) if place.startswith("qt6ct:") else f"{family} {size}")

	def keep(self, section):
		live = self.read()
		ini = {}
		for role, (_, _, _, ini_key) in ROLES.items():
			if ini_key and (role in section or f"{role}_size" in section):
				ini[ini_key] = f"{live[role]},  {live[f'{role}_size']}"
		gtk.mirror(ini)
		return super().keep(section)

	def doctor(self, section):
		out = []
		live = self.read()
		families = {f.lower() for f in installed.font_families()}
		for role in ROLES:
			name = split_style(live[role])[0]
			if families and name.lower() not in families:
				out.append({"level": "warn", "check": f"fonts.{role}", "detail": f"font {name!r} is set but not installed, so apps fall back to a default"})
			for place in self._places(role)[1:]:
				want = qt_font(live[role], live[f"{role}_size"])
				if places.get(place) != want and (role in section or f"{role}_size" in section):
					out.append({"level": "warn", "check": f"fonts.{role}", "detail": f"{place} is not the kept font: `lacquer set fonts.{role} '{live[role]}'` makes Qt agree"})
		if not out:
			out.append({"level": "ok", "check": "fonts.installed", "detail": "the fonts are installed"})
		return out


MODULE = Fonts()
