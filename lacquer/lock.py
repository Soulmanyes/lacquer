"""One change to the desktop at a time, across processes.

The CLI, the window, the auto-revert timer and the hooks (`lacquer sync`) can
run at the same moment. A call that changes things waits here for the one
before it, so a hook never writes in the middle of a revert.
"""
import fcntl
import functools
import os
import threading

from . import paths

FILE = os.path.join(paths.RUNTIME, "lock")
_thread = threading.RLock()
_depth = 0
_handle = None


def exclusive(fn):
	"""Decorator: fn runs alone. A locked function may call another one."""
	@functools.wraps(fn)
	def locked(*args, **kwargs):
		global _depth, _handle
		with _thread:
			if _depth == 0:
				os.makedirs(paths.RUNTIME, exist_ok=True)
				_handle = open(FILE, "w")  # noqa: SIM115 - held until the outermost call ends
				fcntl.flock(_handle, fcntl.LOCK_EX)
			_depth += 1
			try:
				return fn(*args, **kwargs)
			finally:
				_depth -= 1
				if _depth == 0:
					_handle.close()
					_handle = None
	return locked
