"""What Lacquer does, independent of who asks (CLI now, GUI later).

Every function returns plain data (dicts, lists) and raises LacquerError with
a message for the user. Keys are `<section>.<module key>`, for example
`windows.decoration.rounding`.
"""
import difflib
import os
import shutil
import time

from . import paths, state, tomlio
from .modules import discover
from .values import Invalid, LacquerError

MIN_TIMEOUT, MAX_TIMEOUT, DEFAULT_TIMEOUT = 5, 120, 15

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

def schema(prefix=""):
	return {
		f"{name}.{key}": spec.public()
		for name, module in modules().items()
		for key, spec in module.schema().items()
		if f"{name}.{key}".startswith(prefix)
	}


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

def _preview(changes, replace, keep_now, timeout):
	"""changes: {module name: {key: value}}, already validated."""
	if not MIN_TIMEOUT <= timeout <= MAX_TIMEOUT:
		raise Invalid(f"timeout must be {MIN_TIMEOUT} to {MAX_TIMEOUT} seconds")
	risky = {
		f"{name}.{k}": why
		for name, values in changes.items()
		for k, v in values.items()
		if (why := modules()[name].risk(k, v))
	}
	if risky and keep_now:
		raise LacquerError("risky values can't be kept in one step, preview them first: " + "; ".join(f"{k} ({why})" for k, why in risky.items()))

	# State (and the timer) go first: if the preview makes the screen
	# unusable, the revert key and the timer already know about it.
	st = state.load()
	for name, values in changes.items():
		entry = st["modules"].setdefault(name, {"values": {}, "replace": False})
		if replace:
			entry.update(values={}, replace=True)
		entry["values"].update(values)
	if risky:
		state.arm_timer(st, timeout)
	else:
		state.save(st)

	try:
		for name, values in changes.items():
			modules()[name].preview(values)
	except LacquerError as e:
		revert()
		raise LacquerError(f"{e}. The whole preview was reverted.") from e

	result = {"previewed": {f"{name}.{k}": v for name, values in changes.items() for k, v in values.items()}}
	if risky:
		result["risky"] = risky
		result["auto_revert_in"] = timeout
	if keep_now:
		result.update(keep())
	return result


def set_values(pairs, keep_now=False, timeout=DEFAULT_TIMEOUT):
	"""pairs: [(key, value)]. Shows them live; saved only after keep()."""
	changes = {}
	for key, value in pairs:
		module, rest = _split(key)
		changes.setdefault(module.name, {})[rest] = _validate(module, rest, value)
	return _preview(changes, False, keep_now, timeout)


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


def revert(force=False):
	"""Drops the running preview. force reverts every module even with no
	preview on record (for changes made behind Lacquer's back)."""
	names = list(modules()) if force else [n for n in state.load()["modules"] if n in modules()]
	state.clear()
	for name in names:
		modules()[name].revert()
	return {"reverted": names}


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


# -- themes and snapshots --

def _names(folder):
	try:
		return sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".toml"))
	except FileNotFoundError:
		return []


def theme_list():
	return {"themes": _names(paths.THEMES)}


def theme_save(name):
	if not name or "/" in name or name.startswith("."):
		raise Invalid(f"bad theme name {name!r}")
	if not os.path.isfile(paths.CURRENT):
		raise LacquerError("nothing kept yet, so there is no look to save")
	os.makedirs(paths.THEMES, exist_ok=True)
	path = os.path.join(paths.THEMES, f"{name}.toml")
	shutil.copy2(paths.CURRENT, path)
	return {"saved": path}


def snapshot_list():
	return {"snapshots": _names(paths.SNAPSHOTS)}


def snapshot_restore(name, keep_now=False):
	path = os.path.join(paths.SNAPSHOTS, f"{name}.toml")
	if not os.path.isfile(path):
		raise LacquerError(f"no snapshot '{name}'")
	return apply(path, keep_now)


# -- setup --

def install():
	done = []
	if not os.path.lexists(paths.USER_BIN):
		os.makedirs(os.path.dirname(paths.USER_BIN), exist_ok=True)
		os.symlink(paths.LAUNCHER, paths.USER_BIN)
		done.append(f"linked {paths.USER_BIN}")
	theme = tomlio.load(paths.CURRENT)
	for module in modules().values():
		done += module.install(_saved(theme, module))
	return {"installed": done}


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
