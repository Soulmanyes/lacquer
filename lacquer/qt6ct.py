"""qt6ct.conf: the look of Qt apps (they need QT_QPA_PLATFORMTHEME=qt6ct).

Running Qt apps watch the file and take a change at once. A key is addressed
as `Section/key`, for example `Appearance/icon_theme`.
"""
import os
import shutil

from . import ini, paths

PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(paths.HOME, ".config"), "qt6ct", "qt6ct.conf")


def installed():
	return shutil.which("qt6ct") is not None or os.path.isfile(PATH)


def get(key):
	section, name = key.split("/", 1)
	value = ini.get(paths.read_text(PATH) or "", section, name)
	if value and value[0] == value[-1] == '"':
		value = value[1:-1]
	return value


def put(key, value):
	"""Sets the key; None takes it out of the file."""
	section, name = key.split("/", 1)
	if value is not None and "," in value:
		value = f'"{value}"'  # Qt reads a bare comma as a list
	ini.edit(PATH, section, {name: value})
