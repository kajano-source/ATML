# ATML for VS Code

Language support for **ATML (Animation Text Markup Language)** `.atml` files.

## Features

- Syntax highlighting (TextMate grammar `text.html.atml`) for ATML tags, attributes,
  `a-*` sugar attributes, numbers with units (`s`, `ms`, `%`, `px`, `deg`),
  and `<script type="atml">` ATMLScript blocks.
- 20+ snippets (`atml-doc`, `stage`, `scene`, `actor`, `animate`, `timeline`,
  `transition`, `trigger`, `camera`, `a-fade`…`a-morph`, `dog` starter…).
- Commands:
  - **ATML: Build to HTML** (`atml.build`, default keybinding `Ctrl+Shift+B`)
  - **ATML: Preview Animation** (`atml.preview` — Simple Browser, or embedded webview fallback)
  - **ATML: Publish Site to dist/** (`atml.publish`)
  - **ATML: Run in Browser** (`atml.run` — builds to `dist/` and opens your default browser)
  - **Run and Debug (F5)**: the ATML debug target compiles the open file and opens it in your browser (creates a `type: atml` launch config)
- Hover docs for ATML tags / attributes / easings.
- Completions for tags, attributes, and `ease` / `shape` values.
- Pass-through formatter (trims trailing whitespace; preserves semantics).
- Status bar FPS indicator (`$(pulse) ATML 12fps`) from the `fps` attribute
  or `atml.defaultFps`.
- Settings: `atml.defaultFps` (default `12`), `atml.autoBuildOnSave` (default `false`),
  `atml.compilerPath` (default `""` = auto-detect).

## Install

### From `.vsix`

```sh
code --install-extension atml-1.3.0.vsix
```

### From source

```sh
cd vscode-atml
npm install
npm run compile
```

Then press `F5` in VS Code to launch the Extension Development Host,
or package with `vsce package`. See [DEVELOP.md](./DEVELOP.md).

## Build behavior

`ATML: Build to HTML` runs:

```sh
atml build <file.atml> -o dist/<name>.html
```

Compiler resolution order:

1. `atml.compilerPath` setting (binary, or `*.py` script run via `python3`).
2. `compiler/atmlc.py` next to the extension or workspace.
3. `atml` on `PATH`.

Build output goes to the **Output > ATML** channel; `file.atml:line[:col]: message`
lines become editor diagnostics.

## Requirements

- VS Code `^1.85.0`
- Python 3 + the ATML compiler (`compiler/atmlc.py`), or an `atml` binary on `PATH`.

## License

MIT
