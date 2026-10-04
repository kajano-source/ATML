"""ATML compiler v1.0 -- Python stdlib only."""
import argparse
import html as htmlmod
import json
import os
import re
import sys
from html.parser import HTMLParser

VERSION = "1.0"
ATML_TAGS = {"atml", "stage", "scene", "actor", "animate", "timeline", "clip",
             "transition", "trigger", "camera", "loop", "key", "tween", "draw",
             "pixel", "part"}
GEOM_TAGS = {"rect", "circle", "ellipse", "line", "poly", "path", "text",
             "draw", "pixel", "part"}
SHAPES = {"rect", "circle", "ellipse", "line", "poly", "path", "text",
          "image", "sprite", "group"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
EASINGS = {"linear", "ease", "ease-in", "ease-out", "ease-in-out", "spring",
           "bounce", "elastic"}


class Node:
    def __init__(self, tag, attrs, line):
        self.tag = tag
        self.attrs = attrs or {}
        self.line = line
        self.children = []
        self.text = ""


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = Node("root", {}, 0)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        line, _ = self.getpos()
        t = tag.lower()
        ad = {}
        for k, v in attrs:
            ad[k.lower()] = v if v is not None else ""
        node = Node(t, ad, line)
        self.stack[-1].children.append(node)
        if t in VOID:
            return
        self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        line, _ = self.getpos()
        ad = {}
        for k, v in attrs:
            ad[k.lower()] = v if v is not None else ""
        node = Node(tag.lower(), ad, line)
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        t = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == t:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not data:
            return
        n = Node(None, {}, self.getpos()[0])
        n.text = data
        self.stack[-1].children.append(n)

    def handle_comment(self, data):
        n = Node("!comment", {}, self.getpos()[0])
        n.text = data
        self.stack[-1].children.append(n)


def parse_dur_ms(s, default=2000):
    if s is None or s == "":
        return default
    s = str(s).strip().lower()
    m = re.match(r"^([\d.]+)\s*ms$", s)
    if m:
        return float(m.group(1))
    m = re.match(r"^([\d.]+)\s*s$", s)
    if m:
        return float(m.group(1)) * 1000.0
    m = re.match(r"^([\d.]+)$", s)
    if m:
        return float(m.group(1)) * 1000.0
    return None


def parse_fps(v):
    if v is None or v == "":
        return None
    try:
        f = float(str(v).strip())
    except ValueError:
        return None
    if f <= 0:
        return None
    return f


def esc(s):
    return htmlmod.escape(str(s), quote=True)

class Compiler:
    def __init__(self, source, filename="<memory>", fps_override=None,
                 title_override=None):
        self.source = source
        self.filename = filename
        self.fps_override = fps_override
        self.title_override = title_override
        self.errors = []
        self.warnings = []
        self.css = []
        self.animations = {}
        self.timelines = {}
        self.transitions = {}
        self.triggers = []
        self.cameras = {}
        self.actors = {}
        self.config = {"version": "1.0", "fps": 60, "width": 800,
                       "height": 600, "title": "ATML Animation",
                       "loop": False, "autoplay": True,
                       "background": "#ffffff"}
        self._anim_seq = 0
        self._a_seq = 0
        self.has_html = bool(re.search(r"<html[\s>]", source, re.I))

    def err(self, line, msg):
        self.errors.append("%s:%s: error: %s" % (self.filename, line, msg))

    def warn(self, line, msg):
        self.warnings.append("%s:%s: warning: %s" % (self.filename, line, msg))

    def compile(self):
        tb = TreeBuilder()
        try:
            tb.feed(self.source)
            tb.close()
        except Exception as e:
            self.err(1, "parse failed: %s" % e)
        root = tb.root
        self.extract_config(root)
        if self.fps_override is not None:
            self.config["fps"] = self.fps_override
        if self.title_override is not None:
            self.config["title"] = self.title_override
        body = self.compile_children(root, in_actor=False, scene=None)
        self.validate_refs()
        if self.errors:
            raise ValueError("\n".join(self.errors))
        return self.emit_doc(body)

    def extract_config(self, root):
        found = self.find_first(root, "atml")
        if found is not None:
            a = found.attrs
            for k in ("version", "title", "background"):
                if k in a:
                    self.config[k] = a[k]
            for k in ("fps", "width", "height"):
                if k in a:
                    try:
                        self.config[k] = float(a[k]) if k == "fps" else int(float(a[k]))
                    except ValueError:
                        self.err(found.line, "invalid %s=%r" % (k, a[k]))
            for k in ("loop", "autoplay"):
                if k in a:
                    self.config[k] = str(a[k]).lower() in ("1", "true", "yes")
            self.unwrap(root, found)

    def find_first(self, node, tag):
        for c in node.children:
            if c.tag == tag:
                return c
            if c.tag is not None and not c.tag.startswith("!"):
                r = self.find_first(c, tag)
                if r is not None:
                    return r
        return None

    def unwrap(self, parent, target):
        def rec(n):
            for i, c in enumerate(n.children):
                if c is target:
                    n.children[i:i + 1] = c.children
                    return True
                if rec(c):
                    return True
            return False
        rec(parent)

    def compile_children(self, node, in_actor, scene):
        return "".join(self.compile_node(c, in_actor, scene) for c in node.children)

    def compile_node(self, node, in_actor, scene):
        if node.tag is None:
            return node.text
        if node.tag == "!comment":
            return "<!--%s-->" % node.text
        tag = node.tag
        if tag == "script" and node.attrs.get("type", "").lower() == "atml":
            raw = "".join(ch.text if ch.tag is None else "" for ch in node.children)
            js, errs = self.compile_script_block(raw, node.line)
            for e in errs:
                self.errors.append(e)
            return '<script data-atml-script="compiled">\n%s\n</script>' % js
        if tag in ("script", "style"):
            inner = "".join(ch.text if ch.tag is None
                            else self.compile_node(ch, in_actor, scene)
                            for ch in node.children)
            attr = "".join(' %s="%s"' % (k, esc(v)) for k, v in node.attrs.items())
            return "<%s%s>%s</%s>" % (tag, attr, inner, tag)
        if tag == "stage":
            return self.compile_stage(node)
        if tag == "scene":
            return self.compile_scene(node)
        if tag == "actor":
            return self.compile_actor(node)
        if tag == "animate":
            self.compile_animate(node, parent_loop=None)
            return "<!-- atml:animate %s -->" % esc(node.attrs.get("target", node.attrs.get("id", "")))
        if tag == "timeline":
            self.compile_timeline(node)
            return "<!-- atml:timeline %s -->" % esc(node.attrs.get("id", ""))
        if tag == "transition":
            self.compile_transition(node)
            return "<!-- atml:transition %s -->" % esc(node.attrs.get("id", ""))
        if tag == "trigger":
            self.compile_trigger(node)
            return "<!-- atml:trigger -->"
        if tag == "camera":
            self.compile_camera(node)
            return "<!-- atml:camera %s -->" % esc(node.attrs.get("id", ""))
        if tag == "loop":
            inner = ""
            times = node.attrs.get("times", node.attrs.get("count", "infinite"))
            for c in node.children:
                if c.tag == "animate":
                    self.compile_animate(c, parent_loop=times)
                elif c.tag is None:
                    inner += c.text
                else:
                    inner += self.compile_node(c, in_actor, scene)
            return inner
        if tag in ("key", "tween", "clip"):
            self.warn(node.line, "<%s> outside <animate>/<timeline> ignored" % tag)
            return ""
        if in_actor and tag in GEOM_TAGS:
            return self.compile_geom(node, in_actor=True)
        if tag in ATML_TAGS:
            self.warn(node.line, "<%s> unexpected here; skipped" % tag)
            return self.compile_children(node, in_actor, scene)
        return self.compile_html_elem(node, in_actor, scene)

    def compile_html_elem(self, node, in_actor, scene):
        aid = self.compile_sugar(node)
        attr = ""
        for k, v in node.attrs.items():
            if k.startswith("a-"):
                continue
            attr += ' %s="%s"' % (k, esc(v))
        if aid:
            m = re.search(r'class="([^"]*)"', attr)
            if m:
                attr = attr.replace(m.group(0),
                                    'class="%s atml-a-%s"' % (m.group(1), aid), 1)
            else:
                attr += ' class="atml-a-%s"' % aid
        if node.tag in VOID and not node.children:
            return "<%s%s>" % (node.tag, attr)
        inner = self.compile_children(node, in_actor, scene)
        return "<%s%s>%s</%s>" % (node.tag, attr, inner, node.tag)

    def compile_stage(self, node):
        a = node.attrs
        sid = a.get("id", "stage")
        w = a.get("width", self.config["width"])
        h = a.get("height", self.config["height"])
        fps = a.get("fps", self.config["fps"])
        bg = a.get("background", self.config.get("background", "#ffffff"))
        try:
            w, h = int(float(w)), int(float(h))
        except ValueError:
            self.err(node.line, "invalid stage width/height")
            w, h = 800, 600
        inner = self.compile_children(node, False, None)
        return ('<div class="atml-stage" data-stage="%s" data-fps="%s" '
                'style="width:%spx;max-width:100%%;aspect-ratio:%d / %d;'
                'background:%s;position:relative;overflow:hidden;margin:0 auto;">'
                '%s</div>' % (esc(sid), esc(str(fps)), w, w, h, esc(str(bg)), inner))

    def compile_scene(self, node):
        a = node.attrs
        sid = a.get("id", "scene")
        dur = a.get("dur", a.get("duration", ""))
        bg = a.get("background", "transparent")
        inner = self.compile_children(node, False, sid)
        extra = ' data-dur="%s"' % esc(dur) if dur else ""
        return ('<div class="atml-scene" data-scene="%s"%s '
                'style="position:relative;width:100%%;height:100%%;background:%s;">'
                '%s</div>' % (esc(sid), extra, esc(bg), inner))

    def compile_actor(self, node):
        a = node.attrs
        aid = a.get("id", "actor%d" % (len(self.actors) + 1))
        x, y = a.get("x", 0), a.get("y", 0)
        w, h = a.get("w", a.get("width", 100)), a.get("h", a.get("height", 100))
        shape = a.get("shape", "rect")
        if shape not in SHAPES:
            self.err(node.line, "unknown actor shape=%r (expected one of %s)"
                     % (shape, sorted(SHAPES)))
            shape = "rect"
        fill = a.get("fill", "#4da3ff")
        stroke = a.get("stroke", "none")
        sw = a.get("stroke-width", a.get("strokewidth", 2))
        opacity = a.get("opacity", 1)
        rotate = a.get("rotate", 0)
        scale = a.get("scale", 1)
        anchor = a.get("anchor", "center")
        visible = a.get("visible", "true")
        z = a.get("z", 0)
        use = a.get("use", a.get("transition", ""))
        try:
            fx, fy = float(x), float(y)
        except ValueError:
            self.err(node.line, "invalid actor x/y")
            fx, fy = 0, 0
        try:
            fw = float(w)
        except ValueError:
            self.err(node.line, "invalid actor w")
            fw = 100
        try:
            fh = float(h)
        except ValueError:
            self.err(node.line, "invalid actor h")
            fh = 100
        self.actors[aid] = {"x": fx, "y": fy, "w": fw, "h": fh,
                            "shape": shape, "fill": fill}
        geoms = []
        texts = []
        for c in node.children:
            if c.tag is None:
                if c.text.strip():
                    texts.append(c.text.strip())
                continue
            if c.tag in GEOM_TAGS or c.tag in ("polygon",):
                geoms.append(self.compile_geom(c, in_actor=True,
                                               dflt_fill=fill,
                                               dflt_stroke=stroke, dflt_sw=sw))
            else:
                geoms.append(self.compile_node(c, True, None))
        if not geoms and not texts:
            geoms.append(self.default_shape(shape, fill, stroke, sw, fw, fh))
        if texts and shape == "text":
            geoms.append('<text x="50%%" y="50%%" dominant-baseline="middle" '
                         'text-anchor="middle" fill="%s">%s</text>'
                         % (esc(fill), esc(" ".join(texts))))
        elif texts:
            geoms.append(esc(" ".join(texts)))
        if shape in ("image", "sprite") and ("src" in a or "href" in a):
            src = a.get("src", a.get("href", ""))
            svg = ('<img src="%s" style="width:100%%;height:100%%;'
                   'object-fit:contain;" alt="">' % esc(src))
        else:
            svg = ('<svg width="100%%" height="100%%" viewBox="0 0 %s %s" '
                   'preserveAspectRatio="none" '
                   'style="display:block;overflow:visible;">%s</svg>'
                   % (fw, fh, "".join(geoms)))
        style = ("left:%spx;top:%spx;width:%spx;height:%spx;opacity:%s;"
                 "z-index:%s;position:absolute;"
                 % (fx, fy, fw, fh, opacity, z))
        if str(visible).lower() in ("0", "false", "no", "hidden"):
            style += "display:none;"
        transform = []
        try:
            if float(rotate):
                transform.append("rotate(%sdeg)" % rotate)
        except ValueError:
            pass
        try:
            if float(scale) != 1:
                transform.append("scale(%s)" % scale)
        except ValueError:
            pass
        if transform:
            style += "transform:%s;" % " ".join(transform)
        if anchor:
            style += "transform-origin:%s;" % esc(str(anchor).replace("_", " "))
        trans_cls = ""
        if use:
            trans_cls = " atml-trans-%s" % re.sub(r"\W+", "", use)
        html = ('<div class="atml-actor%s" data-atml-id="%s" style="%s">%s</div>'
                % (trans_cls, esc(aid), style, svg))
        if use:
            self._anim_seq += 1
            tr = self.transitions.get(use)
            if tr:
                base = dict(tr)
            else:
                base = {"dur": 1000,
                        "keys": [{"at": "0%", "opacity": 0},
                                 {"at": "100%", "opacity": 1}],
                        "ease": "ease", "delay": 0, "fps": None,
                        "loop": 0, "direction": "normal", "fill": "both",
                        "trigger": ""}
            base["target"] = aid
            base["id"] = "use-%s-%d" % (use, self._anim_seq)
            self.animations[base["id"]] = base
            self.css.append(self.keyframes_css(base["id"], base))
        return html

    def default_shape(self, shape, fill, stroke, sw, w, h):
        if shape == "circle":
            return ('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" '
                    'stroke-width="%s"/>' % (w / 2, h / 2, min(w, h) / 2,
                                             esc(fill), esc(stroke), esc(str(sw))))
        if shape == "ellipse":
            return ('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s" '
                    'stroke="%s" stroke-width="%s"/>' % (w / 2, h / 2, w / 2,
                                                         h / 2, esc(fill),
                                                         esc(stroke), esc(str(sw))))
        if shape == "line":
            st = fill if stroke in ("none", "") else stroke
            return ('<line x1="0" y1="%s" x2="%s" y2="%s" stroke="%s" '
                    'stroke-width="%s"/>' % (h / 2, w, h / 2, esc(st), esc(str(sw))))
        if shape == "text":
            return ('<text x="50%%" y="50%%" dominant-baseline="middle" '
                    'text-anchor="middle" fill="%s">text</text>' % esc(fill))
        return ('<rect x="0" y="0" width="%s" height="%s" fill="%s" '
                'stroke="%s" stroke-width="%s"/>' % (w, h, esc(fill),
                                                     esc(stroke), esc(str(sw))))

    def compile_geom(self, node, in_actor=False, dflt_fill="#4da3ff",
                     dflt_stroke="none", dflt_sw=2):
        tag = node.tag
        a = dict(node.attrs)
        if tag == "part":
            pid = a.get("id", "part")
            parts = []
            for c in node.children:
                if c.tag is None:
                    parts.append(c.text)
                elif getattr(c, "tag", None) in GEOM_TAGS:
                    parts.append(self.compile_geom(c, True))
                else:
                    parts.append(self.compile_node(c, True, None))
            inner = "".join(parts)
            gattr = "".join(' %s="%s"' % (k, esc(v)) for k, v in a.items()
                            if k != "id")
            return '<g data-part="%s"%s>%s</g>' % (esc(pid), gattr, inner)
        if tag == "pixel":
            try:
                x = float(a.get("x", 0))
                y = float(a.get("y", 0))
                size = float(a.get("size", a.get("s", 4)))
            except ValueError:
                self.err(node.line, "invalid <pixel> x/y/size")
                x, y, size = 0, 0, 4
            color = a.get("color", a.get("fill", "#000"))
            return ('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" '
                    'data-pixels="1"/>' % (x, y, size, size, esc(color)))
        if tag == "draw":
            d = a.get("d", a.get("path", a.get("points", "")))
            morph = a.get("morph", "")
            rest = "".join(' %s="%s"' % (k, esc(v)) for k, v in a.items()
                           if k not in ("d", "path", "points", "morph"))
            m = ' data-morph="%s"' % esc(morph) if morph else ""
            return '<path d="%s"%s%s fill="%s"/>' % (esc(d), rest, m,
                                                    esc(a.get("fill", dflt_fill)))
        if tag == "poly":
            pts = a.get("points", "")
            rest = "".join(' %s="%s"' % (k, esc(v)) for k, v in a.items()
                           if k != "points")
            if not rest:
                rest = ' fill="%s"' % esc(dflt_fill)
            return '<polygon points="%s"%s/>' % (esc(pts), rest)
        if tag == "text":
            inner = "".join(c.text if c.tag is None
                            else self.compile_node(c, True, None)
                            for c in node.children)
            rest = "".join(' %s="%s"' % (k, esc(v)) for k, v in a.items())
            return "<text%s>%s</text>" % (rest, inner)
        t = {"poly": "polygon"}.get(tag, tag)
        rest = "".join(' %s="%s"' % (k, esc(v)) for k, v in a.items())
        if node.children:
            inner = "".join(c.text if c.tag is None
                            else self.compile_node(c, True, None)
                            for c in node.children)
            return "<%s%s>%s</%s>" % (t, rest, inner, t)
        return "<%s%s/>" % (t, rest)

    def anim_common(self, attrs, line):
        dur = parse_dur_ms(attrs.get("dur", attrs.get("duration", "2s")), 2000)
        if dur is None:
            self.err(line, "invalid dur=%r" % attrs.get("dur"))
            dur = 2000
        delay = parse_dur_ms(attrs.get("delay", "0s"), 0)
        if delay is None:
            self.err(line, "invalid delay=%r" % attrs.get("delay"))
            delay = 0
        fps = attrs.get("fps", None)
        if fps is not None and fps != "":
            if parse_fps(fps) is None:
                self.err(line, "invalid fps=%r (must be positive number)" % fps)
                fps = None
        ease = attrs.get("ease", attrs.get("easing", "ease"))
        if (ease not in EASINGS and not ease.startswith("cubic-bezier")
                and not ease.startswith("steps(")):
            self.warn(line, "unknown ease=%r, using as-is" % ease)
        return {"dur": dur, "delay": delay, "fps": fps, "ease": ease,
                "loop": attrs.get("loop", 0),
                "direction": attrs.get("direction", "normal"),
                "fill": attrs.get("fill", "both"),
                "trigger": attrs.get("trigger", "")}

    def compile_animate(self, node, parent_loop=None):
        a = node.attrs
        target = a.get("target", a.get("for", a.get("actor", "")))
        if not target:
            if "id" in a and a["id"] in self.actors:
                target = a["id"]
            else:
                self.err(node.line, '<animate> missing target="actorId"')
                return
        aid = a.get("id", "anim%d" % (len(self.animations) + 1))
        base = self.anim_common(a, node.line)
        base.update({"id": aid, "target": target})
        if parent_loop is not None:
            base["loop"] = parent_loop
        keys, tweens, frm, to = [], [], {}, {}
        for c in node.children:
            if c.tag == "key":
                ka = dict(c.attrs)
                at = ka.pop("at", ka.pop("offset", "0%"))
                if not re.match(r"^(\d+(\.\d+)?%|\d+(\.\d+)?\s*(ms|s)?)$",
                                str(at).strip()):
                    self.err(c.line, "invalid key at=%r" % (at,))
                    continue
                ka["at"] = at
                keys.append(ka)
            elif c.tag == "tween":
                ta = c.attrs
                if "prop" not in ta or "from" not in ta or "to" not in ta:
                    self.err(c.line, "<tween> needs prop/from/to")
                    continue
                tweens.append({"prop": ta["prop"], "from": ta["from"],
                               "to": ta["to"]})
            elif c.tag is None:
                continue
            else:
                self.warn(c.line, "<%s> unexpected inside <animate>" % c.tag)
        for k, v in a.items():
            if k.startswith("from-"):
                frm[k[5:]] = v
            elif k.startswith("to-"):
                to[k[3:]] = v
        base["keys"] = keys
        base["tweens"] = tweens
        if frm:
            base["from"] = frm
        if to:
            base["to"] = to
        self.animations[aid] = base
        self.css.append(self.keyframes_css(aid, base))

    def keyframes_css(self, aid, anim):
        stops = self.stops_for(anim)
        if not stops:
            return ""
        name = "atml-kf-%s" % re.sub(r"\W+", "", aid)
        lines = ["@keyframes %s {" % name]
        for off, props in stops:
            decls = "; ".join("%s: %s" % (self.css_prop(k), v)
                              for k, v in props.items())
            lines.append("  %s%% { %s; }" % (round(off * 100, 2), decls))
        lines.append("}")
        dur = anim.get("dur", 2000)
        delay = anim.get("delay", 0)
        loop = anim.get("loop", 0)
        sloop = str(loop)
        if sloop.lower() in ("true", "infinite", "yes"):
            it = "infinite"
        elif sloop.isdigit() and int(sloop) > 1:
            it = sloop
        else:
            it = "1"
        ease = anim.get("ease", "ease")
        if not (ease in EASINGS or ease.startswith("cubic-bezier")
                or ease.startswith("steps(")):
            ease = "ease"
        lines.append(".atml-anim-%s { animation: %s %sms %s %sms %s %s; }" %
                     (re.sub(r"\W+", "", aid), name, dur, ease, delay, it,
                      anim.get("direction", "normal")))
        return "\n".join(lines)

    def css_prop(self, k):
        return {"x": "--atml-x", "y": "--atml-y"}.get(k, k)

    def stops_for(self, anim):
        dur = anim.get("dur", 2000) or 2000
        stops = []
        for k in anim.get("keys", []):
            at = k.get("at", "0%")
            s = str(at).strip()
            if s.endswith("%"):
                try:
                    off = float(s[:-1]) / 100.0
                except ValueError:
                    continue
            else:
                ms = parse_dur_ms(s, None)
                if ms is None:
                    continue
                off = ms / dur
            props = {p: v for p, v in k.items() if p != "at"}
            stops.append((max(0.0, min(1.0, off)), props))
        for tw in anim.get("tweens", []):
            stops.append((0.0, {tw["prop"]: tw["from"]}))
            stops.append((1.0, {tw["prop"]: tw["to"]}))
        if anim.get("from") or anim.get("to"):
            stops.append((0.0, dict(anim.get("from", {}))))
            stops.append((1.0, dict(anim.get("to", {}))))
        stops.sort(key=lambda s: s[0])
        return stops

    def compile_timeline(self, node):
        a = node.attrs
        tid = a.get("id", "tl%d" % (len(self.timelines) + 1))
        tl = {"id": tid, "fps": a.get("fps", self.config["fps"]),
              "loop": a.get("loop", False),
              "autoplay": str(a.get("autoplay", "true")).lower()
              not in ("0", "false", "no"),
              "clips": []}
        if tl["fps"] not in (None, "") and parse_fps(tl["fps"]) is None:
            self.err(node.line, "invalid timeline fps=%r" % a.get("fps"))
        for c in node.children:
            if c.tag == "clip":
                ca = c.attrs
                if "target" not in ca:
                    self.err(c.line, "<clip> missing target")
                    continue
                clip = {"target": ca["target"], "at": ca.get("at", "0s"),
                        "dur": ca.get("dur", ""),
                        "action": ca.get("action", ca.get("do", "play"))}
                if "fps" in ca:
                    if parse_fps(ca["fps"]) is None:
                        self.err(c.line, "invalid clip fps=%r" % ca["fps"])
                    else:
                        clip["fps"] = ca["fps"]
                tl["clips"].append(clip)
            elif c.tag is None:
                continue
            else:
                self.warn(c.line, "<%s> unexpected inside <timeline>" % c.tag)
        self.timelines[tid] = tl

    def compile_transition(self, node):
        a = node.attrs
        tid = a.get("id", a.get("name", "trans%d" % (len(self.transitions) + 1)))
        base = self.anim_common(a, node.line)
        keys = []
        for c in node.children:
            if c.tag == "key":
                ka = dict(c.attrs)
                ka.setdefault("at", "0%")
                keys.append(ka)
        base["keys"] = keys
        base["target"] = a.get("target", "")
        self.transitions[tid] = base
        if keys:
            self.css.append(self.keyframes_css("trans-%s" % tid,
                                               dict(base, id="trans-%s" % tid)))

    def compile_trigger(self, node):
        a = node.attrs
        on = a.get("on", "")
        if not on:
            self.err(node.line, '<trigger> missing on="click|hover|scroll|'
                     'load|view|time:..|key:.."')
            return
        tgt = a.get("target", a.get("for", a.get("selector", "")))
        do = a.get("do", a.get("action", "play"))
        self.triggers.append({"on": on, "target": tgt or a.get("animate", ""),
                              "animate": a.get("animate", a.get("play", tgt)),
                              "do": do, "to": a.get("to", ""),
                              "selector": a.get("selector", "")})

    def compile_camera(self, node):
        a = node.attrs
        cid = a.get("id", "cam%d" % (len(self.cameras) + 1))
        self.cameras[cid] = {"x": a.get("x", 0), "y": a.get("y", 0),
                             "zoom": a.get("zoom", 1),
                             "rotate": a.get("rotate", 0),
                             "shake": a.get("shake", 0),
                             "follow": a.get("follow", "")}

    def compile_sugar(self, node):
        kinds = [k for k in node.attrs if k.startswith("a-")]
        if not kinds:
            return ""
        mods = {}
        anims = {}
        for k in kinds:
            v = node.attrs[k]
            if k in ("a-fps", "a-delay", "a-dur", "a-loop", "a-trigger", "a-ease"):
                mods[k[2:]] = v
            elif k in ("a-fade", "a-slide", "a-bounce", "a-spin", "a-float",
                       "a-wiggle", "a-morph", "a-draw"):
                anims[k[2:]] = v
            else:
                self.warn(node.line, "unknown attribute %r ignored" % k)
        if not anims:
            return ""
        self._a_seq += 1
        aid = "a%d" % self._a_seq
        target = node.attrs.get("id", "a-el-%d" % self._a_seq)
        node.attrs.setdefault("data-atml-id", target)
        node.attrs.setdefault("id", target)
        dur = parse_dur_ms(mods.get("dur", "2s"), 2000)
        if dur is None:
            self.err(node.line, "invalid a-dur=%r" % mods.get("dur"))
            dur = 2000
        delay = parse_dur_ms(mods.get("delay", "0s"), 0)
        if delay is None:
            self.err(node.line, "invalid a-delay=%r" % mods.get("delay"))
            delay = 0
        anim = {"id": aid, "target": target, "dur": dur, "delay": delay,
                "fps": mods.get("fps", self.config["fps"]),
                "ease": mods.get("ease", "ease"),
                "loop": mods.get("loop", 1), "direction": "normal",
                "fill": "both", "trigger": mods.get("trigger", ""),
                "keys": self.sugar_keys(anims)}
        self.animations[aid] = anim
        self.css.append(self.keyframes_css(aid, anim))
        return self._a_seq

    def sugar_keys(self, anims):
        keys = []
        for kind, val in anims.items():
            v = (val or "").strip()
            if kind == "fade":
                if "out" in v:
                    keys += [{"at": "0%", "opacity": 1},
                             {"at": "100%", "opacity": 0}]
                else:
                    keys += [{"at": "0%", "opacity": 0},
                             {"at": "100%", "opacity": 1}]
            elif kind == "slide":
                keys += [{"at": "0%", "x": -40, "opacity": 0},
                         {"at": "100%", "x": 0, "opacity": 1}]
            elif kind == "bounce":
                keys += [{"at": "0%", "y": 0}, {"at": "30%", "y": -30},
                         {"at": "60%", "y": 0}, {"at": "80%", "y": -12},
                         {"at": "100%", "y": 0}]
            elif kind == "spin":
                keys += [{"at": "0%", "rotate": 0},
                         {"at": "100%", "rotate": 360}]
            elif kind == "float":
                keys += [{"at": "0%", "y": 0}, {"at": "50%", "y": -12},
                         {"at": "100%", "y": 0}]
            elif kind == "wiggle":
                keys += [{"at": "0%", "rotate": 0}, {"at": "25%", "rotate": 6},
                         {"at": "75%", "rotate": -6},
                         {"at": "100%", "rotate": 0}]
            elif kind == "morph":
                if "||" in v:
                    a_, b_ = v.split("||", 1)
                    keys += [{"at": "0%", "d": a_.strip()},
                             {"at": "100%", "d": b_.strip()}]
                else:
                    keys += [{"at": "0%", "scale": 1},
                             {"at": "50%", "scale": 1.1},
                             {"at": "100%", "scale": 1}]
            elif kind == "draw":
                keys += [{"at": "0%", "opacity": 0},
                         {"at": "100%", "opacity": 1}]
        return keys

    def compile_script_block(self, text, line):
        entries_js = []
        errors = []
        try:
            stmts = self.parse_script(text, line)
        except ValueError as e:
            errors.append("%s:%s: error: atml script: %s"
                          % (self.filename, line, e))
            return ("/* atml script error */", errors)
        extra_anims = {}
        for s in stmts:
            k = s["kind"]
            if k == "actor":
                self.actors[s["name"]] = s["props"]
                entries_js.append("ATML.defineActor(%s, %s);"
                                  % (json.dumps(s["name"]),
                                     json.dumps(s["props"])))
            elif k == "draw":
                aid = "script-draw-%s" % re.sub(r"\W+", "", s["name"])
                anim = {"id": aid, "target": s.get("target", s["name"]),
                        "dur": s.get("dur", 2000), "delay": 0,
                        "fps": s.get("fps", self.config["fps"]),
                        "ease": "linear", "loop": 0, "direction": "normal",
                        "fill": "both", "trigger": "",
                        "keys": [{"at": "0%", "opacity": 0},
                                 {"at": "100%", "opacity": 1}],
                        "d": s.get("d", "")}
                extra_anims[aid] = anim
                entries_js.append("ATML.defineAnimation(%s, %s);"
                                  % (json.dumps(aid), json.dumps(anim)))
            elif k == "animate":
                aid = s["name"]
                anim = {"id": aid, "target": s.get("target", aid),
                        "dur": s.get("dur", 2000), "delay": 0,
                        "fps": s.get("fps", self.config["fps"]),
                        "ease": s.get("ease", "ease"),
                        "loop": s.get("loop", 0), "direction": "normal",
                        "fill": "both", "trigger": "",
                        "keys": s.get("keys", [])}
                extra_anims[aid] = anim
                self.css.append(self.keyframes_css(aid, anim))
                entries_js.append("ATML.defineAnimation(%s, %s);"
                                  % (json.dumps(aid), json.dumps(anim)))
            elif k == "timeline":
                self.timelines[s["name"]] = {"id": s["name"],
                                             "clips": s["clips"],
                                             "autoplay": True, "loop": False,
                                             "fps": self.config["fps"]}
                entries_js.append(
                    "(function(){var d=window.__ATML__=window.__ATML__||{};"
                    "d.timelines=d.timelines||{};d.timelines[%s]=%s;})();"
                    % (json.dumps(s["name"]),
                       json.dumps(self.timelines[s["name"]])))
            elif k == "on":
                tr = {"on": s["on"], "target": s.get("selector", ""),
                      "animate": s.get("play", ""),
                      "do": s.get("do", "play"),
                      "selector": s.get("selector", "")}
                self.triggers.append(tr)
                entries_js.append(
                    "(function(){var d=window.__ATML__=window.__ATML__||{};"
                    "d.triggers=d.triggers||[];d.triggers.push(%s);"
                    "ATML.refresh();})();" % json.dumps(tr))
            elif k == "transition":
                self.transitions[s["name"]] = {"keys": s.get("keys", []),
                                               "dur": 1000}
                entries_js.append(
                    "(function(){var d=window.__ATML__=window.__ATML__||{};"
                    "d.transitions=d.transitions||{};d.transitions[%s]=%s;})();"
                    % (json.dumps(s["name"]),
                       json.dumps(s.get("keys", []))))
            elif k == "config":
                if "fps" in s:
                    self.config["fps"] = s["fps"]
                entries_js.append("/* config %s */" % json.dumps(s))
        for aid, anim in extra_anims.items():
            self.animations[aid] = anim
        return ("\n".join(entries_js) if entries_js else "/* atml: empty */",
                errors)

    def parse_script(self, text, base_line):
        stmts = []
        cleaned = []
        for ln in text.splitlines():
            s = re.sub(r"//.*$", "", ln)
            if s.strip():
                cleaned.append(s)
        src = "\n".join(cleaned)
        if not src.strip():
            return stmts
        for m in re.finditer(r"actor\s+([A-Za-z_][\w-]*)\s*\{([^}]*)\}", src):
            props = {}
            for pm in re.finditer(r"([\w-]+)\s*:\s*([^;}\n]+)",
                                  m.group(2)):
                props[pm.group(1)] = pm.group(2).strip()
            stmts.append({"kind": "actor", "name": m.group(1),
                          "props": props})
        for m in re.finditer(r"draw\s+([A-Za-z_][\w-]*)\s+using\s+path\s+"
                             r"\"([^\"]+)\"", src):
            stmts.append({"kind": "draw", "name": m.group(1),
                          "d": m.group(2), "target": m.group(1),
                          "dur": 2000})
        for m in re.finditer(
                r"animate\s+([A-Za-z_][\w-]*)"
                r"(?:\s*->\s*\{([^}]*)\})?"
                r"\s+over\s+([\d.]+\s*(?:ms|s)?)"
                r"(?:\s+ease\s+([\w-]+\(?[^;\n]*\)?))?"
                r"(?:\s+fps\s+(\d+))?"
                r"(?:\s+loop\s+(\S+))?", src):
            dur = parse_dur_ms(m.group(3).strip(), None)
            if dur is None:
                raise ValueError("bad duration %r" % m.group(3))
            keys = []
            if m.group(2):
                for pm in re.finditer(r"([\w-]+)\s*:\s*([^;}\n]+)",
                                      m.group(2)):
                    keys.append({"at": "100%", pm.group(1):
                                 pm.group(2).strip()})
            stmts.append({"kind": "animate", "name": m.group(1),
                          "target": m.group(1), "dur": dur,
                          "ease": (m.group(4) or "ease").strip(),
                          "fps": float(m.group(5)) if m.group(5) else 60,
                          "loop": m.group(6) or 0, "keys": keys})
        for m in re.finditer(r"timeline\s+([A-Za-z_][\w-]*)\s*\{([^}]*)\}",
                             src):
            clips = []
            for cm in re.finditer(r"at\s+([\d.]+\s*(?:ms|s)?)\s*:\s*"
                                  r"(play|show|hide|pause)\s+([\w-]+)",
                                  m.group(2)):
                clips.append({"target": cm.group(3), "at": cm.group(1),
                              "dur": "", "action": cm.group(2)})
            stmts.append({"kind": "timeline", "name": m.group(1),
                          "clips": clips})
        for m in re.finditer(
                r"on\s+(\w+)\s*\(\s*([^)]+?)\s*\)\s*->\s*"
                r"(play|pause|reverse|toggle|seek|show|hide)\s+([\w-]+)"
                r"(\s+reversed)?", src):
            stmts.append({"kind": "on", "on": m.group(1),
                          "selector": m.group(2).strip(),
                          "do": m.group(3), "play": m.group(4)})
        for m in re.finditer(r"transition\s+([A-Za-z_][\w-]*)\s*\{([^}]*)\}",
                             src):
            keys = []
            for pm in re.finditer(r"([\w-]+)\s*:\s*([^;}\n]+)", m.group(2)):
                keys.append({"at": "100%", pm.group(1):
                             pm.group(2).strip()})
            stmts.append({"kind": "transition", "name": m.group(1),
                          "keys": keys})
        for m in re.finditer(r"(?:^|[;\n])\s*fps\s+(\d+(?:\.\d+)?)",
                             src):
            stmts.append({"kind": "config", "fps": float(m.group(1))})
        for m in re.finditer(r"stage\s+(\d+)\s*x\s*(\d+)", src):
            stmts.append({"kind": "config", "width": int(m.group(1)),
                          "height": int(m.group(2))})
        if not stmts and src.strip():
            raise ValueError("could not parse script: %r..." % src[:60])
        return stmts

    def validate_refs(self):
        for aid, anim in self.animations.items():
            tgt = str(anim.get("target", "")).split(".")[0]
            if tgt and tgt not in self.actors and tgt.startswith("a-el-"):
                continue
            if tgt and tgt not in self.actors and not tgt.startswith("a-el"):
                # target may be plain HTML id (a-* sugar / hand HTML) -- ok
                pass

    def timeline_json(self):
        return {"version": VERSION, "fps": self.config["fps"],
                "title": self.config["title"],
                "stages": [], "scenes": [],
                "actors": self.actors, "animations": self.animations,
                "timelines": self.timelines,
                "transitions": self.transitions,
                "triggers": self.triggers, "cameras": self.cameras}

    def load_runtime(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(here, "..", "runtime", "atml.js"),
                     os.path.join(here, "atml.js"),
                     os.path.join(os.getcwd(), "runtime", "atml.js")):
            if os.path.exists(cand):
                with open(cand, "r", encoding="utf-8") as f:
                    return f.read()
        return ("/* ATML runtime missing */\n"
                "window.ATML=window.ATML||{play:function(){},pause:function(){},"
                "seek:function(){},reverse:function(){},toggle:function(){},"
                "show:function(){},hide:function(){},refresh:function(){},"
                "defineActor:function(){},defineAnimation:function(){}};")

    def emit_doc(self, body):
        data = json.dumps(self.timeline_json())
        css = "\n".join(c for c in self.css if c)
        base_css = (
            ".atml-stage{position:relative;overflow:hidden;margin:0 auto}"
            ".atml-scene{position:relative;width:100%;height:100%}"
            ".atml-actor{position:absolute}"
            ".atml-actor svg{display:block}"
        )
        runtime = self.load_runtime()
        head_extra = ("<style>\n%s\n%s\n</style>" % (base_css, css))
        payload = ("<script>window.__ATML__ = %s;</script>" % data
                   + "\n<script>\n%s\n</script>" % runtime)
        marker = "<!-- compiled with ATML v%s -->" % VERSION
        if self.has_html:
            out = body
            if re.search(r"</head\s*>", out, re.I):
                inject = head_extra + "\n" + payload + "\n</head>"
                out = re.sub(r"</head\s*>", lambda m: inject, out,
                             count=1, flags=re.I)
            else:
                out = head_extra + "\n" + payload + "\n" + out
            if marker not in out:
                out = marker + "\n" + out
            return out
        title = esc(self.config.get("title", "ATML Animation"))
        bg = esc(self.config.get("background", "#ffffff"))
        return ("<!DOCTYPE html>\n%s\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width,"
                " initial-scale=1\">\n<title>%s</title>\n%s\n%s\n</head>\n"
                "<body style=\"margin:0;background:%s;\">\n%s\n</body>\n</html>"
                % (marker, title, head_extra, payload, bg, body))


def compile_atml(source, filename="<memory>", fps=None, title=None):
    c = Compiler(source, filename, fps_override=fps, title_override=title)
    return c.compile()


def compile_file(path, out=None, fps=None, title=None, minify=False):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    html = compile_atml(src, filename=path, fps=fps, title=title)
    if minify:
        html = re.sub(r">\s+<", "><", html)
        html = re.sub(r"\n\s*", "\n", html)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
    return html


SCAFFOLD = """<atml version="1.0" fps="60" width="800" height="600" title="%(name)s">
<stage id="main" width="800" height="600" fps="60" background="#111827">
  <scene id="intro" dur="4s">
    <actor id="box" x="100" y="100" w="120" h="120" shape="rect" fill="#4da3ff">
      <rect x="0" y="0" width="120" height="120" rx="12" fill="#4da3ff"/>
    </actor>
    <animate target="box" dur="2s" ease="ease-out">
      <key at="0%%" x="100" opacity="0"/>
      <key at="100%%" x="340" opacity="1"/>
    </animate>
  </scene>
</stage>
</atml>
"""


def cmd_new(name):
    fname = name if name.endswith(".atml") else name + ".atml"
    if os.path.exists(fname):
        print("atml: %s already exists" % fname, file=sys.stderr)
        return 1
    with open(fname, "w", encoding="utf-8") as f:
        f.write(SCAFFOLD % {"name": os.path.splitext(os.path.basename(fname))[0]})
    print("created %s" % fname)
    return 0


def cmd_check(path):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        compile_atml(src, filename=path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print("%s: OK" % path)
    return 0


def cmd_build(args):
    with open(args.input, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        html = compile_atml(src, filename=args.input, fps=args.fps,
                            title=args.title)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    if args.minify:
        html = re.sub(r">\s+<", "><", html)
        html = re.sub(r"\n\s*", "\n", html)
    out = args.o or (os.path.splitext(args.input)[0] + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("compiled %s -> %s" % (args.input, out))
    return 0


def cmd_publish(args):
    import shutil
    outdir = args.o
    if not outdir:
        print("atml publish: missing -o DIST/ (output directory)", file=sys.stderr)
        return 1
    os.makedirs(outdir, exist_ok=True)
    base = (args.base or "/")
    if not base.endswith("/"):
        base += "/"
    pages = []
    for inp in args.inputs:
        with open(inp, "r", encoding="utf-8") as f:
            src = f.read()
        try:
            html = compile_atml(src, filename=inp, fps=args.fps,
                                title=args.title if len(args.inputs) == 1 else None)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        if args.minify:
            html = re.sub(r">\s+<", "><", html)
            html = re.sub(r"\n\s*", "\n", html)
        srcdir = os.path.dirname(os.path.abspath(inp)) or os.getcwd()
        refs = re.findall(r'''(?:src|href)\s*=\s*"([^"]+)"''', html)
        refs += re.findall(r"""(?:src|href)\s*=\s*'([^']+)'""", html)
        for ref in sorted(set(refs)):
            if re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#|/)", ref):
                continue  # absolute URL, protocol-relative, anchor, or root path: untouched
            clean = ref.split("?", 1)[0].split("#", 1)[0]
            fsrc = os.path.normpath(os.path.join(srcdir, clean))
            if not os.path.isfile(fsrc):
                print("%s: ATML0012 Asset not found: %s" % (inp, clean),
                      file=sys.stderr)
                return 1
            fdst = os.path.normpath(os.path.join(outdir, clean))
            os.makedirs(os.path.dirname(fdst) or outdir, exist_ok=True)
            shutil.copy2(fsrc, fdst)
            html = html.replace('"' + ref + '"', '"' + base + clean + '"')
            html = html.replace("'" + ref + "'", "'" + base + clean + "'")
        adir = os.path.join(srcdir, "assets")
        if os.path.isdir(adir):
            for root, _dirs, files in os.walk(adir):
                for fn in files:
                    fsrc = os.path.join(root, fn)
                    rel = os.path.relpath(fsrc, srcdir)
                    fdst = os.path.join(outdir, rel)
                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    shutil.copy2(fsrc, fdst)
        leaf = os.path.splitext(os.path.basename(inp))[0] + ".html"
        outname = "index.html" if len(args.inputs) == 1 else leaf
        with open(os.path.join(outdir, outname), "w", encoding="utf-8") as f:
            f.write(html)
        pages.append(outname)
        print("published %s -> %s" % (inp, os.path.join(outdir, outname)))
    with open(os.path.join(outdir, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")
    if len(pages) > 1:
        sm = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in pages:
            sm.append("  <url><loc>%s%s</loc></url>" % (base, p))
        sm.append("</urlset>")
        with open(os.path.join(outdir, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write("\n".join(sm) + "\n")
        print("wrote %s" % os.path.join(outdir, "sitemap.xml"))
    print("publish complete: %d page(s) in %s/" % (len(pages), outdir))
    return 0


def cmd_serve(path, port):
    import http.server
    import functools
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        html = compile_atml(src, filename=path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    print("serving %s at http://127.0.0.1:%d/ (Ctrl+C to stop)" % (path, port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atmlc", description="ATML compiler v1.0")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="compile .atml to .html")
    b.add_argument("input", help="input .atml file")
    b.add_argument("-o", default=None, help="output .html file")
    b.add_argument("--minify", action="store_true")
    b.add_argument("--fps", type=float, default=None)
    b.add_argument("--title", default=None)
    c = sub.add_parser("check", help="validate .atml")
    c.add_argument("input")
    n = sub.add_parser("new", help="scaffold a new .atml file")
    n.add_argument("name")
    s = sub.add_parser("serve", help="serve compiled .atml locally")
    s.add_argument("input")
    s.add_argument("--port", type=int, default=8000)
    p = sub.add_parser("publish", help="build + stage a deployable static site dir")
    p.add_argument("inputs", nargs="+", help="one or more input .atml files")
    p.add_argument("-o", default=None, help="output directory (e.g. dist/)")
    p.add_argument("--base", default="/", help="sub-path hosting base (e.g. /myrepo/)")
    p.add_argument("--minify", action="store_true")
    p.add_argument("--fps", type=float, default=None)
    p.add_argument("--title", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "check":
        return cmd_check(args.input)
    if args.cmd == "new":
        return cmd_new(args.name)
    if args.cmd == "serve":
        return cmd_serve(args.input, args.port)
    if args.cmd == "publish":
        return cmd_publish(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
