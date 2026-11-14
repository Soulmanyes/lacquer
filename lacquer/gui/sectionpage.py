"""The page of one section, built from its schema alone.

Settings are grouped by the middle of their key (`decoration.blur.size` sits
in "Decoration › Blur"). Every setting shows, except one that does nothing in
the current state (`applies` of add_item()). A section that needs more than
this subclasses SectionPage in `pages/` and overrides build().
"""
from gi.repository import Adw

from . import labels, rows


class SectionPage(Adw.PreferencesPage):
	def __init__(self, app, name, info, schema):
		"""schema: the section's part of `core.schema()` (full keys)."""
		super().__init__()
		self.app, self.name, self.info, self.schema = app, name, info, schema
		self.rows = {}  # full key -> row (anything with load() and set_preview())
		self._groups = {}
		self._items = []  # (group, widget, applies: None or fn(values) -> bool)
		self._values = {}  # full key -> live value of this section, as last loaded
		self.build()
		self._apply_visibility()

	# -- for build() --

	def group(self, title, description=""):
		"""The group with this title, made on first use."""
		if title not in self._groups:
			group = Adw.PreferencesGroup(title=title, description=description)
			self._groups[title] = group
			self.add(group)
		return self._groups[title]

	def add_item(self, group, widget, applies=None):
		"""Puts any widget into a group. `applies(values)` (values: full key ->
		live value of this section) returning False hides it: for a setting
		that does nothing in the current state. None = always shown."""
		group.add(widget)
		self._items.append((group, widget, applies))

	def add_row(self, group, key, applies=None, row=None):
		"""Adds the row for a key (made from the schema unless given)."""
		row = row or rows.make(key, self.schema[key], self.app)
		self.rows[key] = row
		self.add_item(group, row.widget, applies)
		return row

	def build(self):
		for key in self.schema:
			self.add_row(self.group(labels.group(key, self.info["title"])), key)

	# -- for the window --

	def load(self, values):
		"""values: entries of `core.get()`; keys of other sections are ignored."""
		for key, row in self.rows.items():
			if key in values:
				row.load(values[key])
		prefix = self.name + "."
		self._values.update({k: entry.get("value") for k, entry in values.items() if k.startswith(prefix)})
		self._apply_visibility()

	def _apply_visibility(self):
		shown = set()
		for group, widget, applies in self._items:
			visible = applies is None or applies(self._values)
			widget.set_visible(visible)
			if visible:
				shown.add(group)
		for group in self._groups.values():
			group.set_visible(group in shown)
