"""What is installed: GTK themes, icon themes, cursor themes, fonts."""
import functools
import os
import re
import subprocess

from . import paths

_DATA = os.environ.get("XDG_DATA_HOME") or os.path.join(paths.HOME, ".local", "share")
THEME_ROOTS = [os.path.join(paths.HOME, ".themes"), os.path.join(_DATA, "themes"), "/usr/local/share/themes", "/usr/share/themes"]
ICON_ROOTS = [os.path.join(paths.HOME, ".icons"), os.path.join(_DATA, "icons"), "/usr/local/share/icons", "/usr/share/icons"]
USER_DEFAULT_CURSOR = os.path.join(paths.HOME, ".icons", "default", "index.theme")


def _named(roots, test):
	found = set()
	for root in roots:
		if os.path.isdir(root):
			found.update(name for name in os.listdir(root) if os.path.isdir(os.path.join(root, name)) and test(os.path.join(root, name)))
	return sorted(found, key=str.lower)


def gtk_themes():
	return _named(THEME_ROOTS, lambda d: os.path.isdir(os.path.join(d, "gtk-3.0")) or os.path.isdir(os.path.join(d, "gtk-4.0")))


def icon_themes():
	"""Themes with icons in them (a cursor-only theme lists no Directories)."""
	def has_icons(d):
		text = paths.read_text(os.path.join(d, "index.theme"))
		return bool(text and re.search(r"^Directories\s*=\s*\S", text, re.MULTILINE))
	return _named(ICON_ROOTS, has_icons)


def cursor_themes():
	return _named(ICON_ROOTS, lambda d: os.path.isdir(os.path.join(d, "cursors")) or os.path.isfile(os.path.join(d, "manifest.hl")))


def default_cursor():
	"""The theme the name `default` stands for, or None."""
	for root in ICON_ROOTS:
		text = paths.read_text(os.path.join(root, "default", "index.theme"))
		found = text and re.search(r"^Inherits\s*=\s*([^,\n]+)", text, re.MULTILINE)
		if found:
			return found.group(1).strip()
	return None


@functools.cache
def font_families():
	try:
		out = subprocess.run(["fc-list", ":", "family"], check=False, capture_output=True, text=True, timeout=10).stdout
	except (OSError, subprocess.TimeoutExpired):
		return []
	return sorted({name.strip() for line in out.splitlines() for name in line.split(",") if name.strip()}, key=str.lower)
