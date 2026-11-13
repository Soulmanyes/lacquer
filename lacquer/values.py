"""Value types shared by all modules: checking, CLI parsing and comparing.

Theme file formats:
  color     "#rrggbb" or "#rrggbbaa"
  gradient  a color, or {colors = ["#..", "#.."], angle = 45}
  gaps      an integer, or {top = 4, right = 8, bottom = 4, left = 8}
  vec2      [x, y]
"""
import json
import re
from dataclasses import asdict, dataclass


class LacquerError(Exception):
	"""Any failure that should reach the user as a plain message."""


class Invalid(LacquerError):
	"""A value that does not fit its key."""


@dataclass
class Key:
	name: str
	type: str
	default: object = None
	min: object = None
	max: object = None
	choices: dict | None = None
	description: str = ""

	def public(self):
		return {k: v for k, v in asdict(self).items() if k != "name" and v is not None and v != ""}


COLOR = re.compile(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
SIDES = ("top", "right", "bottom", "left")


def parse_cli(text):
	"""Turns a command-line word into a value: JSON if it parses, else a string."""
	try:
		return json.loads(text)
	except ValueError:
		return text


def _color(key, value):
	if not isinstance(value, str) or not COLOR.match(value):
		raise Invalid(f"{key.name}: color must be \"#rrggbb\" or \"#rrggbbaa\", got {value!r}")
	return value.lower()


def _number(key, value, kinds, word):
	if isinstance(value, bool) or not isinstance(value, kinds):
		raise Invalid(f"{key.name}: needs {word}, got {value!r}")
	if key.min is not None and value < key.min:
		raise Invalid(f"{key.name}: {value} is below the minimum {key.min}")
	if key.max is not None and value > key.max:
		raise Invalid(f"{key.name}: {value} is above the maximum {key.max}")
	return value


def _whole(key, value, what):
	if isinstance(value, bool) or not isinstance(value, int) or value < 0:
		raise Invalid(f"{key.name}: {what} must be a whole number of 0 or more, got {value!r}")
	return value


def normalize(key, value):
	"""Checks a value against its key and returns it in the stored form."""
	t = key.type
	if t == "bool":
		if not isinstance(value, bool):
			raise Invalid(f"{key.name}: needs true or false, got {value!r}")
		return value
	if t == "int":
		if isinstance(value, str) and key.choices:
			if value not in key.choices:
				raise Invalid(f"{key.name}: pick one of {', '.join(key.choices)}")
			return key.choices[value]
		return _number(key, value, int, "a whole number")
	if t == "float":
		return float(_number(key, value, (int, float), "a number"))
	if t == "str":
		if not isinstance(value, str):
			raise Invalid(f"{key.name}: needs text, got {value!r}")
		return value
	if t == "color":
		return _color(key, value)
	if t == "gradient":
		if isinstance(value, str):
			return _color(key, value)
		if not isinstance(value, dict) or set(value) - {"colors", "angle"} or not isinstance(value.get("colors"), list) or not value["colors"]:
			raise Invalid(f"{key.name}: needs a color or {{colors = [...], angle = N}}, got {value!r}")
		colors = [_color(key, c) for c in value["colors"]]
		angle = value.get("angle", 0)
		if isinstance(angle, bool) or not isinstance(angle, int):
			raise Invalid(f"{key.name}: angle must be a whole number of degrees")
		if len(colors) == 1 and angle == 0:
			return colors[0]
		return {"colors": colors, "angle": angle}
	if t == "gaps":
		if isinstance(value, dict):
			if not value or set(value) - set(SIDES):
				raise Invalid(f"{key.name}: sides are {', '.join(SIDES)}")
			sides = {s: _whole(key, value.get(s, 0), s) for s in SIDES}
			return sides["top"] if len(set(sides.values())) == 1 else sides
		return _whole(key, value, "gap")
	if t == "vec2":
		if not isinstance(value, list) or len(value) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
			raise Invalid(f"{key.name}: needs [x, y], got {value!r}")
		return value
	raise Invalid(f"{key.name}: unknown type {t}")


def same(a, b):
	"""True if two stored values mean the same thing (floats compared loosely)."""
	if isinstance(a, bool) or isinstance(b, bool):
		return a is b
	if isinstance(a, (int, float)) and isinstance(b, (int, float)):
		return abs(a - b) < 1e-4
	if isinstance(a, dict) and isinstance(b, dict):
		return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
	if isinstance(a, list) and isinstance(b, list):
		return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
	return a == b
