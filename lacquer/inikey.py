"""One key of any INI file as a place: `ini:<path>::<Section>/<key>`.

For files other programs also write (kdeglobals): only that one line changes.
"""
from . import ini, paths


def place(path, section, key):
	return f"ini:{path}::{section}/{key}"


def _split(rest):
	path, _, where = rest.partition("::")
	section, _, key = where.rpartition("/")
	return path, section, key


def get(rest):
	path, section, key = _split(rest)
	return ini.get(paths.read_text(path) or "", section, key)


def put(rest, value):
	"""Sets the key; None takes it out of the file."""
	path, section, key = _split(rest)
	ini.edit(path, section, {key: value})
