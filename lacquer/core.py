"""What Lacquer does, independent of who asks (CLI now, GUI later).

Every function returns plain data (dicts, lists) and raises LacquerError with
a message for the user. Keys are `<section>.<module key>`, for example
`windows.decoration.rounding`.
"""
import difflib
import importlib.util
import os
import shutil
import time

from . import lock, paths, state, tomlio
from .modules import discover
from .values import Invalid, LacquerError, same

MIN_TIMEOUT, MAX_TIMEOUT, DEFAULT_TIMEOUT = 5, 120, 15
DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name=Lacquer
Comment=Desktop look customiser
Exec={paths.LAUNCHER} gui
Icon=preferences-desktop-theme
Categories=Settings;DesktopSettings;
StartupWMClass={paths.APP_ID}
"""

_modules = None


def modules():
	global _modules
	if _modules is None:
		_modules = discover()
	return _modules


# -- theme file <-> flat keys --

def flatten(module, section):
	"""Nested theme section to {key: value}. Raises on keys the module lacks."""
	schema = module.schema()
	flat = {}

	def walk(node, path):
		for name, value in node.items():
			key = ".".join(path + [name])
			if key in schema:
				flat[key] = value
			elif isinstance(value, dict):
				walk(value, path + [name])
			else:
				raise Invalid(f"{module.name}.{key}: no such key")

	walk(section, [])
	return flat


def unflatten(flat):
	tree = {}
	for key, value in flat.items():
		node = tree
		*parents, leaf = key.split(".")
		for p in parents:
			node = node.setdefault(p, {})
		node[leaf] = tomlio.Inline(value) if isinstance(value, dict) else value
	return tree


def _saved(theme, module):
	return flatten(module, theme.get(module.name, {}))


def _split(key):
	"""`windows.decoration.rounding` to (module, `decoration.rounding`)."""
	section, _, rest = key.partition(".")
	module = modules().get(section)
	if module is None:
		raise Invalid(f"{key}: no section '{section}' (have: {', '.join(modules()) or 'none'})")
	if rest not in module.schema():
		near = difflib.get_close_matches(rest, module.schema(), n=3)
		hint = f" (did you mean {', '.join(f'{section}.{n}' for n in near)}?)" if near else ""
		raise Invalid(f"{key}: no such key{hint}")
	return module, rest


def _validate(module, key, value):
	try:
		return module.validate(key, value)
	except Invalid as e:
		raise Invalid(f"{module.name}.{e}") from e


def _with_warnings(result, warnings):
	if warnings:
		result["warnings"] = warnings
	return result


def _store(theme, name, section):
	"""Puts a module's flat section into the theme; an empty one is dropped."""
	if section:
		theme[name] = unflatten(section)
	else:
		theme.pop(name, None)


def _write_current(theme):
	paths.atomic_write(paths.CURRENT, tomlio.dumps(theme))
	os.makedirs(paths.SNAPSHOTS, exist_ok=True)
	shutil.copy2(paths.CURRENT, os.path.join(paths.SNAPSHOTS, time.strftime("%Y%m%d-%H%M%S") + ".toml"))


# -- reading --

def sections():
	"""The usable sections in display order, with what a front-end needs to
	lay them out: {name: {"title"}}."""
	ordered = sorted(modules().values(), key=lambda m: (m.order, m.name))
	return {m.name: {"title": m.title or m.name.capitalize()} for m in ordered}


def schema(prefix=""):
	"""{key: spec}; `needs` in a spec is what must hold for this key to do
	anything: {other key: [values it may have]}."""
	out = {}
	for name, module in modules().items():
		keys = module.schema()
		for key, spec in keys.items():
			if f"{name}.{key}".startswith(prefix):
				needs = {f"{name}.{other}": allowed for other, allowed in module.needs(key, keys).items()}
				out[f"{name}.{key}"] = spec.public() | ({"needs": needs} if needs else {})
	return out


def get(prefix=""):
	"""Live value of each key, plus `saved` when Lacquer keeps it and
	`preview` when the live value is an unkept preview."""
	theme = tomlio.load(paths.CURRENT)
	pending = state.load()["modules"]
	out = {}
	for name, module in modules().items():
		keys = [k for k in module.schema() if f"{name}.{k}".startswith(prefix)]
		saved = _saved(theme, module)
		previewing = pending.get(name, {}).get("values", {})
		for key, value in module.read(keys).items():
			entry = {"value": value}
			if key in saved:
				entry["saved"] = saved[key]
			if key in previewing:
				entry["preview"] = True
			out[f"{name}.{key}"] = entry
	if not out and prefix:
		_split(prefix)
	return out


