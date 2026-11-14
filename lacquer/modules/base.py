"""The interface every area module fills in."""
from .. import values


class Module:
	# Section name in the theme file, and the first part of every key.
	name = ""
	# For front-ends: the section's title and its place in the list (low first).
	title = ""
	order = 100

	def detect(self) -> bool:
		"""Is the target installed and usable? If not the module is hidden."""
		return False

	def schema(self):
		"""Returns {key: values.Key} for everything this module can set."""
		return {}

	def needs(self, key, schema):
		"""Returns what must hold for `key` to do anything, as {other key:
		[values it may have]}; empty when nothing (`schema` is schema()).
		Front-ends hide the key while one of them has another value.
		Default: `enabled` of the nearest table above the key must be on."""
		parts = key.split(".")[:-1]
		while parts:
			switch = ".".join([*parts, "enabled"])
			if switch != key and switch in schema and schema[switch].type == "bool":
				return {switch: [True]}
			parts.pop()
		return {}

	def read(self, keys=None):
		"""Returns the live value of each key (all keys if None)."""
		return {}

	def validate(self, key, value):
		"""Returns the value in stored form, or raises values.Invalid."""
		return values.normalize(self.schema()[key], value)

	def risk(self, key, value) -> str | None:
		"""Returns why this value could leave the desktop unusable, or None."""

	def preview(self, changes):
		"""Shows {key: value} live without saving."""
		raise NotImplementedError

	def keep(self, section):
		"""Makes {key: value} (the whole section) the saved config.

		Returns a list of warnings. On failure it restores what was saved
		before and raises LacquerError.
		"""
		raise NotImplementedError

	def revert(self):
		"""Puts back what was there before the preview."""
		raise NotImplementedError

	def unchanged(self, changes):
		"""The preview ends because every previewed value is to go back to
		what it was; `changes` holds the last of them, not yet shown."""
		self.revert()

	def doctor(self, section):
		"""Returns findings: [{"level": "ok"|"warn"|"error", "check", "detail"}]."""
		return []

	def install(self, section):
		"""Hooks the module into the system. Returns a list of what it did."""
		return []
