"""The Noctalia shell, and through its templates the terminals and apps
Lacquer does not color itself.

Lacquer hands Noctalia the palette as a custom palette file and turns off the
Noctalia templates that Lacquer's own targets replace.
"""
from .. import noctalia, noctaliapalette
from . import Target

NAME = "Lacquer"
FILE = noctaliapalette.path(NAME)
SOURCE, CUSTOM, TEMPLATES = "noctalia:theme.source", "noctalia:theme.custom_palette", "noctalia:theme.templates.builtin_ids"


class Shell(Target):
	name = "shell"

	def detect(self):
		return noctalia.running()

	def render(self, look):
		ids = noctalia.get("theme.templates.builtin_ids") or []
		if self.name not in look.handover:
			look.handover[self.name] = {
				"source": noctalia.get("theme.source"), "custom_palette": noctalia.get("theme.custom_palette"),
				"templates": [i for i in ids if i in look.templates],
			}
		# The file and the template list first: setting the source is what
		# makes Noctalia apply the palette.
		return {
			f"file:{FILE}": noctaliapalette.dumps(look.palette),
			TEMPLATES: [i for i in ids if i not in look.templates],
			CUSTOM: NAME, SOURCE: "custom",
		}

	def release(self, handover):
		before = handover.get(self.name)
		if before is None:
			return {}
		ids = noctalia.get("theme.templates.builtin_ids") or []
		return {
			TEMPLATES: ids + [i for i in before["templates"] if i not in ids],
			CUSTOM: before["custom_palette"], SOURCE: before["source"],
			f"file:{FILE}": None,
		}

	def live(self, look):
		# Noctalia reads a palette file when the source or name changes, not
		# when the file does; this makes it read the file and run its templates.
		noctalia.msg("config-reload")
		noctalia.msg("templates-apply")

	def reverted(self):
		self.live(None)


TARGET = Shell()
