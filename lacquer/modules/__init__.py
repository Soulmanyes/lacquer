"""One file per area. Each file exposes MODULE, an instance of base.Module.

Adding an area means adding one file here; nothing else changes.
"""
import importlib
import pkgutil


def discover():
	"""Returns {section name: module} for every area that is installed."""
	found = {}
	for info in pkgutil.iter_modules(__path__):
		if info.name == "base":
			continue
		module = importlib.import_module(f"{__name__}.{info.name}").MODULE
		if module.detect():
			found[module.name] = module
	return found
