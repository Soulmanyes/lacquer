"""The page of one section, built from its schema alone.

Settings are grouped by the middle of their key (`decoration.blur.size` sits
in "Decoration › Blur"). Every setting shows, except one that does nothing in
the current state: a key it depends on has another value, such as a switch
that is off (`needs` in the schema), or the page says
so (`applies` of add_item()). A section that needs more than this subclasses
SectionPage in `pages/` and overrides build().
"""
from gi.repository import Adw

from . import labels, rows, search


class SectionPage(Adw.PreferencesPage):
	def __init__(self, app, name, info, schema):
		"""schema: the section's part of `core.schema()` (full keys)."""
		super().__init__()
		self.app, self.name, self.info, self.schema = app, name, info, schema
		self.rows = {}  # full key -> row (anything with load() and set_preview())
		self._groups = {}
		self._items = []  # (group, widget, applies: None or fn(values) -> bool, search text)
		self._values = {}  # full key -> live value of this section, as last loaded
		self._words = []  # the running search
		self.build()
		self._none = Adw.PreferencesGroup(description="Nothing on this page matches the search.", visible=False)
		self.add(self._none)
		self._apply_visibility()

	# -- for build() --

	def group(self, title, description=""):
		"""The group with this title, made on first use."""
		if title not in self._groups:
			group = Adw.PreferencesGroup(title=title, description=description)
			self._groups[title] = group
			self.add(group)
		return self._groups[title]

	def add_item(self, group, widget, applies=None, text=""):
		"""Puts any widget into a group. `applies(values)` (values: full key ->
		live value of this section) returning False hides it: for a setting
		that does nothing in the current state. None = always shown. `text`
		is what the search finds it by, next to the group's title."""
		group.add(widget)
		self._items.append((group, widget, applies, search.fold(f"{group.get_title()} {text}")))

	def add_row(self, group, key, applies=None, row=None):
		"""Adds the row for a key (made from the schema unless given). Without
		`applies`, a key hides while a key it `needs` has a value that is not
		allowed (a switch that is off, another blur variant)."""
		spec = self.schema[key]
		row = row or rows.make(key, spec, self.app)
		self.rows[key] = row
		needs = spec.get("needs")
		if applies is None and needs:
			def applies(values):
				# A value not loaded yet hides nothing.
				return all(values.get(other) is None or values[other] in allowed for other, allowed in needs.items())
		self.add_item(group, row.widget, applies, f"{key} {labels.title(key)} {spec.get('description', '')}")
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

	def filter(self, words):
		"""Shows only what holds every word (`search.fold` form; none = all).
		A search also finds what does nothing right now, so a setting behind
		a switch that is off can still be found. Returns how many items show."""
		self._words = words
		return self._apply_visibility()

	def _apply_visibility(self):
		shown, count = set(), 0
		for group, widget, applies, text in self._items:
			if self._words:
				visible = search.matches(self._words, text)
			else:
				visible = applies is None or applies(self._values)
			widget.set_visible(visible)
			if visible:
				shown.add(group)
				count += 1
		for group in self._groups.values():
			group.set_visible(group in shown)
		self._none.set_visible(bool(self._words) and not count)
		return count
