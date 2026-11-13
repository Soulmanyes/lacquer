"""GTK's settings.ini files.

GTK apps on Wayland use gsettings; these files are what XWayland and some
sandboxed apps fall back to. Lacquer copies kept values into them so every
app agrees.
"""
import os

from . import ini, paths

_CONFIG = os.environ.get("XDG_CONFIG_HOME") or os.path.join(paths.HOME, ".config")
FILES = [os.path.join(_CONFIG, d, "settings.ini") for d in ("gtk-3.0", "gtk-4.0")]


def mirror(values):
	"""Sets {settings.ini key: value} in each file that exists. Returns the files changed."""
	if not values:
		return []
	return [path for path in FILES if os.path.isfile(path) and ini.edit(path, "Settings", values)]


def stale(values):
	"""[(file, key, value in file)] where a file disagrees with `values`."""
	out = []
	for path in FILES:
		text = paths.read_text(path)
		if text is None:
			continue
		for key, value in values.items():
			found = ini.get(text, "Settings", key)
			if found is not None and found != str(value):
				out.append((path, key, found))
	return out
