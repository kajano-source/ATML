# Changelog

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
