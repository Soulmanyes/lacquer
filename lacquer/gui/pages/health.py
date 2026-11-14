"""Health page: what `lacquer doctor` finds, problems first.

Read when the window opens, after every keep or revert, and on "Check again".
The sidebar shows how many problems and warnings there are.
"""
from gi.repository import Adw, Gtk

from ... import core
from ..rows import CENTER

SECTION = None
TITLE = "Health"
ORDER = 20
# level -> (group title, icon, CSS class of the icon), in display order
LEVELS = {
	"error": ("Problems", "dialog-error-symbolic", "error"),
	"warn": ("Warnings", "dialog-warning-symbolic", "warning"),
	"ok": ("Fine", "object-select-symbolic", "success"),
}


class Page(Adw.PreferencesPage):
	def __init__(self, app):
		super().__init__()
		self.app = app
		self.findings = []  # as last read
		self._listed = []  # (group, row), replaced on refresh

		self.summary = Adw.PreferencesGroup(title="Health", description="Checking the setup…")
		again = Gtk.Button(label="Check again", valign=CENTER)
		again.connect("clicked", lambda *_: self.refresh())
		self.summary.set_header_suffix(again)
		self.add(self.summary)
		self.groups = {}
		for level, (title, _icon, _css) in LEVELS.items():
			self.groups[level] = Adw.PreferencesGroup(title=title, visible=False)
			self.add(self.groups[level])
		self.refresh()

	def refresh(self):
		self.app.run(lambda: core.doctor()["findings"], then=self._fill)

	def _fill(self, findings):
		self.findings = findings
		for group, row in self._listed:
			group.remove(row)
		self._listed = []
		count = dict.fromkeys(LEVELS, 0)
		for finding in findings:
			level = finding["level"] if finding["level"] in LEVELS else "warn"
			count[level] += 1
			row = Adw.ActionRow(title=finding["detail"], subtitle=finding["check"], use_markup=False)
			row.add_prefix(Gtk.Image(icon_name=LEVELS[level][1], css_classes=[LEVELS[level][2]]))
			self.groups[level].add(row)
			self._listed.append((self.groups[level], row))
		for level, group in self.groups.items():
			group.set_visible(bool(count[level]))
		found = count["error"] + count["warn"]
		if found:
			parts = [f"{count[level]} {word}{'s' if count[level] != 1 else ''}" for level, word in (("error", "problem"), ("warn", "warning")) if count[level]]
			self.summary.set_description(" and ".join(parts) + " found. The same list as `lacquer doctor`.")
		else:
			self.summary.set_description("Nothing wrong found. The same list as `lacquer doctor`.")
		self.app.retitle(self, f"{TITLE} ({found})" if found else TITLE)
