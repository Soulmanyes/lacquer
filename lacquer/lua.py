"""Writing Python values as Lua source."""
import json
import re

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


def emit(value, pretty=True, depth=0):
	"""Returns Lua source for a value. pretty=False gives one line (for eval)."""
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, (int, float)):
		return repr(value)
	if isinstance(value, str):
		return json.dumps(value, ensure_ascii=False)
	if isinstance(value, list):
		return "{" + ", ".join(emit(v, False) for v in value) + "}"
	if isinstance(value, dict):
		if not value:
			return "{}"
		items = [f"{k if NAME.match(k) else '[' + json.dumps(k) + ']'} = {emit(v, pretty, depth + 1)}" for k, v in value.items()]
		if not pretty:
			return "{" + ", ".join(items) + "}"
		pad = "\t" * (depth + 1)
		return "{\n" + "".join(f"{pad}{i},\n" for i in items) + "\t" * depth + "}"
	raise TypeError(f"cannot write {value!r} as Lua")
