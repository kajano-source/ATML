# ATML Language Guide — v1.0.0

> The complete manual for ATML (Animation & Transition Markup Language).
> Compile with `python3 compiler/atmlc.py` (shim `./atml`). Extension id `atml`.
> Guide version 1.0.0 · 2026 · MIT. Every tag, attribute, command and error is documented here.

**Contents** — Ch1 Mental model · Ch2 HTML interop · Ch3 `<atml>`+`<stage>` · Ch4 `<scene>` · Ch5 `<actor>` · Ch6 Geometry+`<draw>` · Ch7 `<pixel>` · Ch8 `<part>` · Ch9 Positioning · Ch10 Animation model · Ch11 `<key>` props · Ch12 `<tween>` · Ch13 `<timeline>`+`<clip>` · Ch14 `<transition>` · Ch15 `a-*` sugar · Ch16 ATMLScript · Ch17 Easings · Ch18 FPS · Ch19 Triggers · Ch20 Camera · Ch21 Text/Image/Sprite · Ch22 Publish · Ch23 CLI · Ch24 Errors · Ch25 Editors · Ch26 Performance · Ch27 A11y · Ch28 Versioning · AppA Tags · AppB Props matrix · AppC Easing cheatsheet · AppD Dog tutorial · AppE Migration checklist · AppF Changelog

---
# Ch1 — Mental model & file anatomy

## 1.1 What ATML is

ATML is a **declarative markup language**: you describe a *stage* (a canvas with a
size and frame rate), the *actors* on it (shapes, text, images), and *how they move*
(keyframes, tweens, transitions, timelines). The compiler `atmlc` turns one `.atml`
file into one self-contained `.html` file: inline SVG for vector drawing, CSS
keyframes for cheap motion, and a ~6 KB vanilla-JS runtime for timelines, triggers,
cameras and reduced-motion handling. There is no framework, no bundler, no network
fetch at play time — the output runs from `file://`.

```text
  .atml source            atmlc                       .html output
 +------------+     +-----------------+     +-----------------------------+
 | <stage>    |     | parse+validate  |     | <svg> actors (exact coords) |
 | <actor> x2 | --> | quantize @ fps  | --> | <style> CSS keyframes       |
 | <key> ...  |     | inline runtime  |     | <script> timeline/triggers |
 +------------+     +-----------------+     +-----------------------------+
```

## 1.2 The four ideas

| # | Idea | Tags | One-liner |
|---|------|------|-----------|
| 1 | **Stage** | `<atml> <stage> <scene>` | *Where* and *when*: size, fps, background, scenes. |
| 2 | **Actors** | `<actor>` + geometry + `<pixel>` + `<part>` | *What*: every visible thing, positioned exactly. |
| 3 | **Motion** | `<key>` `<tween>` `<transition>` `<timeline>` | *How it moves*: stops, pacing, presets, sequencing. |
| 4 | **Wiring** | triggers, `<camera>`, ATMLScript, `a-*` sugar | *When it starts* and *how the viewer sees it*. |

If you can answer *where, what, how, when* you can write any ATML file.

## 1.3 Minimal file anatomy

Every file has exactly one `<atml>` root, one `<stage>`, and one or more `<scene>`:

```atml
<atml version="1.0.0" title="Hello">
  <stage width="800" height="600" fps="60" bg="#0b1020">
    <scene id="main" dur="2s">
      <actor id="dot" shape="circle" cx="400" cy="300" r="24" fill="#7dd3fc">
        <key at="0%" cx="100" />
        <key at="100%" cx="700" />
        <tween dur="2s" ease="ease-in-out" loop="infinite" />
      </actor>
    </scene>
  </stage>
</atml>
```

| Nesting level | Tag | Cardinality | Role |
|---|---|---|---|
| 0 | `<atml>` | exactly 1 | Root. Carries `version`, document `title`, SEO meta. |
| 1 | `<stage>` | exactly 1 | Canvas: `width height fps bg`. Everything visual lives inside. |
| 2 | `<scene>` | 1..n | Time slice: `id dur bg`. Scenes play in order (or by trigger). |
| 3 | `<actor>` / geometry / HTML | 0..n | Visible things. Actors animate; raw HTML just renders. |
| 4 | `<key>` `<tween>` `<part>` `<transition>` | 0..n | Motion and sub-parts belonging to the parent actor. |
| 4 | `<timeline>` `<clip>` `<camera>` | 0..n | Scene-level sequencing, camera, wiring. |

## 1.4 Compile it

```bash
./atml check hello.atml            # validate, prints ATMLxxxx diagnostics
./atml build hello.atml -o hello.html   # compile to one self-contained file
./atml serve --port 8000           # preview with live rebuild
```

## 1.5 Design rules (why ATML looks like this)

1. **Coordinates are truth.** No auto-layout inside `<stage>`. `x=400` means pixel 400. Reproducible down to the sub-pixel.
2. **Motion is data, not code.** Keyframes are markup so designers can read and diff them.
3. **Cheap things are cheap.** Anything expressible as CSS goes to CSS; JS only handles timelines, triggers and cameras.
4. **HTML is a guest, not a stranger.** Raw HTML passes through untouched, so migration is incremental (Ch2).
5. **One file in, one file out.** The compiler never fetches the network and never emits a network dependency (except assets *you* reference).

---
# Ch2 — HTML interop, passthrough & migration recipe

## 2.1 Passthrough rule

Any element that is **not** an ATML tag passes through to the output **byte-identical**
(attributes preserved, order preserved). ATML tags are: `atml stage scene actor rect
circle ellipse line poly path draw text image pixel part key tween timeline clip
transition camera script style`. Everything else — `<div> <h1> <button> <img>` — is HTML.

```atml
<atml version="1.0.0" title="Mixed">
  <stage width="800" height="450" fps="60" bg="#ffffff">
    <scene id="main" dur="3s">
      <h1 class="hero" a-fade="in 800ms">Hello, regular HTML</h1>
      <actor id="dot" shape="circle" cx="400" cy="300" r="20" fill="#ff5a5a" />
      <div class="caption">This div is untouched by the compiler.</div>
    </scene>
  </stage>
</atml>
```

Notes:

- HTML inside `<scene>` is positioned by normal CSS flow (or your classes); ATML actors use stage coordinates. The two systems coexist: HTML overlays/underlays via `z`.
- `a-*` sugar attributes (Ch15) work on **any** HTML element — that is how you animate HTML without converting it.
- `<style>` and `<script>` blocks pass through (a `<script type="text/atml">` block is ATMLScript, Ch16; anything else is verbatim JS).

## 2.2 What the compiler does with mixed content

| Input | Output |
|---|---|
| ATML actor/geometry | Inline `<svg>` with deterministic `id`s (`atml-<actor-id>`) |
| HTML element | Same element in place; `a-*` attrs compiled to CSS classes + removed from markup |
| `<style>` | Merged into output `<head>`, after generated keyframes (yours wins ties) |
| `<script type="text/atml">` | Compiled to runtime wiring calls |
| other `<script>` | Copied verbatim to end of `<body>` |
| comments `<!-- -->` | Preserved |

## 2.3 Migration recipe: HTML → ATML in 5 steps (summary; full checklist in AppE)

```bash
# 0. baseline: it already works — ATML accepts plain HTML inside a stage
./atml new page --template site   # scaffold if starting fresh
```

1. **Wrap**: put your page (or one section) inside `<atml><stage><scene>` — change nothing else. `build` must produce a pixel-identical page.
2. **Sugar**: add `a-fade` / `a-slide-up` to headers, cards, buttons. Rebuild; motion appears, markup unchanged.
3. **Islands**: convert one visual at a time (a logo, a hero blob, a chart) from `<div>`/`<img>` to `<actor>` with exact coordinates.
4. **Choreograph**: add `<key>`/`<tween>` or a `<transition use=>` for entrances; wire clicks with `trigger=` or ATMLScript.
5. **Publish**: `./atml publish page.atml -o dist/` and diff against the old page before switching traffic.

Worked example:

```html
<!-- before: plain HTML hero -->
<h1 class="hero">Ship it</h1>
```
```atml
<!-- after step 2: same HTML, one attribute -->
<h1 class="hero" a-fade="in 800ms" a-slide-up="24px 800ms">Ship it</h1>
<!-- after step 3: hero blob becomes a precise actor behind the HTML -->
<actor id="blob" shape="path" d="M 100 300 C 200 150 500 150 700 300 C 500 420 200 420 100 300 Z" fill="#dbeafe" />
```

---
# Ch3 — Root `<atml>` + `<stage>`

## 3.1 `<atml>`: the document root

| Attr | Required | Default | Meaning |
|---|---|---|---|
| `version` | **yes** | — | Language version, e.g. `1.0.0`. Compiler warns on mismatch (Ch28). |
| `title` | no | `Untitled` | `<title>` of the output page. |
| `desc` | no | — | `<meta name="description">` (SEO, Ch22). |
| `keywords` | no | — | `<meta name="keywords">`. |
| `og-image` | no | — | Open-Graph image URL. |
| `lang` | no | `en` | `<html lang>`. |
| `bg` | no | `#ffffff` | Page background outside the stage. |

Exactly one `<atml>` per file; exactly one `<stage>` inside it (ATML0002 otherwise).

## 3.2 `<stage>`: the canvas

| Attr | Required | Default | Meaning |
|---|---|---|---|
| `width` | **yes** | — | Stage width in px (integer > 0). |
| `height` | **yes** | — | Stage height in px (integer > 0). |
| `fps` | no | `60` | Global frame rate 1–240 (Ch18). Scenes/actors may override. |
| `bg` | no | transparent | Stage background color. |
| `grid` | no | off | Snap/guide grid step, e.g. `grid="20"` draws a 20px guide overlay in `serve`. |
| `show-grid` | no | `false` | Show the grid in built output too (default: preview only). |
| `responsive` | no | `true` | Scale stage to fit container width preserving aspect. `false` = fixed px. |

Runnable examples:

```atml
<!-- minimal stage -->
<atml version="1.0.0"><stage width="800" height="600"><scene id="s" dur="1s" /></stage></atml>

<!-- full-bleed responsive hero stage with design grid -->
<atml version="1.0.0" title="Hero" desc="Landing hero">
  <stage width="1440" height="720" fps="60" bg="#0b1020" grid="24" responsive="true">
    <scene id="hero" dur="4s" />
  </stage>
</atml>

<!-- fixed-size pixel-art stage: low fps default, crisp scaling -->
<stage width="256" height="256" fps="12" bg="#1a1b26" responsive="false">
```

Output mapping: `<stage>` becomes `<div class="atml-stage" style="width:…;aspect-ratio:…">`
containing one inline `<svg viewBox="0 0 W H">` per scene. With `responsive="true"` the
SVG scales; coordinates stay exact in viewBox space.

---
# Ch4 — `<scene>`

A scene is a **time slice**: a set of actors sharing a duration, background and
default pacing. Scenes play in document order unless started by a trigger (Ch19).

| Attr | Required | Default | Meaning |
|---|---|---|---|
| `id` | **yes** | — | Unique in file. Referenced by triggers, timelines, links. |
| `dur` | **yes** | — | Scene duration: `800ms`, `2s`, `120f` (frames). |
| `bg` | no | inherit stage | Scene background (color or `url(...)`). |
| `fps` | no | inherit stage | Scene frame rate 1–240; overrides stage. |
| `loop` | no | `false` | `true` / `false` / count (`loop="3"`) / `infinite`. |
| `ease` | no | `linear` | Default easing for tweens in this scene. |
| `trigger` | no | `auto` | What starts the scene: `auto onload onclick …` (Ch19). |
| `next` | no | next sibling | Which scene follows (`next="outro"` or `next="none"`). |

Examples:

```atml
<!-- three-act structure -->
<stage width="800" height="450" fps="60">
  <scene id="intro" dur="2s" bg="#0b1020" next="main" />
  <scene id="main" dur="6s" bg="#111a33" loop="false" />
  <scene id="outro" dur="2s" bg="#000000" trigger="onend:main" />
</stage>

<!-- looping ambient background, 30fps to halve cost -->
<scene id="ambient" dur="8s" fps="30" loop="infinite" bg="#0e1530">
  <!-- actors... -->
</scene>

<!-- frame-count duration: exactly 48 frames at scene fps -->
<scene id="stinger" dur="48f" fps="24" bg="#ffffff">
```

Scene switching is a hard cut by default; add a `<transition>` (Ch14) on the scene
or on entering actors for fades/wipes. `onend:<id>` triggers (Ch19) chain scenes
without JavaScript.

---
# Ch5 — `<actor>`: every attribute + every shape

An actor is **one drawable, positionable, animatable thing**. It renders as one SVG
group/element with `id="atml-<id>"`, so CSS and ATMLScript can target it too.

## 5.1 Attribute table (complete)

