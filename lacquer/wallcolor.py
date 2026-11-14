"""The main color of an image, through ImageMagick (`magick`)."""
import re
import shutil
import subprocess

from . import color
from .values import LacquerError

LINE = re.compile(r"^\s*(\d+):.*?#([0-9A-Fa-f]{6})", re.MULTILINE)


def available():
	return shutil.which("magick") is not None


def seed(path):
	"""The image's most common colorful color as `#rrggbb`. A gray image
	gives its most common gray."""
	if not available():
		raise LacquerError("taking colors from a wallpaper needs ImageMagick (`magick`), which is not installed")
	try:
		out = subprocess.run(
			["magick", f"{path}[0]", "-resize", "96x96", "-colors", "8", "-depth", "8", "-format", "%c", "histogram:info:-"],
			check=False, capture_output=True, text=True, timeout=30,
		)
	except (OSError, subprocess.TimeoutExpired) as e:
		raise LacquerError(f"ImageMagick could not read {path}: {e}") from e
	found = [(int(count), f"#{rgb.lower()}") for count, rgb in LINE.findall(out.stdout)]
	if out.returncode or not found:
		raise LacquerError(f"ImageMagick could not read {path}: {out.stderr.strip() or 'no colors found'}")
	colorful = [(count * color.to_oklch(c)[1], c) for count, c in found if color.to_oklch(c)[1] >= 0.04]
	return max(colorful)[1] if colorful else max(found)[1]
