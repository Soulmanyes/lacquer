"""The GNOME interface settings (GTK theme, icons, cursor, fonts).

GTK apps on Wayland read these, not settings.ini. A change is saved and
applied at once; there is no live-only mode.
"""
import functools
import shutil
import subprocess

from .values import LacquerError

SCHEMA = "org.gnome.desktop.interface"


def _run(*args):
	try:
		out = subprocess.run(["gsettings", *args], check=False, capture_output=True, text=True, timeout=5)
	except (OSError, subprocess.TimeoutExpired) as e:
		raise LacquerError(f"gsettings did not answer `{' '.join(args)}`: {e}") from e
	if out.returncode:
		raise LacquerError(f"gsettings refused `{' '.join(args)}`: {out.stderr.strip()}")
	return out.stdout.strip()


@functools.cache
def available():
	if shutil.which("gsettings") is None:
		return False
	try:
		_run("get", SCHEMA, "gtk-theme")
	except LacquerError:
		return False
	return True


def get(key):
	"""A string or a number, as stored."""
	text = _run("get", SCHEMA, key)
	if text[:1] in "'\"":
		return text[1:-1].replace("\\'", "'")
	try:
		return int(text)
	except ValueError:
		return float(text)


def put(key, value):
	"""Sets the key; None puts back the system default."""
	if value is None:
		_run("reset", SCHEMA, key)
	else:
		_run("set", SCHEMA, key, str(value))
