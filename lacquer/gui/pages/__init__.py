"""Pages that need more than the generic SectionPage. One file per page.

A file exposes `Page` and either
  SECTION = "<section name>"   replaces that section's generic page
                               (Page is a SectionPage subclass), or
  SECTION = None, TITLE, ORDER an extra page: Page(app), with refresh()
                               called after every keep.
Adding a page means adding one file here; nothing else changes.
"""
import importlib
import pkgutil


def discover():
	"""Returns ({section name: Page class}, [extra page modules by ORDER])."""
	custom, extra = {}, []
	for info in pkgutil.iter_modules(__path__):
		module = importlib.import_module(f"{__name__}.{info.name}")
		if module.SECTION:
			custom[module.SECTION] = module.Page
		else:
			extra.append(module)
	return custom, sorted(extra, key=lambda m: m.ORDER)
