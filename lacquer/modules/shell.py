"""Noctalia shell look: corner radius, font, borders, shadows, animation speed,
panel look and screen corners. Everything else under `shell` is behaviour.
"""
from ..noctalia import ConfigModule

LOOK = {
	"corner_radius_scale", "font_family", "app_icon_colorize", "show_close_buttons",
	"button_borders", "card_borders", "input_borders", "popup_borders", "popup_shadows",
	"settings_window_translucent",
	"animation.enabled", "animation.speed",
	"panel.borders", "panel.border_color", "panel.border_width", "panel.shadow",
	"panel.transparency_mode", "panel.list_item_background", "panel.floating_offset",
	"screen_corners.enabled", "screen_corners.size",
}


class Shell(ConfigModule):
	name = "shell"
	title = "Shell"
	order = 40
	table = "shell"

	def wanted(self, key):
		return key in LOOK


MODULE = Shell()
