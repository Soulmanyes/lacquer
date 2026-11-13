# CLAUDE.md

Lacquer is the owner's desktop look customiser (Hyprland now; Noctalia, GTK/Qt,
cursor, fonts, wallpaper in later phases). `PLAN.md` is the spec: read it before
adding a phase.

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
- Remove test themes and snapshots afterwards (`~/.config/lacquer/themes`,
  `~/.local/state/lacquer/snapshots`).
