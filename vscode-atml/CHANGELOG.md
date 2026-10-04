# Changelog

## 1.3.0 — 2026-10-04

- New ATML debug target: F5 / Run and Debug now runs the `.atml` file in your
  browser (`type: atml` launch config, `atmlDebug.ts` inline adapter driving
  `atml run`). No more "no extension for debugging ATML" popup.

## 1.2.0 — 2026-10-04

- New command `atml.run`: builds `dist/` output and opens it with the OS default
  browser (`xdg-open` / `open` / `start`).

## 1.1.2 — 2026-10-04

- Fix: installer shims pointed at `compiler/atml.py`; corrected to `compiler/atmlc.py`
  (the installed `atml` command works now).
- Fix: extension package icon is PNG (`vsce` rejects SVG); added `repository` field
  so `vsce package` succeeds.

## 1.1.1 — 2026-10-04

- Fix: `atml build -o dist/...` now creates missing output directories instead of
  crashing with `FileNotFoundError`.

## 1.1.0 — 2026-10-04

- New command `atml.publish`: publish the active `.atml` file to `dist/` (index.html + assets).
- Commands are now `atml.build` / `atml.preview` / `atml.publish`.

## 1.0.0 — 2026-10-04

- Initial release of the ATML VS Code extension.
- TextMate grammar (`text.html.atml`) with ATML tags, attributes, `a-*` sugar,
  numbers + units, easings, and `<script type="atml">` ATMLScript blocks.
- Language configuration (comments, brackets, auto-closing ATML tags, indentation, onEnter rules).
- 20+ snippets including `atml-doc` scaffold and `dog` starter.
- Commands `atml.build` / `atml.preview`, hover docs, completions, pass-through formatter, FPS status bar.
- Settings `atml.defaultFps`, `atml.autoBuildOnSave`, `atml.compilerPath`.
