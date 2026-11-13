"""Base for modules whose target saves every change at once.

Noctalia (`config-set`) and gsettings have no live-only mode. So a preview
writes the real setting after storing the old value, revert writes the old
value back, and keep only forgets the old values.

A module fills in `read()` and `write()`; preview/keep/revert come from here.
"""
from . import state
from .modules.base import Module
from .values import LacquerError, same


class Persistent(Module):
	def write(self, changes):
		"""Sets {key: value} on the target. Raises LacquerError on refusal."""
		raise NotImplementedError

	def snapshot_keys(self, changes):
		"""Keys whose old value must be stored before `changes` is written.

		Override when writing one key also changes others."""
		return list(changes)

	def preview(self, changes):
		if not changes:
			return
		old = state.old_load(self.name)
		fresh = [k for k in self.snapshot_keys(changes) if k not in old]
		if fresh:
			old.update(self.read(fresh))
			state.old_save(self.name, old)
		self.write(changes)
		self.check(changes)

	def check(self, changes):
		"""Raises if the target did not take a value as given (it clamped it)."""
		live = self.read(list(changes))
		off = [f"{k}: asked {v!r}, got {live.get(k)!r}" for k, v in changes.items() if not same(live.get(k), v)]
		if off:
			raise LacquerError(f"{self.name} did not take the values as given (out of range?): " + "; ".join(off))

	def keep(self, section):
		# The target already holds the values. Keys dropped from the section
		# (unset, or a theme replacing the section) simply stay as they are.
		state.old_clear(self.name)
		return []

	def revert(self):
		old = state.old_load(self.name)
		if old:
			self.write(old)
		# Cleared only after the write worked, so `lacquer revert --force`
		# can try again.
		state.old_clear(self.name)
