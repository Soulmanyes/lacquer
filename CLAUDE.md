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
- Palette engine: `palette.engine` is `noctalia` (Noctalia makes the colors)
  or `lacquer` (Lacquer makes them from `palette.seed`: `'#rrggbb'`,
  `wallpaper` or an image file). In `lacquer` mode one color is
  `palette.dark.<name>` / `palette.light.<name>` (`lacquer get palette.dark`
  lists them; `lacquer unset` gives the derived color back), and
  `palette.base <Noctalia palette name>` starts from an existing palette.
  Never edit `lacquer.css`, `Lacquer.colors`, `colors/lacquer.conf`,
  `palettes/Lacquer.json`, `lacquer_palette.lua` or
  `~/.local/state/lacquer/palette*.json`. GTK and KDE apps show new colors
  after a restart.
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
- `lacquer/core.py` is the only thing front-ends call (`cli.py` and the GTK
  window in `lacquer/gui/`). It returns plain dicts and raises `LacquerError`.
- The window (`lacquer gui [page]`, launcher entry from `lacquer install`)
  builds every section's page from `core.schema()` and `core.sections()`. A
  new area needs no GUI code: give the module `title` and `order`. Every
  setting shows; one that does nothing in the current state is hidden by an
  `applies` function in its page (`add_row`/`add_item`, see
  `gui/pages/palette.py`). A new value
  type is one class in `gui/rows.py` (`BY_TYPE`); a picker for a `Key.hint`
  (`image`, `font`) is one class in `BY_HINT`; a page that needs more than
  the generic one is one file in `gui/pages/` (see its `__init__.py`). Every
  core call from the window goes through `gui/worker.py` (one thread), except
  `core.status()` in the one-second poll.
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
- The `lacquer` palette engine: `palettegen.generate()` makes the palette,
  `modules/palette.py` plans the places, one file in `lacquer/colortargets/`
  per program that gets colors (exposes `TARGET`, see its `__init__.py`). A
  new program = one new file there.
- Module keys are relative (`decoration.rounding`); the section name is added
  by core (`windows.decoration.rounding`).
- Hyprland facts that shaped the code are in `PLAN.md` ("Facts probed").
  `hyprctl binds -j` does not report a bind's command, only its key.

## Testing

- `python -m py_compile lacquer/*.py lacquer/modules/*.py lacquer/gui/*.py lacquer/gui/pages/*.py`, `ruff check .`
- Window tests: launch with `LACQUER_APP_ID=dev.lacquer.Test lacquer gui
  <page>` through `ui-shot` (a wrapper script, so stderr lands in a file). A
  window on workspace 77 redraws rarely: wait about 10 s (or shoot twice)
  before trusting a screenshot. Clicks are not possible there, so drive the
  flows by code: a script that makes `gui.window.App`, changes
  `page.rows[key].widget` on GLib timeouts and prints `core.status()` (risky
  timer, revert, the clamp path, keep, unset; same safe keys as below).
- Live tests change the owner's real desktop. Use values equal to the current
  ones, or small ones, and always end with `lacquer revert` / `lacquer unset`,
  then `lacquer status` (no preview) and `hyprctl configerrors` (empty).
- Test the timer with `--timeout 5` on `windows.decoration.dim_around 0.85`
  (risky by rule, invisible in practice).
- GTK/Qt tests: one step on `cursor.size` or `fonts.interface_size`, then
  revert; after it `dconf dump /org/gnome/desktop/interface/` and
  `~/.config/qt6ct/qt6ct.conf` must equal a copy taken before. The timer path
  is `toolkit.gtk_theme NoSuchTheme --timeout 5`.
- Palette engine tests: never while a game is running (it reloads Hyprland
  and Noctalia). `lacquer set palette.engine lacquer`, look, `lacquer revert`;
  then `gtk.css`, `kdeglobals`, `qt6ct.conf` and `noctalia msg config-get
  theme` must equal copies taken before. For code-only checks run it in a
  sandbox: `env -i` with `XDG_CONFIG_HOME`, `XDG_STATE_HOME`,
  `XDG_RUNTIME_DIR`, `XDG_DATA_HOME` in a temp folder and a `PATH` holding
  only `python3` and `magick`.
- Remove test themes and snapshots afterwards (`~/.config/lacquer/themes`,
  `~/.local/state/lacquer/snapshots`).
- Noctalia tests: small steps on `bar.default.padding` or
  `shell.panel.floating_offset`; the clamp path is
  `bar.default.capsule_opacity 7`. A revert leaves the old value as an explicit
  line in `~/.local/state/noctalia/settings.toml` (Noctalia has no unset);
  that is expected.
