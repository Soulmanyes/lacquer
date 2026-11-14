"""The palette as one JSON file for other programs (Shellac) to read:
~/.local/state/lacquer/palette.json.

{"version": 1, "mode": "dark", "seed": "#..", "dark": {"primary": "#..", ...,
"terminal.red": "#.."}, "light": {...}}. The file is gone while the engine is
not `lacquer`.
"""
import json
import os

from .. import paths
from . import Target

FILE = os.path.join(paths.STATE, "palette.json")


class Export(Target):
	name = "export"

	def render(self, look):
		data = {"version": 1, "mode": look.mode, "seed": look.seed, **look.palette}
		return {f"file:{FILE}": json.dumps(data, indent=1) + "\n"}

	def release(self, handover):
		return {f"file:{FILE}": None}


TARGET = Export()
