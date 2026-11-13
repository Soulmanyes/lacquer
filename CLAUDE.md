# CLAUDE.md

Lacquer is the owner's desktop look customiser (Hyprland, Noctalia, GTK/Qt,
cursor and fonts). `PLAN.md` is the spec: read it before
adding a phase.

Sections: `windows` (Hyprland), `bar`, `shell`, `palette`, `wallpaper`
(Noctalia), `toolkit`, `cursor`, `fonts` (GTK/Qt). `lacquer status` lists the
ones that are usable right now.

## Changing the owner's look: use the CLI, not the config files

Any request like "make the corners rounder" or "try a blue border" goes through
`lacquer` (on PATH, symlink to `bin/lacquer`). Do not hand-edit
`~/.config/hypr/config/*.lua` for look options, and never edit
`~/.config/hypr/config/lacquer.lua` (generated on every keep).

1. `lacquer get <prefix> --json`: live values. `saved` = Lacquer keeps it,
   `preview` = live but not kept. `lacquer schema <prefix>` gives type, range,
   default and description.
2. `lacquer set KEY VALUE [KEY VALUE ...] --json`: live preview, nothing saved.
   Values are JSON or plain text: `12`, `0.9`, `true`, `'#b48cf0'`,
   `'{"colors":["#b48cf0","#7aa2f7"],"angle":45}'`, `'{"top":4,"left":8}'`.
3. Check the result on the owner's real screen (the preview is global, so a
   plain screenshot shows it; delete the screenshot after).
4. `lacquer keep` or `lacquer revert`. Ask the owner which unless they already
   said to keep it.

Rules:

- A reply with `risky` means a 15 s timer is running (`auto_revert_in`). It
  reverts the whole preview unless `lacquer keep` runs first. Risky values
  cannot be kept in one step (`--keep` is refused). Do not raise `--timeout`
  to get around this; tell the owner what is risky and let them look.
- Read `warnings` after a keep. "overridden by a later config file" means
  hypr-dashboard's `dashboard_options.lua` sets the same option and wins;
  `lacquer doctor` lists those options. Change those in hypr-dashboard instead.
- `lacquer unset KEY` hands a key back to the other config files.
- Revert is `hyprctl reload`: it also drops anything else set live with
  `hyprctl eval`.
- Noctalia sections (`bar`, `shell`, `palette`, `wallpaper`): do not call
  `noctalia msg config-set` or edit `settings.toml` for look values. Keys are
  Noctalia's own names: `bar.<bar name>.<setting>` (`bar.default.radius`),
  `shell.corner_radius_scale`, `palette.mode`, `palette.source`,
  `palette.custom_palette`, `wallpaper.default`, `wallpaper.monitors.<output>`.
  There is no range or choice list in the schema: Noctalia checks on write, and
  a refused or clamped value reverts the whole preview with its message.
- `wallpaper.default` puts the image on every monitor. To keep one monitor
  different, give its `wallpaper.monitors.<output>` in the same `set`.
- A palette change runs Noctalia's templates (kitty, GTK, ...) and shows a
  Noctalia notification; that is normal.
- GTK/Qt sections: do not call `gsettings set`, `nwg-look` or edit
  `qt6ct.conf`, `settings.ini` or `~/.icons/default` for these. Keys:
  `toolkit.gtk_theme`, `toolkit.icon_theme`, `toolkit.qt_style`,
  `cursor.theme`, `cursor.size`, `fonts.interface`, `fonts.document`,
  `fonts.monospace` (family, may end in Bold/Italic) and each `_size` (points).
  `lacquer schema toolkit` / `cursor` lists the installed themes under
  `choices`. An icon theme or font that is not installed is refused; a missing
  GTK or cursor theme and extreme sizes are risky. Colors are not here: they
  come from the palette.
- Never edit `~/.config/hypr/config/lacquer_cursor.lua` (cursor env vars,
  rewritten on every cursor keep). The env vars reach apps started after the
  next login; the cursor itself changes at once.
- If a keep fails half-way (Hyprland config error), a Noctalia preview stays
  live: `lacquer revert --force` puts it back.
- The owner's blind revert key is Super+Backspace (bound in `lacquer.lua`).
- `lacquer apply <theme>` previews a whole theme; a section in the theme
  replaces that whole section. `lacquer theme save <name>` stores the kept look.
  Every keep also writes a snapshot (`lacquer snapshot list|restore`).

## Code

- Python, tabs, no dependencies outside the standard library.
- `lacquer/core.py` is the only thing front-ends call (CLI now, GTK GUI in
  phase 5). It returns plain dicts and raises `LacquerError`.
- One area = one file in `lacquer/modules/` exposing `MODULE` (see `base.py`
  for the interface). `core.py` and `cli.py` must not need a change for a new
  area. Value types shared by modules live in `values.py`.
- Targets that save every change at once (Noctalia, later gsettings) subclass
  `persistent.Persistent`: fill in `read()` and `write()`, it does
  preview/keep/revert with the old values in `$XDG_RUNTIME_DIR/lacquer/old/`.
  A Noctalia config table is a `noctalia.ConfigModule` with `table` and
  `wanted(key)` (see `modules/shell.py`, 20 lines).
- A key that lands in several programs' settings (gsettings, `qt6ct.conf`) is
  a `places.Placed` module: fill in `read()`, `write()` and `touched()` (the
  place names a change can alter); revert then restores each place exactly. A
  new kind of place is one entry in `places.KINDS`. Files only written on keep
  (GTK `settings.ini`) go through `gtk.mirror()` in the module's `keep()`.
  `ini.edit()` changes one key of a foreign INI file and leaves a
  `.bak-lacquer` copy the first time. A module with its own Hyprland Lua file
  hooks it in with `hyprconf.hook()` (see `modules/cursor.py`).
- Module keys are relative (`decoration.rounding`); the section name is added
  by core (`windows.decoration.rounding`).
- Hyprland facts that shaped the code are in `PLAN.md` ("Facts probed").
  `hyprctl binds -j` does not report a bind's command, only its key.

## Testing

- `python -m py_compile lacquer/*.py lacquer/modules/*.py`, `ruff check .`
- Live tests change the owner's real desktop. Use values equal to the current
  ones, or small ones, and always end with `lacquer revert` / `lacquer unset`,
  then `lacquer status` (no preview) and `hyprctl configerrors` (empty).
- Test the timer with `--timeout 5` on `windows.decoration.dim_around 0.85`
  (risky by rule, invisible in practice).
- GTK/Qt tests: one step on `cursor.size` or `fonts.interface_size`, then
  revert; after it `dconf dump /org/gnome/desktop/interface/` and
  `~/.config/qt6ct/qt6ct.conf` must equal a copy taken before. The timer path
  is `toolkit.gtk_theme NoSuchTheme --timeout 5`.
- Remove test themes and snapshots afterwards (`~/.config/lacquer/themes`,
  `~/.local/state/lacquer/snapshots`).
- Noctalia tests: small steps on `bar.default.padding` or
  `shell.panel.floating_offset`; the clamp path is
  `bar.default.capsule_opacity 7`. A revert leaves the old value as an explicit
  line in `~/.local/state/noctalia/settings.toml` (Noctalia has no unset);
  that is expected.
