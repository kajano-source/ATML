# ATML — Animation & Transition Markup Language

**Write `.atml`, get `.html`. One command. No framework. No build chain.**

ATML is a tiny declarative language for drawing shapes precisely and animating them.
You describe *what the stage looks like* and *how it moves* — the ATML compiler
(`atmlc`) emits a single self-contained `.html` file (inline SVG + CSS + vanilla JS
runtime) that runs anywhere a browser runs.

```bash
python3 compiler/atmlc.py build hello.atml -o hello.html
# or via the shim:
./atml build hello.atml -o hello.html
```

> Version **1.2.0** · Extension id **`atml`** · License **MIT** ·
> Full manual: [`ATML_LANGUAGE_GUIDE.md`](ATML_LANGUAGE_GUIDE.md)

---

## 30-line quickstart: a bouncing ball

Save this as `ball.atml`:

```atml
<atml version="1.2.0" title="Bouncing Ball">
  <stage width="800" height="600" fps="60" bg="#0b1020">
    <scene id="main" dur="2s" bg="#0b1020">
      <!-- ground -->
      <actor id="ground" shape="rect"
             x="0" y="540" w="800" h="60"
             fill="#1b2340" />
      <!-- the ball -->
      <actor id="ball" shape="circle"
             cx="400" cy="100" r="36"
             fill="#ff5a5a" stroke="#ffffff" stroke-w="3">
        <!-- fall down, squash, rise, repeat -->
        <key at="0%"   cy="100" sy="1" />
        <key at="45%"  cy="504" sy="1" />
        <key at="55%"  cy="504" sy="0.72" sx="1.22" />
        <key at="75%"  cy="260" sy="1" sx="1" />
        <key at="100%" cy="100" sy="1" />
        <tween dur="2s" ease="ease-in-out" loop="infinite" />
      </actor>
      <!-- soft shadow that tracks the ball -->
      <actor id="shadow" shape="ellipse"
             cx="400" cy="548" rx="46" ry="10"
             fill="#000000" opacity="0.35">
        <key at="0%"   rx="30" opacity="0.18" />
        <key at="50%"  rx="52" opacity="0.4" />
        <key at="100%" rx="30" opacity="0.18" />
        <tween dur="2s" ease="ease-in-out" loop="infinite" />
      </actor>
    </scene>
  </stage>
</atml>
```

Compile and open it:

```bash
./atml build ball.atml -o ball.html
python3 -m http.server 8000
# open http://localhost:8000/ball.html
```

You just declared a stage, two actors, keyframes and a loop — no JavaScript written
by hand. Change `fps`, tweak a `<key>`, rebuild. That is the whole loop.

---

## Features

| Area | What you get |
|---|---|
| Precise drawing | `rect circle ellipse line poly path text image`, plus `<draw>` path mini-language (`M L C Q Z`), `<pixel>` art, `<part>` sub-parts. Draw a dog, a logo, a chart — pixel-exact. |
| Keyframe animation | `<key at="…%">` on any animatable prop + `<tween dur delay ease loop direction fill>` |
| Transitions library | `fade slide bounce spin float wiggle morph draw` via `<transition use="…">` |
| Sugar on plain HTML | `a-*` attributes (`a-fade`, `a-slide-up`, …) animate any HTML element without a stage |
| Timelines & clips | `<timeline>` + `<clip>` for play / pause / seek / scrub UIs |
| ATMLScript | Tiny `<script type="text/atml">` block: `on click … -> play …` — no JS needed for wiring |
| FPS control | Global → scene → actor override, 1–240 fps, deterministic quantization |
| Camera | Pan / zoom / follow / shake with `<camera>` |
| HTML interop | Any HTML passes through; migrate one `<div>` at a time |
| One-file output | Zero dependencies, works from `file://`, embeddable, emailable |
| Tooling | `build check new serve publish run`, VS Code / Cursor / JetBrains / Devin support |

---

## FPS control

One attribute, three levels. More specific wins:

```atml
<stage width="800" height="450" fps="60">
  <scene id="intro" dur="3s" fps="30"><!-- cinematic, half the work -->
    <actor id="hero" shape="rect" x="10" y="10" w="80" h="80" fill="#7dd3fc" fps="12">
      <key at="0%" x="10" /><key at="100%" x="700" />
      <tween dur="3s" ease="linear" />
    </actor>
  </scene>
</stage>
```

