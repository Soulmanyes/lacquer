# Lacquer plan

Desktop look customiser for Hyprland (and Noctalia when present). Sibling of
Shellac, but Lacquer never styles terminals or individual apps: it covers
"everything else". Private repo until it works; standalone now, may merge into
hypr-dashboard later.

## Decisions (owner, 2026-11-13)

- **Core first, GUI on top.** One declarative theme file (TOML) is the source of
  truth. A CLI (`lacquer`) with JSON output does get / set / preview / keep /
  revert / apply / snapshot. The GTK4/libadwaita GUI (Python, same stack as
  hypr-dashboard) is a thin front-end over the same core.
- **Areas:** Hyprland look, Noctalia theme, system palette, GTK/Qt + icons +
  cursor + fonts, wallpaper. Each area is a module. Modules for things that
  are not installed hide themselves ("only when applicable").
- **Palette works with and without Noctalia.** `palette.engine = "noctalia" | "lacquer"`.
  Exactly one writer per target: in `lacquer` mode, Noctalia templates for the
  targets Lacquer writes are turned off, or the two fight (except `hyprland`,
  see Status: there Lacquer's file is loaded later and wins). Lacquer never
  touches Noctalia's kitty/alacritty/btop templates (terminals/apps are out of
  scope; Shellac can read the palette).
- **Apply flow:** live preview, manual Keep / Revert. Only risky settings (list
  below) get a 15 s auto-revert timer. A fixed keybind runs `lacquer revert`
  blind.
- **Themes:** one whole-look file per theme, made of self-contained sections
  (`[palette]`, `[windows]`, `[bar]`, `[toolkit]`, `[cursor]`, `[fonts]`,
  `[wallpaper]`). "Take the palette from theme X" = copy one section.
- **Name:** Lacquer, `~/claude/lacquer`, CLI `lacquer`.

## Risky settings (auto-revert timer)

Ones that can leave you unable to see or click Revert:

