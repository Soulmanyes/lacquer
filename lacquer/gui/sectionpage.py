"""The page of one section, built from its schema alone.

Settings are grouped by the middle of their key (`decoration.blur.size` sits
in "Decoration › Blur"). The ones the module lists as `common` always show;
the rest appear with the "Show all settings" switch. A section that needs
more than this subclasses SectionPage in `pages/` and overrides build().
"""
from fnmatch import fnmatchcase

from gi.repository import Adw

from . import labels, rows


class SectionPage(Adw.PreferencesPage):
	def __init__(self, app, name, info, schema):
		"""schema: the section's part of `core.schema()` (full keys)."""
		super().__init__()
		self.app, self.name, self.info, self.schema = app, name, info, schema
		self.rows = {}  # full key -> row (anything with load() and set_preview())
		self._groups = {}
		self._items = []  # (group, widget, always shown)
		self._toggle = Adw.SwitchRow(title="Show all settings")
		self._toggle.connect("notify::active", lambda *_: self._apply_visibility())
		self._toggle_group = Adw.PreferencesGroup()
		self._toggle_group.add(self._toggle)
		self.add(self._toggle_group)
		self.build()
		hidden = sum(1 for _group, _widget, always in self._items if not always)
		self._toggle_group.set_visible(hidden > 0)
		self._toggle.set_subtitle(f"{hidden} more are hidden")
		self._apply_visibility()

	# -- for build() --

	def is_common(self, key):
		patterns = self.info["common"]
		rest = key[len(self.name) + 1:]
		return not patterns or any(fnmatchcase(rest, p) for p in patterns)

	def group(self, title, description=""):
		"""The group with this title, made on first use."""
		if title not in self._groups:
			group = Adw.PreferencesGroup(title=title, description=description)
			self._groups[title] = group
			self.add(group)
		return self._groups[title]

	def add_item(self, group, widget, always=True):
		"""Puts any widget into a group; `always` False hides it until
		"Show all settings" is on."""
		group.add(widget)
		self._items.append((group, widget, always))

	def add_row(self, group, key, always=True, row=None):
		"""Adds the row for a key (made from the schema unless given)."""
		row = row or rows.make(key, self.schema[key], self.app)
		self.rows[key] = row
		self.add_item(group, row.widget, always)
		return row

	def build(self):
		for key in self.schema:
			self.add_row(self.group(labels.group(key, self.info["title"])), key, self.is_common(key))

	# -- for the window --

	def load(self, values):
		"""values: entries of `core.get()`; keys of other sections are ignored."""
		for key, row in self.rows.items():
			if key in values:
				row.load(values[key])

	def _apply_visibility(self):
		show_all = self._toggle.get_active()
		shown = set()
		for group, widget, always in self._items:
			visible = always or show_all
			widget.set_visible(visible)
			if visible:
				shown.add(group)
		for group in self._groups.values():
			group.set_visible(group in shown)