| Attr | Required | Default | Meaning |
|---|---|---|---|
| `id` | **yes** | — | Unique in file. |
| `shape` | **yes** | — | `rect circle ellipse line poly path text image group` (+ `pixel` via `<pixel>`, Ch7). |
| `x` `y` | for most shapes | `0` | Position (top-left for rect/text/image; see §5.2 per shape). |
| `w` `h` | `rect image` | — | Width/height in px. |
| `cx` `cy` | `circle ellipse` | — | Center. |
| `r` | `circle` | — | Radius. |
| `rx` `ry` | `ellipse rect` | — | Ellipse radii / rect corner radius. |
| `x1 y1 x2 y2` | `line` | — | Endpoints. |
| `points` | `poly` | — | `x1,y1 x2,y2 …` vertex list. |
| `d` | `path` | — | SVG path data (M L C Q Z subset, Ch6). |
| `str` | `text` | — | Literal string. |
| `src` | `image` | — | Asset URL/path. Copied by `publish`. |
| `fill` | no | `#7dd3fc` | Fill color / `none`. |
| `stroke` | no | `none` | Stroke color. |
| `stroke-w` | no | `2` | Stroke width px. |
| `opacity` | no | `1` | 0–1. Animatable. |
| `rotate` | no | `0` | Degrees. Animatable. |
| `scale` `sx` `sy` | no | `1` | Uniform / axis scale. Animatable. |
| `anchor` | no | shape-dependent | Which point `x/y` pins (Ch9). |
| `z` | no | document order | Paint order (higher = on top). |
| `fps` | no | inherit | Per-actor fps override 1–240. |
| `trigger` | no | inherit scene | What starts this actor's tween. |
| `class` | no | — | Extra CSS classes on the output element. |

## 5.2 Every shape, runnable

```atml
<!-- rect: x/y = top-left -->
<actor id="box" shape="rect" x="50" y="60" w="160" h="100" rx="12" fill="#7dd3fc" stroke="#0b1020" stroke-w="3" />

<!-- circle: cx/cy = center -->
<actor id="sun" shape="circle" cx="700" cy="90" r="46" fill="#fbbf24" />

<!-- ellipse -->
<actor id="shadow" shape="ellipse" cx="400" cy="520" rx="90" ry="16" fill="#000000" opacity="0.3" />

<!-- line -->
<actor id="beam" shape="line" x1="0" y1="0" x2="800" y2="450" stroke="#ff5a5a" stroke-w="4" />

<!-- poly: triangle -->
<actor id="tri" shape="poly" points="400,80 700,380 100,380" fill="#34d399" />

<!-- path: freeform (see Ch6 for the d mini-language) -->
<actor id="leaf" shape="path" d="M 200 300 C 260 200 380 200 420 300 C 380 380 260 380 200 300 Z" fill="#34d399" />

<!-- text -->
<actor id="caption" shape="text" x="400" y="420" str="hello atml" font="32px system-ui" fill="#e5e7eb" anchor="center" />

<!-- image -->
<actor id="logo" shape="image" x="24" y="24" w="120" h="60" src="assets/logo.png" />

<!-- group: container for <part> children (Ch8); x/y moves the whole group -->
<actor id="dog" shape="group" x="300" y="220">
  <part id="body" shape="ellipse" cx="0" cy="40" rx="90" ry="55" fill="#c98f4e" />
  <part id="head" shape="circle" cx="90" cy="-10" r="48" fill="#d9a45f" />
</actor>
```

Shape defaults: `fill` defaults to `#7dd3fc` so a missing fill is visible, never
invisible; `stroke` defaults to `none`. `group` renders no geometry of its own —
only its `<part>` children (Ch8).

---
# Ch6 — Geometry: rect/circle/ellipse/line/poly/path/text/image + `<draw>` + morph rules

Standalone geometry tags (`<rect> <circle> …`) are identical to same-named `<actor>`
shapes except they **do not animate by themselves** — wrap them in an `<actor shape="group">`
or use `<actor>` directly when you need motion. Use bare tags for static set-dressing.

## 6.1 Tag-for-tag reference

| Tag | Key attrs | Example |
|---|---|---|
| `<rect>` | `x y w h rx fill stroke stroke-w` | `<rect x="10" y="10" w="120" h="80" rx="10" fill="#7dd3fc" />` |
| `<circle>` | `cx cy r` | `<circle cx="400" cy="300" r="40" fill="#ff5a5a" />` |
| `<ellipse>` | `cx cy rx ry` | `<ellipse cx="400" cy="500" rx="90" ry="16" />` |
| `<line>` | `x1 y1 x2 y2` | `<line x1="0" y1="0" x2="800" y2="450" stroke="#fff" stroke-w="2" />` |
| `<poly>` | `points` | `<poly points="0,450 200,250 400,450" fill="#34d399" />` |
| `<path>` | `d` | `<path d="M 10 10 L 200 10 L 200 200 Z" fill="none" stroke="#fff" />` |
| `<text>` | `str font size color anchor` | `<text x="400" y="100" str="Hi" font="bold 48px system-ui" fill="#fff" anchor="center" />` |
| `<image>` | `x y w h src` | `<image x="0" y="0" w="800" h="450" src="assets/bg.jpg" />` |
| `<draw>` | `d dur ease` path-stroke animation | `<draw d="M 0 400 C 200 100 600 100 800 400" stroke="#7dd3fc" stroke-w="6" dur="2s" />` (self-drawing line) |

## 6.2 `<draw>` path-command micro-tutorial (M L C Q Z)

`<draw>` (and any `d` attribute) accepts this subset — deliberately small so morphing stays well-defined:

| Cmd | Name | Syntax | Example | Draws |
|---|---|---|---|
| `M` | move | `M x y` | `M 50 400` | Lift the pen to (50,400). Starts a sub-path. |
| `L` | line | `L x y` | `L 750 400` | Straight segment. |
| `C` | cubic | `C x1 y1 x2 y2 x y` | `C 200 100 600 100 750 400` | Bézier with two controls. |
| `Q` | quadratic | `Q x1 y1 x y` | `Q 400 50 750 400` | Bézier with one control. |
| `Z` | close | `Z` | `… L 50 400 Z` | Straight line back to the sub-path start. |

Progressive disclosure — one path, five steps:

```atml
<!-- 1. just a dot-to-be: move only -->
<draw d="M 50 400" stroke="#7dd3fc" stroke-w="6" />
<!-- 2. a straight horizon -->
<draw d="M 50 400 L 750 400" stroke="#7dd3fc" stroke-w="6" />
<!-- 3. quad lift -->
<draw d="M 50 400 Q 400 200 750 400" stroke="#7dd3fc" stroke-w="6" />
<!-- 4. cubic S-curve -->
<draw d="M 50 400 C 250 100 550 500 750 200" stroke="#7dd3fc" stroke-w="6" />
<!-- 5. closed + self-draw animation -->
<draw d="M 50 400 C 250 100 550 100 750 400 Z" stroke="#7dd3fc" stroke-w="6" fill="none" dur="2s" ease="ease-in-out" />
```

`<draw>` animates stroke-dashoffset from full-length to 0 over `dur` — the classic
"line draws itself" effect, free with one tag.

## 6.3 Morph rules (`morph` transition + `d` keyframes)

Morphing interpolates one `d` into another. It works **iff**:

1. Same command sequence (e.g. both `M C C Z` — use the compiler's `check --normalize` hint to rewrite).
2. Same coordinate count per command.
3. Both paths open or both closed (`Z` on both or neither).
4. Fill/stroke are interpolated separately (colors lerp, `none` treated as transparent).

```atml
<!-- circle-ish blob morphs into a leaf: same skeleton M C C Z -->
<actor id="blob" shape="path" fill="#7dd3fc"
       d="M 300 300 C 300 200 500 200 500 300 C 500 400 300 400 300 300 Z">
  <key at="0%"   d="M 300 300 C 300 200 500 200 500 300 C 500 400 300 400 300 300 Z" />
  <key at="100%" d="M 250 300 C 320 180 480 180 550 300 C 480 420 320 420 250 300 Z" />
  <tween dur="2s" ease="ease-in-out" loop="infinite" direction="alternate" />
</actor>
```

Violation → `ATML0021` (morph skeleton mismatch) with the normalized skeletons printed.

---
# Ch7 — `<pixel>`: pixel art

`<pixel>` draws grid art: rows of characters mapped through a palette. Crisp by
default (`image-rendering: pixelated`), animated with the same `<key>`/`<tween>` as actors.

| Attr | Required | Default | Meaning |
|---|---|---|---|
| `id` | **yes** | — | Unique id. |
| `grid` | **yes** | — | Row strings; `.` = transparent. All rows same length (ATML0015). |
| `palette` | **yes** | — | `char=color;…` mapping, e.g. `R=#ff5a5a;W=#ffffff`. |
| `x` `y` | no | `0` | Top-left of the whole sprite. |
| `scale` (`px`) | no | `8` | Screen px per pixel cell. |
| other actor attrs | no | — | `opacity rotate z fps trigger class` all apply. |

## 7.1 8×8 heart (copy-paste it)

```atml
<pixel id="heart" x="360" y="200" scale="12" palette="R=#ff5a5a;W=#ffffff">
  <grid>
    .RR.RR..
    RRRRRRRR
    RWWRRWRR
    RRRRRRRR
    .RRRRRR.
    ..RRRR..
    ...RR...
    ....R...
  </grid>
</pixel>
```

Rows: 8, columns: 8. `.` transparent, `R` red, `W` white sparkle. At `scale="12"` it
renders 96×96 px. Tip: author at 8×8 or 16×16, scale up — never author big.

## 7.2 More pixel examples

```atml
<!-- beating heart: scale pulses, 12fps suits pixel art -->
<pixel id="heart2" x="360" y="200" scale="12" fps="12" palette="R=#ff5a5a">
  <grid>.RR.RR.. RRRRRRRR RRRRRRRR RRRRRRRR .RRRRRR. ..RRRR.. ...RR... ....R...</grid>
  <key at="0%" scale="12" /><key at="15%" scale="15" /><key at="30%" scale="12" />
  <key at="100%" scale="12" />
  <tween dur="1s" loop="infinite" />
</pixel>

<!-- tiny invader, two frames via alternate loop -->
<pixel id="invader" x="100" y="100" scale="10" palette="G=#34d399">
  <grid>..G...G.. ...G.G... ..GGGGG.. .GG.G.GG. GGGGGGGG G.GGGGG.G G..G.G..G ...G.G...</grid>
  <key at="0%" grid-frame="0" /><key at="100%" grid-frame="1" />
  <tween dur="0.5s" loop="infinite" />
</pixel>
```

Constraints: max 64×64 cells per sprite (ATML0016 beyond that — split into tiles);
palette chars are single characters; rows must be equal length.

---
# Ch8 — `<part>`: sub-part animation

`<part>` is a shape **owned by an `<actor shape="group">`**. Coordinates are relative
to the group's `x/y`; the part can still carry its own `<key>`/`<tween>` (e.g. a tail
wags while the whole dog walks). Parts render as `atml-<actor>-<part>` elements.

| Attr | Required | Default | Meaning |
|---|---|---|---|
| `id` | **yes** | — | Unique within the actor. |
| `shape` | **yes** | — | Any drawable shape (rect circle ellipse line poly path text image). |
| shape geometry | per shape | — | Same attrs as `<actor>` (§5.1), relative to group origin. |
| `pivot` | no | part center | Rotation pivot `x,y` (relative coords) — crucial for limbs. |
| `z` | no | document order | Order within the group. |

```atml
<!-- walking dog: group strides, tail wags, head bobs — three independent tweens -->
<actor id="dog" shape="group" x="100" y="300">
  <part id="body" shape="ellipse" cx="0" cy="40" rx="90" ry="55" fill="#c98f4e" />
  <part id="tail" shape="path" d="M -88 30 Q -130 0 -118 -44" stroke="#c98f4e" stroke-w="16" fill="none" pivot="-88,30">
    <key at="0%" rotate="-12" /><key at="50%" rotate="18" /><key at="100%" rotate="-12" />
    <tween dur="0.5s" loop="infinite" ease="ease-in-out" />
  </part>
  <part id="head" shape="circle" cx="90" cy="-10" r="48" fill="#d9a45f">
    <key at="0%" y="0" /><key at="50%" y="-8" /><key at="100%" y="0" />
    <tween dur="1s" loop="infinite" ease="sine-in-out" />
  </part>
  <key at="0%" x="100" /><key at="100%" x="620" />
  <tween dur="6s" ease="linear" loop="infinite" />
</actor>
```

Pivot rule: set `pivot` at the **joint** (shoulder/hip/tail-base), not the center, or
rotation will orbit instead of swinging. The compiler warns (`ATML0030`) when a part
rotates more than ±30° around its center — usually a missing pivot.

---
# Ch9 — Precision positioning: anchors, units, grid, z, camera

## 9.1 Anchors

`anchor` decides which point of the actor the `x/y` (or `cx/cy`) refers to:

| Value | Meaning | Default for |
|---|---|---|
| `top-left` | `x/y` = top-left corner | rect image text (left-baseline*) |
| `center` | position = bounding-box center | circle ellipse poly path |
| `top-center` `bottom-center` `left-center` `right-center` | edge midpoints | — |
| `top-right` `bottom-left` `bottom-right` | corners | — |
| `baseline-left` | text baseline start | text when `anchor` unset + `x/y` given |