- `decoration:screen_shader` (can black out the screen)
- `decoration:active_opacity` / `inactive_opacity` / `fullscreen_opacity` near 0
- `decoration:dim_strength` near 1 with dim on
- cursor theme missing/broken, cursor size very small or 0
- GTK font size tiny or huge, broken GTK theme (the GUI's own dialog)
- animation speeds so slow the desktop is unusable
- heavy blur/shadow (`blur:passes`, `blur:size`, shadow range): iGPU hang history

Ugly-but-usable settings (colors, gaps, rounding, borders, wallpaper, bar) have
no timer. A Hyprland crash during a preview reverts by itself, because a
preview never writes the saved config.

## Facts probed (2026-11-13)

- Hyprland 0.57.1 (held), Lua config. `hyprctl keyword` is gone ("unknown
  request"). Live set: `hyprctl eval 'hl.config({general={gaps_in=6}})'` works.
  `hyprctl reload` re-runs the saved Lua and undoes it (tested, gaps back to 1).
- Hyprland accepts out-of-range values: Lacquer validates type/min/max itself
  from `hyprctl descriptions -j` + `getoption` (socket code reused from
  hypr-dashboard `hypr.py`, credited).
- `hyprland.lua` order: config.* ... `require("noctalia").apply_theme()` ...
  `require("config.dashboard_options")` last.
- Noctalia config is `~/.config/noctalia/config.toml`; `[theme]` has
  `mode`, `source = "wallpaper"`, `wallpaper_scheme`, `templates.builtin_ids`.
  Custom palettes in `~/.config/noctalia/palettes/`. `noctalia msg` has
  `config-get/config-set/config-reload`, `color-scheme-get/set`,
  `theme-mode-get/set`, `templates-apply`, `wallpaper-get/set`. These persist
  immediately (no live-only mode).
- Installed: gsettings, nwg-look, qt6ct. Not installed: matugen, wallust, pywal.

## Design

### Module interface

Each theme section maps 1:1 to a module with:

- `detect()`: is the target installed? (hides the module if not)
- `schema()`: keys, types, ranges, which keys are risky
- `read()`: current saved values
- `preview(values)`: show live
- `keep()`: write to saved config
- `revert()`: restore what was there before the preview

Adding an area = adding one module file. No other code changes.

### Preview / revert per target

- **Hyprland:** preview = `hyprctl eval`; revert = `hyprctl reload`; keep =
  write `~/.config/hypr/config/lacquer.lua`.
- **Persistent targets** (gsettings, Noctalia `config-set`, wallpaper): before
  a preview, save old values to `$XDG_RUNTIME_DIR/lacquer/preview.json`;
  revert restores from that file. The file survives a GUI crash, so
  `lacquer revert` still works.
- **Cursor:** preview with `hyprctl setcursor`, never `hl.env` (removing an env
  and reloading does not unset it). Env vars + gsettings only on keep.
- **Timer:** a detached process (not the GUI), so the revert still happens if
  the GUI dies.
- **Revert keybind:** lives in saved config, so a preview can never remove
  it. Runs the CLI only (no GUI or Noctalia needed). Key picked with the
  owner after checking `hyprctl binds -j` (Super+= is taken).

### Saved Hyprland file

`~/.config/hypr/config/lacquer.lua`, required from `hyprland.lua`
(back up `hyprland.lua` first; `~/.config/hypr` has no git). Placed after
`apply_theme()` so Lacquer border colors win in `lacquer` palette mode, and
before `dashboard_options`.

**Known issue until merge:** hypr-dashboard's `dashboard_options` loads later,
so any look option it also sets (gaps, rounding, ...) overrides Lacquer
silently. Phase 1 has `lacquer doctor` list those overlaps.

### Files

- Themes: `~/.config/lacquer/themes/<name>.toml`; current: `~/.config/lacquer/current.toml`
- Snapshots: `~/.local/state/lacquer/snapshots/<timestamp>.toml` (every keep)
- Preview state: `$XDG_RUNTIME_DIR/lacquer/`

### How Claude uses it

`lacquer get --json`, `lacquer set windows.rounding 12 --preview`,
screenshot check on the owner's screen, then `keep` or `revert`. Documented in
the project CLAUDE.md, plus a memory pointer, so future sessions use the CLI
instead of editing configs by hand.

## Phases (owner may reorder)

1. **Core + Hyprland module.** Theme TOML, CLI (JSON), validation,
   preview/keep/revert, snapshots, risky timer, revert keybind, `doctor`.
   Claude can drive the look from here on.
2. **Noctalia module.** Bar/theme via `noctalia msg`, palette engine
   `noctalia`, wallpaper.
3. **Toolkit module.** GTK3/4 (gsettings), Qt (qt6ct), icons, cursor, fonts.
4. **Own palette engine** (`lacquer` mode, no Noctalia): pick generator
   (matugen vs Python), write GTK/Qt/Hyprland colors, export for Shellac.
5. **GUI.** GTK4/libadwaita, sections per module, Keep/Revert bar.
6. Later: go public (`/go-public lacquer`), merge talk with hypr-dashboard.

## Status

- **Phase 1 done (2026-11-13).** `lacquer install` ran: `hyprland.lua` loads
  `config.lacquer` (backup `hyprland.lua.bak-2026-11-13`), `~/.local/bin/lacquer`
  links to `bin/lacquer`. Revert key: Super+Backspace. Private repo
  Soulmanyes/lacquer.
- Phase 1 choices that differ from the sketch above:
  - Keys are Hyprland option names with dots (`windows.decoration.rounding`,
    not `windows.rounding`), so the schema comes straight from
    `hyprctl descriptions -j` and new Hyprland options show up by themselves.
  - `lacquer set` previews by default; `--keep` saves in one step and is
    refused for risky values.
  - The `[windows]` section covers `decoration:*`, the look part of
    `general:` (gaps, border size, colors), group colors, the groupbar and
    `animations:enabled`. Animation curves and speeds (`hl.animation`) are not
    options, so they are not in Phase 1; they need their own module.
  - Pressing the revert key with no preview on record does nothing
    (`lacquer revert --force` reloads anyway).

- **Phase 2 done (2026-11-13).** Four sections through `noctalia msg`:
  `[bar]` (look of every bar, keys `<bar>.<setting>`), `[shell]` (corner
  radius, font, borders, shadows, animation, panel look, screen corners),
  `[palette]` (`engine = "noctalia"` only, plus mode/source/palette names),
  `[wallpaper]` (`default`, `monitors.<output>`, fill and transition).
  Owner's scope choices: all three areas; bar + shell look, no per-widget
  look, no widget order.
- Phase 2 choices that differ from the sketch above:
  - Old values of persistent targets are in
    `$XDG_RUNTIME_DIR/lacquer/old/<module>.json` (one file per module), not in
    `preview.json`: core clears `preview.json` before it calls a module's
    revert. `lacquer/persistent.py` is the shared base (toolkit module next).
  - Noctalia gives no ranges or choices, so the schema has types only and
    Noctalia validates on write. It clamps silently, so a preview reads the
    value back and fails (and reverts) when it differs.
  - Everything goes through `config-set` (it applies the theme and runs the
    templates too); `color-scheme-set` / `theme-mode-set` are not needed.
  - Each `config-set` reloads Noctalia's config and plugins, so values already
    live are skipped.

- **Phase 3 done (2026-11-13).** Three sections: `[toolkit]` (`gtk_theme`,
  `icon_theme`, `qt_style`), `[cursor]` (`theme`, `size`), `[fonts]`
  (`interface`, `document`, `monospace`, each with `_size`). Owner's scope
  choices: that core set (no text scaling, antialiasing or hinting); Qt through
  qt6ct only; on keep one value goes everywhere.
- Phase 3 facts and choices:
  - gsettings is what GTK apps on Wayland use. The settings.ini files are a
    fallback (XWayland, sandboxed apps) and were stale; keep copies kept values
    into them. First change to a foreign file leaves `<file>.bak-lacquer`.
  - One Lacquer key lands in several places that can disagree (icons:
    gsettings and `qt6ct.conf`). `lacquer/places.py` names each place
    (`gsettings:icon-theme`, `qt6ct:Appearance/icon_theme`); a preview stores
    the old value per place, so revert is exact (a key that was absent is
    removed again).
  - Cursor preview also sets gsettings, not only `hyprctl setcursor`: GTK apps
    draw their own cursor from it, and Hyprland syncs it anyway
    (`cursor:sync_gsettings_theme`). Only the env vars wait for keep. They are
    in `~/.config/hypr/config/lacquer_cursor.lua` (own file: the windows module
    rewrites `lacquer.lua` whole), hooked into `hyprland.lua` on the first
    cursor keep. They reach apps started after the next login.
  - qt6ct 0.11 stores fonts as QFont strings (`[Fonts] general`, `fixed`);
    Lacquer writes the 16-field form, checked with QFont.fromString on Qt 6.12.
  - Missing icon theme or font is refused (a typo, not a risk). Missing GTK or
    cursor theme and extreme sizes are risky (timer).
  - The owner's current cursor, GTK theme, Qt style and fonts were kept
    through Lacquer the same day. Icons were split (gsettings named
    Papirus-Dark, not installed; qt6ct had breeze): the owner picked
    breeze-dark for both.

- **Phase 4 done (2026-11-14), live-tested and in use.** `palette.engine =
  "lacquer"` with `palette.seed` (`#rrggbb`, `wallpaper` or an image file),
  `palette.base` (a Noctalia custom palette to start from) and one key per
  color (`palette.dark.primary`, `palette.light.terminal.red`). Tested in a
  sandbox without Noctalia, Hyprland and gsettings (set, revert, keep, unset,
  switch back) and on the real desktop as a preview (engine switch, one picked
  color, a seed change, revert: `gtk.css`, `kdeglobals`, `qt6ct.conf`,
  `hyprland.lua`, `noctalia.lua` and Noctalia's settings came back identical).
  The owner's desktop runs on the `lacquer` engine since then (kept, default
  seed `#b48cf0`; `hyprland.lua` loads `config.lacquer_palette`, backup
  `hyprland.lua.bak-2026-11-14`).
- Phase 4 facts and choices:
  - Generator is Lacquer's own Python (`palettegen.py`, OKLCH, Material
    "tonal spot" shape), not matugen: no dependency, and matugen is not
    installed. An image seed needs ImageMagick.
  - One file per color target in `lacquer/colortargets/` (`gtk`, `qt`, `kde`,
    `hyprland`, `shell`, `export`). A target returns places, so preview and
    revert are the same code as the toolkit module.
  - With Noctalia running, Lacquer hands it the palette as the custom palette
    `Lacquer` and turns off the Noctalia templates its own targets replace
    (`gtk3`, `gtk4`, `kcolorscheme`, `qt`). Noctalia's `hyprland` template
    stays on: turning it off makes Noctalia delete `~/.config/hypr/noctalia.lua`
    and its require line (the owner's `decorations.lua` reads
    `require("noctalia").colors`), and turning it on again appends the require
    at the end of `hyprland.lua`, after `config.lacquer`. Noctalia's other
    templates (kitty, btop, ...) keep running from Lacquer's palette. What was
    there before is in the engine file (`handover`) and comes back when the
    engine is `noctalia` again.
  - The engine's state is `~/.local/state/lacquer/palette-engine.json`. Seed,
    base and picked colors stay in it while the engine is `noctalia`.
  - `palette.source` / `palette.custom_palette` set while the engine is
    `lacquer` are held back and used when the engine goes back to `noctalia`.
  - Shellac export: `~/.local/state/lacquer/palette.json` (format in
    `colortargets/export.py`). Shellac does not read it yet.
  - Hyprland colors are in `config/lacquer_palette.lua`, loaded before
    `config.lacquer`, so a border color kept in `[windows]` still wins.
  - Known gap: a dark/light switch made in Noctalia's own UI does not re-run
    Lacquer's targets (Hyprland, GTK, Qt, KDE keep the old mode's colors until
    the next `lacquer set palette...`).

