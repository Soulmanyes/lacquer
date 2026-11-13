"""Hooking a Lacquer-written Lua file into the owner's hyprland.lua."""
import os
import shutil
import time

from . import hypr, paths
from .values import LacquerError

HYPR_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(paths.HOME, ".config"), "hypr")
MAIN_LUA = os.path.join(HYPR_DIR, "hyprland.lua")
DASHBOARD_REQUIRE = 'require("config.dashboard_options")'


def config_file(name):
	return os.path.join(HYPR_DIR, "config", f"{name}.lua")


def hooked(require):
	return require in (paths.read_text(MAIN_LUA) or "")


def hook(require, comment):
	"""Adds a require line (with its comment lines) to hyprland.lua, before
	dashboard_options or at the end. Backs the file up first and restores it
	if Hyprland reports config errors. Returns a list of what it did."""
	text = paths.read_text(MAIN_LUA)
	if text is None:
		raise LacquerError(f"{MAIN_LUA} not found")
	if require in text:
		return [f"hyprland.lua already has {require}"]
	backup = f"{MAIN_LUA}.bak-{time.strftime('%Y-%m-%d')}"
	if os.path.exists(backup):
		backup += time.strftime("-%H%M%S")
	shutil.copy2(MAIN_LUA, backup)
	block = [*comment, require, ""]
	lines = text.split("\n")
	at = next((i for i, line in enumerate(lines) if DASHBOARD_REQUIRE in line), None)
	if at is None:
		lines = text.rstrip("\n").split("\n") + [""] + block
	else:
		while at > 0 and lines[at - 1].startswith("--"):
			at -= 1
		lines[at:at] = block
	paths.atomic_write(MAIN_LUA, "\n".join(lines))
	hypr.reload()
	errors = hypr.config_errors()
	if errors:
		shutil.copy2(backup, MAIN_LUA)
		hypr.reload()
		raise LacquerError("Hyprland reported config errors, hyprland.lua is restored: " + "; ".join(errors))
	return [f"backed up hyprland.lua to {backup}", f"added {require} to hyprland.lua"]