*Text: default is alphabetic baseline at `x`, vertical `y` = baseline. Set
`anchor="center"` to center the whole string on the point instead.

```atml
<!-- same point, three framings -->
<actor id="a" shape="rect" x="400" y="300" w="120" h="80" anchor="center" fill="#7dd3fc" />
<actor id="b" shape="rect" x="400" y="300" w="120" h="80" anchor="top-left" fill="#ff5a5a" />
<actor id="c" shape="text" x="400" y="300" str="pin" anchor="center" />
```

## 9.2 Units

| Unit | Form | Meaning |
|---|---|---|
| `px` (bare numbers) | `x="400"` | Stage pixels (viewBox units). Default. |
| `%` | `x="50%"` | Percent of stage width (for x/w) or height (for y/h). |
| `f` (frames, durations only) | `dur="48f"` | Frames at current fps level. |
| `ms` `s` (durations only) | `dur="800ms"` | Milliseconds / seconds. |

Percentages resolve against the **stage**, not the parent group (groups are offsets,
not viewports). Percent + anchor is the responsive-centering idiom:

```atml
<actor id="title" shape="text" x="50%" y="20%" str="ATML" anchor="center" />
```

## 9.3 Grid

`<stage grid="20">` overlays a 20px guide grid in `serve` (never in `build` output
unless `show-grid="true"`). Authors commonly pick multiples of 8 or the grid step for
all coordinates; `check --align 8` flags off-grid values (advisory only).

## 9.4 `z` (paint order)

Higher `z` paints later (on top). Default = document order (later = on top). `z` accepts
negatives. HTML passthrough participates: give HTML `style="z-index:…"` or an actor
`z` — actors and HTML share one stacking context rooted at the scene.

## 9.5 Camera (preview)

`<camera>` (Ch20) reframes everything without moving actors — prefer it over
re-positioning a whole scene for pans/zooms/shake.

---
# Ch10 — Animation model: dur, delay, fps, ease, loop, direction, fill, trigger

Motion = **stops** (`<key>`) + **pacing** (`<tween>`). One `<tween>` per actor (or part);
any number of `<key>` stops. The tween interpolates between consecutive keys.

## 10.1 `<tween>` attribute tables

| Attr | Default | Values | Meaning |
|---|---|---|---|
| `dur` | `1s` | `ms s f` | Time from first to last key. |
| `delay` | `0ms` | `ms s f` | Wait before starting. Negative = start mid-way (scrub-in). |
| `fps` | inherit | `1–240` | Quantize this tween's sampling (Ch18). |
| `ease` | `linear` | Ch17 catalog | Pacing curve between keys. |
| `loop` | `false` | `false true infinite N` | Repeat count. |
| `direction` | `normal` | `normal reverse alternate alternate-reverse` | Play order per iteration. |
| `fill` | `both` | `none forwards backwards both` | Pose before start / after end (CSS-fill semantics). |
| `trigger` | inherit scene | Ch19 events | What starts the tween. |

## 10.2 Time units

| Unit | Example | Resolves to |
|---|---|---|
| `ms` | `delay="250ms"` | 0.25 s |
| `s` | `dur="2s"` | 2000 ms |
| `f` | `dur="48f"` | 48 ÷ fps seconds (fps = nearest override level) |

## 10.3 `<key at>`: stop positions

| Form | Meaning |
|---|---|---|
| `at="0%"` … `at="100%"` | Percent of `dur`. First key need not be 0% (fill covers the gap). |
| `at="0ms"` / `at="1.5s"` | Absolute offset from tween start (must be ≤ dur). |
| `at="12f"` | Frame offset at tween fps. |

Keys should ascend; the compiler sorts and warns (`ATML0022`) on duplicates (last wins).

## 10.4 Worked pacing examples

```atml
<!-- gentle entrance: wait, rise, stay -->
<actor id="card" shape="rect" x="300" y="500" w="200" h="120" fill="#ffffff">
  <key at="0%" y="500" opacity="0" /><key at="100%" y="200" opacity="1" />
  <tween dur="800ms" delay="300ms" ease="cubic-out" fill="both" />
</actor>

<!-- ping-pong patrol -->
<actor id="guard" shape="circle" cx="100" cy="300" r="20" fill="#ff5a5a">
  <key at="0%" cx="100" /><key at="100%" cx="700" />
  <tween dur="3s" ease="linear" loop="infinite" direction="alternate" />
</actor>

<!-- three-beat bounce in, then hold forever -->
<actor id="pop" shape="circle" cx="400" cy="300" r="10" fill="#34d399">
  <key at="0%" r="10" /><key at="60%" r="60" /><key at="80%" r="46" /><key at="100%" r="50" />
  <tween dur="600ms" ease="ease-out" fill="forwards" />
</actor>
```

---
# Ch11 — `<key>`: every animatable property

Any of these may appear on `<key>` (and as `a-*` sugar values, Ch15). `✓` = interpolable.

| Prop | Type | ✓ | Notes |
|---|---|---|---|
| `x` `y` | number/% | ✓ | Actor/group origin. |
| `cx` `cy` | number/% | ✓ | Circle/ellipse center. |
| `r` `rx` `ry` | number | ✓ | Radii. Clamped ≥ 0. |
| `w` `h` | number/% | ✓ | Rect/image size. |
| `x1 y1 x2 y2` | number | ✓ | Line endpoints. |
| `points` | list | ✓ iff same vertex count | Poly morph. |
| `d` | path | ✓ iff same skeleton (Ch6.3) | Path morph. |
| `fill` `stroke` | color/`none` | ✓ | RGBA lerp. |
| `stroke-w` | number | ✓ | |
| `opacity` | 0–1 | ✓ | |
| `rotate` | degrees | ✓ | Shortest-path spin unless `spin=` hints (Ch14). |
| `scale` `sx` `sy` | number | ✓ | |
| `tx` `ty` | number | ✓ | Extra translate stacked after x/y (for sugar composition). |
| `skew` `skewX` `skewY` | degrees | ✓ | |
| `font-size` | px | ✓ | Text only. |
| `letter-spacing` | px | ✓ | |
| `z` | int | ✗ (steps) | Jumps at the key (no in-between). |
| `grid-frame` | int | ✗ (steps) | `<pixel>` frame select. |
| `visibility` | `visible hidden` | ✗ (steps) | |

Non-animatable attrs (`id shape src str`) on a `<key>` → `ATML0023` error. Colors accept
`#rgb #rrggbb #rrggbbaa`, `rgb()`, and CSS names (`red` …). Angles accept `deg` suffix or bare numbers.

```atml
<!-- one keyframe driving six props at once -->
<key at="50%" x="400" y="200" rotate="180" scale="1.4" fill="#f472b6" opacity="0.9" />
```

---
# Ch12 — `<tween>`

`<tween>` is the pacing record for the preceding `<key>` list. One per actor/part;
a second `<tween>` is `ATML0024`. (For multi-segment pacing with different easings per
segment, use per-key `ease` overrides — below.)

## 12.1 Full shape

```atml
<tween dur="2s" delay="0ms" fps="60" ease="cubic-in-out"
       loop="infinite" direction="alternate" fill="both" trigger="auto" />
```

All attributes are optional; shown defaults are the effective defaults after inheritance
(scene `ease`/`fps` flow down unless the tween sets its own).

## 12.2 Per-key easing

```atml
<actor id="ball" shape="circle" cx="400" cy="100" r="30" fill="#ff5a5a">
  <key at="0%" cy="100" ease="quad-in" />
  <key at="50%" cy="500" ease="quad-out" />
  <key at="100%" cy="100" />
  <tween dur="2s" ease="linear" loop="infinite" />
</actor>
```

The `ease` on a key governs the segment **leaving** that key. Falls accelerate
(`quad-in` going down), rises decelerate (`quad-out` going up) — the classic gravity cheat.

## 12.3 `fill` semantics with examples

| `fill` | Before first key | After last key | Use |
|---|---|---|---|
| `none` | base pose | base pose | throwaway blips |
| `backwards` | first key | base pose | delayed entrances |
| `forwards` | base pose | last key | entrances that stick |
| `both` (default) | first key | last key | almost everything |

---
# Ch13 — `<timeline>` + `<clip>`: sequencing with play/pause/seek

A timeline binds several actors'/scenes' tweens to **one scrubable clock** and exposes
player controls (buttons or ATMLScript). Timelines compile to tiny JS (the one case where
output needs JS beyond CSS).

| Tag | Attr | Meaning |
|---|---|---|
| `<timeline>` | `id` (req), `dur`, `loop`, `autoplay="true\|false"` | Master clock. `dur` defaults to longest child. |
| `<clip>` | `for` (req: actor/part/scene id), `at` (start offset), `dur`, `ease`, `trigger` | Places that target's animation on the master clock. |

## 13.1 Full player example (play / pause / seek)

```atml
<atml version="1.0.0" title="Player">
  <stage width="800" height="450" fps="60" bg="#0b1020">
    <scene id="main" dur="6s">
      <actor id="a" shape="circle" cx="100" cy="225" r="30" fill="#7dd3fc">
        <key at="0%" cx="100" /><key at="100%" cx="700" />
        <tween dur="6s" ease="linear" />
      </actor>
      <actor id="b" shape="rect" x="350" y="150" w="100" h="100" fill="#f472b6">
        <key at="0%" rotate="0" /><key at="100%" rotate="360" />
        <tween dur="6s" ease="linear" />
      </actor>
      <timeline id="master" dur="6s" autoplay="false">
        <clip for="a" at="0s" dur="6s" />
        <clip for="b" at="1s" dur="4s" ease="ease-in-out" />
      </timeline>
      <div class="player">
        <button data-atml-play="master">Play</button>
        <button data-atml-pause="master">Pause</button>
        <input type="range" data-atml-seek="master" min="0" max="100" value="0" />
      </div>
      <script type="text/atml">
        on click [data-atml-play]  -> play master
        on click [data-atml-pause] -> pause master
        on input [data-atml-seek]  -> seek master to event.value %
      </script>
    </scene>
  </stage>
</atml>
```

`data-atml-play/pause/seek` are compiler-known hooks: they work with zero ATMLScript,
but the script block above shows the explicit form. `seek` jumps the master clock; clips
recompute their local pose from `at/dur/ease` — scrubbing is exact, not simulated.

---
# Ch14 — `<transition>` library + `use=`

Transitions are **named, reusable motion presets** for entrances, exits and emphasis.
Define once, apply by `trigger=` on actors or `use=` in sugar.

## 14.1 Defining and using

```atml
<transition id="rise" use="fade-up" dur="600ms" ease="cubic-out" dy="24" />
<actor id="card" shape="rect" x="300" y="200" w="200" h="120" fill="#fff" trigger="onload:rise" />
<!-- equivalent sugar on HTML: -->
<div class="card" a-fade="in 600ms" a-slide-up="24px 600ms">hi</div>
```

`<transition>` attrs: `id` (req), `use` (req), `dur` (default per preset), `delay`,
`ease` (preset default unless overridden), preset params (`dx dy scale spin …`), `loop`, `trigger`.

## 14.2 The library (complete)

| `use=` | Effect | Default dur | Params | Best for |
|---|---|---|---|
| `fade` | opacity 0→1 (or reverse with `dir="out"`) | 500ms | `from to` | reveals, crossfades |
| `fade-up` `fade-down` `fade-left` `fade-right` | fade + 8–32px drift | 600ms | `d` px distance | cards, heroes |
| `slide-left` `slide-right` `slide-up` `slide-down` | translate across | 600ms | `d` | drawers, toasts |
| `bounce` | overshoot-in settle | 800ms | `h` height | playful entrances, balls |
| `spin` | rotate 0→N° | 1000ms | `turns` | loaders, badges |
| `float` | gentle ±y bob, infinite | 3000ms | `amp` | ambient icons, clouds |
| `wiggle` | ±rotation shake | 500ms | `deg` | errors, attention |
| `pulse` | scale 1→1.06→1 | 1200ms | `to` | live dots, CTAs |
| `morph` | path `d` A→B (needs `from to`) | 1000ms | `from to` | blob/logo transforms |
| `draw` | stroke self-draw (needs path target) | 1500ms | — | signatures, diagrams |

Every preset accepts `dur delay ease loop direction trigger` overrides. `dir="out"`
reverses entrance presets into exits. Custom presets: compose `<key>`s once, reference
by `id` — `use=` is just shorthand for the built-ins.

---
# Ch15 — `a-*` sugar attributes on plain HTML

Sugar animates **ordinary HTML** with zero ATML structural tags. The compiler turns each
`a-*` into a CSS keyframe + class and strips the attribute from output.

## 15.1 Full table

