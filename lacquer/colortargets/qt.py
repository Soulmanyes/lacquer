"""Qt apps through qt6ct: a color scheme file that qt6ct.conf points at.

Running Qt apps watch qt6ct.conf and recolor at once.
"""
import os

from .. import color, qt6ct
from . import Target

FILE = os.path.join(os.path.dirname(qt6ct.PATH), "colors", "lacquer.conf")
PATH, CUSTOM = "qt6ct:Appearance/color_scheme_path", "qt6ct:Appearance/custom_palette"

# QPalette roles in the order qt6ct stores them.
ORDER = (
	"windowText", "button", "light", "midlight", "dark", "mid", "text", "brightText", "buttonText", "base", "window", "shadow",
	"highlight", "highlightedText", "link", "linkVisited", "alternateBase", "default", "toolTipBase", "toolTipText", "placeholderText", "accent",
)


def _group(c, disabled=False):
	text = color.mix(c["on_surface"], c["surface"], 0.5) if disabled else c["on_surface"]
	roles = {
		"windowText": text, "button": c["surface"], "light": "#ffffff", "midlight": "#cacaca", "dark": "#9f9f9f", "mid": "#b8b8b8",
		"text": text, "brightText": "#ffffff", "buttonText": text, "base": c["surface"], "window": c["surface"], "shadow": c["shadow"],
		"highlight": color.mix(c["surface"], c["primary"], 0.3), "highlightedText": c["primary"],
		"link": c["secondary"], "linkVisited": c["primary"], "alternateBase": c["surface_variant"], "default": c["surface"],
		"toolTipBase": c["surface_variant"], "toolTipText": c["on_surface"], "placeholderText": c["on_surface_variant"], "accent": c["primary"],
	}
	return ", ".join(roles[name] for name in ORDER)


class Qt(Target):
	name = "qt"
	templates = ("qt",)

	def detect(self):
		return qt6ct.installed()

	def render(self, look):
		if self.name not in look.handover:
			look.handover[self.name] = {"path": qt6ct.get("Appearance/color_scheme_path"), "custom": qt6ct.get("Appearance/custom_palette")}
		c = look.colors
		text = (
			"# Written by Lacquer (~/claude/lacquer): do not edit by hand.\n[ColorScheme]\n"
			f"active_colors={_group(c)}\ndisabled_colors={_group(c, True)}\ninactive_colors={_group(c)}\n"
		)
		return {f"file:{FILE}": text, PATH: FILE, CUSTOM: "true"}

	def release(self, handover):
		before = handover.get(self.name)
		if before is None:
			return {}
		return {PATH: before["path"], CUSTOM: before["custom"], f"file:{FILE}": None}


TARGET = Qt()