- Range **1–240**. Values are quantized to frame boundaries (see Guide Ch18 for math).
- Rule of thumb: **12 fps** = snappy cartoon / pixel art; **30** = cinematic & cheap;
  **60** = buttery UI/physics. Higher is rarely visible — measure first.
- The compiler emits `prefers-reduced-motion` handling automatically (motion collapses
  to the final frame unless the viewer opts back in).

---

## Precise drawing — yes, including a dog

Every coordinate is explicit. Anchors (`center`, `top-left`, …), `px`/`%`, `z` order,
and an optional grid make placement deterministic — what you write is what renders.

A (very good) dog in ~15 lines:

```atml
<actor id="dog" shape="group" x="300" y="200">
  <part id="body" shape="ellipse" cx="0" cy="40" rx="90" ry="55" fill="#c98f4e" />
  <part id="head" shape="circle" cx="90" cy="-10" r="48" fill="#d9a45f" />
  <part id="ear"  shape="ellipse" cx="70" cy="-48" rx="16" ry="30" fill="#8a5a2b" />
  <part id="snout" shape="ellipse" cx="126" cy="2" rx="26" ry="18" fill="#f2d3a0" />
  <part id="nose" shape="circle" cx="146" cy="-4" r="8" fill="#222222" />
  <part id="eye"  shape="circle" cx="102" cy="-20" r="7" fill="#222222" />
  <part id="tail" shape="path" d="M -88 30 Q -130 0 -118 -44" stroke="#c98f4e" stroke-w="16" fill="none" />
  <part id="leg1" shape="rect" x="-60" y="80" w="24" h="60" rx="10" fill="#b57a3e" />
  <part id="leg2" shape="rect" x="36" y="80" w="24" h="60" rx="10" fill="#b57a3e" />
</actor>
```

Full start-to-finish tutorial (sketch → parts → wag the tail): Guide **AppD**.

---

## Transitions vs animations

| | `<transition>` | `<key>` + `<tween>` animation |
|---|---|---|
| Purpose | Reusable **entrance/exit/effect** preset | Bespoke **multi-stop** motion you author |
| Syntax | `<transition id="t1" use="fade-up" dur="600ms" />` then `trigger="t1"` | `<key at="0%">…<key at="100%">…` + `<tween …/>` |
| Library | `fade fade-up slide-left slide-right bounce spin float wiggle morph draw …` | Any animatable prop, any easing |
| Best for | Page reveals, hovers, scene changes, sugar `a-*` | Characters, physics, choreography |
| Customizable | `dur delay ease` overrides | Fully — every stop is yours |

Rule: **transition for the common move, keyframes for the special move.**

---

## Project structure

```text
atml/
├── README.md                 # you are here
├── ATML_LANGUAGE_GUIDE.md    # the massive manual (start here to learn)
├── LICENSE                   # MIT
├── CONTRIBUTING.md
├── atml                      # CLI shim -> python3 compiler/atmlc.py
├── compiler/
│   └── atmlc.py              # the compiler (build/check/new/serve/publish)
├── runtime/
│   └── atml-runtime.js       # tiny vanilla runtime inlined into output HTML
├── examples/                 # small runnable .atml files
├── vscode-atml/              # VS Code extension (id: `atml`)
├── installer/                # per-OS installers (Arch/Debian/Fedora/Windows)
└── .github/workflows/        # ci.yml + release.yml
```

---

## Install

Requires **Python 3.9+**. No other dependency.

| OS | One-liner |
|---|---|
| Arch Linux (AUR) | `yay -S atml` (see `installer/arch/PKGBUILD`) |
| Debian / Ubuntu | `sudo dpkg -i atml_1.2.0_amd64.deb` (see `installer/debian/`) |
| Fedora | `sudo rpm -i atml-1.2.0-1.noarch.rpm` (see `installer/fedora/atml.spec`) |
| Windows | Download `atml-1.2.0-win.zip`, unzip, run `atml.exe build …` (see `installer/windows/`) |
| Any OS (source) | `git clone … && cd atml && chmod +x atml && ./atml check examples/` |

Verify: `./atml --help` prints the `ATML compiler v1.0` banner and subcommands.

---

## Editor setup

### VS Code

