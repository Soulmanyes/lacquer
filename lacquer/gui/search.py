"""The search box in the header: filters the settings of every section page.

A page takes part by having filter(words) -> number of matches (SectionPage
has it). While a search runs, pages without a match leave the sidebar.
"""
import re

from gi.repository import Gtk

SPLIT = re.compile(r"[\s_.›]+")


def fold(text):
	"""Text in the form the search compares: lower case, `_` and `.` as spaces."""
	return " ".join(SPLIT.split(text.lower())).strip()


def matches(words, text):
	"""Does folded `text` have a word starting with each of `words`?
	(`round` finds `rounding`, not `around`.)"""
	text = " " + text
	return all(" " + word in text for word in words)


class Search(Gtk.SearchEntry):
	def __init__(self, app):
		super().__init__(placeholder_text="Search settings", width_request=240, tooltip_text="Ctrl+F")
		self.app = app
		self.connect("search-changed", lambda *_: self.apply())
		self.connect("stop-search", lambda *_: self.set_text(""))
		keys = Gtk.ShortcutController(scope=Gtk.ShortcutScope.GLOBAL)
		keys.add_shortcut(Gtk.Shortcut(
			trigger=Gtk.ShortcutTrigger.parse_string("<Control>f"),
			action=Gtk.CallbackAction.new(lambda *_: self.grab_focus() or True),
		))
		app.add_controller(keys)

	def apply(self):
		"""Filters every page with the text in the box (also after the pages are built)."""
		words = fold(self.get_text()).split()
		stack, pages = self.app.stack, self.app.section_pages
		found = {name: page.filter(words) for name, page in pages.items()}
		# No match anywhere: every page stays, each saying so.
		keep = {name for name, count in found.items() if count or not words or not any(found.values())}
		for name in keep:
			stack.get_page(pages[name]).set_visible(True)
		current = stack.get_visible_child_name()
		if words and keep and current not in keep:
			stack.set_visible_child_name(next(name for name in pages if name in keep))
		for name in found.keys() - keep:
			stack.get_page(pages[name]).set_visible(False)
