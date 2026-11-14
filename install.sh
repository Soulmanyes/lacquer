#!/bin/sh
# Installs Lacquer for the current user (and removes it with --uninstall):
# copies the app to ~/.local/share/lacquer, links `lacquer` into ~/.local/bin,
# then runs `lacquer install`, which hooks it into your Hyprland config and adds
# the launcher entry. Your look (~/.config/lacquer) is never touched, so
# reinstalling or updating keeps it. Run this again after changing the code in a clone.
# Without cloning the repo first (installs the latest release, or updates the installed copy):
#   curl -fsSL https://raw.githubusercontent.com/Soulmanyes/lacquer/master/install.sh | sh
# The whole script is one { } block, so a download cut off midway runs nothing.
{
set -eu

src="$(cd "$(dirname "$0")" && pwd)"
data="${XDG_DATA_HOME:-$HOME/.local/share}"
dest="$data/lacquer"
bin="$HOME/.local/bin/lacquer"
desktop="$data/applications/dev.lacquer.Lacquer.desktop"

# run through curl | sh: the app isn't next to the script, so download the latest
# release (master if there is none yet) and run its installer
if [ ! -f "$src/lacquer/core.py" ] && [ "${1:-}" != "--uninstall" ]; then
	command -v curl >/dev/null || { echo "Install curl first." >&2; exit 1; }
	tmp="$(mktemp -d)"
	trap 'rm -rf "$tmp"' EXIT
	echo "Downloading Lacquer"
	# releases/latest redirects to .../tag/<tag>
	tag="$(curl -fsSLo /dev/null -w '%{url_effective}' \
		https://github.com/Soulmanyes/lacquer/releases/latest | sed -n 's|.*/tag/||p')"
	ref="${tag:+tags/$tag}"
	curl -fsSL "https://github.com/Soulmanyes/lacquer/archive/refs/${ref:-heads/master}.tar.gz" |
		tar -xz -C "$tmp" --strip-components=1
	sh "$tmp/install.sh" "$@" < /dev/null
	exit
fi

# only a link into the installed copy is ours to remove or replace
ours() { [ -L "$bin" ] && [ "$(readlink "$bin")" = "$dest/bin/lacquer" ]; }

if [ "${1:-}" = "--uninstall" ]; then
	rm -rf "$dest" "$desktop"
	if ours; then rm -f "$bin"; fi
	echo "Removed $dest"
	echo "Your look stays in ${XDG_CONFIG_HOME:-$HOME/.config}/lacquer and your Hyprland config is unchanged."
	echo "See README.md for removing the lines Lacquer added."
	exit 0
fi

missing=""
if command -v python3 >/dev/null; then
	python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || missing="$missing  Python 3.11 or newer
"
else
	missing="$missing  python3
"
fi
command -v hyprctl >/dev/null || missing="$missing  hyprctl (Hyprland)
"
if [ -n "$missing" ]; then
	printf 'Missing:\n%s' "$missing" >&2
	exit 1
fi
python3 - <<'PY' 2>/dev/null || echo "No PyGObject with GTK 4 and libadwaita found: the \`lacquer\` command works, the window (\`lacquer gui\`) will not. On Arch: sudo pacman -S python-gobject gtk4 libadwaita"
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
PY

if [ "$src" != "$dest" ]; then
	echo "Installing Lacquer to $dest"
	mkdir -p "$dest"
	# no old modules left behind: every file in modules/, colortargets/ and gui/pages/ is loaded
	rm -rf "$dest/lacquer" "$dest/bin"
	cp -R "$src/lacquer" "$src/bin" "$dest/"
	cp "$src/install.sh" "$src/LICENSE" "$dest/"
	find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
fi
chmod +x "$dest/bin/lacquer" "$dest/install.sh"

if [ -e "$bin" ] || [ -L "$bin" ]; then
	if ! ours; then
		if [ -L "$bin" ]; then
			echo "$bin pointed to $(readlink "$bin"); it now points to the installed copy."
		else
			echo "$bin exists and is not a link to Lacquer. Move it away, then run this again." >&2
			exit 1
		fi
	fi
fi
mkdir -p "$(dirname "$bin")"
ln -sfn "$dest/bin/lacquer" "$bin"

# hooks Lacquer into hyprland.lua (dated backup first) and writes the launcher entry;
# does nothing where that is already done
if ! "$dest/bin/lacquer" install; then
	echo "Lacquer is in $dest, but hooking it into your setup failed (see above)." >&2
	echo "Fix that, then run: lacquer install" >&2
	exit 1
fi
echo "Installed. Run \`lacquer gui\` or open \"Lacquer\" from your launcher; \`lacquer doctor\` checks the setup."
# outside a Hyprland session the Hyprland sections are hidden, so nothing was hooked
[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] ||
	echo "Hyprland is not running here: run \`lacquer install\` once inside it to hook Lacquer into your config."
case ":$PATH:" in
	*":$HOME/.local/bin:"*) ;;
	*) echo "$HOME/.local/bin is not on your PATH: add it, or run $bin" ;;
esac
}
