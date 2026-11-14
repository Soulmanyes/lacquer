"""One row class per value type. Pages call make() and never look at types.

A new value type is one class here plus an entry in BY_TYPE; a new picker for
a `Key.hint` is one class plus an entry in BY_HINT.

Every row has: `widget` (what goes on the page), `load(entry)` with an entry
of `core.get()`, and `set_preview(flag)`. A change the user makes goes to
`app.change(key, value)`; the undo arrow calls `app.unset(key)`.
"""
from gi.repository import Adw, Gio, GLib, Gtk, Pango

from . import labels

CENTER = Gtk.Align.CENTER
SIDES = ("top", "right", "bottom", "left")
MAX_GRADIENT_COLORS = 10


def pick_image(parent, done):
	"""Opens a file dialog for one image and calls done(path)."""
	images = Gtk.FileFilter()
	images.set_name("Images")
	images.add_mime_type("image/*")
	filters = Gio.ListStore.new(Gtk.FileFilter)
	filters.append(images)
	dialog = Gtk.FileDialog(title="Pick an image", filters=filters)

	def finished(dialog, result):
		try:
			done(dialog.open_finish(result).get_path())
		except GLib.Error:
			pass  # closed without picking

	dialog.open(parent.get_root(), None, finished)


def spin(low, high, step=1, digits=0):
	"""A typeable number box for use inside a row."""
	button = Gtk.SpinButton.new_with_range(low, high, step)
	button.set_digits(digits)
	button.set_numeric(True)
	button.set_valign(CENTER)
	return button


class Marks:
	"""The two things every setting shows: a `preview` pill while its value is
	live but not kept, and an undo arrow while Lacquer keeps it."""

	def make_marks(self, app, key):
		self.mark = Gtk.Label(label="preview", valign=CENTER, visible=False, css_classes=["lacquer-mark"])
		self.reset = Gtk.Button(
			icon_name="edit-undo-symbolic", valign=CENTER, visible=False, css_classes=["flat"],
			tooltip_text="Kept by Lacquer. Click to stop keeping it and hand it back to the other config.",
		)
		self.reset.connect("clicked", lambda *_: app.unset(key))

	def set_preview(self, flag):
		self.mark.set_visible(flag)


class Row(Marks):
	"""Subclasses fill in build() (returns the Adw row) and show(value), and
	call self.changed(value) when the user changes it."""

	def __init__(self, key, spec, title, app):
		self.key, self.spec, self.app = key, spec, app
		self.loading = False
		self.widget = self.build(title, spec.get("description", ""))
		self.make_marks(app, key)
		self.widget.add_suffix(self.mark)
		self.widget.add_suffix(self.reset)

	def build(self, title, text):
		raise NotImplementedError

	def show(self, value):
		raise NotImplementedError

	def load(self, entry):
		self.loading = True
		try:
			self.show(entry.get("value"))
		finally:
			self.loading = False
		self.set_preview(bool(entry.get("preview")))
		self.reset.set_visible("saved" in entry)

	def changed(self, value):
		if not self.loading:
			self.app.change(self.key, value)

	def action_row(self, title, text, *suffixes):
		row = Adw.ActionRow(title=title, subtitle=text, use_markup=False)
		for widget in suffixes:
			row.add_suffix(widget)
		return row


class BoolRow(Row):
	def build(self, title, text):
		row = Adw.SwitchRow(title=title, subtitle=text, use_markup=False)
		row.connect("notify::active", lambda *_: self.changed(row.get_active()))
		return row

	def show(self, value):
		self.widget.set_active(bool(value))


class NumberRow(Row):
	"""int and float. Keys without a range (Noctalia's) get a wide one:
	Noctalia checks the value when it is written."""

	def build(self, title, text):
		spec = self.spec
		self.whole = spec["type"] == "int"
		low, high = spec.get("min"), spec.get("max")
		span = high - low if low is not None and high is not None else None
		if self.whole:
			step, digits = 1, 0
		elif span is None:
			step, digits = 0.05, 2
		elif span <= 2:
			# Two decimals, or as many as the default has (blur noise: 0.0117).
			shown = repr(spec.get("default", 0)).partition(".")[2]
			step, digits = 0.01, min(4, max(2, len(shown)))
		elif span <= 50:
			step, digits = 0.1, 2
		else:
			step, digits = 1, 1
		row = Adw.SpinRow.new_with_range(-100000 if low is None else low, 100000 if high is None else high, step)
		row.set_title(title)
		row.set_subtitle(text)
		row.set_use_markup(False)
		row.set_digits(digits)
		row.set_numeric(True)
		row.connect("notify::value", self._changed)
		return row

	def _changed(self, *_):
		value = self.widget.get_value()
		self.changed(round(value) if self.whole else round(value, 4))

	def show(self, value):
		value = value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
		# A live value outside the described range is shown as it is.
		adjustment = self.widget.get_adjustment()
		adjustment.set_lower(min(adjustment.get_lower(), value))
		adjustment.set_upper(max(adjustment.get_upper(), value))
		self.widget.set_value(value)


