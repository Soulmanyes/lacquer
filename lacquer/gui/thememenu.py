"""The Themes button in the header: save and load a theme from any page.

The Themes page has the same, plus the snapshots.
"""
from gi.repository import Gtk

from .. import core


class ThemeMenu(Gtk.MenuButton):
	def __init__(self, app):
		super().__init__(label="Themes", tooltip_text="Save the look as a theme, or load one")
		self.app = app
		self.name = Gtk.Entry(placeholder_text="Theme name", hexpand=True)
		self.name.connect("activate", self._save)
		save = Gtk.Button(label="Save", css_classes=["suggested-action"], tooltip_text="Stores the kept look. A preview is not part of it.")
		save.connect("clicked", self._save)
		top = Gtk.Box(spacing=6)
		top.append(self.name)
		top.append(save)
		self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
		scroll = Gtk.ScrolledWindow(child=self.list, hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True, max_content_height=360)
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, width_request=300)
		for margin in ("top", "bottom", "start", "end"):
			getattr(box, f"set_margin_{margin}")(8)
		box.append(top)
		box.append(Gtk.Separator())
		box.append(scroll)
		self.popover = Gtk.Popover(child=box)
		self.popover.connect("show", lambda *_: self.refresh())
		self.set_popover(self.popover)

	def refresh(self):
		self.app.run(lambda: core.theme_list()["themes"], then=self._fill)

	def _fill(self, themes):
		while (child := self.list.get_first_child()) is not None:
			self.list.remove(child)
		if not themes:
			self.list.append(Gtk.Label(label="No themes saved yet", css_classes=["dim-label"], margin_top=6, margin_bottom=6))
		for name in themes:
			button = Gtk.Button(css_classes=["flat"], tooltip_text="Shows the theme as a preview: Keep or Revert it afterwards")
			button.set_child(Gtk.Label(label=name, xalign=0, ellipsize=3))
			button.connect("clicked", self._load, name)
			self.list.append(button)

	def _load(self, _button, name):
		self.popover.popdown()
		self.app.run(core.apply, name, then=self.app.previewed)

	def _save(self, *_):
		name = self.name.get_text().strip()
		if name:
			self.app.run(core.theme_save, name, then=lambda _result: self._saved(name))

	def _saved(self, name):
		self.app.toast(f"Saved theme “{name}”")
		self.name.set_text("")
		self.popover.popdown()
		self.app.refresh_pages()
