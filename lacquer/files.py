"""A whole file as a place (`file:<path>`): its text, or None when absent."""
import os

from . import paths


def get(path):
	return paths.read_text(path)


def put(path, text):
	"""Writes the file; None removes it. The file's mode is kept."""
	old = paths.read_text(path)
	if text == old:
		return
	if text is None:
		os.remove(path)
		return
	mode = os.stat(path).st_mode if old is not None else None
	paths.atomic_write(path, text)
	if mode is not None:
		os.chmod(path, mode)