| Attr | Value grammar | Effect | Example |
|---|---|---|---|
| `a-fade` | `in\|out DUR [delay D]` | opacity | `a-fade="in 800ms"` |
| `a-slide-up/down/left/right` | `DIST DUR [delay D]` | translate + optional fade with `a-fade` | `a-slide-up="24px 600ms"` |
| `a-bounce` | `[DUR]` | overshoot entrance | `a-bounce="800ms"` |
| `a-spin` | `[turns TURNS] [DUR]` | rotate | `a-spin="turns 1 1s"` |
| `a-float` | `[AMPpx DUR]` | infinite bob | `a-float="8px 3s"` |
| `a-wiggle` | `[DEG DUR]` | shake | `a-wiggle="6deg 500ms"` |
| `a-pulse` | `[DUR]` | infinite scale throb | `a-pulse="1.2s"` |
| `a-delay` | `D` | extra delay for all sugar on element | `a-delay="200ms"` |
| `a-ease` | `EASING` | override easing (Ch17) | `a-ease="cubic-out"` |
| `a-trigger` | `EVENT` | start condition (Ch19) | `a-trigger="onvisible"` |
| `a-repeat` | `N\|infinite` | loop count | `a-repeat="infinite"` |

`DUR/D` accept `ms/s`; defaults: fade 500ms, slide 600ms, bounce 800ms, spin 1s, float 3s, wiggle 500ms, pulse 1.2s.

## 15.2 Stagger recipe (no JS)

```html
<ul class="grid">
  <li a-fade="in 600ms" a-slide-up="16px 600ms" a-delay="0ms">one</li>
  <li a-fade="in 600ms" a-slide-up="16px 600ms" a-delay="90ms">two</li>
  <li a-fade="in 600ms" a-slide-up="16px 600ms" a-delay="180ms">three</li>
</ul>
```

Increment `a-delay` per item. `onvisible` trigger (default for sugar below the fold)
starts each card as it scrolls in.

---
# Ch16 — ATMLScript block grammar

ATMLScript wires events to actions without JavaScript. One block per scene (a second is
`ATML0024`-class warning `ATML0031`, merged).

```atml
<script type="text/atml">
  on click #go   -> play intro
  on click #stop -> pause intro
</script>
```

## 16.1 EBNF-ish grammar

```ebnf
program    = { statement } ;
statement  = "on" event selector "->" action ;
event      = "click" | "hover" | "leave" | "input" | "load" | "visible"
           | "key" | "time" | "end" ;
selector   = css-selector | "[data-atml-" name "]" ;
action     = "play" id | "pause" id | "seek" id "to" value
           | "toggle" id | "goto" scene-id | "restart" id
           | "set" prop "of" id "to" value ;
value      = percent | time | number ;
```

Selectors are CSS (`#id .class [attr]`). `event.value` exposes range-input/seek values.
Statements run in order; later `set` wins ties within one event tick.

## 16.2 Five examples

```atml
<script type="text/atml">
  # 1. basic transport
  on click #play   -> play master
  on click #pause  -> pause master
  # 2. scrubber
  on input #scrub  -> seek master to event.value %
  # 3. scene jukebox
  on click #s1btn  -> goto intro
  on end intro     -> goto main
  # 4. hover emphasis + leave reset
  on hover #logo   -> play wiggle-once
  on leave #logo   -> restart wiggle-once
  # 5. live prop poke (no timeline needed)
  on click #dimmer -> set opacity of hero to 0.25
</script>
```

Anything beyond this grammar (fetch, math, conditionals) belongs in a verbatim
`<script>` JS block — ATMLScript intentionally stays tiny so output stays auditable.

---
# Ch17 — Easing catalog

Easing names are shared by `<tween ease>`, per-key `ease`, `<transition ease>` and
`a-ease`. Unknown names → `ATML0025` (did-you-mean suggestion). All easings map to
`cubic-bezier()` in CSS output except `steps`, spring/elastic/bounce (JS-sampled at the
active fps level, Ch18).

Catalog: 33 easings. Values = normalized progress at t = 0 .25 .5 .75 1 (for feel).

## `linear` — constant velocity

- Progress at t=0/.25/.5/.75/1: `0.00 0.25 0.50 0.75 1.00`
- Best for: conveyors, patrols, spinning loaders.
- Snippet:

```atml
<tween dur="1s" ease="linear" />
```

## `ease` — CSS ease (gentle in, soft out)

- Progress at t=0/.25/.5/.75/1: `0.00 0.20 0.45 0.72 1.00`
- Best for: default-ish UI motion.
- Snippet:

```atml
<tween dur="1s" ease="ease" />
```

## `ease-in` — slow start, abrupt stop

- Progress at t=0/.25/.5/.75/1: `0.00 0.10 0.28 0.55 1.00`
- Best for: exits, falling away.
- Snippet:

```atml
<tween dur="1s" ease="ease-in" />
```

## `ease-out` — fast start, gentle stop

- Progress at t=0/.25/.5/.75/1: `0.00 0.45 0.72 0.90 1.00`
- Best for: entrances (most common).
- Snippet:

```atml
<tween dur="1s" ease="ease-out" />
```

## `ease-in-out` — slow both ends

- Progress at t=0/.25/.5/.75/1: `0.00 0.28 0.50 0.72 1.00`
- Best for: hero moves, camera pans.
- Snippet:

```atml
<tween dur="1s" ease="ease-in-out" />
```

## `quad-in` — t² accelerate

- Progress at t=0/.25/.5/.75/1: `0.00 0.06 0.25 0.56 1.00`
- Best for: gravity falls (short).
- Snippet:

```atml
<tween dur="1s" ease="quad-in" />
```

## `quad-out` — decelerate

- Progress at t=0/.25/.5/.75/1: `0.00 0.44 0.75 0.94 1.00`
- Best for: soft landings (short).
- Snippet:

```atml
<tween dur="1s" ease="quad-out" />
```

## `quad-in-out` — symmetric t²

- Progress at t=0/.25/.5/.75/1: `0.00 0.12 0.50 0.88 1.00`
- Best for: two-beat shuttles.
- Snippet:

```atml
<tween dur="1s" ease="quad-in-out" />
```

## `cubic-in` — t³ accelerate

- Progress at t=0/.25/.5/.75/1: `0.00 0.03 0.22 0.52 1.00`
- Best for: weighty drops.
- Snippet:

```atml
<tween dur="1s" ease="cubic-in" />
```

## `cubic-out` — t³ decelerate

- Progress at t=0/.25/.5/.75/1: `0.00 0.48 0.78 0.96 1.00`
- Best for: cards, modals (sugar default).
- Snippet:

```atml
<tween dur="1s" ease="cubic-out" />
```

## `cubic-in-out` — symmetric t³

- Progress at t=0/.25/.5/.75/1: `0.00 0.09 0.50 0.91 1.00`
- Best for: scene transitions.
- Snippet:

```atml
<tween dur="1s" ease="cubic-in-out" />
```

## `quart-in` — t⁴ hard accelerate

- Progress at t=0/.25/.5/.75/1: `0.00 0.02 0.16 0.47 1.00`
- Best for: rockets, punches.
- Snippet:

```atml
<tween dur="1s" ease="quart-in" />
```

## `quart-out` — t⁴ hard brake

- Progress at t=0/.25/.5/.75/1: `0.00 0.53 0.84 0.98 1.00`
- Best for: snappy UI.
- Snippet:

```atml
<tween dur="1s" ease="quart-out" />
```

## `quart-in-out` — symmetric t⁴

- Progress at t=0/.25/.5/.75/1: `0.00 0.06 0.50 0.94 1.00`
- Best for: dramatic reveals.
- Snippet:

```atml
<tween dur="1s" ease="quart-in-out" />
```

## `quint-in` — t⁵ extreme

- Progress at t=0/.25/.5/.75/1: `0.00 0.01 0.10 0.41 1.00`
- Best for: rare: use quart first.
- Snippet:

```atml
<tween dur="1s" ease="quint-in" />
```

## `quint-out` — t⁵ brake

- Progress at t=0/.25/.5/.75/1: `0.00 0.59 0.90 0.99 1.00`
- Best for: overshoot-free snap.
- Snippet:

```atml
<tween dur="1s" ease="quint-out" />
```

## `quint-in-out` — symmetric t⁵

- Progress at t=0/.25/.5/.75/1: `0.00 0.03 0.50 0.97 1.00`
- Best for: title slams.
- Snippet:

```atml
<tween dur="1s" ease="quint-in-out" />
```

## `sine-in` — gentle sine start

- Progress at t=0/.25/.5/.75/1: `0.00 0.08 0.29 0.59 1.00`
- Best for: organic entrances.
- Snippet:

```atml
<tween dur="1s" ease="sine-in" />
```

## `sine-out` — gentle sine stop

- Progress at t=0/.25/.5/.75/1: `0.00 0.41 0.71 0.92 1.00`
- Best for: breathing, floats.
- Snippet:

```atml
<tween dur="1s" ease="sine-out" />
```

## `sine-in-out` — sine both ends

- Progress at t=0/.25/.5/.75/1: `0.00 0.15 0.50 0.85 1.00`
- Best for: bobs, hovering (default for float).
- Snippet:

```atml
<tween dur="1s" ease="sine-in-out" />
```

## `expo-in` — near-flat then snap

- Progress at t=0/.25/.5/.75/1: `0.00 0.01 0.06 0.34 1.00`
- Best for: lasers, alerts.
- Snippet:

```atml
<tween dur="1s" ease="expo-in" />
```

## `expo-out` — snap then settle

- Progress at t=0/.25/.5/.75/1: `0.00 0.66 0.94 0.99 1.00`
- Best for: toasts, popovers.
- Snippet:

```atml
<tween dur="1s" ease="expo-out" />
```

## `expo-in-out` — symmetric expo

- Progress at t=0/.25/.5/.75/1: `0.00 0.02 0.50 0.98 1.00`
- Best for: cinematic wipes.
- Snippet:

```atml
<tween dur="1s" ease="expo-in-out" />
```

## `circ-in` — circular dig-in

- Progress at t=0/.25/.5/.75/1: `0.00 0.05 0.18 0.44 1.00`
- Best for: rolling, wheels.
- Snippet:

```atml
<tween dur="1s" ease="circ-in" />
```

## `circ-out` — circular-star settle

- Progress at t=0/.25/.5/.75/1: `0.00 0.56 0.82 0.95 1.00`
- Best for: orbits arriving.
- Snippet:

```atml
<tween dur="1s" ease="circ-out" />
```

## `circ-in-out` — symmetric circ

- Progress at t=0/.25/.5/.75/1: `0.00 0.07 0.50 0.93 1.00`
- Best for: planet motion.
- Snippet:

```atml
<tween dur="1s" ease="circ-in-out" />
```

## `back-in` — wind-up then go (overshoots start)

- Progress at t=0/.25/.5/.75/1: `-0.05 -0.08 -0.02 0.45 1.00`
- Best for: slingshots.
- Snippet:

```atml
<tween dur="1s" ease="back-in" />
```

## `back-out` — overshoot then settle

- Progress at t=0/.25/.5/.75/1: `0.00 0.55 1.02 1.08 1.00`
- Best for: playful cards (sugar bounce-ish).
- Snippet:

```atml
<tween dur="1s" ease="back-out" />
```

## `back-in-out` — both overshoots

- Progress at t=0/.25/.5/.75/1: `-0.05 0.15 0.50 0.85 1.05`
- Best for: character pops.
- Snippet:

```atml
<tween dur="1s" ease="back-in-out" />
```

## `elastic-out` — spring wobble (JS-sampled)

- Progress at t=0/.25/.5/.75/1: `0.00 0.68 1.25 0.94 1.00`
- Best for: jelly, notifications.
- Snippet:

```atml
<tween dur="1s" ease="elastic-out" />
```

## `bounce-out` — ballistic bounces (JS-sampled)

- Progress at t=0/.25/.5/.75/1: `0.00 0.55 0.78 0.92 1.00`
- Best for: balls, badges (transition bounce).
- Snippet:

```atml
<tween dur="1s" ease="bounce-out" />
```

## `spring` — underdamped 1.5 oscillations

- Progress at t=0/.25/.5/.75/1: `0.00 0.60 1.15 0.97 1.00`
- Best for: drag-release, toggles.
- Snippet:

```atml
<tween dur="1s" ease="spring" />
```

## `steps-4` — 4 hard steps (no interp)

- Progress at t=0/.25/.5/.75/1: `0.00 0.25 0.50 0.75 1.00`
- Best for: sprite flicker, clocks.
- Snippet:

```atml
<tween dur="1s" ease="steps-4" />
```

Guidance: entrances → `*-out`; exits → `*-in`; loops → `*-in-out`/`sine`; physics →
`quad`/`bounce`; UI default `cubic-out`; never use `elastic`/`bounce` on text longer than
a word (wobble hurts readability).

---
# Ch18 — FPS: 1–240, overrides, quantization, guidance, reduced motion

## 18.1 Levels and override rule

Three levels; most specific wins: `<stage fps>` → `<scene fps>` → `<actor>/<tween fps>`.
Range **1–240** everywhere; out-of-range → `ATML0009` (clamped in `--lenient`, error otherwise).

