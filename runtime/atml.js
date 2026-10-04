/* ATML runtime v1.0 — standalone engine.
 * Reads window.__ATML__ (scenes/timelines/animations/triggers/cameras),
 * drives rAF throttled per-FPS, WAAPI where possible, SVG attr tween incl.
 * path `d` lerp for morph when command counts match, fallback crossfade.
 * Works with compiler output AND hand-written HTML (data-atml attributes).
 * API: ATML.play(id), ATML.pause(id), ATML.seek(id, t), ATML.reverse(id),
 *        ATML.toggle(id), ATML.show(id), ATML.hide(id), ATML.refresh(),
 *        ATML.defineActor/defineAnimation helpers for ATMLScript output.
 */
(function (global) {
  'use strict';

  var ATML = {};
  var store = { animations: {}, timelines: {}, triggers: [] };
  var state = {}; // id -> {el, anim, playing, startTime, pausedAt, reversed, raf}

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function parseDur(v, defMs) {
    if (v === undefined || v === null || v === '') return defMs;
    if (typeof v === 'number') return v;
    var s = String(v).trim().toLowerCase();
    if (s === 'infinite' || s === 'none') return defMs;
    var m = s.match(/^([\d.]+)\s*ms$/); if (m) return parseFloat(m[1]);
    m = s.match(/^([\d.]+)\s*s$/); if (m) return parseFloat(m[1]) * 1000;
    m = s.match(/^([\d.]+)$/); if (m) return parseFloat(m[1]) * 1000;
    return defMs;
  }

  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }

  // ---- easing ----
  function cubicBezier(p1x, p1y, p2x, p2y) {
    // Newton-Raphson approx
    function sampleX(t) { return 3 * p1x * t * (1 - t) * (1 - t) + 3 * p2x * t * t * (1 - t) + t * t * t; }
    function sampleY(t) { return 3 * p1y * t * (1 - t) * (1 - t) + 3 * p2y * t * t * (1 - t) + t * t * t; }
    function dx(t) { return 3 * p1x * (1 - t) * (1 - t) + 6 * (p2x - p1x) * t * (1 - t) + 3 * (1 - p2x) * t * t; }
    return function (x) {
      var t = x;
      for (var i = 0; i < 5; i++) {
        var err = sampleX(t) - x;
        if (Math.abs(err) < 1e-4) break;
        var d = dx(t); if (Math.abs(d) < 1e-4) break;
        t -= err / d;
      }
      return sampleY(t);
    };
  }
  function makeEase(name) {
    if (!name) return function (t) { return t; };
    var s = String(name).trim();
    if (s === 'linear') return function (t) { return t; };
    if (s === 'ease') return cubicBezier(0.25, 0.1, 0.25, 1);
    if (s === 'ease-in') return cubicBezier(0.42, 0, 1, 1);
    if (s === 'ease-out') return cubicBezier(0, 0, 0.58, 1);
    if (s === 'ease-in-out') return cubicBezier(0.42, 0, 0.58, 1);
    var m = s.match(/^cubic-bezier\(([^)]+)\)/);
    if (m) {
      var p = m[1].split(',').map(Number);
      if (p.length === 4 && p.every(isFinite)) return cubicBezier(p[0], p[1], p[2], p[3]);
    }
    m = s.match(/^steps\((\d+)/);
    if (m) { var n = Math.max(1, parseInt(m[1], 10)); return function (t) { return Math.floor(t * n) / n; }; }
    if (s === 'spring') return function (t) { return 1 - Math.cos(t * 4.5 * Math.PI) * Math.exp(-t * 4); };
    if (s === 'bounce') return function (t) {
      if (t < 1 / 2.75) return 7.5625 * t * t;
      if (t < 2 / 2.75) { t -= 1.5 / 2.75; return 7.5625 * t * t + 0.75; }
      if (t < 2.5 / 2.75) { t -= 2.25 / 2.75; return 7.5625 * t * t + 0.9375; }
      t -= 2.625 / 2.75; return 7.5625 * t * t + 0.984375;
    };
    if (s === 'elastic') return function (t) { return t === 0 || t === 1 ? t : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI / 3)) + 1; };
    return function (t) { return t; };
  }

  // ---- color / number helpers ----
  var NUM_RE = /-?\d+(\.\d+)?/g;
  function parseColor(c) {
    if (!c || typeof c !== 'string') return null;
    c = c.trim().toLowerCase();
    var m;
    if ((m = c.match(/^#([0-9a-f]{3})$/))) {
      return [parseInt(m[1][0] + m[1][0], 16), parseInt(m[1][1] + m[1][1], 16), parseInt(m[1][2] + m[1][2], 16)];
    }
    if ((m = c.match(/^#([0-9a-f]{6})$/))) {
      return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)];
    }
    if ((m = c.match(/^rgba?\(([^)]+)\)/))) {
      var p = m[1].split(',').map(function (x) { return parseFloat(x); });
      if (p.length >= 3) return [p[0] | 0, p[1] | 0, p[2] | 0];
    }
    return null;
  }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function lerpColor(a, b, t) {
    var ca = parseColor(a), cb = parseColor(b);
    if (!ca || !cb) return t < 0.5 ? a : b;
    return 'rgb(' + Math.round(lerp(ca[0], cb[0], t)) + ',' + Math.round(lerp(ca[1], cb[1], t)) + ',' + Math.round(lerp(ca[2], cb[2], t)) + ')';
  }
  function lerpValue(prop, a, b, t) {
    if ((prop === 'fill' || prop === 'stroke' || prop === 'color' || prop === 'background') ) return lerpColor(a, b, t);
    var na = parseFloat(a), nb = parseFloat(b);
    if (isFinite(na) && isFinite(nb)) {
      var ua = String(a).replace(/^[-\d.\s]+/, ''), ub = String(b).replace(/^[-\d.\s]+/, '');
      var u = ub || ua || '';
      return (lerp(na, nb, t)) + u;
    }
    // path morph handled separately; generic fallback
    return t < 0.5 ? a : b;
  }

  // ---- path morph ----
  function tokenizeD(d) {
    var toks = String(d).match(/[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e[-+]?\d+)?/g);
    return toks || [];
  }
  function isNumTok(t) { return /^-?\d/.test(t); }
  function morphD(a, b, t) {
    var ta = tokenizeD(a), tb = tokenizeD(b);
    if (ta.length !== tb.length) return null;
    for (var i = 0; i < ta.length; i++) {
      var na = isNumTok(ta[i]), nb = isNumTok(tb[i]);
      if (na !== nb) return null;
      if (!na && ta[i] !== tb[i]) return null;
    }
    return ta.map(function (tok, i) {
      if (!isNumTok(tok)) return tok;
      return String(lerp(parseFloat(tok), parseFloat(tb[i]), t));
    }).join(' ');
  }

  // ---- property application ----
  var CSS_PROPS = { opacity: 1, fill: 1, stroke: 1 };
  function applyProp(el, prop, value) {
    if (!el) return;
    var target = el;
    // named sub-part support: ATML.play callers resolve part elements; here el is already resolved
    switch (prop) {
      case 'x': target.style.left = cssNum(value, 'px'); break;
      case 'y': target.style.top = cssNum(value, 'px'); break;
      case 'w': case 'width': target.style.width = cssNum(value, 'px'); break;
      case 'h': case 'height': target.style.height = cssNum(value, 'px'); break;
      case 'opacity': case 'fill': case 'stroke':
        target.style[prop] = value;
        var svg = target.querySelector ? (target.querySelector('svg') || (target.tagName && target.tagName.toLowerCase() === 'svg' ? target : null)) : null;
        if (svg) {
          if (prop === 'opacity') svg.style.opacity = value;
          else svg.setAttribute(prop, value);
        }
        if (target.setAttribute && (target.tagName === 'path' || target.tagName === 'rect' || target.tagName === 'circle' || target.tagName === 'g')) {
          try { target.setAttribute(prop, value); } catch (e) {}
        }
        break;
      case 'rotate': case 'scale': case 'scaleX': case 'scaleY': case 'skewX': case 'skewY':
        applyTransform(el, prop, value); break;
      case 'd': case 'morph':
        applyPath(el, value); break;
      case 'points':
        applyPoints(el, value); break;
      case 'cx': case 'cy': case 'r': case 'rx': case 'ry': case 'x1': case 'y1': case 'x2': case 'y2':
        applySvgAttr(el, prop, value); break;
      case 'blur': target.style.filter = mergeFilter(target, 'blur', 'blur(' + value + 'px)'); break;
      case 'anchor': break; // handled at layout via transform-origin
      default:
        // generic: try style then attribute
        try { target.style[prop] = value; } catch (e) {}
        break;
    }
  }
  function cssNum(v, unit) { return (typeof v === 'number' || /^-?[\d.]+$/.test(String(v).trim())) ? String(v).trim() + unit : String(v); }
  var _tr = {};
  function applyTransform(el, prop, value) {
    var id = el.__atmlT || (el.__atmlT = 't' + Math.random().toString(36).slice(2));
    var cur = _tr[id] || {};
    if (prop === 'rotate') cur.rotate = parseFloat(value) || 0;
    else if (prop === 'scale') cur.scale = parseFloat(value);
    else if (prop === 'scaleX') cur.scaleX = parseFloat(value);
    else if (prop === 'scaleY') cur.scaleY = parseFloat(value);
    else if (prop === 'skewX') cur.skewX = parseFloat(value);
    else if (prop === 'skewY') cur.skewY = parseFloat(value);
    _tr[id] = cur;
    var parts = [];
    if (cur.rotate) parts.push('rotate(' + cur.rotate + 'deg)');
    if (cur.scale !== undefined) parts.push('scale(' + cur.scale + ')');
    else { if (cur.scaleX !== undefined || cur.scaleY !== undefined) parts.push('scale(' + (cur.scaleX === undefined ? 1 : cur.scaleX) + ',' + (cur.scaleY === undefined ? 1 : cur.scaleY) + ')'); }
    if (cur.skewX) parts.push('skewX(' + cur.skewX + 'deg)');
    if (cur.skewY) parts.push('skewY(' + cur.skewY + 'deg)');
    el.style.transform = parts.join(' ');
  }
  function mergeFilter(el, kind, val) {
    var f = el.style.filter || '';
    f = f.replace(/blur\([^)]*\)/g, '').trim();
    return (f ? f + ' ' : '') + val;
  }
  function svgInner(el) {
    if (!el) return null;
    if (el.tagName && /^(svg|path|g|rect|circle|ellipse|polygon|line|text)$/i.test(el.tagName)) return el;
    return el.querySelector ? (el.querySelector('svg path, svg rect, svg circle, svg ellipse, svg polygon, svg line, svg text, svg g') || el.querySelector('svg')) : null;
  }
  function applyPath(el, value) {
    var p = svgInner(el);
    if (p && p.setAttribute) { try { p.setAttribute('d', value); } catch (e) {} }
    if (el.querySelector) { var all = el.querySelectorAll('path'); for (var i = 0; i < all.length; i++) { try { all[i].setAttribute('d', value); } catch (e) {} } }
  }
  function applyPoints(el, value) {
    var t = svgInner(el);
    var list = [];
    if (t && t.setAttribute && /polygon|polyline/i.test(t.tagName || '')) list.push(t);
    if (el.querySelectorAll) { var all = el.querySelectorAll('polygon,polyline'); for (var i = 0; i < all.length; i++) list.push(all[i]); }
    list.forEach(function (n) { try { n.setAttribute('points', value); } catch (e) {} });
  }
  function applySvgAttr(el, prop, value) {
    var t = svgInner(el);
    var list = t ? [t] : [];
    if (el.querySelectorAll) { var all = el.querySelectorAll('circle,ellipse,line,rect'); for (var i = 0; i < all.length; i++) list.push(all[i]); }
    list.forEach(function (n) { try { n.setAttribute(prop, value); } catch (e) {} });
  }

  function resolveTarget(target) {
    if (!target) return null;
    var parts = String(target).split('.');
    var base = document.querySelector('[data-atml-id="' + parts[0] + '"]') || document.getElementById(parts[0]);
    if (!base) return null;
    if (parts.length > 1) {
      var sub = base.querySelector('[data-part="' + parts.slice(1).join('.') + '"]') || base.querySelector('[data-part="' + parts[1] + '"]');
      return sub || base;
    }
    return base;
  }

  // ---- keyframe sampling ----
  function stopsFor(anim) {
    // returns sorted [{off, props}]
    var dur = anim.dur || 2000;
    var stops = [];
    (anim.keys || []).forEach(function (k) {
      var off;
      if (k.at === undefined || k.at === null || k.at === '') off = 0;
      else if (typeof k.at === 'number') off = clamp01(k.at);
      else {
        var s = String(k.at).trim();
        if (s.slice(-1) === '%') off = clamp01(parseFloat(s) / 100);
        else off = clamp01(parseDur(s, 0) / dur);
      }
      var props = {}; Object.keys(k).forEach(function (p) { if (p !== 'at') props[p] = k[p]; });
      stops.push({ off: off, props: props });
    });
    (anim.tweens || []).forEach(function (tw) {
      stops.push({ off: 0, props: (function () { var o = {}; o[tw.prop] = tw.from; return o; })() });
      stops.push({ off: 1, props: (function () { var o = {}; o[tw.prop] = tw.to; return o; })() });
    });
    if (anim.from || anim.to) {
      var f = anim.from || {}, t = anim.to || {};
      stops.push({ off: 0, props: f });
      stops.push({ off: 1, props: t });
    }
    if (!stops.length) return [];
    // merge same offsets
    stops.sort(function (a, b) { return a.off - b.off; });
    return stops;
  }
  function sampleStops(stops, t, easeFn) {
    var e = easeFn(clamp01(t));
    if (!stops.length) return {};
    if (e <= stops[0].off) return stops[0].props;
    var last = stops[stops.length - 1];
    if (e >= last.off) return last.props;
    var i = 0;
    while (i < stops.length - 1 && stops[i + 1].off < e) i++;
    var a = stops[i], b = stops[i + 1];
    var span = (b.off - a.off) || 1;
    var lt = (e - a.off) / span;
    var out = {};
    var keys = {};
    Object.keys(a.props).forEach(function (k) { keys[k] = 1; });
    Object.keys(b.props).forEach(function (k) { keys[k] = 1; });
    Object.keys(keys).forEach(function (k) {
      var va = a.props[k] !== undefined ? a.props[k] : b.props[k];
      var vb = b.props[k] !== undefined ? b.props[k] : a.props[k];
      if (k === 'd' || k === 'morph') {
        var m = morphD(va, vb, lt);
        out[k] = m !== null ? m : (lt < 0.5 ? va : vb);
      } else {
        out[k] = lerpValue(k, va, vb, lt);
      }
    });
    return out;
  }

  function quantize(timeMs, fps) {
    fps = +fps || 0;
    if (!fps || fps <= 0) return timeMs;
    var frame = 1000 / fps;
    return Math.floor(timeMs / frame) * frame;
  }

  function runAnimation(id) {
    var anim = store.animations[id];
    if (!anim) return;
    var el = resolveTarget(anim.target);
    if (!el) return;
    var st = state[id] || (state[id] = {});
    st.el = el; st.anim = anim;
    stopRaf(st);
    var dur = anim.dur || 2000;
    var delay = anim.delay || 0;
    var easeFn = makeEase(anim.ease);
    var stops = stopsFor(anim);
    var fps = +anim.fps || +(window.__ATML__ && window.__ATML__.fps) || 0;
    var loop = anim.loop;
    var loops = (loop === true || loop === 'true' || loop === 'infinite') ? Infinity : (parseInt(loop, 10) || 0);
    if (anim.autoplay === false) return;
    var direction = anim.direction || 'normal';
    var start = performance.now() + delay;
    st.playing = true; st.start = start; st.pausedAt = null;
    // NOTE: no WAAPI fast-path. A previous revision fired element.animate()
    // with a hand-built `translate` property here; the malformed values stacked
    // with the rAF-driven style.transform and displaced actors by hundreds of
    // px. The rAF loop below is the single source of truth.
    function frame(now) {
      if (!st.playing) return;
      var raw = now - st.start;
      if (raw < 0) { st.raf = requestAnimationFrame(frame); return; }
      var q = quantize(raw, fps);
      var iter = Math.floor(q / dur);
      var within = q - iter * dur;
      var done = false;
      if (loops !== Infinity && iter > loops) { within = dur; done = true; }
      else if (loops === 0 && iter >= 1) { within = dur; done = true; }
      var t = clamp01(within / dur);
      if ((direction === 'reverse') || st.reversed) t = 1 - t;
      else if (direction === 'alternate' && (iter % 2 === 1)) t = 1 - t;
      else if (direction === 'alternate-reverse' && (iter % 2 === 0)) t = 1 - t;
      var props = sampleStops(stops, t, easeFn);
      Object.keys(props).forEach(function (p) { applyProp(st.el, p, props[p]); });
      if (done) {
        st.playing = false;
        if (anim.fill === 'none') { /* leave */ }
        return;
      }
      st.raf = requestAnimationFrame(frame);
    }
    st.raf = requestAnimationFrame(frame);
  }
  function stopRaf(st) { if (st.raf) cancelAnimationFrame(st.raf); st.raf = null; }

  // ---- public API ----
  ATML.play = function (id) {
    if (!id) { Object.keys(store.animations).forEach(runAnimation); runTimelines(); return; }
    if (store.animations[id]) { var st = state[id] || {}; st.reversed = false; runAnimation(id); return; }
    // timeline id?
    playTimeline(id);
  };
  ATML.pause = function (id) {
    function p(k) { var st = state[k]; if (st && st.playing) { st.playing = false; stopRaf(st); st.pausedAt = performance.now(); } }
    if (id) p(id); else Object.keys(state).forEach(p);
  };
  ATML.seek = function (id, tMs) {
    var anim = store.animations[id]; if (!anim) return;
    var el = resolveTarget(anim.target); if (!el) return;
    var dur = anim.dur || 2000;
    var t = typeof tMs === 'string' ? parseDur(tMs, 0) : tMs;
    var stops = stopsFor(anim);
    var props = sampleStops(stops, clamp01(t / dur), makeEase(anim.ease));
    Object.keys(props).forEach(function (p) { applyProp(el, p, props[p]); });
  };
  ATML.reverse = function (id) {
    if (id && store.animations[id]) { var st = state[id] || {}; st.reversed = !st.reversed; runAnimation(id); if (st.reversed) { /* reversed flag consumed */ state[id].reversed = true; } return; }
    Object.keys(store.animations).forEach(function (k) { state[k] = state[k] || {}; state[k].reversed = true; runAnimation(k); });
  };
  ATML.toggle = function (id) {
    var st = state[id];
    if (st && st.playing) ATML.pause(id); else ATML.play(id);
  };
  ATML.show = function (id) { var el = resolveTarget(id) || document.getElementById(id); if (el) el.style.display = ''; };
  ATML.hide = function (id) { var el = resolveTarget(id) || document.getElementById(id); if (el) el.style.display = 'none'; };
  ATML.defineActor = function (name, props) {
    window.__ATML__ = window.__ATML__ || {};
    window.__ATML__.actors = window.__ATML__.actors || {};
    window.__ATML__.actors[name] = props || {};
  };
  ATML.defineAnimation = function (name, anim) {
    window.__ATML__ = window.__ATML__ || {};
    window.__ATML__.animations = window.__ATML__.animations || {};
    window.__ATML__.animations[name] = anim || {};
    ATML.refresh();
  };
  ATML.refresh = function () { loadStore(); autostart(); };

  // ---- timelines ----
  function playTimeline(id) {
    var tl = store.timelines[id];
    if (!tl) return;
    (tl.clips || []).forEach(function (clip) {
      var at = parseDur(clip.at || '0s', 0);
      setTimeout(function () {
        if (clip.target && store.animations[clip.target]) ATML.play(clip.target);
        else if (clip.target) { var el = resolveTarget(clip.target); if (el) { el.scrollIntoView && el.scrollIntoView(); } }
        if (clip.action === 'show') ATML.show(clip.target);
        if (clip.action === 'hide') ATML.hide(clip.target);
      }, at);
    });
  }
  function runTimelines() { Object.keys(store.timelines).forEach(function (id) { var tl = store.timelines[id]; if (tl.autoplay) playTimeline(id); }); }

  // ---- triggers ----
  function bindTriggers() {
    (store.triggers || []).forEach(function (tr) {
      var on = String(tr.on || 'load');
      var els;
      if (tr.selector) els = $all(tr.selector);
      else if (tr.target && !/^(play|pause|reverse|toggle|seek|show|hide)$/.test(tr.target)) els = [resolveTarget(tr.target)].filter(Boolean);
      else els = [document.body];
      // time:2s / key:Space forms: on="time:2s", on="key:Space"
      if (on.indexOf('time:') === 0) {
        setTimeout(function () { fireTrigger(tr); }, parseDur(on.slice(5), 0));
        return;
      }
      if (on.indexOf('key:') === 0) {
        var key = on.slice(4);
        document.addEventListener('keydown', function (e) { if (e.key === key || e.code === key) fireTrigger(tr); });
        return;
      }
      els.forEach(function (el) {
        if (!el || el.__atmlBound) return; el.__atmlBound = true;
        if (on === 'click') el.addEventListener('click', function () { fireTrigger(tr); });
        else if (on === 'hover') el.addEventListener('mouseenter', function () { fireTrigger(tr); });
        else if (on === 'load' || on === 'view') { /* handled below */ }
        else if (on === 'scroll') window.addEventListener('scroll', function () { fireTrigger(tr); });
      });
      if (on === 'load') window.addEventListener('load', function () { fireTrigger(tr); });
      if (on === 'view' || on === 'scroll') {
        var target = resolveTarget(tr.animate || tr.target) || document.body;
        if ('IntersectionObserver' in window) {
          var io = new IntersectionObserver(function (ents) { ents.forEach(function (en) { if (en.isIntersecting) fireTrigger(tr); }); }, { threshold: 0.2 });
          try { io.observe(target); } catch (e) {}
        } else { setTimeout(function () { fireTrigger(tr); }, 500); }
      }
    });
    // data-atml trigger attributes (hand-written HTML): data-atml="play:INTRO" data-atml-on="click"
    $all('[data-atml]').forEach(function (el) {
      if (el.__atmlBound) return; el.__atmlBound = true;
      var action = el.getAttribute('data-atml');
      var on = el.getAttribute('data-atml-on') || 'click';
      el.addEventListener(on === 'hover' ? 'mouseenter' : on, function () {
        var parts = action.split(':');
        var verb = parts[0], arg = parts.slice(1).join(':');
        if (ATML[verb]) ATML[verb](arg);
      });
    });
  }
  function fireTrigger(tr) {
    var do_ = tr.do || tr.action || 'play';
    var tgt = tr.animate || tr.play || tr.target;
    if (do_ === 'play') ATML.play(tgt);
    else if (do_ === 'pause') ATML.pause(tgt);
    else if (do_ === 'reverse') ATML.reverse(tgt);
    else if (do_ === 'toggle') ATML.toggle(tgt);
    else if (do_ === 'seek') ATML.seek(tgt, tr.to || 0);
    else if (do_ === 'show') ATML.show(tgt);
    else if (do_ === 'hide') ATML.hide(tgt);
  }

  // ---- cameras ----
  function applyCameras() {
    var cams = (window.__ATML__ && window.__ATML__.cameras) || {};
    Object.keys(cams).forEach(function (id) {
      var c = cams[id];
      var stage = document.querySelector('[data-stage]') || document.querySelector('.atml-stage') || document.body;
      var parts = [];
      if (c.zoom) parts.push('scale(' + c.zoom + ')');
      if (c.rotate) parts.push('rotate(' + c.rotate + 'deg)');
      if (c.x || c.y) parts.push('translate(' + (-(parseFloat(c.x) || 0)) + 'px,' + (-(parseFloat(c.y) || 0)) + 'px)');
      if (c.shake) { parts.push('translate(' + (Math.random() * c.shake - c.shake / 2) + 'px,' + (Math.random() * c.shake - c.shake / 2) + 'px)'); }
      if (c.follow) {
        var t = resolveTarget(c.follow);
        if (t) { try { var r = t.getBoundingClientRect(); parts.push('translate(' + (-r.left / 2) + 'px,' + (-r.top / 2) + 'px)'); } catch (e) {} }
      }
      if (parts.length && stage && stage.style) { stage.style.transform = parts.join(' '); stage.style.transformOrigin = 'center center'; }
    });
  }

  function loadStore() {
    var d = window.__ATML__ || {};
    store.animations = d.animations || {};
    store.timelines = d.timelines || {};
    store.triggers = d.triggers || [];
  }
  function autostart() {
    Object.keys(store.animations).forEach(function (id) {
      var a = store.animations[id];
      var auto = a.autoplay;
      if (auto === false || auto === 'false') return;
      if (a.trigger) return; // trigger-bound: wait
      runAnimation(id);
    });
    runTimelines();
    bindTriggers();
    applyCameras();
    // pixel blocks: ensure crisp rendering
    $all('[data-pixels]').forEach(function (el) { el.style.imageRendering = 'pixelated'; });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { loadStore(); autostart(); });
  else { loadStore(); autostart(); }

  global.ATML = ATML;
})(typeof window !== 'undefined' ? window : this);