- **Phase 5 done (2026-11-14), not used by the owner yet.** `lacquer gui
  [page]` opens a GTK4/libadwaita window (launcher entry "Lacquer" from
  `lacquer install`). Owner's choice: every section gets a page showing every
  setting (2026-11-14: the `common` lists and "Show all settings" switch are
  gone); only settings that do nothing in the current state are hidden.
  - Pages are built from `core.schema()`; rows by value type
    (`gui/rows.py`), with pickers for `Key.hint` `image` and `font`.
  - Palette page: engine, mode, seed (color, wallpaper or image), base, and
    the palette as swatches. Themes page: save, preview a theme or snapshot.
  - A change previews after 250 ms. The bar at the bottom shows the count,
    the risky countdown, Revert and Keep. A row shows a `preview` pill and,
    when Lacquer keeps the key, an undo arrow (`unset`). A preview that ends
    outside the window (timer, Super+Backspace, CLI) is noticed within a
    second. Closing with a preview running asks Keep / Revert / Cancel.
  - Tested by code on the real window (risky timer, revert, clamp error,
    timer expiry, keep, unset) and by screenshot (palette, windows, themes).
    Not tested: real mouse clicks, the color/font/file dialogs, the
    close dialog, bar/shell/wallpaper/fonts pages by eye.
  - Search box in the header (2026-11-14, Ctrl+F): filters all section pages,
    pages without a match leave the sidebar. A key whose switch is off
    (`needs`: `enabled` of its table, `capsule` for the bar's capsule keys)
    is hidden, but a search still finds it. The settings of a blur variant
    (`decoration.blur.water.*`, ...) show only while `decoration.blur.variant`
    is that variant; `glass.*` shows for frost, drops, prism, heat_shimmer
    and aurora, which all read it.
  - Deleting a theme (2026-11-14): `lacquer theme delete <name>`, and a bin
    button on the Themes page that asks first (no undo; snapshots can not be
    deleted). Health page: the `doctor` findings, problems first, read at
    start, after every keep or revert and on "Check again"; the sidebar
    shows the count ("Health (2)"). Tested by code on the real window and by
    screenshot with made-up findings; the delete question itself was not
    seen (it did not draw on workspace 77).
- The Noctalia community template `papirus-icons` is off since 2026-11-14
  (it set an icon theme that is not installed on every template run).
  Turning the last community template with GTK parts off makes Noctalia
  delete `noctalia-extensions.css`; `lacquer.css` then imports a missing file
  until the next palette write (any `lacquer set palette...` fixes it).

## Open questions

- Follow a dark/light switch made in Noctalia (hook or watcher) in `lacquer` mode.
- Shellac reading `palette.json`.
- Animations module (curves, speeds): which phase?
