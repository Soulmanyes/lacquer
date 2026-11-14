"""Themes page: saved themes and the automatic snapshots. Both are shown as a
preview first, like any other change. A theme can be deleted here (after a
question, there is no undo); snapshots can not.
"""
from gi.repository import Adw, Gtk

from ... import core
from ..rows import CENTER

SECTION = None
TITLE = "Themes"
ORDER = 10
SNAPSHOTS_SHOWN = 20


def _when(name):
	"""`20261114-093012` to `2026-11-14 09:30:12`; other names stay."""
	if len(name) == 15 and name[8] == "-" and name.replace("-", "").isdigit():
		return f"{name[:4]}-{name[4:6]}-{name[6:8]} {name[9:11]}:{name[11:13]}:{name[13:]}"
	return name


class Page(Adw.PreferencesPage):
	def __init__(self, app):
		super().__init__()
		self.app = app
		self._listed = []  # (group, row) of the lists, replaced on refresh

		save = Adw.PreferencesGroup(title="Save", description="Stores the kept look as a theme. A preview is not part of it.")
		self.name = Gtk.Entry(valign=CENTER, width_chars=22, placeholder_text="Theme name")
		self.name.connect("activate", self._save)
		button = Gtk.Button(label="Save", valign=CENTER, css_classes=["suggested-action"])
		button.connect("clicked", self._save)
		row = Adw.ActionRow(title="Save the kept look as")
		row.add_suffix(self.name)
		row.add_suffix(button)
		save.add(row)
		self.add(save)

		self.themes = Adw.PreferencesGroup(title="Themes", description="A section in a theme replaces that whole section.")
		self.snapshots = Adw.PreferencesGroup(title="Snapshots", description="A copy of the look from every keep, newest first.")
		self.add(self.themes)
		self.add(self.snapshots)
		self.refresh()

	def refresh(self):
		self.app.run(lambda: (core.theme_list()["themes"], core.snapshot_list()["snapshots"]), then=self._fill)

	def _fill(self, lists):
		themes, snapshots = lists
		for group, row in self._listed:
			group.remove(row)
		self._listed = []
		for name in themes:
			self._list(self.themes, name, core.apply, name, delete=True)
		if not themes:
			self._list(self.themes, "No themes saved yet")
		for name in sorted(snapshots, reverse=True)[:SNAPSHOTS_SHOWN]:
			self._list(self.snapshots, _when(name), core.snapshot_restore, name)

	def _list(self, group, title, action=None, name=None, delete=False):
		row = Adw.ActionRow(title=title, use_markup=False)
		if action:
			button = Gtk.Button(label="Preview", valign=CENTER)
			button.connect("clicked", lambda *_: self.app.run(action, name, then=self.app.previewed))
			row.add_suffix(button)
		if delete:
			button = Gtk.Button(icon_name="user-trash-symbolic", valign=CENTER, css_classes=["flat"], tooltip_text="Delete this theme")
			button.connect("clicked", lambda *_: self.ask_delete(name))
			row.add_suffix(button)
		group.add(row)
		self._listed.append((group, row))

	def ask_delete(self, name):
		"""Asks first: a deleted theme is gone. Returns the dialog."""
		dialog = Adw.AlertDialog(heading=f"Delete theme “{name}”?", body="The file is removed for good. The kept look and the snapshots stay.")
		dialog.add_response("cancel", "Cancel")
		dialog.add_response("delete", "Delete")
		dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
		dialog.set_close_response("cancel")
		dialog.connect("response", lambda _dialog, response: response == "delete" and self.delete(name))
		dialog.present(self.app)
		return dialog

	def delete(self, name):
		self.app.run(core.theme_delete, name, then=lambda _result: self._deleted(name))

	def _deleted(self, name):
		self.app.toast(f"Deleted theme “{name}”")
		self.refresh()

	def _save(self, *_):
		name = self.name.get_text().strip()
		if name:
			self.app.run(core.theme_save, name, then=self._saved)

	def _saved(self, _result):
		self.app.toast(f"Saved theme “{self.name.get_text().strip()}”")
		self.name.set_text("")
		self.refresh()