```atml
<stage width="800" height="450" fps="60">
  <scene id="film" dur="4s" fps="30">
    <actor id="hero" shape="rect" x="0" y="0" w="40" h="40" fill="#fff" fps="12">
       <!-- this actor samples at 12fps inside a 30fps scene on a 60fps stage -->
    </actor>
  </scene>
</stage>
```

## 18.2 Quantization math (deterministic)

The compiler samples JS-driven motion at the active fps; CSS motion gets matching
`steps()` hints only for `steps-*` easings. Frame boundaries are exact:

```text
frame_dt   = 1 / fps                 e.g. 60fps -> 16.666…ms
frame(i)   = round(t_ms / frame_dt)  nearest frame index
quant(t)   = frame(i) * frame_dt     snapped time actually rendered
max_err    = frame_dt / 2            worst-case timing error (60fps: 8.3ms)
frames_total = ceil(dur_ms / frame_dt)
```

| fps | frame | worst err | frames for 2s | feel |
|---|---|---|---|---|
| 12 | 83.3ms | 41.7ms | 24 | snappy cartoon / pixel art |
| 24 | 41.7ms | 20.8ms | 48 | film |
| 30 | 33.3ms | 16.7ms | 60 | cinematic, half the cost of 60 |
| 60 | 16.7ms | 8.3ms | 120 | buttery default |
| 120 | 8.3ms | 4.2ms | 240 | high-refresh UI (measure first) |
| 240 | 4.2ms | 2.1ms | 480 | ceiling; only for measurement rigs |

`f` durations resolve at the *nearest override level*: `dur="48f"` inside a 24fps
scene = 2.000s exactly; the same file at stage 60fps = 0.800s. Pin `fps` where you use `f`.

## 18.3 12 vs 60 guidance

| Choose | When | Why |
|---|---|---|
| 12 | pixel art, cartoon characters, background loops | chunky charm; 5× fewer samples; matches sprite tradition |
| 24–30 | cinematic scenes, slow pans | filmic; cheap on mobile |
| 60 | physics, drag, camera follow, text motion | smoothness is legibility |
| >60 | almost never | most panels are 60Hz; file bloat without visible gain |

Mix freely: a 12fps hero over a 60fps camera is a legitimate, great-looking choice.

## 18.4 `prefers-reduced-motion`

Every build includes (unless `--no-reduced-motion`):

```css
@media (prefers-reduced-motion: reduce) {
  .atml-anim { animation: none !important; }
  .atml-anim { opacity: 1 !important; transform: none !important; }
}
```

JS timelines expose `ATML.reducedMotion()` and auto-collapse to final keyframes;
opt back in per element with `data-atml-motion="always"`. Ch27 has the full policy.

---
# Ch19 — Triggers & events

Triggers start scenes, tweens, transitions and timelines. Grammar: `onevent[:target]`.

| Trigger | Fires when | Example |
|---|---|---|
| `auto` (default) | scene/tween starts with its parent | `trigger="auto"` |
| `onload` | page/scene loaded | `trigger="onload"` |
| `onclick:SEL` | click on selector | `trigger="onclick:#go"` |
| `onhover:SEL` / `onleave:SEL` | pointer enter/leave | `trigger="onhover:.card"` |
| `onscroll` / `onvisible[:SEL]` | element enters viewport (IntersectionObserver) | `trigger="onvisible"` |
| `onkey:NAME` | keyboard (Enter Escape arrows …) | `trigger="onkey:Enter"` |
| `ontime:2s` | delay after scene start | `trigger="ontime:1.5s"` |
| `onend:ID` | actor/scene/timeline ID finishes | `trigger="onend:intro"` |
| `onloop:ID` | iteration boundary | `trigger="onloop:ambient"` |
| `onmedia:(max-width:600px)` | media query matches | responsive variants |

Examples:

```atml
<!-- click-to-play character -->
<actor id="rex" shape="circle" cx="400" cy="300" r="40" fill="#ff5a5a" trigger="onclick:#go">
  <key at="0%" cy="300" /><key at="50%" cy="150" /><key at="100%" cy="300" />
  <tween dur="1s" ease="quad-in-out" />
</actor>
<button id="go">Jump</button>

<!-- scroll-driven gallery: each card fades as it appears -->
<div class="card" a-fade="in 600ms" a-trigger="onvisible">…</div>

<!-- chained scenes: outro waits for main -->
<scene id="outro" dur="2s" trigger="onend:main" next="none" />

<!-- keyboard-accessible modal -->
<scene id="modal" dur="400ms" trigger="onkey:Enter" />
```

Unknown event names → `ATML0026`. `onclick` without a selector targets the actor itself.
Triggers compose: `trigger="onvisible onclick:#replay"` means *either* (OR semantics).

---
# Ch20 — Camera

`<camera>` reframes the scene (pan/zoom/follow/shake) without touching actor coords.
One camera per scene (a second is merged with warning `ATML0031`).

| Attr | Default | Meaning |
|---|---|---|
| `x` `y` | `0 0` | Look-at offset px (added to all actors, inverted). Animatable. |
| `zoom` | `1` | Scale about stage center. Animatable (dolly). |
| `follow` | — | Actor id to track (`follow="hero"` keeps hero centered). |
| `shake` | `0` | Trauma 0–1: procedural offset, decays over `shake-dur`. |
| `shake-dur` | `500ms` | Shake decay time. |
| `bounds` | stage | `x,y,w,h` clamp box for follow (camera never shows outside). |

```atml
<!-- slow dolly-in over 6s -->
<scene id="establish" dur="6s">
  <camera x="0" y="0" zoom="1">
    <key at="0%" zoom="1" x="0" y="0" />
    <key at="100%" zoom="1.6" x="120" y="40" />
    <tween dur="6s" ease="sine-in-out" />
  </camera>
</scene>

<!-- follow the hero through a wide world, clamped to world bounds -->
<camera follow="hero" bounds="0,0,2400,450" zoom="1.25" />

<!-- impact shake (trauma 0.7, decays in 400ms) -->
<camera shake="0.7" shake-dur="400ms" trigger="onend:explosion" />
```

Camera + `follow` + `bounds` is the standard side-scroller recipe: build the world wide
(e.g. 2400px), keep the stage 800px, let the camera do the walking.

---
# Ch21 — Text, image & sprite

## 21.1 Text

| Attr | Meaning |
|---|---|---|
| `str` | literal (entities OK: `&amp; &lt;`) |
| `font` | CSS font shorthand (`bold 48px system-ui`) or split `font-size font-family font-weight` |
| `fill` | glyph color; `stroke`+`stroke-w` = outline |
| `anchor` | `center` recommended for stage-centered titles |
| `letter-spacing` `line-height` | animatable spacing |

```atml
<actor id="title" shape="text" x="50%" y="38%" str="ATML" font="bold 96px system-ui" fill="#ffffff" anchor="center">
  <key at="0%" opacity="0" font-size="64" /><key at="100%" opacity="1" font-size="96" />
  <tween dur="900ms" ease="cubic-out" fill="both" />
</actor>
```

Fonts: output uses system stacks by default (zero network). Webfonts work via normal
`<link>` passthrough — add it, reference the family in `font`, done.

## 21.2 Image

| Attr | Meaning |
|---|---|---|
| `src` | relative (`assets/x.png`) or absolute URL |
| `x y w h` | placement box; image is letterboxed, never stretched, unless `fit="fill"` |
| `fit` | `contain` (default) `cover` `fill` |
| `alt` | accessibility label → `<title>` in SVG (Ch27) |

`publish` copies local assets into the output dir and rewrites `src` (Ch22). Missing file → `ATML0012`.

## 21.3 Sprites (image-sequence)

```atml
<!-- 6-frame run cycle from a strip: frame 64x64, 12fps -->
<actor id="runner" shape="image" x="100" y="300" w="64" h="64"
       src="assets/run.png" sprite="6x1" frame-w="64" frame-h="64" fps="12">
  <key at="0%" sprite-frame="0" /><key at="100%" sprite-frame="5" />
  <tween dur="0.5s" loop="infinite" ease="steps-6" />
</actor>
```

`sprite="COLSxROWS"` + `sprite-frame` (steps-quantized). Keep strips ≤2048px wide for mobile GPUs.

---
# Ch22 — Publish websites with ATML

ATML ships small sites well: landing pages, posters, invites, portfolios, animated docs.

## 22.1 One page

```bash
./atml new site --template site
./atml build site.atml -o dist/index.html
./atml publish site.atml -o dist/
```

`publish` = `build` + copy local `assets/` + rewrite relative URLs + emit `sitemap.xml`
when multi-page. Flags: `--base /docs/` (sub-path hosting), `--minify`, `--no-reduced-motion`.

## 22.2 Multi-page

```bash
./atml build index.atml -o dist/index.html
./atml build about.atml -o dist/about.html
./atml publish index.atml about.atml -o dist/ --base /
```

Link pages with normal `<a href="about.html">` passthrough, or `goto` for scene-SPAs (Ch16).

## 22.3 Assets

| Rule | Detail |
|---|---|---|
| Relative stays relative | `assets/logo.png` beside the `.atml` → copied to `dist/assets/logo.png` |
| Absolute URLs untouched | `https://…` never copied, never rewritten |
| Size budget | ≤500 KB images; prefer SVG actors over PNG where possible |

## 22.4 SEO

`<atml title desc keywords og-image>` emits `<title>`, meta description/keywords, OG tags.
ATML content is server-rendered markup (SVG in HTML), so crawlers see text without JS.
Add one `<h1>` passthrough per page for document outline.

## 22.5 Deploy recipes

```bash
# GitHub Pages: push dist/ to gh-pages (or Docs folder)
./atml publish site.atml -o dist/ --base /myrepo/
# then: git subtree push --prefix dist origin gh-pages

# Netlify: drag dist/ onto app.netlify.com, or:
netlify deploy --dir dist --prod

# Vercel:
vercel --prod dist/

# cPanel/shared hosting: zip dist/ and upload to public_html, unzip.
```

All hosts serve the output as static files — no server code, no build step on the host.

---
# Ch23 — CLI complete

Binary: `python3 compiler/atmlc.py`. Shim: `./atml` (same args). Version 1.0.0.

## 23.1 `build`

```text
./atml build IN.atml -o OUT.html [--fps N] [--minify] [--lenient] [--no-reduced-motion]
  --fps N              override stage fps (1-240)
  --minify             collapse whitespace in output HTML
  --lenient            clamp recoverable errors to warnings (exit 0 unless fatal)
  --no-reduced-motion  omit prefers-reduced-motion CSS (not recommended)
```

## 23.2 `check`

```text
./atml check PATH [--align N]
  PATH accepts a file or directory (all *.atml, recursive)
  --align N  advisory: flag coordinates not multiples of N
Prints ATMLxxxx diagnostics with file:line:col, one per line.
```

## 23.3 `new`

```text
./atml new NAME [--template TEMPLATE]
  TEMPLATE = empty | ball | dog | site | transitions | timeline | pixel-heart
  writes NAME.atml (or NAME/ for site) and prints next steps
```

## 23.4 `serve`

```text
./atml serve [--port 8000] [--dir .] [--open]
  live-rebuilds on .atml save; serves grid overlay + error console overlay
```

## 23.5 `publish`

```text
./atml publish IN.atml [MORE.atml ...] -o DIST/ [--base /] [--minify]
```

## 23.6 Exit codes

| Code | Meaning | Example |
|---|---|---|
| 0 | ok (warnings allowed) | build with deprecation hint |
| 1 | usage/CLI error | unknown flag, missing `-o` |
| 2 | compile error | `ATML00xx` fatal, no output written |
| 3 | validation error | `check` found diagnostics |

## 23.7 `--help` (version banner)

```bash
./atml --help        # prints the `ATML compiler v1.0` banner + subcommand list
./atml build --help  # flags for one subcommand (same as this chapter)
./atml build --help
```

---
# Ch24 — Errors & debugging (ATML0001…ATML0040)

Diagnostics print as `path.atml:LINE:COL: ATMLxxxx severity message`. `check` lists all;
`build` stops at the first fatal (or collects with `--lenient`). Fix column points at the
offending attribute.

## ATML0001 · fatal — Root must be `<atml>`.

- Trigger: File starts with `<stage>` or HTML.
- Fix: Wrap in `<atml version="1.0.0">…</atml>`.

## ATML0002 · fatal — Expected exactly one `<stage>`.

- Trigger: Zero or two `<stage>` tags.
- Fix: Keep one `<stage>` directly inside `<atml>`.

## ATML0003 · fatal — `<scene>` missing required `id`/`dur`.

- Trigger: `<scene dur="2s">` with no id.
- Fix: Add `id="main"` (unique).

## ATML0004 · fatal — Duplicate id.

- Trigger: Two actors share `id="ball"`.
- Fix: Rename; ids are file-global.

## ATML0005 · fatal — Unknown tag.

- Trigger: `<circlee …>` typo.
- Fix: See AppA; check spelling.

## ATML0006 · fatal — Unknown attribute on ATML tag.

- Trigger: `<actor colour=…>`.
- Fix: British spellings not accepted; use `color`-family `fill`.