1. Install the **`atml`** extension (`vscode-atml/`, version 1.2.0): syntax highlight,
   snippets (`atml-stage`, `atml-actor`, `atml-key`…), `build` task, live preview.
2. From source: `cd vscode-atml && npm install && npx vsce package && code --install-extension atml-1.2.0.vsix`.

### Cursor

Cursor is VS Code-compatible — install the same `atml-1.2.0.vsix`
(`Extensions → … → Install from VSIX`). `.atml` files get highlighting + completions.
Add a `.cursor/rules` line so Cursor treats `.atml` as XML-ish ATML, not raw HTML.

### JetBrains (IntelliJ / WebStorm / PyCharm)

`Settings → Editor → File Types → HTML` → add `*.atml` pattern for highlighting,
or import the TextMate bundle from `vscode-atml/syntaxes/atml.tmLanguage.json`.
Point an External Tool at `python3 compiler/atmlc.py build $FilePath$ -o $FileDir$/$FileNameWithoutExtension$.html`.

### Devin

Give Devin this repo + the prompt: *"ATML 1.2.0. Compile with
`python3 compiler/atmlc.py build <file>.atml -o out.html`. Spec is
`ATML_LANGUAGE_GUIDE.md`. Keep edits to `.atml`/docs; do not touch the compiler
unless asked."* It can build, check, and publish sites headlessly.

---

## CLI reference

CLI is `python3 compiler/atmlc.py` (shim `./atml`).

| Command | Shape | Purpose |
|---|---|---|
| `build` | `./atml build in.atml -o out.html [--fps N] [--minify]` | Compile `.atml` → self-contained `.html` |
| `check` | `./atml check in.atml` (or a directory) | Validate + print `ATMLxxxx` diagnostics |
| `new` | `./atml new mysite --template site\|ball\|dog\|empty` | Scaffold a starter file |
| `serve` | `./atml serve --port 8000 --dir .` | Local preview server with live rebuild |
| `publish` | `./atml publish a.atml [b.atml …] -o dist/ [--base /] [--minify]` | Build + copy assets + sitemap for static hosting |
| `run` | `./atml run in.atml [--out DIR] [--no-browser]` | Compile + open in your default browser |

Exit codes: `0` ok · `1` usage/CLI error · `2` compile error · `3` validation error.
Full flags: Guide Ch23.

---

## Publish your website

ATML is a legitimate way to ship small sites — landing pages, posters, invites,
portfolios, docs with motion:

```bash
./atml new site --template site
./atml build site.atml -o dist/index.html
./atml publish site.atml -o dist/
# upload dist/ anywhere: GitHub Pages, Netlify, Vercel, cPanel
```

- Multi-page: one `.atml` per page → `dist/index.html`, `dist/about.html`, …
- Assets: relative `assets/` paths are copied by `publish` and rewritten.
- SEO: `<atml title desc keywords og-image>` emits `<meta>`/OG tags.
- Deploy recipes (Pages / Netlify / Vercel / cPanel): Guide Ch22.

---

## Examples

| File | Shows |
|---|---|
| `examples/hello.atml` | First scene: ball, box and greeting text with keyframed motion |
| `examples/dog.atml` | `<part>`-built dog (body, head, face, legs, tail) |
| `examples/fps.atml` | Side-by-side fps comparison row |
| `examples/morph.atml` | Blob-to-star path morph |
| `examples/site.atml` | Mini landing-page site fed to `publish` |
| `examples/transitions.atml` | HTML `a-*` sugar transitions on plain elements |
| Guide AppG | 10 more copy-paste scenes (sunrise, spinner, toast, dolly, player…) |

Run them all: `./atml check examples/ && for f in examples/*.atml; do ./atml build "$f" -o "dist/$(basename ${f%.atml}.html)"; done`

---

## Versioning

SemVer. Current **1.2.0**. The language version is pinned per file
(`<atml version="1.0">`); the 1.x compiler accepts `1.0` files and warns on
`0.x`/future `2.x`. Policy + changelog: Guide Ch28 / AppF.

## License

**MIT** © 2026 ATML contributors — see [`LICENSE`](LICENSE). Do anything; keep the notice.

## Contributing

Small, friendly, strict on spec compliance — see [`CONTRIBUTING.md`](CONTRIBUTING.md).
