"""The GTK4/libadwaita window. A thin front-end: everything it does goes
through `lacquer.core`, the same calls the CLI makes.

  rows.py         one row class per value type (and per Key hint)
  sectionpage.py  the page every section gets, built from its schema
  pages/          one file per page that needs more than that
  window.py       the window: preview queue, Keep/Revert bar, timer
  worker.py       the one thread core calls run on
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from .window import run  # after the versions are set

__all__ = ["run"]