## ATML0007 · fatal — Missing required attribute.

- Trigger: `<actor shape="rect">` with no geometry.
- Fix: Add per-shape required attrs (AppA).

## ATML0008 · fatal — Bad value type.

- Trigger: `width="wide"`.
- Fix: Numbers must parse as float; colors as CSS.

## ATML0009 · error — fps out of range 1–240.

- Trigger: `fps="0"` / `fps="500"`.
- Fix: Pick 12/30/60 (Ch18). `--lenient` clamps.

## ATML0010 · error — Bad time literal.

- Trigger: `dur="2sec"`.
- Fix: Use `ms`, `s`, or `f` (`dur="2s"`).

## ATML0011 · error — Bad percent/angle.

- Trigger: `at="half"`.
- Fix: `at="50%"`, `rotate="90"`.

## ATML0012 · error — Asset not found.

- Trigger: `src="assets/nope.png"`.
- Fix: Fix path; `publish` copies from source dir.

## ATML0013 · error — Bad color.

- Trigger: `fill="bluish"`.
- Fix: Use `#rgb/#rrggbb`, `rgb()`, or named colors.

## ATML0014 · error — Bad path data.

- Trigger: `d="M banana"`.
- Fix: Only M L C Q Z + numbers (Ch6.2).

## ATML0015 · error — `<pixel>` ragged rows.

- Trigger: Rows of differing length.
- Fix: Pad with `.` to equal width.

## ATML0016 · error — `<pixel>` exceeds 64×64.

- Trigger: 128-wide sprite.
- Fix: Split into tiles.

## ATML0017 · error — `<poly>` needs ≥3 vertices.

- Trigger: `points="0,0 10,10"`.
- Fix: Add a third point.

## ATML0018 · error — Empty `<timeline>`/scene.

- Trigger: Scene with no actors and no HTML.
- Fix: Add content or drop the scene.

## ATML0019 · fatal — Unclosed tag / malformed XML.

- Trigger: `<actor …>` never closed.
- Fix: Close it; ATML is XML-strict.

## ATML0020 · fatal — Text outside root.

- Trigger: Stray bytes before `<atml>`.
- Fix: Move into a scene or delete.

## ATML0021 · error — Morph skeleton mismatch.

- Trigger: `d` keyframes mix `C` and `Q`.
- Fix: Rewrite to same command sequence (check prints both).

## ATML0022 · warning — Duplicate/unsorted `<key at>`.

- Trigger: Two `at="50%"`.
- Fix: Last wins; sort ascending.

## ATML0023 · error — Non-animatable prop on `<key>`.

- Trigger: `<key src="…">`.
- Fix: Animate Ch11 props only.

## ATML0024 · error — Second `<tween>` on one actor.

- Trigger: Copy-paste double tween.
- Fix: Merge into one.

## ATML0025 · error — Unknown easing.

- Trigger: `ease="bouncy"`.
- Fix: Did-you-mean suggests `bounce-out` (Ch17).

## ATML0026 · error — Unknown trigger/event.

- Trigger: `trigger="onclik"`.
- Fix: See Ch19 table.

## ATML0027 · error — Unknown `use=` preset.

- Trigger: `use="swirl"`.
- Fix: See Ch14 library.

## ATML0028 · error — Unknown ATMLScript action.

- Trigger: `-> explode x`.
- Fix: Grammar is play/pause/seek/toggle/goto/restart/set (Ch16).

## ATML0029 · error — Bad selector.

- Trigger: `on click ###`.
- Fix: Use valid CSS selectors.

## ATML0030 · warning — Suspicious rotation pivot.

- Trigger: Limb rotates ±60° about center.
- Fix: Add `pivot="x,y"` at the joint (Ch8).

## ATML0031 · warning — Merged duplicate block.

- Trigger: Two `<script type="text/atml">`.
- Fix: Merged in order; prefer one.

## ATML0032 · warning — Fill gap at 0%/100%.

- Trigger: First key at 30%.
- Fix: Add keys or rely on `fill` deliberately.

## ATML0033 · warning — `f` duration without pinned fps.

- Trigger: `dur="48f"`, no fps nearby.
- Fix: Pin fps at tween/scene/stage.

## ATML0034 · warning — Reduced-motion disabled.

- Trigger: `--no-reduced-motion` used.
- Fix: Re-enable unless kiosk use (Ch27).

## ATML0035 · error — Version mismatch.

- Trigger: `version="2.0.0"` on 1.0 compiler.
- Fix: Set `version="1.0.0"` (Ch28).

## ATML0036 · warning — Deprecated alias.

- Trigger: `stroke-width=` instead of `stroke-w=`.
- Fix: Rename; alias removed in 2.0.

## ATML0037 · warning — Off-grid coordinate (`--align`).

- Trigger: `x="13"` with `--align 8`.
- Fix: Advisory only; snap or ignore.

## ATML0038 · warning — Large image asset.

- Trigger: `src` > 500KB.
- Fix: Compress or redraw as actors.

## ATML0039 · error — Sprite frame out of range.

- Trigger: `sprite-frame="9"` on 6-frame strip.
- Fix: Clamp to 0..N-1.

## ATML0040 · error — Timeline `clip for=` dangling.

- Trigger: `for="ghost"`.
- Fix: Point at an existing actor/scene id.

Debug workflow: `./atml check file.atml` → fix fatals top-down (later errors are often
cascades) → `./atml serve` for the visual + overlay console → `build --lenient` only to
triage, never to ship.

---
# Ch25 — Editor setup: VS Code / Cursor / JetBrains / Devin

Extension id **`atml`**, version 1.0.0, source in `vscode-atml/`.

## 25.1 VS Code

1. Build/install: `cd vscode-atml && npm install && npx vsce package && code --install-extension atml-1.0.0.vsix`.
2. Features: syntax highlight (`syntaxes/atml.tmLanguage.json`), snippets
   (`atml-stage`, `atml-actor`, `atml-key`, `atml-tween`, `atml-transition`, `atml-timeline`),
   `Tasks: ATML build` (Ctrl+Shift+B), hover docs for every attr, `check` diagnostics as squiggles.
3. Preview: `ATML: Serve preview` opens `serve` + browser side by side.

## 25.2 Cursor

1. Same VSIX: `Extensions → … → Install from VSIX → atml-1.0.0.vsix`.
2. Add to `.cursor/rules`: `Treat *.atml as ATML 1.0.0 markup (XML dialect). Build with `python3 compiler/atmlc.py build`.`
3. Ask Cursor: *"add a 600ms fade-up entrance to every .card"* — it will emit `a-*` sugar correctly after seeing one example.

## 25.3 JetBrains (IntelliJ / WebStorm / PyCharm)

1. `Settings → Editor → File Types → HTML → + *.atml` (highlighting now).
2. Optional: import `vscode-atml/syntaxes/atml.tmLanguage.json` via TextMate Bundles plugin.
3. External tool: `Program: python3`, `Args: compiler/atmlc.py build $FilePath$ -o $FileDir$/$FileNameWithoutExtension$.html`, `Working dir: $ProjectFileDir$`. Bind to a hotkey.
4. Live templates for `actor/key/tween` (XML templates, copy from `vscode-atml/snippets/`).

## 25.4 Devin (headless agent)

Give Devin: repo URL + `ATML_LANGUAGE_GUIDE.md` + the instruction *"ATML 1.0.0; compile
with `python3 compiler/atmlc.py build <f>.atml -o out.html`; run `./atml check` before
declaring done; docs-only PRs unless compiler change requested."* Devin can scaffold
(`new`), batch-build examples, and `publish` static sites without interaction.

---
# Ch26 — Performance & limits

| Budget | Limit | Why / what to do |
|---|---|---|
| Actors per scene | ~500 soft | beyond: merge static set-dressing into one `<path>` |
| Keys per tween | ~64 soft | beyond: split across chained tweens/timelines |
| `<pixel>` cells | 64×64 hard (ATML0016) | tile bigger art |
| Image asset | 500KB advisory (ATML0038) | compress; SVG actors are free |
| Sprite strip | ≤2048px wide | mobile GPU texture comfort |
| fps | 1–240 hard | prefer 12/30/60 (Ch18) |
| Output HTML | aim < 1MB | `--minify`; externalize big images |

Cheap-vs-dear: `transform/opacity` keyframes (GPU) > `fill/stroke` lerp (paint) > `d/points`
morph (layout-ish, keep ≤ a few at once) > JS timelines (one rAF loop total — fine).
`float`/`pulse` presets are transform-only by design; `morph`/`draw` are the dear ones.
Measure with `serve` + browser devtools; halve fps before simplifying choreography.

---
# Ch27 — Accessibility

1. **Reduced motion first**: output collapses animation under `prefers-reduced-motion` (Ch18.4). Never ship `--no-reduced-motion` for public sites.
2. **Labels**: `alt` on `<image>`, `aria-label` passes through on any HTML, `<title>` inside actors becomes SVG-accessible name.
3. **Keyboard**: triggers used by click should also bind `onkey:Enter` (Ch19 modal example); player buttons are real `<button>`s.
4. **Contrast**: no enforcement — run your palette through a contrast checker; text actors over art need scrims.
5. **Seizure safety**: keep full-screen flashes ≤3/s; the compiler warns when opacity keyframes strobe faster than 3Hz across >40% of stage area.
6. **Opt-in motion**: `data-atml-motion="always"` forces animation even under reduced-motion (use for essential instructional motion only, with a static fallback caption).

---
# Ch28 — Versioning (1.0.0 policy)

ATML follows SemVer for both language and compiler, locked together at **1.0.0**:

| Bump | Means | Example |
|---|---|---|
| patch `1.0.x` | bugfix, output-identical or closer-to-spec | 1.0.1 fixes a bezier sampler |
| minor `1.x.0` | additive, old files still build | 1.1.0 adds a `use="confetti"` preset |
| major `X.0.0` | breaking, files pin `version` | 2.0.0 removes `stroke-width` alias |

Per-file pin: `<atml version="1.0.0">`. A 1.x compiler **builds** any `1.0.x` file,
**warns** (`ATML0035`) on `0.x` or `≥2.0`, and **refuses** unknown majors without `--lenient`.
Deprecated spellings (e.g. `stroke-width`) warn for one full minor series before removal.
Changelog: AppF.

---
# AppA — Full tag reference (every tag × every attr)

`R` = required. Defaults in backticks. Parent = where the tag may appear.

## `<atml>` — parent: root (1×/file)

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `version` | R | — | language version, `1.0.0` |
| `title` | – | `Untitled` | page title |
| `desc` | – | — | meta description |
| `keywords` | – | — | meta keywords |
| `og-image` | – | — | OG image |
| `lang` | – | `en` | html lang |
| `bg` | – | #fff | page bg |

## `<stage>` — parent: atml (1×)

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `width` | R | — | px |
| `height` | R | — | px |
| `fps` | – | `60` | 1–240 |
| `bg` | – | transparent | color |
| `grid` | – | off | guide step px |
| `show-grid` | – | `false` | emit grid in build |
| `responsive` | – | `true` | scale to container |

## `<scene>` — parent: stage (1..n)

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `id` | R | — | unique |
| `dur` | R | — | ms/s/f |
| `bg` | – | inherit | color/url |
| `fps` | – | inherit | 1–240 |
| `loop` | – | `false` | bool/count/infinite |
| `ease` | – | `linear` | default easing |
| `trigger` | – | `auto` | Ch19 |
| `next` | – | next sibling | scene id/none |

## `<actor>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `id` | R | — | unique |
| `shape` | R | — | rect circle ellipse line poly path text image group |
| `x/y` | ~R | `0` | position |
| `w/h` | rect·image | — | size |
| `cx/cy` | circ·ell | — | center |
| `r` | circle | — | radius |
| `rx/ry` | ell·rect | — | radii/corners |
| `x1/y1/x2/y2` | line | — | endpoints |
| `points` | poly | — | vertices |
| `d` | path | — | M L C Q Z |
| `str` | text | — | string |
| `src` | image | — | asset |
| `fill` | – | `#7dd3fc` | color/none |
| `stroke` | – | `none` | color |
| `stroke-w` | – | `2` | px |
| `opacity` | – | `1` | 0–1 |
| `rotate` | – | `0` | deg |
| `scale/sx/sy` | – | `1` | factor |
| `anchor` | – | shape dep. | Ch9 |
| `z` | – | doc order | int |
| `fps` | – | inherit | 1–240 |
| `trigger` | – | inherit | Ch19 |
| `class` | – | — | CSS classes |

## `<rect>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `x` | – | `0` |  |
| `y` | – | `0` |  |
| `w` | R | — |  |
| `h` | R | — |  |
| `rx` | – | `0` | corner |
| `fill/stroke/stroke-w/opacity/z` | – | actor deps |  |

## `<circle>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `cx` | R | — |  |
| `cy` | R | — |  |
| `r` | R | — | ≥0 |
| `fill/stroke/opacity/z` | – | actor deps |  |

## `<ellipse>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `cx/cy` | R | — |  |
| `rx/ry` | R | — |  |
| `fill/stroke/opacity/z` | – | actor deps |  |

