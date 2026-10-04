#!/usr/bin/env python3
"""ATML 1.1.1 GUI installer — Python standard library only (tkinter + ttk).

Run:
    python3 installer/gui_installer.py

Steps: Welcome -> Components -> Editor detection -> Install -> Finish.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TK = True
except ImportError:  # tkinter missing (e.g. minimal Arch install)
    HAS_TK = False
    tk = None  # type: ignore
    ttk = None  # type: ignore

ATML_VERSION = "1.1.1"
APP_TITLE = f"ATML {ATML_VERSION} Setup"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def repo_root() -> Path:
    """Repo root = parent of installer/ dir this file lives in."""
    here = Path(__file__).resolve()
    # .../atml/installer/gui_installer.py -> .../atml
    if here.parent.name == "installer":
        return here.parent.parent
    return Path.cwd()


def install_base(prefix: str | None = None) -> Path:
    """Per-OS share dir."""
    if prefix:
        return Path(prefix).expanduser() / "share" / "atml" \
            if Path(prefix).name != "atml" else Path(prefix).expanduser()
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        return Path(base) / "ATML"
    if system == "Darwin":
        return home / "Library" / "Application Support" / "ATML"
    # Linux / other Unix
    xdg = os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share"))
    return Path(xdg) / "atml"


def bin_dir(prefix: str | None = None) -> Path:
    system = platform.system()
    if prefix:
        p = Path(prefix).expanduser()
        # If prefix already points at the share dir, put bins next to it.
        if p.name == "atml":
            return p.parent.parent / "bin" if (p.parent.name == "share") else p / "bin"
        return p / "bin"
    home = Path.home()
    if system == "Windows":
        return install_base() / "bin"
    if system == "Darwin":
        return home / ".local" / "bin"
    return home / ".local" / "bin"


MANIFEST_NAME = "install-manifest.json"

# ---------------------------------------------------------------------------
# Editor detection (pure stdlib)
# ---------------------------------------------------------------------------

def _run_version(cmd: list[str], timeout: int = 8) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        text = (out.stdout or out.stderr or "").strip().splitlines()
        return text[0].strip()[:80] if text else ""
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return ""


def detect_vscode() -> dict:
    home = Path.home()
    exe = shutil.which("code") or shutil.which("code-insiders")
    candidates = [home / ".vscode", Path("/usr/bin/code"),
                  Path("/usr/local/bin/code")]
    found_path = exe or next((str(p) for p in candidates if p.exists()), "")
    version = _run_version([exe, "--version"]) if exe else ""
    if not version and exe:
        version = "found"
    detected = bool(exe or any(p.exists() for p in candidates))
    return {"id": "vscode", "name": "VS Code",
            "detected": detected, "version": version,
            "path": found_path or "(not found)"}


def detect_cursor() -> dict:
    home = Path.home()
    exe = shutil.which("cursor")
    candidates = [home / ".cursor", Path("/usr/bin/cursor"),
                  Path("/opt/cursor"), Path("/usr/local/bin/cursor")]
    found_path = exe or next((str(p) for p in candidates if p.exists()), "")
    version = _run_version([exe, "--version"]) if exe else ""
    detected = bool(exe or any(p.exists() for p in candidates))
    return {"id": "cursor", "name": "Cursor",
            "detected": detected, "version": version,
            "path": found_path or "(not found)"}


def detect_jetbrains() -> dict:
    home = Path.home()
    hits: list[str] = []
    toolbox = [
        home / ".local" / "share" / "JetBrains" / "Toolbox",
        home / "Library" / "Application Support" / "JetBrains" / "Toolbox",
        Path("/opt/jetbrains-toolbox"),
    ]
    for t in toolbox:
        if t.exists():
            hits.append(str(t))
    # Per-product config dirs: ~/.config/JetBrains/<Product><ver>
    cfg = home / ".config" / "JetBrains"
    if cfg.is_dir():
        for child in sorted(cfg.iterdir()):
            hits.append(str(child))
    # /opt/*storm*, /opt/idea*, ~/Library ...
    for pat in ("/opt/*storm*", "/opt/idea*", "/opt/pycharm*",
                str(home / ".local" / "share" / "JetBrains" / "*")):
        for g in glob.glob(pat):
            if g not in hits:
                hits.append(g)
    for b in ("idea", "webstorm", "pycharm", "phpstorm", "clion",
              "goland", "rider"):
        exe = shutil.which(b)
        if exe and exe not in hits:
            hits.append(f"{b}: {exe}")
    detected = bool(hits)
    return {"id": "jetbrains", "name": "JetBrains (IDEA/WebStorm/PyCharm…)",
            "detected": detected,
            "version": f"{len(hits)} location(s)" if hits else "",
            "path": "; ".join(hits[:3]) or "(not found)"}


def detect_devin() -> dict:
    home = Path.home()
    hits: list[str] = []
    exe = shutil.which("devin")
    if exe:
        hits.append(exe)
    for pat in (str(home / "Applications" / "Devin*"),
                str(home / ".devin*"),
                str(home / "Applications" / "devin*")):
        for g in glob.glob(pat):
            if g not in hits:
                hits.append(g)
    detected = bool(hits)
    version = _run_version([exe, "--version"]) if exe else ""
    return {"id": "devin", "name": "Devin Desktop",
            "detected": detected, "version": version,
            "path": "; ".join(hits[:3]) or "(not found)"}


def detect_all_editors() -> list[dict]:
    out = []
    for fn in (detect_vscode, detect_cursor, detect_jetbrains, detect_devin):
        try:
            out.append(fn())
        except Exception:  # never let one detector break the panel
            out.append({"id": fn.__name__, "name": fn.__name__,
                        "detected": False, "version": "error",
                        "path": "(detection error)"})
    return out

# ---------------------------------------------------------------------------
# Install engine (shared logic; also mirrored by cli_install.py)
# ---------------------------------------------------------------------------

COMPONENTS = ("compiler", "runtime", "examples", "vscode", "fileassoc")
EDITORS = ("vscode", "cursor", "jetbrains", "devin")


class InstallEngine:
    """Copies trees into the share dir, writes the `atml` shim,
    connects editors, registers .atml association.

    All installed files are recorded in install-manifest.json so
    uninstall() can remove exactly what was installed.
    """

    def __init__(self, root: Path | None = None, prefix: str | None = None,
                 log=None):
        self.root = Path(root or repo_root())
        self.share = install_base(prefix)
        self.bindir = bin_dir(prefix)
        self.installed: list[str] = []
        self._log = log or (lambda msg: print(msg, flush=True))

    # -- logging ------------------------------------------------------
    def log(self, msg: str) -> None:
        self._log(msg)

    # -- helpers ------------------------------------------------------
    def _record(self, path: Path) -> None:
        self.installed.append(str(path))

    def _copy_tree(self, src: Path, dst: Path) -> int:
        count = 0
        if not src.is_dir():
            self.log(f"  (skip) {src.name}/ not present in repo")
            return 0
        files = [p for p in src.rglob("*") if p.is_file()]
        if not files:
            self.log(f"  (note) {src.name}/ exists but is empty — "
                      "creating directory marker only")
            dst.mkdir(parents=True, exist_ok=True)
            self._record(dst)
            return 0
        for f in files:
            rel = f.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            self._record(target)
            count += 1
        self.log(f"  copied {src.name}/ -> {dst} ({count} files)")
        return count

    def _write_file(self, path: Path, content: str,
                    executable: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if executable and platform.system() != "Windows":
            mode = path.stat().st_mode | 0o111
            path.chmod(mode)
        self._record(path)

    # -- components ---------------------------------------------------
    def install_compiler(self) -> None:
        self.log("[compiler] ATML compiler CLI")
        self._copy_tree(self.root / "compiler", self.share / "compiler")
        self._install_shim()

    def install_runtime(self) -> None:
        self.log("[runtime] HTML converter runtime")
        self._copy_tree(self.root / "runtime", self.share / "runtime")

    def install_examples(self) -> None:
        self.log("[examples] Example projects")
        self._copy_tree(self.root / "examples", self.share / "examples")

    def _install_shim(self) -> None:
        """`atml` launcher on PATH pointing at the installed tree."""
        system = platform.system()
        if system == "Windows":
            shim = self.bindir / "atml.bat"
            content = (
                "@echo off\r\n"
                f"python \"%~dp0..\\compiler\\atml.py\" %*\r\n"
                f"rem ATML {ATML_VERSION} shim. Installed share: {self.share}\r\n"
            )
            self._write_file(shim, content)
            ps1 = self.bindir / "atml.ps1"
            self._write_file(ps1, (
                f"# ATML {ATML_VERSION} shim\n"
                f"$share = '{self.share}'\n"
                "python (Join-Path $share 'compiler\\atml.py') @args\n"
            ))
            self.log(f"  shim -> {shim} (+ atml.ps1). "
                     "Add to PATH: setx PATH \"%PATH%;"
                     f"{self.bindir}\"")
        else:
            shim = self.bindir / "atml"
            content = (
                "#!/usr/bin/env bash\n"
                f"# ATML {ATML_VERSION} shim -> {self.share}\n"
                f'ATML_SHARE="{self.share}"\n'
                'if [ -f "$ATML_SHARE/compiler/atml.py" ]; then\n'
                '  exec python3 "$ATML_SHARE/compiler/atml.py" "$@"\n'
                'elif [ -f "$ATML_SHARE/compiler/__main__.py" ]; then\n'
                '  exec python3 -m compiler "$@"\n'
                'else\n'
                f'  echo "ATML {ATML_VERSION} (share: $ATML_SHARE)" >&2\n'
                '  echo "compiler/ payload not bundled in this checkout; "\n'
                '  echo "share dir contents:" >&2; ls "$ATML_SHARE" >&2\n'
                '  exit 0\n'
                'fi\n'
            )
            self._write_file(shim, content, executable=True)
            self.log(f"  shim -> {shim}")
            self.log(f"  PATH hint: export PATH=\"{self.bindir}:$PATH\"")

    # -- VS Code extension --------------------------------------------
    def find_vsix(self) -> Path | None:
        for pat in ("vscode-atml/*.vsix", "*.vsix",
                    "installer/*.vsix", "dist/*.vsix"):
            hits = sorted(self.root.glob(pat))
            if hits:
                return hits[0]
        return None

    def install_vscode_ext(self, editors: list[str]) -> None:
        self.log("[vscode-ext] editor syntax support")
        vsix = self.find_vsix()
        src_syntax = self.root / "vscode-atml" / "syntaxes"
        for ed in editors:
            if ed in ("vscode", "cursor"):
                bin_name = "code" if ed == "vscode" else "cursor"
                ext_dir = (Path.home() / (".vscode" if ed == "vscode"
                                          else ".cursor") / "extensions"
                           / f"atml-{ATML_VERSION}")
                if vsix and shutil.which(bin_name):
                    self.log(f"  installing {vsix.name} via "
                             f"`{bin_name} --install-extension`")
                    try:
                        r = subprocess.run(
                            [bin_name, "--install-extension", str(vsix)],
                            capture_output=True, text=True, timeout=120)
                        self.log("  " + (r.stdout.strip() or r.stderr.strip()
                                          or "extension installed")[:300])
                    except (subprocess.SubprocessError, OSError) as e:
                        self.log(f"  (warn) {bin_name} install failed: {e}")
                else:
                    if src_syntax.is_dir() and any(src_syntax.iterdir()):
                        ext_dir.mkdir(parents=True, exist_ok=True)
                        n = 0
                        for f in src_syntax.rglob("*"):
                            if f.is_file():
                                t = ext_dir / f.relative_to(src_syntax)
                                t.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(f, t)
                                self._record(t)
                                n += 1
                        self.log(f"  syntax-only install for {ed}: "
                                 f"{n} grammar files -> {ext_dir} "
                                 "(no .vsix found / CLI missing)")
                    else:
                        self.log(f"  (note) {ed}: no .vsix and no "
                                 "vscode-atml/syntaxes payload yet — "
                                 "recorded intent only")
            elif ed == "jetbrains":
                note = self.share / "jetbrains-filetypes-note.txt"
                self._write_file(note, jetbrains_note())
                self.log("  JetBrains: no marketplace plugin bundled; wrote "
                         f"{note} (Settings > Editor > File Types > "
                         "ATML *.atml).")
            elif ed == "devin":
                note = self.share / "devin-cli-note.txt"
                self._write_file(note, devin_note())
                self.log("  Devin Desktop exposes no extension API; "
                         f"wrote {note} (CLI + syntax note).")

    # -- file association ----------------------------------------------
    def install_fileassoc(self) -> None:
        self.log("[fileassoc] .atml file association")
        system = platform.system()
        if system == "Windows":
            reg = self.share / "register-atml-filetype.bat"
            self._write_file(reg, (
                "@echo off\r\n"
                f"rem ATML {ATML_VERSION} .atml association (run as user)\r\n"
                f'ftype ATML.Document="{self.bindir}\\atml.bat" "%%1"\r\n'
                'assoc .atml=ATML.Document\r\n'
            ))
            self.log("  Windows assoc: run "
                     f"{reg} (ftype/assoc), or use the Inno installer "
                     "which does this automatically.")
        else:
            mime = (Path.home() / ".local" / "share" / "mime"
                    / "packages" / "atml.xml")
            mime.parent.mkdir(parents=True, exist_ok=True)
            mime.write_text(mime_xml(), encoding="utf-8")
            self._record(mime)
            desk = (Path.home() / ".local" / "share" / "applications"
                    / "atml.desktop")
            desk.parent.mkdir(parents=True, exist_ok=True)
            desk.write_text(desktop_entry(), encoding="utf-8")
            self._record(desk)
            self.log(f"  mime -> {mime}")
            self.log(f"  desktop -> {desk}")
            for cmd in (["update-mime-database",
                         str(Path.home() / ".local" / "share" / "mime")],
                        ["update-desktop-database",
                         str(Path.home() / ".local" / "share"
                             / "applications")],
                        ["xdg-mime", "default", "atml.desktop",
                         "text/html-atml"]):
                if shutil.which(cmd[0]):
                    try:
                        subprocess.run(cmd, capture_output=True, timeout=30)
                        self.log(f"  ran: {' '.join(cmd)}")
                    except (subprocess.SubprocessError, OSError) as e:
                        self.log(f"  (warn) {' '.join(cmd)}: {e}")

    # -- manifest / uninstall ------------------------------------------
    def write_manifest(self, components: list[str],
                       editors: list[str]) -> Path:
        self.share.mkdir(parents=True, exist_ok=True)
        mp = self.share / MANIFEST_NAME
        mp.write_text(json.dumps({
            "version": ATML_VERSION,
            "components": components,
            "editors": editors,
            "files": self.installed,
            "share": str(self.share),
            "bindir": str(self.bindir),
        }, indent=2), encoding="utf-8")
        return mp

    def run_install(self, components: list[str],
                    editors: list[str]) -> Path:
        self.log(f"ATML {ATML_VERSION} install: share={self.share}")
        self.share.mkdir(parents=True, exist_ok=True)
        self.bindir.mkdir(parents=True, exist_ok=True)
        if "compiler" in components:
            self.install_compiler()
        if "runtime" in components:
            self.install_runtime()
        if "examples" in components:
            self.install_examples()
        if "vscode" in components:
            self.install_vscode_ext(editors)
        if "fileassoc" in components:
            self.install_fileassoc()
        mp = self.write_manifest(components, editors)
        self.log(f"done. Manifest: {mp}")
        return mp

    def run_uninstall(self) -> None:
        mp = self.share / MANIFEST_NAME
        files: list[str] = list(self.installed)
        if mp.is_file():
            try:
                data = json.loads(mp.read_text(encoding="utf-8"))
                files = data.get("files", files)
            except (json.JSONDecodeError, OSError):
                pass
        # Remove deepest paths first.
        for f in sorted(set(files), key=len, reverse=True):
            p = Path(f)
            try:
                if p.is_file() or p.is_symlink():
                    p.unlink()
                    self.log(f"  removed {p}")
                elif p.is_dir():
                    try:
                        p.rmdir()  # only if empty (marker dirs)
                        self.log(f"  removed dir {p}")
                    except OSError:
                        pass
            except OSError as e:
                self.log(f"  (warn) {p}: {e}")
        # Drop now-empty share tree leaves.
        for d in (self.share / "compiler", self.share / "runtime",
                  self.share / "examples", self.share):
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
                    self.log(f"  removed dir {d}")
            except OSError:
                pass
        try:
            if mp.is_file():
                mp.unlink()
        except OSError:
            pass
        self.log("uninstall complete.")

# ---------------------------------------------------------------------------
# Static payload texts
# ---------------------------------------------------------------------------

def jetbrains_note() -> str:
    return (
        f"ATML {ATML_VERSION} — JetBrains setup\n"
        "=====================================\n"
        "No JetBrains marketplace plugin is bundled with this release.\n\n"
        "1. Settings/Preferences > Editor > File Types\n"
        "2. Add a new file type named 'ATML', syntax highlight HTML/XML,\n"
        "   registered patterns: *.atml\n"
        "3. Optional: map the `atml` CLI as an External Tool\n"
        "   (Settings > Tools > External Tools) pointing at\n"
        "   ~/.local/bin/atml (Linux/macOS) or %LOCALAPPDATA%\\ATML\\bin\n"
        "   (Windows).\n"
    )


def devin_note() -> str:
    return (
        f"ATML {ATML_VERSION} — Devin Desktop setup\n"
        "========================================\n"
        "Devin Desktop exposes no extension API, so ATML connects via CLI:\n\n"
        "1. Ensure ~/.local/bin is on PATH (installer shim `atml`).\n"
        "2. Open .atml files as text/HTML in Devin.\n"
        "3. Run `atml build <file.atml>` from the Devin terminal.\n"
    )


def mime_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
        '  <mime-type type="text/html-atml">\n'
        '    <comment>ATML template</comment>\n'
        '    <glob pattern="*.atml"/>\n'
        '  </mime-type>\n'
        '</mime-info>\n'
    )


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name=ATML {ATML_VERSION}\n"
        "Comment=ATML template compiler\n"
        f"Exec={bin_dir() / 'atml'} %f\n"
        "MimeType=text/html-atml;\n"
        "Categories=Development;TextEditor;\n"
        "Terminal=true\n"
    )

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

STEP_TITLES = ["Welcome", "Components", "Editors", "Install", "Finish"]


class InstallerGUI:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("720x560")
        self.root.minsize(640, 480)

        self.engine = InstallEngine(log=self._log_from_thread)
        self.step = 0

        # Component selection state.
        self.comp_vars = {c: tk.BooleanVar(value=True) for c in COMPONENTS}
        # Editor connect toggles (only enabled when detected).
        self.editor_vars = {e: tk.BooleanVar(value=(e == "vscode"))
                            for e in EDITORS}
        self.editor_info: list[dict] = []
        self.detected_map: dict[str, dict] = {}
        self.install_done = False

        self._build_chrome()
        self._build_frames()
        self.show_step(0)
        # Detect editors asynchronously so the window opens fast.
        threading.Thread(target=self._detect_in_background,
                         daemon=True).start()

    # -- chrome -------------------------------------------------------
    def _build_chrome(self) -> None:
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE,
                  font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Label(top, text="Python stdlib only · no downloads",
                  foreground="gray").pack(side="right")

        self.step_label = ttk.Label(self.root, text="", padding=(12, 0))
        self.step_label.pack(fill="x")

        nav = ttk.Frame(self.root, padding=12)
        nav.pack(side="bottom", fill="x")
        self.back_btn = ttk.Button(nav, text="< Back",
                                   command=self.on_back)
        self.back_btn.pack(side="left")
        self.next_btn = ttk.Button(nav, text="Next >",
                                   command=self.on_next)
        self.next_btn.pack(side="right")
        self.install_btn = ttk.Button(nav, text="Install",
                                      command=self.on_install)
        self.install_btn.pack(side="right", padx=6)
        self.uninstall_btn = ttk.Button(nav, text="Uninstall",
                                        command=self.on_uninstall)
        self.uninstall_btn.pack(side="right", padx=6)

    def _build_frames(self) -> None:
        self.container = ttk.Frame(self.root, padding=12)
        self.container.pack(fill="both", expand=True)
        self.frames: list[ttk.Frame] = []
        builders = [self._frame_welcome, self._frame_components,
                    self._frame_editors, self._frame_install,
                    self._frame_finish]
        for build in builders:
            f = ttk.Frame(self.container)
            f.grid(row=0, column=0, sticky="nsew")
            self.container.grid_rowconfigure(0, weight=1)
            self.container.grid_columnconfigure(0, weight=1)
            build(f)
            self.frames.append(f)

    # -- individual steps ---------------------------------------------
    def _frame_welcome(self, f: ttk.Frame) -> None:
        ttk.Label(f, wraplength=640, justify="left", text=(
            f"Welcome to the ATML {ATML_VERSION} installer.\n\n"
            "This wizard installs the ATML compiler CLI, the HTML "
            "converter runtime, example projects, editor support, and "
            "an optional .atml file association.\n\n"
            f"Install location:\n  share: {self.engine.share}\n"
            f"  bins:  {self.engine.bindir}\n\n"
            "Click Next to choose components. Nothing is installed "
            "until you press Install."
        )).pack(anchor="w")

    def _frame_components(self, f: ttk.Frame) -> None:
        ttk.Label(f, text="Select components to install:").pack(anchor="w")
        descs = {
            "compiler": "ATML compiler CLI (`atml` on PATH)",
            "runtime": "HTML converter runtime",
            "examples": "Example projects",
            "vscode": "Editor support (.vsix if present, else syntax-only)",
            "fileassoc": "File association for .atml files",
        }
        for c in COMPONENTS:
            ttk.Checkbutton(f, text=f"{c} — {descs[c]}",
                            variable=self.comp_vars[c]).pack(anchor="w",
                                                             pady=2)

    def _frame_editors(self, f: ttk.Frame) -> None:
        ttk.Label(f, wraplength=640, justify="left", text=(
            "Editor auto-detection. Tick Connect for each editor to wire "
            "up ATML support (VS Code/Cursor get the .vsix when present, "
            "JetBrains gets a file-types note, Devin gets CLI notes)."
        )).pack(anchor="w", pady=(0, 8))
        self.editor_rows = ttk.Frame(f)
        self.editor_rows.pack(fill="x")
        self.editor_status = ttk.Label(f, text="Detecting editors…",
                                       foreground="gray")
        self.editor_status.pack(anchor="w", pady=6)
        ttk.Button(f, text="Re-detect",
                   command=self._redetect).pack(anchor="w")

    def _frame_install(self, f: ttk.Frame) -> None:
        ttk.Label(f, text="Install log:").pack(anchor="w")
        self.log_text = tk.Text(f, height=16, wrap="word",
                                state="disabled")
        scroll = ttk.Scrollbar(f, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.progress = ttk.Progressbar(f, mode="indeterminate")
        self.progress.pack(fill="x", pady=8)
        self.path_hint = ttk.Label(f, foreground="gray", wraplength=640,
                                   text=path_hint_text(self.engine.bindir))
        self.path_hint.pack(anchor="w")

    def _frame_finish(self, f: ttk.Frame) -> None:
        self.finish_label = ttk.Label(f, wraplength=640, justify="left",
                                      text="Not installed yet.")
        self.finish_label.pack(anchor="w")

    # -- navigation ---------------------------------------------------
    def show_step(self, i: int) -> None:
        self.step = max(0, min(i, len(self.frames) - 1))
        self.frames[self.step].tkraise()
        self.step_label.configure(
            text=f"Step {self.step + 1} of {len(self.frames)}: "
                 f"{STEP_TITLES[self.step]}")
        self.back_btn.configure(state="normal" if self.step > 0
                                else "disabled")
        self.next_btn.configure(state="normal" if self.step < len(self.frames) - 1
                                else "disabled")

    def on_back(self) -> None:
        self.show_step(self.step - 1)

    def on_next(self) -> None:
        self.show_step(self.step + 1)

    def selected_components(self) -> list[str]:
        return [c for c in COMPONENTS if self.comp_vars[c].get()]

    def selected_editors(self) -> list[str]:
        return [e for e in EDITORS if self.editor_vars[e].get()]

    # -- editor detection ----------------------------------------------
    def _detect_in_background(self) -> None:
        infos = detect_all_editors()
        self.root.after(0, lambda: self._render_editors(infos))

    def _redetect(self) -> None:
        self.editor_status.configure(text="Detecting editors…")
        threading.Thread(target=self._detect_in_background,
                         daemon=True).start()

    def _render_editors(self, infos: list[dict]) -> None:
        for child in self.editor_rows.winfo_children():
            child.destroy()
        self.editor_info = infos
        self.detected_map = {d["id"]: d for d in infos}
        for d in infos:
            eid = d["id"]
            mark = "✓ detected" if d["detected"] else "✗ not found"
            row = ttk.Frame(self.editor_rows)
            row.pack(fill="x", pady=2)
            cb = ttk.Checkbutton(row, text=f"{d['name']}: {mark}",
                                 variable=self.editor_vars.get(
                                     eid, tk.BooleanVar(value=False)))
            if eid not in self.editor_vars:
                self.editor_vars[eid] = tk.BooleanVar(value=False)
            if not d["detected"]:
                cb.configure(state="disabled")
            cb.pack(side="left")
            detail = f"{d.get('version', '')} {d.get('path', '')}".strip()[:110]
            ttk.Label(row, text=detail, foreground="gray").pack(side="left",
                                                                padx=8)
        n = sum(1 for d in infos if d["detected"])
        self.editor_status.configure(
            text=f"{n} of {len(infos)} editors detected.")

    # -- logging --------------------------------------------------------
    def _log_from_thread(self, msg: str) -> None:
        self.root.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg: str) -> None:
        if not hasattr(self, "log_text"):
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # -- install / uninstall ---------------------------------------------
    def on_install(self) -> None:
        comps = self.selected_components()
        eds = self.selected_editors()
        if not comps:
            messagebox.showinfo(APP_TITLE, "Select at least one component.")
            return
        self.show_step(3)
        self.progress.start(12)
        self.install_btn.configure(state="disabled")
        threading.Thread(target=self._install_worker,
                         args=(comps, eds), daemon=True).start()

    def _install_worker(self, comps: list[str], eds: list[str]) -> None:
        try:
            if "vscode" in comps and not eds:
                self.engine.log("(note) editor support selected but no "
                                "editor ticked — writing generic notes.")
            mp = self.engine.run_install(comps, eds)
            self.install_done = True
            self.root.after(0, lambda: self.finish_label.configure(text=(
                f"ATML {ATML_VERSION} installed.\n\nManifest: {mp}\n"
                f"Share: {self.engine.share}\nBins: {self.engine.bindir}\n\n"
                + path_hint_text(self.engine.bindir))))
            self.root.after(0, lambda: self.show_step(4))
        except Exception:
            self.engine.log("INSTALL FAILED:\n" + traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror(
                APP_TITLE, "Install failed — see the log pane."))
        finally:
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.install_btn.configure(
                state="normal"))

    def on_uninstall(self) -> None:
        if not messagebox.askyesno(APP_TITLE,
                                   "Remove everything this installer "
                                   "installed?"):
            return
        self.show_step(3)
        self.progress.start(12)
        threading.Thread(target=self._uninstall_worker, daemon=True).start()

    def _uninstall_worker(self) -> None:
        try:
            self.engine.run_uninstall()
            self.install_done = False
            self.root.after(0, lambda: self.finish_label.configure(
                text="ATML has been uninstalled (installer payloads "
                     "removed)."))
            self.root.after(0, lambda: self.show_step(4))
        except Exception:
            self.engine.log("UNINSTALL FAILED:\n" + traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.progress.stop())


def path_hint_text(bindir: Path) -> str:
    system = platform.system()
    if system == "Windows":
        return (f"If `atml` is not on PATH, run: setx PATH "
                f"\"%PATH%;{bindir}\"")
    return (f"If `atml` is not found, add to PATH: "
            f"export PATH=\"{bindir}:$PATH\"")


def main(argv: list[str] | None = None) -> int:
    if not HAS_TK:
        print("ERROR: tkinter is not available in this Python.", file=sys.stderr)
        print("Install it, then re-run: python3 installer/gui_installer.py",
              file=sys.stderr)
        print("  Arch:   sudo pacman -S tk", file=sys.stderr)
        print("  Debian: sudo apt install python3-tk", file=sys.stderr)
        print("  Fedora: sudo dnf install python3-tkinter", file=sys.stderr)
        print("Headless alternative: python3 installer/cli_install.py --help",
              file=sys.stderr)
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(f"ERROR: cannot open display: {e}", file=sys.stderr)
        print("Run headless instead: python3 installer/cli_install.py --help",
              file=sys.stderr)
        return 1
    InstallerGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
