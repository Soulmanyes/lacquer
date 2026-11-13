"""Reading and writing theme TOML. Python reads TOML itself but has no writer."""
import json
import re
import tomllib

BARE = re.compile(r"[A-Za-z0-9_-]+$")


class Inline(dict):
	"""A table that is one value (a gradient, per-side gaps): written on one line."""


def load(path):
	"""Returns the file as a dict, or {} if it does not exist."""
	try:
		with open(path, "rb") as f:
			return tomllib.load(f)
	except FileNotFoundError:
		return {}


def _key(name):
	return name if BARE.match(name) else json.dumps(name)


def _value(v):
	if isinstance(v, bool):
		return "true" if v else "false"
	if isinstance(v, (int, float)):
		return repr(v)
	if isinstance(v, str):
		return json.dumps(v, ensure_ascii=False)
	if isinstance(v, list):
		return "[" + ", ".join(_value(x) for x in v) + "]"
	if isinstance(v, dict):
		return "{" + ", ".join(f"{_key(k)} = {_value(x)}" for k, x in v.items()) + "}"
	raise TypeError(f"cannot write {v!r} to TOML")


def _is_table(v):
	return isinstance(v, dict) and not isinstance(v, Inline)


def dumps(data):
	"""Writes nested dicts as [tables]; Inline dicts stay inline."""
	out = []

	def table(node, path):
		plain = [(k, v) for k, v in node.items() if not _is_table(v)]
		if path and (plain or not node):
			out.append(f"[{'.'.join(_key(p) for p in path)}]")
		for k, v in plain:
			out.append(f"{_key(k)} = {_value(v)}")
		if plain or (path and not node):
			out.append("")
		for k, v in node.items():
			if _is_table(v):
				table(v, path + [k])

	table(data, [])
	return "\n".join(out).rstrip("\n") + "\n"


def literal(value):
	"""One value as TOML text (what `noctalia msg config-set` takes)."""
	return _value(value)
