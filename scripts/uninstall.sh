#!/usr/bin/env bash
# ATML 1.1.1 uninstaller for Linux/macOS. Removes what the installer installed.
set -euo pipefail
PREFIX="${PREFIX:-$HOME/.local}"
SHARE="$PREFIX/share/atml"
BINDIR="$PREFIX/bin"
echo "Uninstalling ATML (SHARE=$SHARE BINDIR=$BINDIR)"
rm -f "$BINDIR/atml"
rm -rf "$SHARE"
rm -f "$HOME/.local/share/mime/packages/atml.xml" \
      "$HOME/.local/share/applications/atml.desktop"
rm -rf "$HOME/.vscode/extensions/atml-"* 2>/dev/null || true
command -v update-mime-database >/dev/null && update-mime-database "$HOME/.local/share/mime" || true
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" || true
echo "Uninstall complete."
