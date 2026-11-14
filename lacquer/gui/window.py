"""The window: a page per section, the preview queue and the Keep/Revert bar.

Pages talk to the window through seven calls: change(key, value),
unset(key), run(fn, *args, then=), previewed(result), refresh_pages(),
toast(text) and retitle(page, title).
"""
import os
import sys

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .. import core, paths
from . import pages
from .search import Search
from .sectionpage import SectionPage
from .thememenu import ThemeMenu
from .updatemenu import UpdateMenu
from .worker import Worker

# A test launch gets its own id, so it never raises the owner's open window.
APP_ID = os.environ.get("LACQUER_APP_ID") or paths.APP_ID
SEND_DELAY_MS = 250  # a dragged slider sends its last value, not every step
GO_ACTION = "go"
CSS = """
list.boxed-list, .card { border: 1px solid alpha(currentColor, 0.25); }
.lacquer-mark {
	background: alpha(@accent_bg_color, 0.3);
	border: 1px solid @accent_bg_color;
	border-radius: 999px;
	padding: 1px 8px;
	font-size: smaller;
}
.lacquer-swatches { padding: 12px; }
.lacquer-swatch { padding: 4px; }
.lacquer-bar {
	background: alpha(@accent_bg_color, 0.18);
	border-top: 2px solid @accent_bg_color;
	padding: 8px 12px;
}
.lacquer-bar .timer { color: @warning_color; font-weight: bold; }
row.lacquer-found { background: alpha(@accent_bg_color, 0.35); outline: 2px solid @accent_bg_color; outline-offset: -2px; }
"""