## `<line>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `x1/y1/x2/y2` | R | — |  |
| `stroke` | – | `#fff` |  |
| `stroke-w` | – | `2` |  |

## `<poly>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `points` | R | — | ≥3 vertices |
| `fill/stroke/z` | – | actor deps |  |

## `<path>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `d` | R | — | M L C Q Z |
| `fill/stroke/stroke-w/z` | – | actor deps |  |

## `<draw>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `d` | R | — | self-drawn stroke |
| `stroke/stroke-w` | – | `#7dd3fc/6` |  |
| `dur/ease` | – | `1.5s/linear` | draw pacing |

## `<text>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `x/y/str` | R | — |  |
| `font` | – | `32px system-ui` |  |
| `fill/anchor/letter-spacing` | – | deps |  |

## `<image>` — parent: scene/group

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `x/y/w/h/src` | R* | — | *src always R |
| `fit` | – | `contain` | contain/cover/fill |
| `alt` | – | — | a11y label |

## `<pixel>` — parent: scene

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `id/grid/palette` | R | — | rows equal, ≤64² |
| `x/y` | – | `0` |  |
| `scale` | – | `8` | px per cell |
| `+actor anim attrs` | – | deps | opacity/rotate/z/fps… |

## `<part>` — parent: actor[group]

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `id/shape` | R | — | any drawable |
| `geometry` | per shape | — | relative coords |
| `pivot` | – | center | rotation joint |
| `z` | – | doc order |  |

## `<key>` — parent: actor/part/camera

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `at` | R | — | % or ms/s/f stop |
| `any Ch11 prop` | – | — | interpolated |
| `ease` | – | inherit | segment easing |

## `<tween>` — parent: actor/part (≤1)

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `dur` | – | `1s` |  |
| `delay` | – | `0ms` | neg = scrub-in |
| `fps` | – | inherit | 1–240 |
| `ease` | – | `linear` |  |
| `loop` | – | `false` |  |
| `direction` | – | `normal` | 4 values |
| `fill` | – | `both` | 4 values |
| `trigger` | – | inherit |  |

## `<timeline>` — parent: scene

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `id` | R | — |  |
| `dur` | – | longest clip |  |
| `loop` | – | `false` |  |
| `autoplay` | – | `true` |  |

## `<clip>` — parent: timeline

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `for` | R | — | actor/scene id |
| `at` | – | `0s` | master offset |
| `dur` | – | target dur |  |
| `ease` | – | inherit |  |
| `trigger` | – | inherit |  |

## `<transition>` — parent: scene/actor-level

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `id/use` | R | — | preset Ch14 |
| `dur/delay/ease/loop/direction/trigger` | – | preset deps | overrides |
| `dx/dy/scale/turns/amp/deg/from/to/dir` | – | preset-specific |  |

## `<camera>` — parent: scene (≤1)

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `x/y` | – | `0` | pan |
| `zoom` | – | `1` | dolly |
| `follow` | – | — | actor id |
| `shake/shake-dur` | – | `0/500ms` | trauma |
| `bounds` | – | stage | clamp box |

## `<script>` — parent: scene

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `type` | R | — | `text/atml` = ATMLScript, else verbatim JS |
| `wiring statements` | if atml | — | Ch16 grammar |

## `<style>` — parent: scene/stage

| Attr | Req | Default | Meaning |
|---|---|---|---|
| `verbatim CSS` | R | — | merged after generated keyframes (wins ties) |

---
# AppB — Animatable-props matrix (prop × tag support)

`●` interpolates · `○` steps (jumps at key) · `—` not applicable (ATML0023 if keyed).

| Prop | actor | part | camera | sugar (`a-*`) | pixel | Mode |
|---|---|---|---|---|---|---|
| `x / y` | ● | ● | ● (pan) | via slide | — (x/y whole) | interp |
| `cx / cy` | ● | ● | — | — | — | interp |
| `r / rx / ry` | ● | ● | — | — | — | interp |
| `w / h` | ● | ● | — | — | — | interp |
| `x1 y1 x2 y2` | ● | ● | — | — | — | interp |
| `points` | ● | ● | — | — | — | interp iff same count |
| `d` | ● | ● | — | — | — | interp iff same skeleton |
| `fill / stroke` | ● | ● | — | — | — | color lerp |
| `stroke-w` | ● | ● | — | — | — | interp |
| `opacity` | ● | ● | — | fade | ● | interp |
| `rotate` | ● | ● | — | spin/wiggle | ● | interp shortest-path |
| `scale sx sy` | ● | ● | ● (zoom) | pulse | ● (whole) | interp |
| `tx ty` | ● | ● | — | slide compose | — | interp |
| `skew skewX skewY` | ● | ● | — | — | — | interp |
| `font-size` | ● (text) | ● | — | — | — | interp |
| `letter-spacing` | ● (text) | ● | — | — | — | interp |
| `z / grid-frame / visibility` | ○ | ○ | — | — | ○ frame | steps |
| `sprite-frame` | ●-steps | — | — | — | — | steps |
| `zoom (camera)` | — | — | ● | — | — | interp |

Rule of thumb: if it is a number, color, or same-skeleton path — it interpolates.
Counts/ids/strings step. When in doubt, `check` tells you (`ATML0023`).

---
# AppC — Easing cheatsheet (one page)

| Need | Use | Avoid |
|---|---|---|
| default entrance | `cubic-out` / `ease-out` | `linear` (robotic) |
| exit | `ease-in` / `quad-in` | `*-out` (floats away slowly) |
| loop / ambient | `sine-in-out` | `expo` (jerky at wrap) |
| weight / gravity | `quad-in` down, `quad-out` up | symmetric easings |
| UI snap | `quart-out` / `expo-out` | `back` on long text |
| playfulness | `back-out` / `bounce-out` | on paragraphs |
| camera | `sine-in-out` / `cubic-in-out` | `linear` unless mechanical |
| pixel art | `linear` + low fps | smooth easings (mushy pixels) |
| scrub/timeline | `linear` (clock is the easing) | anything else |

Copy-paste defaults: actor entrance `<tween dur="600ms" ease="cubic-out" fill="both" />`;
ambient `<tween dur="3s" ease="sine-in-out" loop="infinite" direction="alternate" />`;
ball `<tween dur="1s" ease="quad-in-out" loop="infinite" direction="alternate" />`.

---
# AppD — Dog tutorial, start to finish

Goal: the README dog, standing, tail wagging, walking across the stage. Six steps.

**Step 0 — scaffold.** `mkdir dog && cd dog && ../atml new rex --template dog` (or paste step 1).

**Step 1 — stage + ground.**

```atml
<atml version="1.0.0" title="Rex">
  <stage width="800" height="450" fps="60" bg="#0b1020" grid="20">
    <scene id="main" dur="6s" loop="infinite">
      <actor id="ground" shape="rect" x="0" y="390" w="800" h="60" fill="#1b2340" />
    </scene>
  </stage>
</atml>
```

**Step 2 — body masses (ellipses read as torso + head; no detail yet).**

```atml
<actor id="rex" shape="group" x="120" y="230">
  <part id="body" shape="ellipse" cx="0" cy="40" rx="90" ry="55" fill="#c98f4e" />
  <part id="head" shape="circle" cx="90" cy="-10" r="48" fill="#d9a45f" />
</actor>
```

**Step 3 — face + ears (small dark shapes carry all the character).**

```atml
<part id="ear" shape="ellipse" cx="70" cy="-48" rx="16" ry="30" fill="#8a5a2b" />
<part id="snout" shape="ellipse" cx="126" cy="2" rx="26" ry="18" fill="#f2d3a0" />
<part id="nose" shape="circle" cx="146" cy="-4" r="8" fill="#222222" />
<part id="eye" shape="circle" cx="102" cy="-20" r="7" fill="#222222" />
<part id="leg1" shape="rect" x="-60" y="80" w="24" h="60" rx="10" fill="#b57a3e" />
<part id="leg2" shape="rect" x="36" y="80" w="24" h="60" rx="10" fill="#b57a3e" />
<part id="tail" shape="path" d="M -88 30 Q -130 0 -118 -44" stroke="#c98f4e" stroke-w="16" fill="none" pivot="-88,30" />
```

**Step 4 — wag (pivot at tail base, ±15°, 0.5s loop).**

```atml
<part id="tail" shape="path" d="M -88 30 Q -130 0 -118 -44" stroke="#c98f4e" stroke-w="16" fill="none" pivot="-88,30">
  <key at="0%" rotate="-14" /><key at="50%" rotate="16" /><key at="100%" rotate="-14" />
  <tween dur="0.5s" loop="infinite" ease="sine-in-out" />
</part>
```

**Step 5 — walk (group tween; bob the head against the stride).**

```atml
<actor id="rex" shape="group" x="120" y="230">
  <!-- parts from steps 2-4 -->
  <key at="0%" x="120" /><key at="100%" x="640" />
  <tween dur="6s" ease="linear" loop="infinite" />
</actor>
```

**Step 6 — build, check, admire.** `./atml check rex.atml && ./atml build rex.atml -o rex.html`.
Common fixes: tail orbits instead of wagging → `pivot` missing (ATML0030); legs detach
while walking → legs are parts (relative) not actors (absolute) — keep them inside the group.

---
# AppE — Migrate HTML → ATML checklist

- [ ] 1. Wrap one section in `<atml><stage><scene>`; `build`; pixel-diff (must be identical).
- [ ] 2. Add document `title/desc` (Ch22.4 SEO).
- [ ] 3. Sugar entrances: `a-fade` + `a-slide-up` on hero/cards; `a-delay` stagger.
- [ ] 4. Convert the logo/hero art to `<actor>` with measured coordinates.
- [ ] 5. Replace GIF/spinner with `a-spin` or `<transition use="spin">`.
- [ ] 6. Wire buttons: `trigger="onclick:#id"` or ATMLScript `on click … -> …`.
- [ ] 7. Scroll reveals: `a-trigger="onvisible"`.
- [ ] 8. Move page to `publish` output; verify assets copied, links relative.
- [ ] 9. Reduced-motion pass: enable-reduced-motion default, test in DevTools emulation.
- [ ] 10. Fonts: keep system stack or add one `<link>` webfont; re-check layout.
- [ ] 11. `check` clean (zero fatals, triage warnings), examples still build.
- [ ] 12. Deploy `dist/` to Pages/Netlify/Vercel/cPanel (Ch22.5); smoke-test `file://` too.

---
# AppF — Changelog

## 1.1.1 — 2026-10-04

- Fix: `build -o` creates missing output directories (`dist/` no longer needs
  to exist first).

## 1.1.0 — 2026-10-04

- `publish` is now implemented in the compiler (previously spec-only): multi-page
  `IN.atml [...] -o DIST/ [--base] [--minify] [--fps]`, local asset copy with
  `ATML0012` on missing files, `.nojekyll`, `sitemap.xml` for multi-page.
- VS Code extension: new `ATML: Publish Site to dist/` command (`atml.publish`).

## 1.0.0 — 2026-10-04 (initial public release)

- Language: `<atml>/<stage>/<scene>/<actor>` + full geometry set (`rect circle ellipse
  line poly path draw text image`), `<pixel>`, `<part>`, `<key>/<tween>`,
  `<timeline>/<clip>`, `<transition>` library (fade/slide/bounce/spin/float/wiggle/pulse/morph/draw),
  `a-*` sugar (11 attrs), ATMLScript (`on … -> play/pause/seek/toggle/goto/restart/set`),
  `<camera>` (pan/zoom/follow/shake), sprites, per-level fps 1–240.
- Compiler `atmlc` (`python3 compiler/atmlc.py`, shim `./atml`): `build/check/new/serve/publish`,
  exit codes 0–3, diagnostics `ATML0001…ATML0040`, `--lenient/--minify/--align`.
- Runtime: single inline vanilla-JS, CSS-first motion, `prefers-reduced-motion` default.
- Editors: VS Code extension (`atml` 1.0.0) + Cursor/JetBrains/Devin recipes.
- Installers: Arch PKGBUILD, Debian package, Fedora spec, Windows zip (see `installer/`).
- Docs: this guide + README quickstart (bouncing ball) + examples (`ball dog site
  transitions timeline pixel-heart`).
- Compatibility promise: every `version="1.0.0"` file builds on all future 1.x compilers.

---
*End of ATML Language Guide v1.1.0. Happy animating.*
---
# AppG — Runnable gallery (10 end-to-end scenes)

Every scene below is complete: save as `gN.atml`, `./atml build gN.atml -o gN.html`, open.
Each teaches one composition from Ch1–Ch28 in under 40 lines.

## g1 — sunrise (fill lerp + ease-out entrance)

Sky warms from night to dawn while the sun rises with a soft stop.

