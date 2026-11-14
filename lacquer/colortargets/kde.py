"""KDE apps (Dolphin, Kate, ...): a color scheme file plus the same colors in
kdeglobals, which is where KDE apps outside Plasma read them from.

Apps pick the colors up when they start.
"""
import os

from .. import color, inikey, paths
from . import Target

CONFIG = os.environ.get("XDG_CONFIG_HOME") or os.path.join(paths.HOME, ".config")
DATA = os.environ.get("XDG_DATA_HOME") or os.path.join(paths.HOME, ".local", "share")
KDEGLOBALS = os.path.join(CONFIG, "kdeglobals")
SCHEMES = os.path.join(DATA, "color-schemes")
NAME = "Lacquer"
FILE = os.path.join(SCHEMES, f"{NAME}.colors")
SCHEME = inikey.place(KDEGLOBALS, "General", "ColorScheme")


def _sections(c):
	"""The color sections of a KDE scheme, {section: {key: "r,g,b"}}."""
	half = color.mix(c["surface"], c["surface_variant"], 0.5)
	tint = color.mix(c["surface"], c["primary"], 0.3)
	base = {
		"DecorationFocus": c["primary"], "DecorationHover": c["primary"],
		"ForegroundActive": c["primary"], "ForegroundInactive": c["on_surface_variant"], "ForegroundLink": c["secondary"],
		"ForegroundNegative": c["error"], "ForegroundNeutral": c["tertiary"], "ForegroundNormal": c["on_surface"],
		"ForegroundPositive": c["tertiary"], "ForegroundVisited": c["secondary"],
	}

	def group(alternate, normal, **changed):
		return {"BackgroundAlternate": alternate, "BackgroundNormal": normal, **base, **changed}

	sections = {
		"Colors:Button": group(half, color.mix(c["surface_variant"], c["on_surface"], 0.05)),
		"Colors:Complementary": group(half, c["surface"], ForegroundNormal=c["primary"]),
		"Colors:Header": group(c["surface"], c["surface_variant"]),
		"Colors:Header][Inactive": group(c["surface_variant"], c["surface"]),
		"Colors:Selection": group(
			half, c["primary"], ForegroundActive=c["on_primary"], ForegroundNormal=c["on_primary"],
			ForegroundNegative=color.mix(c["surface"], c["error"], 0.3),
			ForegroundNeutral=color.mix(c["surface"], c["tertiary"], 0.3), ForegroundPositive=color.mix(c["surface"], c["tertiary"], 0.3),
		),
		"Colors:Tooltip": group(c["surface"], c["surface_variant"]),
		"Colors:View": group(c["surface_variant"], c["surface"], DecorationHover=c["surface"]),
		"Colors:Window": group(tint, c["surface_variant"]),
		"WM": {
			"activeBackground": tint, "activeBlend": c["primary"], "activeForeground": c["primary"],
			"inactiveBackground": c["surface"], "inactiveBlend": c["on_surface_variant"], "inactiveForeground": c["on_surface_variant"],
		},
	}
	return {name: {k: color.csv(v) for k, v in keys.items()} for name, keys in sections.items()}


def _scheme(c):
	text = f"# Written by Lacquer (~/claude/lacquer): do not edit by hand.\n[General]\nColorScheme={NAME}\nName={NAME}\n\n[KDE]\ncontrast=4\n"
	text += (
		f"\n[ColorEffects:Disabled]\nColor={color.csv(c['surface'])}\nColorAmount=0\nColorEffect=0\n"
		"ContrastAmount=0.65\nContrastEffect=1\nIntensityAmount=0.1\nIntensityEffect=2\n"
		f"\n[ColorEffects:Inactive]\nChangeSelectionColor=true\nColor={color.csv(c['surface_variant'])}\nColorAmount=0.025\nColorEffect=2\n"
		"ContrastAmount=0.1\nContrastEffect=2\nEnable=false\nIntensityAmount=0\nIntensityEffect=0\n"
	)
	for name, keys in _sections(c).items():
		text += f"\n[{name}]\n" + "".join(f"{k}={v}\n" for k, v in keys.items())
	return text


class Kde(Target):
	name = "kde"
	templates = ("kcolorscheme",)

	def detect(self):
		return os.path.isfile(KDEGLOBALS)

	def render(self, look):
		if self.name not in look.handover:
			look.handover[self.name] = {"scheme": inikey.get(SCHEME.removeprefix("ini:"))}
		places = {f"file:{FILE}": _scheme(look.colors), SCHEME: NAME}
		for section, keys in _sections(look.colors).items():
			places.update({inikey.place(KDEGLOBALS, section, k): v for k, v in keys.items()})
		return places

	def release(self, handover):
		# The colors in kdeglobals stay until the next writer (Noctalia's
		# template) replaces them; only the name and the file go back.
		before = handover.get(self.name)
		if before is None:
			return {}
		return {SCHEME: before["scheme"], f"file:{FILE}": None}


TARGET = Kde()
