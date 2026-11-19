#!/bin/sh
# Install citrine system-wide:
#   curl -fsSL https://raw.githubusercontent.com/RomanticTinkerer/citrine/main/install.sh | sudo sh
# Remove it again:
#   curl -fsSL https://raw.githubusercontent.com/RomanticTinkerer/citrine/main/install.sh | sudo sh -s -- --uninstall
#
# Puts a private Python environment in /opt/citrine and links `citrine` and `citrine-gui` into
# /usr/local/bin. It never touches your system Python packages.
# Testing without root: CITRINE_PREFIX=/tmp/x CITRINE_SRC=/path/to/checkout sh install.sh
set -eu

PREFIX="${CITRINE_PREFIX:-}"
SRC="${CITRINE_SRC:-https://github.com/RomanticTinkerer/citrine/archive/refs/heads/main.tar.gz}"
HOME_DIR="$PREFIX/opt/citrine"
BIN="$PREFIX/usr/local/bin"
APPS="$PREFIX/usr/share/applications"

say() { printf '%s\n' "citrine: $*"; }
die() { printf '%s\n' "citrine: $*" >&2; exit 1; }

[ -n "$PREFIX" ] || [ "$(id -u)" -eq 0 ] || die "run this as root: ... | sudo sh"

if [ "${1:-}" = "--uninstall" ]; then
  rm -rf "$HOME_DIR" "$BIN/citrine" "$BIN/citrine-gui" "$APPS/citrine.desktop"
  say "removed. Your downloaded games (CitrineData folders) were not touched."
  exit 0
fi

PY=""
for p in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY="$p"; break
  fi
done
[ -n "$PY" ] || die "needs Python 3.11 or newer (try: apt install python3 / dnf install python3 / pacman -S python)"

say "using $("$PY" --version)"
mkdir -p "$HOME_DIR" "$BIN" "$APPS"
# --system-site-packages lets the window find the system's PyGObject (GTK4); nothing else is shared
"$PY" -m venv --system-site-packages "$HOME_DIR" 2>/dev/null || die "could not create a virtual environment (try: apt install python3-venv)"
"$HOME_DIR/bin/pip" install --quiet --upgrade pip
say "installing citrine and its dependencies..."
"$HOME_DIR/bin/pip" install --quiet --upgrade "$SRC"

ln -sf "$HOME_DIR/bin/citrine" "$BIN/citrine"
ln -sf "$HOME_DIR/bin/citrine-gui" "$BIN/citrine-gui"
cat > "$APPS/citrine.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Citrine
Comment=Download chess games from Lichess and Chess.com
Exec=$BIN/citrine-gui
Icon=applications-games
Categories=Game;BoardGame;Utility;
Terminal=false
EOF

if ! "$HOME_DIR/bin/python" -c 'import gi; gi.require_version("Adw", "1")' 2>/dev/null; then
  say "the window (citrine-gui) needs GTK4 and libadwaita. The command line and terminal form work without them."
  say "  Debian/Ubuntu: apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
  say "  Fedora:        dnf install python3-gobject gtk4 libadwaita"
  say "  Arch:          pacman -S python-gobject gtk4 libadwaita"
fi

say "done. Try:  citrine --help   |   citrine --tui   |   citrine-gui"
