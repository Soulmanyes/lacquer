"""Talking to Hyprland.

The socket request and get_option code comes from hypr-dashboard's hypr.py
(same owner, CC0).
"""
import json
import os
import socket
import subprocess

from .values import LacquerError


def running():
	return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and os.environ.get("XDG_RUNTIME_DIR"))


def _socket_path():
	return os.path.join(os.environ["XDG_RUNTIME_DIR"], "hypr", os.environ["HYPRLAND_INSTANCE_SIGNATURE"], ".socket.sock")


def request(command):
	"""Sends one command over the Hyprland socket and returns the reply text."""
	with socket.socket(socket.AF_UNIX) as s:
		s.settimeout(5)
		s.connect(_socket_path())
		s.sendall(command.encode())
		reply = b""
		while chunk := s.recv(65536):
			reply += chunk
	return reply.decode()


def get_option(name):
	"""Returns (type, value), or None if Hyprland can't report this option."""
	try:
		reply = json.loads(request(f"j/getoption {name}"))
	except ValueError:
		return None
	kind = next(k for k in reply if k not in ("option", "set"))
	return kind, reply[kind]


def _hyprctl(*args, timeout=10):
	return subprocess.run(["hyprctl", *args], check=False, capture_output=True, text=True, timeout=timeout).stdout


def hyprctl_json(*args):
	return json.loads(_hyprctl(*args, "-j"))


def eval_lua(code):
	"""Runs Lua in the live session (not saved). Raises on Hyprland's error."""
	reply = _hyprctl("eval", code).strip()
	if reply != "ok":
		raise LacquerError(f"Hyprland refused the change: {reply.split(':1: ', 1)[-1]}")


def reload():
	"""Re-runs the saved config, which drops everything set with eval_lua."""
	_hyprctl("reload")


def config_errors():
	return [e for e in hyprctl_json("configerrors") if e.strip()]


def set_cursor(theme, size):
	"""Changes the cursor of the live session (not saved)."""
	reply = _hyprctl("setcursor", theme, str(size)).strip()
	if reply != "ok":
		raise LacquerError(f"Hyprland refused cursor {theme} {size}: {reply}")
