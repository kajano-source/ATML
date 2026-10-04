#!/usr/bin/env bash
# ATML 1.1.1 installer for Linux (Arch / Debian / Fedora + generic).
# Usage:
#   bash scripts/install.sh [--yes] [--only compiler,runtime,examples,vscode,fileassoc]
#   PREFIX=~/.local bash scripts/install.sh
set -euo pipefail

ATML_VERSION="1.1.1"
PREFIX="${PREFIX:-$HOME/.local}"
SHARE="$PREFIX/share/atml"
BINDIR="$PREFIX/bin"
ONLY="${1:-}"
YES=0
for a in "$@"; do
  [ "$a" = "--yes" ] && YES=1
  case "$a" in --only=*) ONLY="${a#--only=}";; esac
done
ONLY="${ONLY:-compiler,runtime,examples,vscode,fileassoc}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

need() { command -v "$1" >/dev/null 2>&1; }

echo "ATML $ATML_VERSION installer (PREFIX=$PREFIX)"

# --- dependency check -------------------------------------------------------
if ! need python3; then
  echo "python3 not found. Install it first:"
  if need pacman; then echo "  sudo pacman -S python tk";
  elif need apt-get; then echo "  sudo apt install python3 python3-tk";
  elif need dnf; then echo "  sudo dnf install python3 python3-tkinter";
  fi
  exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "NOTE: python tkinter missing (GUI installer needs it)."
  echo "  Arch:   sudo pacman -S tk"
  echo "  Debian: sudo apt install python3-tk"
  echo "  Fedora: sudo dnf install python3-tkinter"
  echo "Continuing with headless install..."
fi

mkdir -p "$SHARE" "$BINDIR"

contains() { case ",$ONLY," in *",$1,"*) return 0;; *) return 1;; esac; }

copy_tree() { # src dst
  if [ -d "$1" ]; then
    if [ -n "$(ls -A "$1" 2>/dev/null)" ]; then
      mkdir -p "$2"; cp -r "$1/." "$2/"
      echo "copied $1 -> $2"
    else
      mkdir -p "$2"; echo "(note) $1 is empty, marker dir created"
    fi
  else
    echo "(skip) $1 not present"
  fi
}

if contains compiler; then
  echo "[compiler]"
  copy_tree "$ROOT/compiler" "$SHARE/compiler"
  cat > "$BINDIR/atml" <<EOF
#!/usr/bin/env bash
# ATML $ATML_VERSION shim -> $SHARE
ATML_SHARE="$SHARE"
if [ -f "\$ATML_SHARE/compiler/atml.py" ]; then
  exec python3 "\$ATML_SHARE/compiler/atml.py" "\$@"
else
  echo "ATML $ATML_VERSION (share: \$ATML_SHARE)" >&2
  ls "\$ATML_SHARE" >&2
fi
EOF
  chmod +x "$BINDIR/atml"
  echo "shim -> $BINDIR/atml"
fi
contains runtime  && { echo "[runtime]";  copy_tree "$ROOT/runtime"  "$SHARE/runtime"; }
contains examples && { echo "[examples]"; copy_tree "$ROOT/examples" "$SHARE/examples"; }

if contains vscode; then
  echo "[vscode-ext]"
  VSIX="$(ls "$ROOT"/vscode-atml/*.vsix "$ROOT"/*.vsix 2>/dev/null | head -n1 || true)"
  if [ -n "${VSIX:-}" ] && need code; then
    code --install-extension "$VSIX" || echo "(warn) code --install-extension failed"
  elif [ -d "$ROOT/vscode-atml/syntaxes" ] && [ -n "$(ls -A "$ROOT/vscode-atml/syntaxes" 2>/dev/null)" ]; then
    mkdir -p "$HOME/.vscode/extensions/atml-$ATML_VERSION"
    cp -r "$ROOT/vscode-atml/syntaxes/." "$HOME/.vscode/extensions/atml-$ATML_VERSION/"
    echo "syntax-only install -> ~/.vscode/extensions/atml-$ATML_VERSION"
  else
    echo "(note) no .vsix and no syntaxes payload yet; skipped"
  fi
fi

if contains fileassoc; then
  echo "[fileassoc]"
  mkdir -p "$HOME/.local/share/mime/packages" "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/mime/packages/atml.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="text/html-atml">
    <comment>ATML template</comment>
    <glob pattern="*.atml"/>
  </mime-type>
</mime-info>
EOF
  cat > "$HOME/.local/share/applications/atml.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ATML $ATML_VERSION
Exec=$BINDIR/atml %f
MimeType=text/html-atml;
Categories=Development;TextEditor;
Terminal=true
EOF
  need update-mime-database && update-mime-database "$HOME/.local/share/mime" || true
  need update-desktop-database && update-desktop-database "$HOME/.local/share/applications" || true
  need xdg-mime && xdg-mime default atml.desktop text/html-atml || true
fi

case ":$PATH:" in *":$BINDIR:"*) ;;
  *) echo "PATH hint: export PATH=\"$BINDIR:\$PATH\"" ;;
esac
echo "ATML $ATML_VERSION installed: share=$SHARE bin=$BINDIR"
