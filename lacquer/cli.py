"""The `lacquer` command. Prints JSON: indented by default, one line with --json."""
import argparse
import json
import shutil
import subprocess
import sys
import time

from . import __version__, core, state
from .values import LacquerError, parse_cli


def _timer(token, seconds):
	"""Runs detached: reverts a risky preview that nobody kept in time."""
	time.sleep(seconds)
	if state.load().get("token") != token:
		return
	core.revert()
	if shutil.which("notify-send"):
		subprocess.run(["notify-send", "-a", "Lacquer", "Lacquer", "Preview was not kept in time, so it was reverted."], check=False)


def _parser():
	common = argparse.ArgumentParser(add_help=False)
	common.add_argument("--json", action="store_true", help="one-line JSON output")
	timed = argparse.ArgumentParser(add_help=False)
	timed.add_argument("--keep", action="store_true", help="save at once (refused for risky values)")
	timed.add_argument("--preview", action="store_true", help="preview only (the default; here for clarity)")
	timed.add_argument("--timeout", type=int, default=core.DEFAULT_TIMEOUT, help="seconds before a risky preview reverts itself")

	p = argparse.ArgumentParser(prog="lacquer", description="Desktop look customiser.")
	p.add_argument("--version", action="version", version=__version__)
	sub = p.add_subparsers(dest="command", required=True)

	def add(name, help, parents=(common,)):
		return sub.add_parser(name, help=help, parents=list(parents))

	add("get", "live values (with what is saved and what is a preview)").add_argument("prefix", nargs="?", default="")
	add("schema", "keys with type, range and default").add_argument("prefix", nargs="?", default="")
	add("set", "preview values: KEY VALUE [KEY VALUE ...]", (common, timed)).add_argument("pairs", nargs="+", metavar="KEY VALUE")
	add("keep", "save the running preview")
	add("revert", "drop the running preview").add_argument("--force", action="store_true", help="revert even with no preview on record")
	add("unset", "stop keeping keys").add_argument("keys", nargs="+")
	add("adopt", "start keeping keys at their live value (for a tool handing them over)").add_argument("keys", nargs="+")
	add("owned", "what Lacquer is the one writer of in other programs' config")
	add("status", "running preview and timer")
	add("apply", "preview a whole theme (name or file)", (common, timed)).add_argument("theme")
	add("doctor", "check the setup and list overlaps with other config")
	add("install", "hook Lacquer into the system (config require, revert key, PATH)")
	add("sync", "follow a change made outside Lacquer (run by hooks, such as Noctalia's dark/light switch)")
	add("gui", "open the window", ()).add_argument("page", nargs="?", help="section to open on, for example windows")

	theme = add("theme", "saved themes").add_subparsers(dest="action", required=True)
	theme.add_parser("list", parents=[common])
	theme.add_parser("save", parents=[common]).add_argument("name")
	theme.add_parser("delete", parents=[common]).add_argument("name")
	snap = add("snapshot", "automatic copies of every kept look").add_subparsers(dest="action", required=True)
	snap.add_parser("list", parents=[common])
	restore = snap.add_parser("restore", parents=[common, timed])
	restore.add_argument("name")
	return p


def _run(args):
	c = args.command
	if c == "get":
		return core.get(args.prefix)
	if c == "schema":
		return core.schema(args.prefix)
	if c == "set":
		if len(args.pairs) % 2:
			raise LacquerError("set needs KEY VALUE pairs")
		pairs = [(k, parse_cli(v)) for k, v in zip(args.pairs[::2], args.pairs[1::2])]
		return core.set_values(pairs, args.keep, args.timeout)
	if c == "keep":
		return core.keep()
	if c == "revert":
		return core.revert(args.force)
	if c == "unset":
		return core.unset(args.keys)
	if c == "adopt":
		return core.adopt(args.keys)
	if c == "owned":
		return core.owned()
	if c == "status":
		return core.status()
	if c == "apply":
		return core.apply(args.theme, args.keep, args.timeout)
	if c == "doctor":
		return core.doctor()
	if c == "install":
		return core.install()
	if c == "sync":
		return core.sync()
	if c == "theme":
		if args.action == "list":
			return core.theme_list()
		return (core.theme_save if args.action == "save" else core.theme_delete)(args.name)
	if args.action == "list":
		return core.snapshot_list()
	return core.snapshot_restore(args.name, args.keep)


def main(argv=None):
	argv = sys.argv[1:] if argv is None else argv
	if argv[:1] == ["_timer"]:
		_timer(argv[1], int(argv[2]))
		return 0
	args = _parser().parse_args(argv)
	if args.command == "gui":
		# Imported here: the CLI must work without GTK.
		from . import gui
		return gui.run(args.page)
	try:
		result, code = _run(args), 0
	except LacquerError as e:
		result, code = {"error": str(e)}, 1
	print(json.dumps(result, ensure_ascii=False) if args.json else json.dumps(result, indent=2, ensure_ascii=False))
	return code
