"""Colors: who makes the palette and which one.

`engine` says who writes the colors. Only "noctalia" exists so far: Noctalia
builds the palette (`source`: builtin, wallpaper, community or custom) and its
templates color the apps. Lacquer's own engine comes in a later phase.
"""
from ..noctalia import ConfigModule
from ..values import Invalid, Key

ENGINES = ("noctalia",)


class Palette(ConfigModule):
	name = "palette"
	table = "theme"

	def wanted(self, key):
		return "." not in key  # not the template lists

	def config_schema(self):
		engine = Key(name="engine", type="str", default="noctalia", description="who writes the colors: " + ", ".join(ENGINES))
		return {"engine": engine, **super().config_schema()}

	def validate(self, key, value):
		if key == "engine" and value not in ENGINES:
			raise Invalid(f"engine: only {', '.join(ENGINES)} so far, got {value!r}")
		return super().validate(key, value)

	def read(self, keys=None):
		live = {"engine": "noctalia", **self.config_values()}
		return live if keys is None else {k: live[k] for k in keys if k in live}

	def write(self, changes):
		super().write({k: v for k, v in changes.items() if k != "engine"})


MODULE = Palette()
