"""The header's version and updates button, the "new version" banner and the
"What's new" window shown once after an update.

GitHub calls run on their own threads, not the worker: they can take
seconds, and the worker is the queue for the desktop.
"""
import threading

from gi.repository import Adw, GLib, Gtk

from .. import __version__, core, updater

OFFLINE = (OSError, ValueError, KeyError)  # no network, GitHub down, an odd reply


class UpdateMenu(Gtk.MenuButton):
	"""Add the button to the header and `.banner` as a top bar."""

	def __init__(self, window):
		super().__init__(icon_name="open-menu-symbolic", tooltip_text="Version and updates")
		self.window = window
		self.updates = core.updates()
		self.latest = None  # a newer release, once the check finds one
		self.installing = False
		self.installed = False  # by this window or an earlier one; the next start runs it

		self.banner = Adw.Banner(button_label="Update")
		self.banner.connect("button-clicked", lambda *_: self.install())

		group = Adw.PreferencesGroup(title="Updates", width_request=380)
		self.row = Adw.ActionRow(title=f"Lacquer {__version__}")
		self.check_button = Gtk.Button(label="Check now", valign=Gtk.Align.CENTER)
		self.check_button.connect("clicked", lambda *_: self.check(force=True))
		self.row.add_suffix(self.check_button)
		group.add(self.row)
		auto = Adw.SwitchRow(
			title="Install updates automatically",
			subtitle="Off: Lacquer tells you about a new version and waits for you to press Update. Checks GitHub once a day",
			active=self.updates.auto)
		auto.connect("notify::active", self._toggle_auto)
		group.add(auto)
		box = Gtk.Box(margin_start=6, margin_end=6, margin_top=6, margin_bottom=6)
		box.append(group)
		self.set_popover(Gtk.Popover(child=box))

		self.check()
		self._whats_new()

	def _thread(self, work):
		threading.Thread(target=work, daemon=True).start()

	def _toggle_auto(self, row, _param):
		self.updates.auto = row.get_active()
		if self.updates.auto and self.latest and not self.updates.failed(self.latest):
			self.install()

	def _show_installed(self, tag):
		self.installed = True
		self.banner.set_revealed(False)
		self.row.set_subtitle(f"{tag} installed. Close and reopen Lacquer to use it")
		self.check_button.set_visible(False)

	def check(self, force=False):
		if self.installing or self.installed:
			return
		self.row.set_subtitle("Checking…")

		def work():
			try:
				latest, error = self.updates.check(force), None
			except OFFLINE as e:
				latest, error = None, e
			GLib.idle_add(found, latest, error)

		def found(latest, error):
			self.latest = latest
			if error:
				# Only a check you asked for complains; the daily one stays quiet.
				self.row.set_subtitle("Couldn't reach GitHub" if force else "")
			elif not latest:
				self.row.set_subtitle("Up to date")
			elif self.updates.installed(latest):
				self._show_installed(latest["tag"])
			else:
				self.row.set_subtitle(f"{latest['tag']} is available")
				if self.updates.auto and not self.updates.dev_checkout and not self.updates.failed(latest):
					self.install()
				else:
					self.banner.set_title(f"Lacquer {latest['tag']} is available")
					self.banner.set_revealed(True)
			return False

		self._thread(work)

	def install(self):
		if self.installing or self.installed or not self.latest:
			return
		if self.updates.dev_checkout:
			self.window.toast("Running from a git checkout: update it with git pull")
			return
		latest = self.latest
		self.installing = True
		self.banner.set_revealed(False)
		self.row.set_subtitle(f"Installing {latest['tag']}…")

		def work():
			try:
				self.updates.install(latest)
				error = None
			except (OSError, RuntimeError) as e:  # network, disk, installer
				error = str(e)
			GLib.idle_add(finished, error)

		def finished(error):
			self.installing = False
			if error:
				self.row.set_subtitle(f"Couldn't update: {error}")
				self.window.toast(f"Couldn't update: {error}")
			else:
				self._show_installed(latest["tag"])
				self.window.toast(f"Updated to {latest['tag']}. Close and reopen Lacquer to use it")
			return False

		self._thread(work)

	# -- what's new --

	def _whats_new(self):
		"""Shows the release notes once, on the first start after an update."""
		def work():
			try:
				releases = self.updates.whats_new()
			except OFFLINE:  # asked again on the next start
				return
			if releases:
				GLib.idle_add(self._show_notes, releases)

		self._thread(work)

	def _show_notes(self, releases):
		win = Gtk.Window(
			title="What's new in Lacquer", transient_for=self.window, modal=True,
			application=self.window.get_application(), default_width=520, default_height=440)
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
		box.append(Gtk.Label(label=f"Updated to {releases[0]['tag']}", xalign=0, css_classes=["title-2"]))
		body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
		for release in releases:
			if len(releases) > 1:
				body.append(Gtk.Label(label=release["tag"], xalign=0, css_classes=["heading"]))
			notes = Gtk.Label(xalign=0, wrap=True, use_markup=True)
			notes.set_markup(updater.notes_markup(release["notes"]))
			body.append(notes)
		box.append(Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER, child=body))
		buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
		if releases[0]["url"]:
			buttons.append(Gtk.LinkButton(uri=releases[0]["url"], label="Open on GitHub"))
		close = Gtk.Button(label="Close", css_classes=["suggested-action"])
		close.connect("clicked", lambda *_: win.close())
		buttons.append(close)
		box.append(buttons)
		win.set_child(box)
		win.set_default_widget(close)
		win.present()
		self.updates.mark_seen()
		return False
