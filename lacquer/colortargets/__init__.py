"""Where the `lacquer` palette engine writes colors. One file per target.

A target turns the palette into places (see places.py): files it writes and
single settings that point programs at them. Adding a target means adding one
file here that exposes TARGET; the palette module needs no change.
"""
import importlib
import pkgutil
from dataclasses import dataclass, field


@dataclass
class Look:
	"""What a target gets to work with."""
	mode: str  # "dark" or "light": the one in use now
	seed: str
	palette: dict  # {"dark": {name: "#rrggbb"}, "light": {...}}, names as in palettegen.NAMES
	templates: tuple = ()  # Noctalia template ids that Lacquer's targets replace
	# What each target found before Lacquer took over, kept until the engine
	# is switched away again. A target writes under its own name.
	handover: dict = field(default_factory=dict)

	@property
	def colors(self):
		return self.palette[self.mode]


class Target:
	name = ""
	# Noctalia's built-in templates that write the same thing. They are turned
	# off while this target is in use: one writer per target.
	templates = ()

	def detect(self) -> bool:
		"""Is the program this target colors here?"""
		return True

	def render(self, look):
		"""Returns {place: value} that puts the palette in use."""
		return {}

	def release(self, handover):
		"""Returns {place: value} that hands the target back when the engine
		is switched away from `lacquer`."""
		return {}

	def live(self, look):
		"""Called after the places are written (look is None after a release),
		for anything a running program needs to notice the change."""

	def reverted(self):
		"""Called after a preview's places were put back."""

	def keep(self, active):
		"""Called on keep; active = the engine is `lacquer`. Returns warnings."""
		return []


def discover():
	"""Every target whose program is here, in name order."""
	found = []
	for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
		target = importlib.import_module(f"{__name__}.{info.name}").TARGET
		if target.detect():
			found.append(target)
	return found
