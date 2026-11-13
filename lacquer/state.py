"""The running preview: which values are live but not kept, and its timer.

Lives in $XDG_RUNTIME_DIR so it survives a GUI crash but not a reboot (a
reboot loads the saved config anyway).
"""
import json
import os
import subprocess
import sys
import time
import uuid

from . import paths


def load():
	text = paths.read_text(paths.PREVIEW)
	state = json.loads(text) if text else {}
	state.setdefault("modules", {})
	return state


def save(state):
	paths.atomic_write(paths.PREVIEW, json.dumps(state))


def clear():
	"""Forgets the preview. A running timer then finds no token and does nothing."""
	try:
		os.remove(paths.PREVIEW)
	except FileNotFoundError:
		pass


def arm_timer(state, seconds):
	"""Starts a detached process that reverts after `seconds` unless kept first.

	Detached so the revert still happens if the caller (GUI, Claude) dies. Each
	call replaces the previous timer: the old one sees a different token.
	"""
	state["token"] = uuid.uuid4().hex
	state["revert_at"] = time.time() + seconds
	save(state)
	subprocess.Popen(
		[sys.executable, paths.LAUNCHER, "_timer", state["token"], str(seconds)],
		stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
	)


def seconds_left(state):
	if not state.get("token"):
		return None
	return max(0, round(state["revert_at"] - time.time()))


# -- old values of persistent targets --
# Targets like Noctalia or gsettings save a change the moment it is made, so a
# preview there has to remember what it replaced. One file per module, written
# before the change, so `lacquer revert` works after a crash.

def _old_path(name):
	return os.path.join(paths.RUNTIME, "old", f"{name}.json")


def old_load(name):
	text = paths.read_text(_old_path(name))
	return json.loads(text) if text else {}


def old_save(name, values):
	paths.atomic_write(_old_path(name), json.dumps(values))


def old_clear(name):
	try:
		os.remove(_old_path(name))
	except FileNotFoundError:
		pass
