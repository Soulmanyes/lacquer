"""Talking to Noctalia through `noctalia msg`.

Facts (v5.4.1): `config-get <path>` prints a value or a whole table as TOML.
`config-set <path> <TOML value>` saves to ~/.local/state/noctalia/settings.toml
and applies at once; there is no live-only mode and no unset. Errors come as
`error: ...` on stdout with exit code 0. Noctalia checks keys, types and
choices itself and clamps numbers that are out of range.
"""
import functools
import shutil
import subprocess
import tomllib

from . import tomlio
from .persistent import Persistent
from .values import Key, LacquerError, same

TYPES = {bool: "bool", int: "int", float: "float", str: "str"}


def msg(*args):
	"""Runs one `noctalia msg` command and returns its output."""
	try:
		out = subprocess.run(["noctalia", "msg", *args], check=False, capture_output=True, text=True, timeout=5)
	except (OSError, subprocess.TimeoutExpired) as e:
		raise LacquerError(f"Noctalia did not answer `msg {args[0]}`: {e}") from e
	text = (out.stdout or out.stderr).strip()
	if out.returncode or text.startswith("error:"):
		raise LacquerError(f"Noctalia refused `{' '.join(args)}`: {text.removeprefix('error:').strip()}")
	return text


@functools.cache
def running():
	if shutil.which("noctalia") is None:
		return False
	try:
		msg("status")
	except LacquerError:
		return False
	return True


def config_get(path):
	"""A config value, or a table as a dict."""
	text = msg("config-get", path)
	try:
		return tomllib.loads(f"v = {text}")["v"]
	except tomllib.TOMLDecodeError:
		return tomllib.loads(text)


def config_set(path, value):
	msg("config-set", path, tomlio.literal(value))


def scalars(table, wanted, prefix=""):
	"""Flattens a config table to {dotted key: value}, plain values only."""
	out = {}
	for name, value in table.items():
		key = prefix + name
		if isinstance(value, dict):
			out.update(scalars(value, wanted, key + "."))
		elif type(value) in TYPES and wanted(key):
			out[key] = round(value, 6) if isinstance(value, float) else value
	return out


class ConfigModule(Persistent):
	"""A module whose keys are plain values of one Noctalia config table.

	Subclasses set `name`, `table` and `wanted(key)`. Noctalia does not report
	ranges or choices, so those are checked by Noctalia on write.
	"""
	table = ""

	def __init__(self):
		self._schema = None

	def detect(self):
		return running()

	def wanted(self, key):
		return True

	def config_values(self):
		return scalars(config_get(self.table), self.wanted)

	def config_schema(self):
		return {k: Key(name=k, type=TYPES[type(v)]) for k, v in self.config_values().items()}

	def schema(self):
		if self._schema is None:
			self._schema = self.config_schema()
		return self._schema

	def read(self, keys=None):
		live = self.config_values()
		return live if keys is None else {k: live[k] for k in keys if k in live}

	def write(self, changes):
		# Every config-set makes Noctalia reload its config and plugins, so
		# values that are already live are skipped.
		live = self.config_values()
		for key, value in changes.items():
			if not same(live.get(key), value):
				config_set(f"{self.table}.{key}", value)
