# ATML 1.1.0 — Installer

All installers place the same payload: `compiler/`, `runtime/`, `examples/`,
`vscode-atml/` syntax support, an `atml` launcher on PATH, and an optional
`.atml` file association.

Install locations:

| OS | Share | Bins (`atml` shim) |
|----|-------|--------------------|
| Linux | `~/.local/share/atml` | `~/.local/bin/atml` |
| macOS | `~/Library/Application Support/ATML` | `~/.local/bin/atml` |
| Windows | `%LOCALAPPDATA%\ATML` | `%LOCALAPPDATA%\ATML\bin\atml.bat` |

## Install matrix

| Distro/OS | Method | Command |
|-----------|--------|---------|
| Arch | GUI installer | `python3 installer/gui_installer.py` |
| Arch | PKGBUILD | `cd installer/arch && makepkg -si` (or `yay -S atml` once published) |
| Arch | shell script | `bash scripts/install.sh --yes` |
| Debian/Ubuntu | GUI installer | `python3 installer/gui_installer.py` |
| Debian/Ubuntu | .deb | stage `installer/debian/usr/...` next to `installer/debian/DEBIAN/control`, then `dpkg-deb --build installer/debian atml_1.1.0_all.deb && sudo dpkg -i atml_1.1.0_all.deb` |
| Debian/Ubuntu | shell script | `bash scripts/install.sh --yes` |
| Fedora | GUI installer | `python3 installer/gui_installer.py` |
| Fedora | .rpm | `rpmbuild -bb installer/fedora/atml.spec` then `sudo dnf install ~/rpmbuild/RPMS/noarch/atml-1.1.0-*.rpm` |
| Fedora | shell script | `bash scripts/install.sh --yes` |
| Windows | Inno Setup (recommended) | `iscc installer\windows\atml.iss`, run the produced `atml-1.1.0-setup.exe` |
| Windows | standalone GUI exe | `installer\windows\build-exe.bat` (PyInstaller onefile), run `dist\atml-setup-1.1.0.exe` |
| Windows | PowerShell | `powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Yes` |
| Any (git clone fallback) | headless/CI | `python3 installer/cli_install.py --only compiler,runtime,examples,vscode --editor vscode --prefix ~/.local --yes` |

Headless flags (`installer/cli_install.py`):

```
--list-editors   print editor detection table and exit
--only a,b,c     subset of: compiler,runtime,examples,vscode,fileassoc
--editor NAME    repeatable; default = all detected (vscode|cursor|jetbrains|devin)
--prefix DIR     install prefix (share = <prefix>/share/atml)
--uninstall      remove what the installer installed
--yes            required for install/uninstall (scripts/CI)
```

## Editor-connect table

| Editor | Detection | Connect behaviour |
|--------|-----------|-------------------|
| VS Code | `code --version`, `~/.vscode`, `/usr/bin/code` | `code --install-extension *.vsix` if a `.vsix` is present, else syntax-only copy to `~/.vscode/extensions/atml-1.1.0/` |
| Cursor | `cursor --version`, `~/.cursor`, `/usr/bin/cursor`, `/opt/cursor` | reuses the same `.vsix`/syntaxes payload via the `cursor` CLI / `~/.cursor/extensions/` |
| JetBrains | Toolbox `~/.local/share/JetBrains/Toolbox`, `~/Library/...`, `~/.config/JetBrains/*`, `/opt/*storm*`, `idea` bins | no marketplace plugin bundled: writes `jetbrains-filetypes-note.txt` (Settings → Editor → File Types → `*.atml`) + external-tool hint for `atml` |
| Devin Desktop | `~/Applications/Devin*`, `~/.devin*`, `devin` bin | no extension API: writes `devin-cli-note.txt` (CLI + open-as-text workflow) |

## Uninstall

| Method | Command |
|--------|---------|
| GUI | open the GUI → **Uninstall** (removes exactly the manifest-listed files) |
| CLI | `python3 installer/cli_install.py --uninstall --yes [--prefix ~/.local]` |
| Linux/macOS script | `bash scripts/uninstall.sh` |
| Arch | `sudo pacman -R atml` |
| Debian | `sudo dpkg -r atml` (or `sudo apt remove atml`) |
| Fedora | `sudo dnf remove atml` |
| Windows | Add/Remove Programs → ATML, or re-run the Inno uninstaller |

## Troubleshooting

- `tkinter` missing (GUI won't start, `py_compile` still passes):
  - Arch: `sudo pacman -S tk`
  - Debian/Ubuntu: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - Headless fallback: `python3 installer/cli_install.py --list-editors`
- `atml: command not found` after install: bins dir isn't on PATH.
  - Linux/macOS: `export PATH="$HOME/.local/bin:$PATH"`
  - Windows: `setx PATH "%PATH%;%LOCALAPPDATA%\ATML\bin"` then reopen the terminal.
- No `.vsix` found: expected until the extension is packaged; the installer
  falls back to syntax-only grammar copy and logs a note.
- `compiler/`, `runtime/`, `examples/` empty: this checkout hasn't landed
  those payloads yet; the installer creates marker dirs + shim and logs
  `(note)` lines instead of failing.
- No display (`TclError: couldn't connect to display`): use
  `python3 installer/cli_install.py --help`.