class ChoiceRow(Row):
	"""Any key with `choices` ({shown name: stored value}). A live value that
	is not among them (a theme that is not installed) is listed too."""

	def build(self, title, text):
		choices = self.spec["choices"]
		self.names = sorted(choices, key=lambda n: choices[n]) if self.spec["type"] == "int" else list(choices)
		self.values = [choices[n] for n in self.names]
		self.model = Gtk.StringList.new(self.names)
		row = Adw.ComboRow(title=title, subtitle=text, use_markup=False, model=self.model)
		row.connect("notify::selected", self._changed)
		return row

	def _changed(self, *_):
		index = self.widget.get_selected()
		if 0 <= index < len(self.values):
			self.changed(self.values[index])

	def show(self, value):
		if value not in self.values:
			self.values.append(value)
			self.model.append(str(value))
		self.widget.set_selected(self.values.index(value))


class TextRow(Row):
	"""Free text: sent on Enter or when the box loses focus."""

	def build(self, title, text):
		self.shown = ""
		self.entry = Gtk.Entry(valign=CENTER, width_chars=26)
		self.entry.connect("activate", self.commit)
		self.focus = Gtk.EventControllerFocus()
		self.focus.connect("leave", self.commit)
		self.entry.add_controller(self.focus)
		return self.action_row(title, text, self.entry)

	def commit(self, *_):
		text = self.entry.get_text()
		if text != self.shown:
			self.shown = text
			self.changed(text)

	def show(self, value):
		typing = self.focus.contains_focus() and self.entry.get_text() != self.shown
		self.shown = "" if value is None else str(value)
		# Text being typed is not replaced by a reload another change caused.
		if not typing:
			self.entry.set_text(self.shown)


class ImageRow(TextRow):
	"""Hint "image": the text box plus a file dialog."""

	def build(self, title, text):
		row = super().build(title, text)
		button = Gtk.Button(icon_name="document-open-symbolic", valign=CENTER, tooltip_text="Pick an image")
		button.connect("clicked", lambda *_: pick_image(row, self._picked))
		row.add_suffix(button)
		return row

	def _picked(self, path):
		self.entry.set_text(path)
		self.commit()


class FontRow(Row):
	"""Hint "font": family with an optional style; the size is its own key."""

	def build(self, title, text):
		self.button = Gtk.FontDialogButton(dialog=Gtk.FontDialog(), level=Gtk.FontLevel.FACE, valign=CENTER)
		self.button.connect("notify::font-desc", self._changed)
		return self.action_row(title, text, self.button)

	def _changed(self, *_):
		desc = self.button.get_font_desc()
		if desc is not None:
			desc = desc.copy()
			desc.unset_fields(Pango.FontMask.SIZE)
			self.changed(desc.to_string())

	def show(self, value):
		self.button.set_font_desc(Pango.FontDescription.from_string(value or "Sans"))


class ColorRow(Row):
	def build(self, title, text):
		self.button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=True), valign=CENTER)
		self.button.connect("notify::rgba", lambda *_: self.changed(labels.to_hex(self.button.get_rgba())))
		return self.action_row(title, text, self.button)

	def show(self, value):
		self.button.set_rgba(labels.to_rgba(value))