def status():
	st = state.load()
	return {
		"modules": list(modules()),
		"preview": {f"{name}.{k}": v for name, entry in st["modules"].items() for k, v in entry["values"].items()},
		"auto_revert_in": state.seconds_left(st),
	}


# -- preview / keep / revert --

def _old_values(st, changes):
	"""{module name: {key: value from before the preview}} for the changed keys.

	Read live for a key's first preview, taken from the state after that. A
	key previewed by an older state file without it has none."""
	out = {}
	for name, values in changes.items():
		entry = st["modules"].get(name, {})
		known = entry.get("before", {})
		fresh = [k for k in values if k not in known and k not in entry.get("values", {})]
		out[name] = {k: known[k] for k in values if k in known}
		if fresh:
			out[name].update(modules()[name].read(fresh))
	return out


def _forget(back):
	"""Takes keys that are back at their old value out of the preview state.
	back: {module name: [keys]}. The timer goes when nothing risky is left."""
	st = state.load()
	for name, keys in back.items():
		entry = st["modules"].get(name)
		if entry is None:
			continue
		for key in keys:
			entry["values"].pop(key, None)
			entry.get("before", {}).pop(key, None)
		if not entry["values"]:
			del st["modules"][name]
	if not st["modules"]:
		state.clear()
		return
	if not any(modules()[name].risk(k, v) for name, entry in st["modules"].items() if name in modules() for k, v in entry["values"].items()):
		st.pop("token", None)
		st.pop("revert_at", None)
	state.save(st)


@lock.exclusive
def _preview(changes, replace, keep_now, timeout, drop_unchanged=False):
	"""changes: {module name: {key: value}}, already validated.

	drop_unchanged: a value equal to the one from before the preview is no
	change. It is not previewed, or, if the key was in the preview, it is
	put back and leaves the preview (which ends when it was the last one).
	Without it such a value stays a preview, so `set` + `keep` can adopt a
	live value."""
	if not MIN_TIMEOUT <= timeout <= MAX_TIMEOUT:
		raise Invalid(f"timeout must be {MIN_TIMEOUT} to {MAX_TIMEOUT} seconds")
	st = state.load()
	before = _old_values(st, changes)
	back, unchanged = {}, []  # back: {module name: [previewed keys now at their old value]}
	if drop_unchanged and not replace:
		kept = {}
		for name, values in changes.items():
			entry = st["modules"].get(name, {"values": {}, "replace": False})
			if entry["replace"]:
				# A theme's section is kept whole, old values included.
				kept[name] = values
				continue
			old = before[name]
			at_old = [k for k, v in values.items() if k in old and same(v, old[k])]
			unchanged += [f"{name}.{k}" for k in at_old]
			back[name] = [k for k in at_old if k in entry["values"]]
			kept[name] = {k: v for k, v in values.items() if k not in at_old or k in entry["values"]}
		changes = {name: values for name, values in kept.items() if values}
	risky = {
		f"{name}.{k}": why
		for name, values in changes.items()
		for k, v in values.items()
		if k not in back.get(name, ()) and (why := modules()[name].risk(k, v))
	}
	if risky and keep_now:
		raise LacquerError("risky values can't be kept in one step, preview them first: " + "; ".join(f"{k} ({why})" for k, why in risky.items()))

	if changes:
		# State (and the timer) go first: if the preview makes the screen
		# unusable, the revert key and the timer already know about it.
		for name, values in changes.items():
			entry = st["modules"].setdefault(name, {"values": {}, "replace": False})
			if replace:
				entry.update(values={}, replace=True)
			entry["values"].update(values)
			old = entry.setdefault("before", {})
			for k, v in before[name].items():
				old.setdefault(k, v)
		if risky:
			state.arm_timer(st, timeout)
		else:
			state.save(st)
		# Modules whose every previewed value is back where it was.
		ended = {name for name, keys in back.items() if keys and set(st["modules"][name]["values"]) <= set(keys)}

		try:
			for name, values in changes.items():
				if name in ended:
					modules()[name].unchanged(values)
				else:
					modules()[name].preview(values)
		except LacquerError as e:
			revert()
			raise LacquerError(f"{e}. The whole preview was reverted.") from e
		if any(back.values()):
			_forget(back)

	result = {"previewed": {
		f"{name}.{k}": v for name, values in changes.items() for k, v in values.items() if k not in back.get(name, ())
	}}
	if unchanged:
		result["unchanged"] = unchanged
	if risky:
		result["risky"] = risky
		result["auto_revert_in"] = timeout
	if keep_now:
		result.update(keep())
	return result


