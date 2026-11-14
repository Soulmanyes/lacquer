"""One background thread for every core call that changes or reads the
desktop, so the window never freezes. Calls run one at a time, in order.
"""
import queue
import threading

from gi.repository import GLib

from ..values import LacquerError


class Worker:
	def __init__(self):
		self.busy = 0
		self._jobs = queue.Queue()
		self._thread = threading.Thread(target=self._loop)
		self._thread.start()

	def call(self, fn, *args, done=None):
		"""Runs fn(*args) on the thread, then done(result, error) on the GTK
		thread. error is a message for the user, or None."""
		self.busy += 1
		self._jobs.put((fn, args, done))

	def stop(self):
		"""Finishes the queued calls, then ends the thread."""
		self._jobs.put(None)
		self._thread.join()

	def _loop(self):
		while (job := self._jobs.get()) is not None:
			fn, args, done = job
			try:
				result, error = fn(*args), None
			except LacquerError as e:
				result, error = None, str(e)
			except Exception as e:  # noqa: BLE001 - a bug in one call must not kill the thread
				result, error = None, f"{type(e).__name__}: {e}"
			GLib.idle_add(self._finish, done, result, error)

	def _finish(self, done, result, error):
		self.busy -= 1
		if done:
			done(result, error)
		return False
