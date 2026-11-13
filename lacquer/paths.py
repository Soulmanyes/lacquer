"""Where Lacquer keeps its files, plus the one safe way to write them."""
import os
import shutil

HOME = os.path.expanduser("~")
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "lacquer")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state"), "lacquer")
RUNTIME = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "lacquer")

CURRENT = os.path.join(CONFIG, "current.toml")
SETTINGS = os.path.join(CONFIG, "config.toml")
THEMES = os.path.join(CONFIG, "themes")
SNAPSHOTS = os.path.join(STATE, "snapshots")
PREVIEW = os.path.join(RUNTIME, "preview.json")

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LAUNCHER = os.path.join(REPO, "bin", "lacquer")
USER_BIN = os.path.join(HOME, ".local", "bin", "lacquer")


def atomic_write(path, text):
	"""Writes through a temp file so a crash never leaves a half-written file."""
	os.makedirs(os.path.dirname(path), exist_ok=True)
	tmp = f"{path}.tmp-{os.getpid()}"
	with open(tmp, "w") as f:
		f.write(text)
	os.replace(tmp, path)


def read_text(path):
	"""Returns the file's text, or None if it does not exist."""
	try:
		with open(path) as f:
			return f.read()
	except FileNotFoundError:
		return None


def backup_once(path):
	"""Copies a file Lacquer is about to change for the first time to
	`<file>.bak-lacquer`. Later changes keep that first copy."""
	backup = f"{path}.bak-lacquer"
	if os.path.isfile(path) and not os.path.exists(backup):
		shutil.copy2(path, backup)