def set_values(pairs, keep_now=False, timeout=DEFAULT_TIMEOUT, drop_unchanged=False):
	"""pairs: [(key, value)]. Shows them live; saved only after keep().
	drop_unchanged: see _preview()."""
	changes = {}
	for key, value in pairs:
		module, rest = _split(key)
		changes.setdefault(module.name, {})[rest] = _validate(module, rest, value)
	return _preview(changes, False, keep_now, timeout, drop_unchanged)


def apply(theme_name, keep_now=False, timeout=DEFAULT_TIMEOUT):
	"""Previews a whole theme file. Each section it has replaces that section;
	sections it lacks are left alone."""
	path = theme_name if os.path.isfile(theme_name) else os.path.join(paths.THEMES, f"{theme_name}.toml")
	if not os.path.isfile(path):
		raise LacquerError(f"no theme '{theme_name}' (looked for {path})")
	theme = tomlio.load(path)
	changes = {}
	for name, module in modules().items():
		if name in theme:
			changes[name] = {k: _validate(module, k, v) for k, v in flatten(module, theme[name]).items()}
	skipped = sorted(set(theme) - set(changes))
	result = _preview(changes, True, keep_now, timeout)
	if skipped:
		result["skipped_sections"] = skipped
	return result


@lock.exclusive
def keep():
	"""Saves the running preview."""
	st = state.load()
	if not st["modules"]:
		return {"kept": {}}
	theme = tomlio.load(paths.CURRENT)
	kept, warnings = {}, []
	try:
		for name, entry in st["modules"].items():
			module = modules()[name]
			section = {} if entry["replace"] else _saved(theme, module)
			section.update(entry["values"])
			warnings += module.keep(section)
			_store(theme, name, section)
			kept.update({f"{name}.{k}": v for k, v in entry["values"].items()})
	finally:
		# Kept or failed, the preview is over (a failed keep reloads the old config).
		state.clear()
	_write_current(theme)
	return _with_warnings({"kept": kept}, warnings)


@lock.exclusive
def revert(force=False):
	"""Drops the running preview. force reverts every module even with no
	preview on record (for changes made behind Lacquer's back)."""
	names = list(modules()) if force else [n for n in state.load()["modules"] if n in modules()]
	state.clear()
	for name in names:
		modules()[name].revert()
	return {"reverted": names}


@lock.exclusive
def unset(keys):
	"""Stops keeping keys, handing them back to the other config files."""
	if state.load()["modules"]:
		raise LacquerError("a preview is running: keep or revert it first")
	theme = tomlio.load(paths.CURRENT)
	touched, warnings = {}, []
	for key in keys:
		module, rest = _split(key)
		section = touched.setdefault(module.name, _saved(theme, module))
		if rest not in section:
			raise LacquerError(f"{key} is not kept by Lacquer")
		del section[rest]
	for name, section in touched.items():
		warnings += modules()[name].keep(section)
		_store(theme, name, section)
	_write_current(theme)
	return _with_warnings({"unset": list(keys)}, warnings)


@lock.exclusive
def adopt(keys):
	"""Starts keeping keys at the value they have right now, whoever set it.
	For a tool that hands its settings over to Lacquer (hypr-dashboard): the
	look does not change, and its own value can go afterwards."""
	if state.load()["modules"]:
		raise LacquerError("a preview is running: keep or revert it first")
	theme = tomlio.load(paths.CURRENT)
	touched, adopted, warnings = {}, {}, []
	for key in keys:
		module, rest = _split(key)
		value = module.read([rest]).get(rest)
		if value is None:
			raise LacquerError(f"{key} has no value to adopt")
		section = touched.setdefault(module.name, _saved(theme, module))
		section[rest] = adopted[key] = _validate(module, rest, value)
	for name, section in touched.items():
		warnings += modules()[name].keep(section)
		_store(theme, name, section)
	_write_current(theme)
	return _with_warnings({"adopted": adopted}, warnings)


