"""Noctalia bar look: size, radius, opacity, capsules, border, margins, font.

Keys are `<bar name>.<setting>` (`default.radius`). Which widgets sit on the
bar, capsule groups and bar behaviour (auto-hide, layer) are not look and stay
in Noctalia's own settings.
"""
from ..noctalia import ConfigModule

BEHAVIOUR = {
	"enabled", "auto_hide", "auto_hide_delay_ms", "smart_auto_hide", "layer",
	"reserve_space", "show_on_workspace_switch", "show_tooltip",
}


class Bar(ConfigModule):
	name = "bar"
	table = "bar"

	def wanted(self, key):
		# `<bar>.<setting>` only: no top-level values, no sub-tables.
		parts = key.split(".")
		return len(parts) == 2 and parts[1] not in BEHAVIOUR


MODULE = Bar()
