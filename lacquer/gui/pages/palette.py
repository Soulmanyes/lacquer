"""Palette page: engine and seed on top, the palette as swatches, Noctalia's
own theme keys behind "Show all settings".
"""
import os

from gi.repository import Gtk

from .. import labels
from ..rows import CENTER, Marks, Row, pick_image
from ..sectionpage import SectionPage

SECTION = "palette"
TOP = ("engine", "mode", "seed", "base")
MODES = ("dark", "light")


class SeedRow(Row):
	"""`palette.seed`: a color, the wallpaper, or an image file."""

	def build(self, title, text):
		self.button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), valign=CENTER)
		self.button.connect("notify::rgba", lambda *_: self.changed(labels.to_hex(self.button.get_rgba())))
		self.source = Gtk.Label(valign=CENTER, css_classes=["dim-label"])
		wallpaper = Gtk.Button(label="Wallpaper", valign=CENTER, tooltip_text="Take the color from the wallpaper")
		wallpaper.connect("clicked", lambda *_: self._send("wallpaper"))
		image = Gtk.Button(icon_name="document-open-symbolic", valign=CENTER, tooltip_text="Take the color from an image")
		row = self.action_row(title, text, self.source, self.button, wallpaper, image)
		image.connect("clicked", lambda *_: pick_image(row, self._send))
		return row

	def _send(self, value):
		self.show(value)
		self.changed(value)

	def show(self, value):
		value = value or ""
		is_color = value.startswith("#")
		self.source.set_label("" if is_color else os.path.basename(value))
		if is_color:
			was, self.loading = self.loading, True
			self.button.set_rgba(labels.to_rgba(value))
			self.loading = was


class Swatch(Marks):
	"""One palette color: a color button with its name under it."""

	def __init__(self, key, name, app):
		self.key, self.app = key, app
		self.loading = False
		self.make_marks(app, key)
		self.button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), halign=CENTER)
		self.button.connect("notify::rgba", self._changed)
		label = Gtk.Label(label=name, css_classes=["caption"], ellipsize=3, max_width_chars=16)
		foot = Gtk.Box(spacing=2, halign=CENTER)
		foot.append(self.mark)
		foot.append(self.reset)
		self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["lacquer-swatch"])
		for child in (self.button, label, foot):
			self.widget.append(child)

	def _changed(self, *_):
		if not self.loading:
			self.app.change(self.key, labels.to_hex(self.button.get_rgba()))

	def load(self, entry):
		self.loading = True
		self.button.set_rgba(labels.to_rgba(entry.get("value")))
		self.loading = False
		self.set_preview(bool(entry.get("preview")))
		self.reset.set_visible("saved" in entry)


class Page(SectionPage):
	def build(self):
		prefix = self.name + "."
		self._groups_with_swatches = 0
		top = self.group("Colors from")
		for name in TOP:
			key = prefix + name
			if key in self.schema:
				row = SeedRow(key, self.schema[key], "Seed", self.app) if name == "seed" else None
				self.add_row(top, key, row=row)

		used = {prefix + name for name in TOP}
		for mode in MODES:
			keys = [k for k in self.schema if k.startswith(f"{prefix}{mode}.")]
			used.update(keys)
			terminal = [k for k in keys if ".terminal." in k]
			self._swatches(f"{mode.capitalize()} colors", [k for k in keys if k not in terminal])
			self._swatches(f"{mode.capitalize()} terminal colors", terminal)

		for key in self.schema:
			if key not in used:
				self.add_row(self.group("Noctalia theme"), key, always=False)

	def _swatches(self, title, keys):
		if not keys:
			return
		group = self.group(title, "" if self._groups_with_swatches else "Lacquer engine. A color picked by hand stays until its undo arrow is clicked.")
		self._groups_with_swatches += 1
		flow = Gtk.FlowBox(
			selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, min_children_per_line=3,
			max_children_per_line=8, row_spacing=10, column_spacing=6, css_classes=["card", "lacquer-swatches"],
		)
		for key in keys:
			swatch = Swatch(key, labels.title(key), self.app)
			self.rows[key] = swatch
			flow.append(swatch.widget)
		self.add_item(group, flow)