def owned():
	"""What Lacquer is the one writer of in other programs' config, and the
	command that opens its window (add a section name to open on that page):
	{"open": [command], "owns": {program: {kind: {their name: Lacquer key},
	or [file paths]}}}. Tools that edit the same config leave these alone."""
	owns = {}
	for module in modules().values():
		for program, kinds in module.owns().items():
			for kind, items in kinds.items():
				have = owns.setdefault(program, {}).setdefault(kind, type(items)())
				if isinstance(items, dict):
					have.update(items)
				else:
					have.extend(items)
	return {"open": [paths.LAUNCHER, "gui"], "owns": owns}


# -- themes and snapshots --

def _names(folder):
	try:
		return sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".toml"))
	except FileNotFoundError:
		return []


def theme_list():
	return {"themes": _names(paths.THEMES)}


def _theme_path(name):
	if not name or "/" in name or name.startswith("."):
		raise Invalid(f"bad theme name {name!r}")
	return os.path.join(paths.THEMES, f"{name}.toml")


def theme_save(name):
	path = _theme_path(name)
	if not os.path.isfile(paths.CURRENT):
		raise LacquerError("nothing kept yet, so there is no look to save")
	os.makedirs(paths.THEMES, exist_ok=True)
	shutil.copy2(paths.CURRENT, path)
	return {"saved": path}


def theme_delete(name):
	"""Removes a saved theme for good. The kept look and the snapshots stay."""
	path = _theme_path(name)
	if not os.path.isfile(path):
		raise LacquerError(f"no theme '{name}'")
	os.remove(path)
	return {"deleted": path}


def snapshot_list():
	return {"snapshots": _names(paths.SNAPSHOTS)}


def snapshot_restore(name, keep_now=False):
	path = os.path.join(paths.SNAPSHOTS, f"{name}.toml")
	if not os.path.isfile(path):
		raise LacquerError(f"no snapshot '{name}'")
	return apply(path, keep_now)


# -- setup --

@lock.exclusive
def install():
	done = []
	if not os.path.lexists(paths.USER_BIN):
		os.makedirs(os.path.dirname(paths.USER_BIN), exist_ok=True)
		os.symlink(paths.LAUNCHER, paths.USER_BIN)
		done.append(f"linked {paths.USER_BIN}")
	# The window needs PyGObject; without it there is nothing to launch.
	if importlib.util.find_spec("gi") and paths.read_text(paths.DESKTOP) != DESKTOP_ENTRY:
		paths.atomic_write(paths.DESKTOP, DESKTOP_ENTRY)
		done.append(f"wrote {paths.DESKTOP}")
	theme = tomlio.load(paths.CURRENT)
	for module in modules().values():
		done += module.install(_saved(theme, module))
	return {"installed": done}


@lock.exclusive
def sync():
	"""Brings the kept look in line after a change made outside Lacquer.
	Run by hooks that `install` sets up (Noctalia's dark/light switch)."""
	if state.load()["modules"]:
		# The preview wrote its own mode, and its revert puts every place back.
		return {"synced": [], "skipped": "a preview is running"}
	done = []
	for module in modules().values():
		done += module.sync()
	return {"synced": done}


def doctor():
	findings = []
	if os.path.realpath(shutil.which("lacquer") or "") == os.path.realpath(paths.LAUNCHER):
		findings.append({"level": "ok", "check": "core.launcher", "detail": "`lacquer` on PATH is this checkout"})
	else:
		findings.append({"level": "warn", "check": "core.launcher", "detail": "`lacquer` on PATH is missing or another copy: run `lacquer install`"})
	st = state.load()
	if st["modules"]:
		findings.append({"level": "warn", "check": "core.preview", "detail": "a preview is running, so 'overridden' findings may be the preview itself"})
	theme = tomlio.load(paths.CURRENT)
	for module in modules().values():
		findings += module.doctor(_saved(theme, module))
	return {"findings": findings, "ok": not any(f["level"] == "error" for f in findings)}
