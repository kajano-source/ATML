#!/usr/bin/env python3
"""ATML 1.0.0 headless installer — twin of gui_installer.py for scripts/CI.

Examples:
    python3 installer/cli_install.py --list-editors
    python3 installer/cli_install.py --only compiler,runtime,examples,vscode \\
        --editor vscode --prefix ~/.local --yes
    python3 installer/cli_install.py --uninstall --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gui_installer import (  # noqa: E402
    ATML_VERSION,
    COMPONENTS,
    EDITORS,
    InstallEngine,
    bin_dir,
    detect_all_editors,
    install_base,
)

VALID_ONLY = ("compiler", "runtime", "examples", "vscode", "fileassoc")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="cli_install.py",
        description=f"ATML {ATML_VERSION} headless installer")
    p.add_argument("--list-editors", action="store_true",
                   help="print editor detection table and exit")
    p.add_argument("--only", default=",".join(VALID_ONLY),
                   help="comma list subset of: " + ",".join(VALID_ONLY))
    p.add_argument("--editor", action="append", default=[],
                   help="editor to connect (repeatable); default: all "
                        "detected. Choices: " + ",".join(EDITORS))
    p.add_argument("--prefix", default=None,
                   help="install prefix (default per-OS: "
                        "~/.local on Linux, %%LOCALAPPDATA%%/ATML on "
                        "Windows). Share= <prefix>/share/atml.")
    p.add_argument("--uninstall", action="store_true",
                   help="remove what the installer installed")
    p.add_argument("--yes", action="store_true",
                   help="non-interactive (required for install/uninstall)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.list_editors:
        rows = detect_all_editors()
        print(f"{'editor':<10}{'detected':<10}{'version':<24}path")
        for d in rows:
            print(f"{d['id']:<10}{str(d['detected']):<10}"
                  f"{d.get('version', ''):<24}{d.get('path', '')}")
        return 0

    only = [c.strip().lower() for c in args.only.split(",") if c.strip()]
    bad = [c for c in only if c not in VALID_ONLY]
    if bad:
        print(f"ERROR: unknown component(s): {bad}. Valid: {VALID_ONLY}",
              file=sys.stderr)
        return 2
    editors = [e.strip().lower() for e in args.editor if e.strip()]
    bad_e = [e for e in editors if e not in EDITORS]
    if bad_e:
        print(f"ERROR: unknown editor(s): {bad_e}. Valid: {EDITORS}",
              file=sys.stderr)
        return 2
    if not editors:
        # Default: connect every detected editor.
        editors = [d["id"] for d in detect_all_editors()
                   if d["detected"] and d["id"] in EDITORS]

    engine = InstallEngine(prefix=args.prefix)
    if args.uninstall:
        if not args.yes:
            print("Refusing to uninstall without --yes.", file=sys.stderr)
            return 2
        print(f"Uninstalling ATML {ATML_VERSION} "
              f"(share={install_base(args.prefix)}, "
              f"bin={bin_dir(args.prefix)})")
        engine.run_uninstall()
        print("Uninstall complete.")
        return 0

    if not args.yes:
        print("Refusing to install without --yes "
              "(use --yes for scripts/CI).", file=sys.stderr)
        return 2
    print(f"Installing ATML {ATML_VERSION}: components={only} "
          f"editors={editors or ['(none)']}")
    engine.run_install(only, editors)
    print("Install complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
