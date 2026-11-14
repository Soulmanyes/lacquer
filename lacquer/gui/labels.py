"""Turns keys into words and colors into GTK's form."""
from gi.repository import Gdk

# Key parts that read better as another word.
WORDS = {"col": "colors"}


def words(part):
	"""`gaps_in` to `Gaps in`. Names with capitals (`eDP-1`) stay as they are."""
	part = WORDS.get(part, part)
	if any(c.isupper() for c in part):
		return part
	return part.replace("_", " ").capitalize()


def title(key):
	return words(key.rsplit(".", 1)[-1])


def group(key, fallback):
	"""Group title of a full key: the parts between section and setting."""
	parents = key.split(".")[1:-1]
	return " › ".join(words(p) for p in parents) or fallback


def to_rgba(text):
	"""`#rrggbb[aa]` to Gdk.RGBA; None or junk is fully transparent."""
	rgba = Gdk.RGBA()
	rgba.red = rgba.green = rgba.blue = rgba.alpha = 0.0
	digits = (text or "").lstrip("#")
	if len(digits) in (6, 8):
		try:
			parts = [int(digits[i:i + 2], 16) / 255 for i in range(0, len(digits), 2)]
		except ValueError:
			return rgba
		rgba.red, rgba.green, rgba.blue = parts[:3]
		rgba.alpha = parts[3] if len(parts) == 4 else 1.0
	return rgba


def to_hex(rgba):
	parts = [round(c * 255) for c in (rgba.red, rgba.green, rgba.blue, rgba.alpha)]
	if parts[3] == 255:
		parts.pop()
	return "#" + "".join(f"{p:02x}" for p in parts)