class Window(Adw.ApplicationWindow):
	def __init__(self, app, target=None):
		super().__init__(application=app, title="Lacquer", default_width=980, default_height=760)
		self.target = target  # page or key to open on, once the pages exist
		self.built = False
		self.worker = Worker()
		self.section_pages = {}
		self.extra_pages = []
		self.pending = {}  # changes waiting to be sent: {key: value}
		self.sending = False
		self.send_timer = 0
		self.preview_keys = set()
		self.closing = False

		self.stack = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
		self.stack.add_named(Adw.StatusPage(title="Reading the current look…"), "loading")
		sidebar = Gtk.StackSidebar(stack=self.stack, width_request=190)
		body = Gtk.Box()
		body.append(sidebar)
		body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
		body.append(self.stack)
		self.toasts = Adw.ToastOverlay(child=body)

		view = Adw.ToolbarView(content=self.toasts)
		header = Adw.HeaderBar()
		header.pack_start(ThemeMenu(self))
		self.search = Search(self)
		header.pack_end(self.search)
		updates = UpdateMenu(self)
		header.pack_end(updates)
		view.add_top_bar(header)
		view.add_top_bar(updates.banner)
		view.add_bottom_bar(self._preview_bar())
		self.set_content(view)

		self.connect("close-request", self._close_request)
		self.worker.call(lambda: (core.sections(), core.schema(), core.get()), done=self._build)

	# -- building --

	def _preview_bar(self):
		self.bar_text = Gtk.Label(xalign=0, hexpand=True)
		self.bar_timer = Gtk.Label(css_classes=["timer"])
		revert = Gtk.Button(label="Revert")
		revert.connect("clicked", lambda *_: self.revert())
		keep = Gtk.Button(label="Keep", css_classes=["suggested-action"])
		keep.connect("clicked", lambda *_: self.keep())
		box = Gtk.Box(spacing=12, css_classes=["lacquer-bar"])
		for widget in (self.bar_text, self.bar_timer, revert, keep):
			box.append(widget)
		self.bar = Gtk.Revealer(child=box, reveal_child=False)
		return self.bar

	def _build(self, result, error):
		if error:
			self.stack.get_child_by_name("loading").set_description(error)
			return
		sections, schema, values = result
		custom, extra = pages.discover()
		for name, info in sections.items():
			part = {k: v for k, v in schema.items() if k.startswith(name + ".")}
			page = custom.get(name, SectionPage)(self, name, info, part)
			self.section_pages[name] = page
			self.stack.add_titled(page, name, info["title"])
		for module in extra:
			page = module.Page(self)
			self.extra_pages.append(page)
			self.stack.add_titled(page, module.__name__.rsplit(".", 1)[-1], module.TITLE)
		self.stack.remove(self.stack.get_child_by_name("loading"))
		self.stack.set_visible_child_name(next(iter(self.section_pages), self.stack.get_visible_child_name()))
		self._show(values)
		self.search.apply()
		self.built = True
		self.go_to(self.target)
		self._poll()
		GLib.timeout_add_seconds(1, self._poll)

	def go_to(self, target):
		"""Opens a page by name (`windows`), or a setting by its key
		(`windows.decoration.rounding`): its page, scrolled to its row."""
		if not self.built:
			self.target = target
			return
		name = (target or "").split(".")[0]
		if not name or self.stack.get_child_by_name(name) is None:
			return
		page = self.section_pages.get(name)
		if "." in target and page is not None:
			# A running search could hide the page or the row.
			self.search.set_text("")
			self.search.apply()
			page.reveal(target)
		self.stack.set_visible_child_name(name)

	# -- for pages --

	def toast(self, text):
		self.toasts.add_toast(Adw.Toast(title=text, timeout=6))

	def retitle(self, page, title):
		"""Changes a page's name in the sidebar (to show a count, say)."""
		self.stack.get_page(page).set_title(title)

	def change(self, key, value):
		"""A setting was changed by hand: preview it (after a short pause, so
		a run of changes is sent once)."""
		self.pending[key] = value
		if self.send_timer:
			GLib.source_remove(self.send_timer)
		self.send_timer = GLib.timeout_add(SEND_DELAY_MS, self._send)

	def unset(self, key):
		self.run(core.unset, [key], then=lambda _result: self.reload())

	def run(self, fn, *args, then=None):
		"""Runs a core call off the GTK thread. An error is shown and the
		pages are read again; otherwise then(result) runs."""
		def done(result, error):
			if error:
				self.toast(error)
				self.reload()
			elif then:
				then(result)
		self.worker.call(fn, *args, done=done)

	def refresh_pages(self):
		"""After something the extra pages list (themes, snapshots) changed."""
		for page in self.extra_pages:
			page.refresh()

	def previewed(self, result):
		"""After any core call that started or changed a preview."""
		changed, unchanged = list(result.get("previewed", {})), result.get("unchanged", [])
		for key in changed:
			self._row_preview(key, True)
		for key in unchanged:
			self._row_preview(key, False)
		if result.get("risky"):
			reasons = "; ".join(f"{k}: {why}" for k, why in result["risky"].items())
			self.toast(f"Risky ({reasons}). Reverts in {result['auto_revert_in']} s unless you keep it.")
		if result.get("skipped_sections"):
			self.toast("Not usable here, skipped: " + ", ".join(result["skipped_sections"]))
		# A change can move other values too (one wallpaper for all monitors,
		# a seed for the whole palette), so read the touched sections again.
		self.reload({key.split(".", 1)[0] for key in changed + unchanged})
		self._poll()

	# -- preview queue --

	def _send(self):
		self.send_timer = 0
		if self.sending or not self.pending:
			return False
		pairs, self.pending = list(self.pending.items()), {}
		self.sending = True
		# A value put back to what it was before the preview is no change.
		self.worker.call(lambda: core.set_values(pairs, drop_unchanged=True), done=self._sent)
		return False

	def _sent(self, result, error):
		self.sending = False
		if error:
			# core reverted the whole preview (or refused the value).
			self.pending.clear()
			self.toast(error)
			self.reload()
			self._poll()
			return
		self.previewed(result)
		self._send()

	# -- keep / revert --

	def keep(self, then=None):
		def kept(result):
			warnings = result.get("warnings", [])
			if warnings:
				dialog = Adw.AlertDialog(heading="Kept, with warnings", body="\n\n".join(warnings))
				dialog.add_response("ok", "OK")
				dialog.present(self)
			elif result.get("kept"):
				self.toast("Kept")
			self._after_end(then)
		# A number typed just before the click is still waiting: it goes first.
		if self.send_timer:
			GLib.source_remove(self.send_timer)
			self._send()
		self.run(core.keep, then=kept)

	def revert(self, then=None):
		self.pending.clear()
		self.run(core.revert, then=lambda _result: self._after_end(then))

	def _after_end(self, then):
		if then:
			then()
			return
		self.reload()
		self.refresh_pages()
		self._poll()

	# -- reading --

	def reload(self, sections=None):
		"""Reads live values again (all sections, or the named ones)."""
		names = list(self.section_pages) if sections is None else [s for s in sections if s in self.section_pages]

		def read():
			values = {}
			for name in names:
				values.update(core.get(name + "."))
			return values

		def done(values, error):
			if error:
				self.toast(error)
			# Newer changes are on their way: their own reload follows.
			elif not self.pending and not self.sending:
				self._show(values)
		self.worker.call(read, done=done)

	def _show(self, values):
		for page in self.section_pages.values():
			page.load(values)

	def _row_preview(self, key, flag):
		page = self.section_pages.get(key.split(".", 1)[0])
		if page and key in page.rows:
			page.rows[key].set_preview(flag)

	def _poll(self):
		"""Once a second: the bar, the timer, and previews that ended or
		started outside the window (timer, revert key, CLI)."""
		status = core.status()
		keys, left = set(status["preview"]), status["auto_revert_in"]
		count = len(keys)
		self.bar_text.set_label(f"{count} change{'s' if count != 1 else ''} in preview, not kept yet")
		self.bar_timer.set_label(f"Reverts in {left} s" if left is not None else "")
		self.bar.set_reveal_child(bool(keys))
		if keys != self.preview_keys:
			idle = not self.worker.busy and not self.pending and not self.sending
			self.preview_keys = keys
			if idle:
				self.reload()
		return True

	# -- closing --

	def _close_request(self, *_):
		if self.closing or not (self.preview_keys or self.pending or self.sending):
			return False
		dialog = Adw.AlertDialog(heading="A preview is still running", body="Keep the previewed look, or revert it?")
		dialog.add_response("cancel", "Cancel")
		dialog.add_response("revert", "Revert")
		dialog.add_response("keep", "Keep")
		dialog.set_response_appearance("keep", Adw.ResponseAppearance.SUGGESTED)
		dialog.set_close_response("cancel")
		dialog.connect("response", self._close_answer)
		dialog.present(self)
		return True

	def _close_answer(self, _dialog, response):
		if response == "cancel":
			return
		self.closing = True
		(self.keep if response == "keep" else self.revert)(then=self.close)


class App(Adw.Application):
	def __init__(self, target=None):
		super().__init__(application_id=APP_ID)
		self.window = None
		self.target = target
		# What a second `lacquer gui <target>` sends to the open window.
		go = Gio.SimpleAction.new(GO_ACTION, GLib.VariantType.new("s"))
		go.connect("activate", self._go)
		self.add_action(go)

	def _go(self, _action, target):
		self.activate()
		self.window.go_to(target.get_string())

	def do_activate(self):
		if self.window is None:
			provider = Gtk.CssProvider()
			provider.load_from_string(CSS)
			Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
			self.window = Window(self, self.target)
		self.window.present()

	def do_shutdown(self):
		if self.window is not None:
			self.window.worker.stop()
		Adw.Application.do_shutdown(self)


def run(target=None):
	"""Opens the window, on a section's page (`windows`) or at one setting
	(`windows.decoration.rounding`) if given. A window that is already open
	goes there instead."""
	app = App(target)
	app.register(None)
	if app.get_is_remote():
		app.activate_action(GO_ACTION, GLib.Variant("s", target or ""))
		return 0
	return app.run([sys.argv[0]])