```atml
<atml version="1.0.0" title="Sunrise">
  <stage width="800" height="450" fps="30" bg="#0b1020">
    <scene id="main" dur="4s" bg="#0b1020">
      <actor id="sky" shape="rect" x="0" y="0" w="800" h="450" fill="#0b1020">
        <key at="0%" fill="#0b1020" /><key at="100%" fill="#f59e0b" />
        <tween dur="4s" ease="sine-in-out" fill="both" />
      </actor>
      <actor id="sun" shape="circle" cx="400" cy="420" r="50" fill="#fde68a">
        <key at="0%" cy="420" opacity="0.4" /><key at="100%" cy="180" opacity="1" />
        <tween dur="4s" ease="cubic-out" fill="both" />
      </actor>
    </scene>
  </stage>
</atml>
```

## g2 — typewriter caption (letter-spacing + opacity)

A title that fades in while its tracking tightens — the docs-site staple.

```atml
<atml version="1.0.0" title="Typewriter">
  <stage width="800" height="450" fps="60" bg="#111827">
    <scene id="main" dur="2s">
      <actor id="t" shape="text" x="50%" y="50%" str="ship it" font="bold 72px system-ui" fill="#ffffff" anchor="center">
        <key at="0%" opacity="0" letter-spacing="24" /><key at="100%" opacity="1" letter-spacing="4" />
        <tween dur="1.6s" ease="cubic-out" fill="both" />
      </actor>
    </scene>
  </stage>
</atml>
```

## g3 — loading spinner (spin transition, infinite)

One tag of motion: a dashed arc spinning forever. The honest loader.

```atml
<atml version="1.0.0" title="Spinner">
  <stage width="400" height="400" fps="60" bg="#ffffff">
    <scene id="main" dur="1s" loop="infinite">
      <transition id="spin1" use="spin" dur="1s" turns="1" loop="infinite" />
      <actor id="arc" shape="circle" cx="200" cy="200" r="60" fill="none" stroke="#3b82f6" stroke-w="10" trigger="spin1" />
    </scene>
  </stage>
</atml>
```

## g4 — toast notification (slide + fade + fill-forwards stick)

Slides up, fades in, stays. The `fill=forwards` landing pattern.

```atml
<atml version="1.0.0" title="Toast">
  <stage width="800" height="450" fps="60" bg="#0b1020">
    <scene id="main" dur="3s">
      <actor id="toast" shape="rect" x="250" y="500" w="300" h="70" rx="14" fill="#ffffff">
        <key at="0%" y="500" opacity="0" /><key at="100%" y="340" opacity="1" />
        <tween dur="600ms" delay="400ms" ease="cubic-out" fill="forwards" />
      </actor>
    </scene>
  </stage>
</atml>
```

## g5 — bouncing ball with squash (per-key easing gravity cheat)

Ch10's gravity recipe rendered whole: quad-in down, quad-out up, squash frame.

```atml
<atml version="1.0.0" title="Ball Physics">
  <stage width="800" height="600" fps="60" bg="#0b1020">
    <scene id="main" dur="2s" loop="infinite">
      <actor id="ball" shape="circle" cx="400" cy="100" r="36" fill="#ff5a5a">
        <key at="0%" cy="100" ease="quad-in" />
        <key at="45%" cy="504" sy="1" ease="quad-out" />
        <key at="55%" cy="504" sy="0.72" sx="1.22" />
        <key at="75%" cy="260" sy="1" sx="1" />
        <key at="100%" cy="100" />
        <tween dur="2s" ease="linear" loop="infinite" />
      </actor>
    </scene>
  </stage>
</atml>
```

## g6 — self-drawing signature (draw preset)

A cubic path that inks itself, then holds. Wedding-invite technology.

```atml
<atml version="1.0.0" title="Signature">
  <stage width="800" height="450" fps="60" bg="#fffbeb">
    <scene id="main" dur="2.5s">
      <draw d="M 150 300 C 300 100 450 100 520 260 C 560 330 660 300 700 220" stroke="#1e3a8a" stroke-w="6" dur="2s" ease="ease-in-out" />
    </scene>
  </stage>
</atml>
```

## g7 — pixel-heart beating at 12fps

Ch7's heart with a pulse tween. Proof that low fps is a feature.

```atml
<atml version="1.0.0" title="Heart">
  <stage width="800" height="450" fps="12" bg="#1a1b26">
    <scene id="main" dur="1s" loop="infinite">
      <pixel id="heart" x="352" y="150" scale="12" palette="R=#ff5a5a;W=#ffffff">
        <grid>.RR.RR.. RRRRRRRR RWWRRWRR RRRRRRRR .RRRRRR. ..RRRR.. ...RR... ....R...</grid>
        <key at="0%" scale="12" /><key at="15%" scale="15" /><key at="30%" scale="12" /><key at="100%" scale="12" />
        <tween dur="1s" loop="infinite" />
      </pixel>
    </scene>
  </stage>
</atml>
```

## g8 — camera dolly across a wide world

World is 2400px; stage is 800px; camera does the walking (Ch20 recipe).

```atml
<atml version="1.0.0" title="Dolly">
  <stage width="800" height="450" fps="60" bg="#0e1530">
    <scene id="main" dur="6s">
      <camera x="0" y="0" zoom="1">
        <key at="0%" x="0" zoom="1" /><key at="100%" x="800" zoom="1.3" />
        <tween dur="6s" ease="sine-in-out" />
      </camera>
      <actor id="m1" shape="circle" cx="300" cy="300" r="80" fill="#7dd3fc" />
      <actor id="m2" shape="circle" cx="1200" cy="200" r="120" fill="#f472b6" />
      <actor id="m3" shape="circle" cx="2100" cy="320" r="60" fill="#34d399" />
    </scene>
  </stage>
</atml>
```

## g9 — scroll-reveal cards (sugar only, no stage actors)

Pure HTML + a-* sugar: the migration-step-2 pattern that ships real sites.

```atml
<atml version="1.0.0" title="Cards">
  <stage width="800" height="450" fps="60" bg="#f8fafc">
    <scene id="main" dur="3s">
      <div class="card" a-fade="in 600ms" a-slide-up="24px 600ms" a-delay="0ms" a-trigger="onvisible">one</div>
      <div class="card" a-fade="in 600ms" a-slide-up="24px 600ms" a-delay="120ms" a-trigger="onvisible">two</div>
      <div class="card" a-fade="in 600ms" a-slide-up="24px 600ms" a-delay="240ms" a-trigger="onvisible">three</div>
    </scene>
  </stage>
</atml>
```

## g10 — click-to-jump with ATMLScript (event wiring, zero JS)

Button + script + trigger: the smallest interactive. Ch16 + Ch19 combined.

```atml
<atml version="1.0.0" title="Jump">
  <stage width="800" height="450" fps="60" bg="#0b1020">
    <scene id="main" dur="1s">
      <actor id="rex" shape="circle" cx="400" cy="350" r="40" fill="#ff5a5a" trigger="onclick:#go">
        <key at="0%" cy="350" /><key at="50%" cy="150" /><key at="100%" cy="350" />
        <tween dur="1s" ease="quad-in-out" />
      </actor>
      <button id="go">Jump</button>
      <script type="text/atml">
        on click #go -> restart rex
      </script>
    </scene>
  </stage>
</atml>
```

---
# AppH — CLI transcripts (what success and failure look like)

## `check` on a healthy file

```text
$ ./atml check examples/ball.atml
ball.atml: OK (0 errors, 0 warnings) — stage 800x600 @60fps, 1 scene, 3 actors
exit 0
```

## `check` catching three mistakes at once

```text
$ ./atml check wip.atml
wip.atml:7:22: ATML0004 fatal: duplicate id 'ball' (first seen line 4)
wip.atml:9:15: ATML0025 error: unknown easing 'bouncy' — did you mean 'bounce-out'?
wip.atml:12:9: ATML0032 warning: first key at 30% with fill='none'; pose before 30% is the base pose
found 1 fatal, 1 error, 1 warning — exit 3
```

## `build` with `--lenient` triage vs strict

```text
$ ./atml build wip.atml -o wip.html --lenient
warning ATML0009: fps '500' clamped to 240 (actor 'bg')
built wip.html (warnings: 1, errors clamped: 1) — exit 0
$ ./atml build wip.atml -o wip.html
wip.atml:9:15: ATML0025 error: unknown easing 'bouncy'
no output written — exit 2
```

## `new` → `build` → `serve` → `publish` happy path

```text
$ ./atml new site --template site
wrote site.atml (edit <title>, then build)
$ ./atml build site.atml -o dist/index.html --minify
built dist/index.html (42 KB, 60fps, reduced-motion on)
$ ./atml serve --port 8000 --dir . &
serving .:8000 with live rebuild (grid overlay on, error overlay on)
$ ./atml publish site.atml -o dist/ --base /myrepo/
published 1 page + 4 assets to dist/ (base /myrepo/)
```

## `serve` overlay showing a runtime diagnostic

```text
[atml serve] rebuilt ball.atml -> ball.html in 41ms
[atml overlay] ATML0030: 'tail' rotates +/-42deg about center — set pivot='-88,30'? (Ch8)
```

---
# AppI — Twelve graded drills (learn ATML in an afternoon)

Each drill states a goal, the tags involved, and a check. Do them in order; each
assumes the previous. Build every drill (`./atml build dN.atml -o dN.html`) and watch it.

## D1 — first stage (10 min)

Tags: `atml stage scene actor(rect)`. Goal: render one static rect.

Place `<actor id="a" shape="rect" x="100" y="100" w="200" h="120" fill="#7dd3fc" />` on an 800×600 stage. Check: `check` is clean; the rect sits exactly at (100,100).

Pass: screenshot shows the rect; moving x by 50 moves it visibly on rebuild.

## D2 — move it (15 min)

Tags: `key tween`. Goal: slide the rect left→right in 2s.

Add `<key at="0%" x="100" />`, `<key at="100%" x="500" />`, `<tween dur="2s" ease="linear" />`. Check: motion takes ~2s wall-clock.

Pass: change ease to `cubic-out`; the start visibly hurries. Revert after.

## D3 — loop the ball (15 min)

Tags: `circle loop direction`. Goal: README bouncing-ball skeleton (no squash yet).

Two keys on `cy` (100→504), `loop="infinite" direction="alternate"`. Check: ball never leaves the stage.

Pass: `fps="12"` on the actor still looks intentional, not broken.

## D4 — squash & stretch (20 min)

Tags: `sx sy` + mid keys. Goal: add the 55% squash frame from the README.

Insert `<key at="55%" cy="504" sy="0.72" sx="1.22" />`. Check: impact reads as squash, not teleport.

Pass: a classmate can point at the squash frame without being told.

## D5 — draw with path (20 min)

Tags: `draw` (M L C Q Z). Goal: self-drawing curve (gallery g6).

Copy g6, then replace the `d` with your initials drawn as one path. Check: `check` reports no ATML0014.

Pass: the line draws itself exactly once per scene play.

## D6 — morph two blobs (20 min)

Tags: `d` keyframes + morph rules (Ch6.3). Goal: blob A→blob B loop.

Write two `d` values with identical command skeletons. Check: no ATML0021.

Pass: deliberately break the skeleton (swap one C for Q) and read the ATML0021 hint; fix it.

## D7 — pixel heart (15 min)

Tags: `pixel grid palette`. Goal: render the Ch7 8×8 heart.

Copy it verbatim first. Then change one palette color. Check: rows stay equal length (no ATML0015).

Pass: draw your own 8×8 glyph (star, arrow) and render it.

## D8 — dog tail wag (25 min)

Tags: `part pivot key`. Goal: tail wags ±15° (AppD step 4).

Build the full AppD dog. Then delete `pivot` and rebuild. Check: ATML0030 fires.

Pass: restore `pivot`; wag reads as a wag, not an orbit.

## D9 — sugar a page (15 min)

Tags: `a-fade a-slide-up a-delay`. Goal: three staggered cards (Ch15.2).

Use raw HTML + sugar only — no actors. Check: output HTML contains no `a-*` attributes (compiled away).

Pass: set `a-trigger="onvisible"` and confirm cards animate on scroll, not on load.

## D10 — wire a button (20 min)

Tags: ATMLScript `on click -> restart`. Goal: gallery g10 jump button.

Add a second button that `pause`s instead. Check: both buttons work from `file://` (no server).

Pass: keyboard twin — add `on key Enter -> restart` for the same target (Ch27 rule 3).

## D11 — camera dolly (20 min)

Tags: `camera x zoom`. Goal: gallery g8 slow push-in.

Change the tween to `dur="6s" ease="sine-in-out"` and describe in one sentence why linear would feel mechanical.

Pass: add `follow` to track one circle; clamp with `bounds` so no void shows.

## D12 — publish (25 min)

Tags: CLI `publish`, SEO attrs. Goal: ship drills D9+D10 as a two-page mini-site.

Add `<atml title desc>` to both, `publish` to `dist/`, deploy to one host from Ch22.5.

Pass: cold-load the public URL on a phone; motion honors reduced-motion when enabled in OS settings.

Grading: D1–D4 must-pass (core loop); D5–D8 pick two (drawing track); D9–D12 pick two
(shipping track). A complete pass = 4 core + 2 drawing + 2 shipping = 8 drills, one afternoon.