class GradientRow(Row):
	"""One color, or several with an angle."""

	def build(self, title, text):
		self.colors, self.angle = ["#000000"], 0
		self.box = Gtk.Box(spacing=6, valign=CENTER)
		return self.action_row(title, text, self.box)

	def show(self, value):
		if isinstance(value, dict):
			self.colors, self.angle = list(value.get("colors") or ["#000000"]), value.get("angle", 0)
		else:
			self.colors, self.angle = [value or "#000000"], 0
		self._rebuild()

	def _rebuild(self):
		was, self.loading = self.loading, True
		while (child := self.box.get_first_child()) is not None:
			self.box.remove(child)
		for index, color in enumerate(self.colors):
			button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=True), rgba=labels.to_rgba(color))
			button.connect("notify::rgba", self._recolor, index)
			self.box.append(button)
		if len(self.colors) > 1:
			self.box.append(self._button("list-remove-symbolic", "Remove the last color", self._remove))
		if len(self.colors) < MAX_GRADIENT_COLORS:
			self.box.append(self._button("list-add-symbolic", "Add a color (makes a gradient)", self._add))
		if len(self.colors) > 1:
			angle = spin(0, 360)
			angle.set_value(self.angle)
			angle.set_tooltip_text("Gradient angle in degrees")
			angle.connect("value-changed", self._turn)
			self.box.append(angle)
		self.loading = was

	def _button(self, icon, tip, action):
		button = Gtk.Button(icon_name=icon, tooltip_text=tip, css_classes=["flat"])
		# Idle: the handler rebuilds the box the button sits in.
		button.connect("clicked", lambda *_: GLib.idle_add(action))
		return button

	def _send(self):
		self.changed(self.colors[0] if len(self.colors) == 1 else {"colors": list(self.colors), "angle": self.angle})

	def _recolor(self, button, _pspec, index):
		if not self.loading:
			self.colors[index] = labels.to_hex(button.get_rgba())
			self._send()

	def _turn(self, button):
		if not self.loading:
			self.angle = button.get_value_as_int()
			self._send()

	def _add(self):
		self.colors.append(self.colors[-1])
		self._rebuild()
		self._send()

	def _remove(self):
		self.colors.pop()
		if len(self.colors) == 1:
			self.angle = 0
		self._rebuild()
		self._send()


class GapsRow(Row):
	"""One number for all sides; open the row for one number per side."""

	def build(self, title, text):
		row = Adw.ExpanderRow(title=title, subtitle=text, use_markup=False)
		self.all = spin(0, 500)
		self.all.set_tooltip_text("All sides")
		self.all.connect("value-changed", self._all_changed)
		row.add_suffix(self.all)
		self.sides = {}
		for side in SIDES:
			side_row = Adw.SpinRow.new_with_range(0, 500, 1)
			side_row.set_title(side.capitalize())
			side_row.set_numeric(True)
			side_row.connect("notify::value", self._side_changed)
			row.add_row(side_row)
			self.sides[side] = side_row
		return row

	def _fill(self, values):
		was, self.loading = self.loading, True
		for side, row in self.sides.items():
			row.set_value(values[side])
		self.all.set_value(values["top"])
		self.loading = was

	def _all_changed(self, *_):
		if not self.loading:
			value = self.all.get_value_as_int()
			self._fill(dict.fromkeys(SIDES, value))
			self.changed(value)

	def _side_changed(self, *_):
		if not self.loading:
			self.changed({side: int(row.get_value()) for side, row in self.sides.items()})

	def show(self, value):
		if isinstance(value, dict):
			self._fill({side: value.get(side, 0) for side in SIDES})
		else:
			self._fill(dict.fromkeys(SIDES, value or 0))


class Vec2Row(Row):
	def build(self, title, text):
		self.x, self.y = spin(-1000, 1000, 1, 1), spin(-1000, 1000, 1, 1)
		for button, tip in ((self.x, "x"), (self.y, "y")):
			button.set_tooltip_text(tip)
			button.connect("value-changed", self._changed)
		return self.action_row(title, text, self.x, self.y)

	def _changed(self, *_):
		pair = [round(self.x.get_value(), 1), round(self.y.get_value(), 1)]
		self.changed([int(v) if v == int(v) else v for v in pair])

	def show(self, value):
		x, y = value if isinstance(value, list) and len(value) == 2 else (0, 0)
		self.x.set_value(x)
		self.y.set_value(y)


BY_TYPE = {
	"bool": BoolRow, "int": NumberRow, "float": NumberRow, "str": TextRow,
	"color": ColorRow, "gradient": GradientRow, "gaps": GapsRow, "vec2": Vec2Row,
}
BY_HINT = {"image": ImageRow, "font": FontRow}


def make(key, spec, app, title=None):
	"""The row for one key of `core.schema()`."""
	cls = BY_HINT.get(spec.get("hint")) or (ChoiceRow if spec.get("choices") else BY_TYPE.get(spec["type"], TextRow))
	return cls(key, spec, title or labels.title(key), app)
