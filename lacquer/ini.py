"""Editing one key of an INI file (GTK settings.ini, qt6ct.conf) in place.

Every other line stays exactly as it was: these files belong to other
programs, and configparser would rewrite them whole.
"""
import os
import re

from . import paths


def _span(lines, section):
	"""(first, end) line numbers of a section's body, or None."""
	start = next((i for i, line in enumerate(lines) if line.strip() == f"[{section}]"), None)
	if start is None:
		return None
	end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
	return start + 1, end


def _find(lines, span, key):
	pattern = re.compile(rf"\s*{re.escape(key)}\s*=")
	return next((i for i in range(*span) if pattern.match(lines[i])), None)


def get(text, section, key):
	"""The value as written in the file, or None."""
	lines = text.split("\n")
	span = _span(lines, section)
	at = _find(lines, span, key) if span else None
	return None if at is None else lines[at].split("=", 1)[1].strip()


def put(text, section, key, value):
	"""Returns the text with the key set; value None takes the key out."""
	lines = text.split("\n")
	span = _span(lines, section)
	at = _find(lines, span, key) if span else None
	if value is None:
		if at is not None:
			del lines[at]
			first, end = span[0], span[1] - 1
			if not any(line.strip() for line in lines[first:end]):
				# The section is empty now: take its header and blank lines out too.
				del lines[first - 1:end]
				while first - 1 == len(lines) and len(lines) > 1 and not lines[-1].strip() and not lines[-2].strip():
					lines.pop()
	elif at is not None:
		lines[at] = f"{key}={value}"
	elif span:
		# After the section's last line that is not blank.
		end = span[1]
		while end > span[0] and not lines[end - 1].strip():
			end -= 1
		lines.insert(end, f"{key}={value}")
	else:
		while lines and not lines[-1].strip():
			lines.pop()
		lines += ([""] if lines else []) + [f"[{section}]", f"{key}={value}", ""]
	return "\n".join(lines)


def edit(path, section, values):
	"""Sets {key: value or None} in the file. Returns True if it changed.

	The first change to a file copies it to `<file>.bak-lacquer`.
	"""
	old = paths.read_text(path) or ""
	new = old
	for key, value in values.items():
		new = put(new, section, key, value)
	if new == old:
		return False
	mode = os.stat(path).st_mode if old else None
	paths.backup_once(path)
	paths.atomic_write(path, new)
	if mode is not None:
		os.chmod(path, mode)
	return True
