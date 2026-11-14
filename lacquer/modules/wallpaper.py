"""Wallpaper through Noctalia: the image per monitor and how it is drawn.

`default` is the image for every monitor; `monitors.<output>` is one monitor.
Setting `default` makes Noctalia put it on every monitor, so list the
monitors that differ in the same `set` (they are written after `default`).
"""
import os
import re

from ..noctalia import ConfigModule, msg
from ..values import Invalid, Key, LacquerError

DRAWING = {"fill_mode", "fill_color", "edge_smoothness", "transition_duration"}


def _outputs():
	"""Noctalia names its outputs only in the error for an unknown one."""
	try:
		msg("wallpaper-get", "lacquer-no-such-output")
	except LacquerError as e:
		found = re.search(r"known: (.*)$", str(e))
		return [o.strip() for o in found.group(1).split(",")] if found else []
	return []


class Wallpaper(ConfigModule):
	name = "wallpaper"
	title = "Wallpaper"
	order = 50
	table = "wallpaper"

	def wanted(self, key):
		return key in DRAWING

	def _images(self):
		return ["default"] + [f"monitors.{o}" for o in _outputs()]

	def config_schema(self):
		images = {k: Key(name=k, type="str", description="image file", hint="image") for k in self._images()}
		return {**images, **super().config_schema()}

	def validate(self, key, value):
		value = super().validate(key, value)
		if key in DRAWING:
			return value
		path = os.path.abspath(os.path.expanduser(value))
		if not os.path.isfile(path):
			raise Invalid(f"{key}: no such file {path}")
		return path

	def read(self, keys=None):
		live = self.config_values()
		for key in self._images():
			if keys is None or key in keys:
				live[key] = msg("wallpaper-get", *key.split(".")[1:])
		return live if keys is None else {k: live[k] for k in keys if k in live}

	def snapshot_keys(self, changes):
		# Writing `default` changes every monitor, so remember them all.
		images = self._images() if any(k not in DRAWING for k in changes) else []
		return list(dict.fromkeys(images + list(changes)))

	def write(self, changes):
		# `default` first: it overwrites the per-monitor images.
		for key in sorted((k for k in changes if k not in DRAWING), key=lambda k: k != "default"):
			msg("wallpaper-set", *key.split(".")[1:], changes[key])
		super().write({k: v for k, v in changes.items() if k in DRAWING})


MODULE = Wallpaper()
