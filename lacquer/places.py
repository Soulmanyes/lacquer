"""One value in another program's settings, named by one string.

`gsettings:icon-theme`, `qt6ct:Appearance/icon_theme`, `file:<path>` (a whole
file), `ini:<path>::<Section>/<key>`, `noctalia:<config path>`. A Lacquer key often
lands in several places that may disagree before Lacquer touches them, so a
preview remembers each place, not the key, and revert puts each place back
exactly.

A new kind of place = one entry in KINDS with `get(rest)` and `put(rest, value)`.
"""
from . import files, gsettings, inikey, noctalia, qt6ct, state
from .persistent import Persistent

KINDS = {"gsettings": gsettings, "qt6ct": qt6ct, "file": files, "ini": inikey, "noctalia": noctalia}


def get(place):
	kind, _, rest = place.partition(":")
	return KINDS[kind].get(rest)


def put(place, value):
	kind, _, rest = place.partition(":")
	KINDS[kind].put(rest, value)


class Placed(Persistent):
	"""A Persistent module that writes to places.

	A module fills in `read()`, `write()` and `touched()`.
	"""

	def touched(self, changes):
		"""Every place that writing `changes` can alter."""
		raise NotImplementedError

	def restored(self):
		"""Called after a revert put the places back (for anything else to redo)."""

	def preview(self, changes):
		if not changes:
			return
		old = state.old_load(self.name)
		fresh = [p for p in self.touched(changes) if p not in old]
		if fresh:
			old.update({p: get(p) for p in fresh})
			state.old_save(self.name, old)
		self.write(changes)
		self.check(changes)

	def revert(self):
		old = state.old_load(self.name)
		for place, value in old.items():
			put(place, value)
		if old:
			self.restored()
		# Cleared only after the writes worked, so `lacquer revert --force`
		# can try again.
		state.old_clear(self.name)
