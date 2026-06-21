// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  /* ═══════════════════════════════════════════════
     Particle System — Canvas-based overlay effects
     ═══════════════════════════════════════════════ */

  var PARTICLE_KEY = 'theme:particle';
  var PARTICLE_CLASS = 'theme-particles-active';
  var NONE_CLASS = 'theme-particles-none';

  // Visual-only PRNG — not for security contexts  // NOSONAR
  function vrand() { return vrand(); }

  // ── Effect Registry ──
  var effects = {};

  // Idle baseline used when a theme's signal var is UNSET (no training): effects
  // read this instead of 0 so particles are visible immediately. A SET var (even "0") wins.
  var IDLE_SIGNAL = 0.5;

  function readSignal(name) {
    var raw = document.documentElement.style.getPropertyValue(name);
    if (raw === '' || raw == null) return IDLE_SIGNAL;
    var n = parseFloat(raw);
    return isFinite(n) ? n : IDLE_SIGNAL;
  }

  function readSignalChain(primary, fallback) {
    var a = document.documentElement.style.getPropertyValue(primary);
    if (a !== '' && a != null && isFinite(parseFloat(a))) return parseFloat(a);
    var b = document.documentElement.style.getPropertyValue(fallback);
    if (b !== '' && b != null && isFinite(parseFloat(b))) return parseFloat(b);
    return IDLE_SIGNAL;
  }

  // ── Active State ──
  var canvas = null;
  var ctx = null;
  var rAFid = null;
  var activeEffect = null;        // current effect name (null = none/css)
  var activeConfig = null;        // { type, params }
  var activeImpl = null;          // { start, stop, update, resize }
  var isRunning = false;
  var effectLevel = null;
  // ── Preference ──
  function readPref() {
    try { return localStorage.getItem(PARTICLE_KEY); } catch (e) { return null; }
  }

  function writePref(val) {
    try { localStorage.setItem(PARTICLE_KEY, val); } catch (e) {}
  }

  function getEffectiveConfig(themeConfig) {
    var pref = readPref();
    if (pref === 'none') return { type: 'none', params: {} };
    if (pref && effects[pref]) return { type: pref, params: {} };
    // Fall back to theme default
    return themeConfig || { type: 'css', params: {} };
  }

  // ── Canvas Lifecycle ──
  function ensureCanvas(themeId) {
    if (canvas) return;
    canvas = document.createElement('canvas');
    canvas.className = 'particle-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.setAttribute('data-particle-theme', themeId || '');
    canvas.style.cssText =
      'position:fixed;inset:0;width:100%;height:100%;' +
      'pointer-events:none;z-index:0;display:block;';
    // First child of app-shell at z-index 0 sits behind .app-main content (its own
    // isolate stacking context) but above the app-shell background.
    var shell = document.querySelector('.app-shell');
    if (shell) {
      shell.insertBefore(canvas, shell.firstChild);
    } else {
      document.body.appendChild(canvas);
    }
    ctx = canvas.getContext('2d');
    resizeCanvas();
  }

  function removeCanvas() {
    if (rAFid) {
      cancelAnimationFrame(rAFid);
      rAFid = null;
    }
    if (canvas && canvas.parentNode) {
      canvas.parentNode.removeChild(canvas);
    }
    canvas = null;
    ctx = null;
    activeImpl = null;
    isRunning = false;
  }

  function resizeCanvas() {
    if (!canvas) return;
    var dpr = window.devicePixelRatio || 1;
    var w = window.innerWidth;
    var h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    if (ctx) {
      ctx.scale(dpr, dpr);
    }
    if (activeImpl && typeof activeImpl.resize === 'function') {
      activeImpl.resize(w, h);
    }
  }

  // ── Animation Loop ──
  var SPEED_SCALE = 0.5;
  var SIM_INTERVAL = (1000 / 60) / SPEED_SCALE;
  var simClock = 0;
  var lastTs = null;
  var sinceStep = 0;

  function animationLoop(timestamp) {
    if (!ctx || !canvas || !isRunning) {
      rAFid = null;
      lastTs = null;
      return;
    }
    var w = window.innerWidth;
    var h = window.innerHeight;

    if (lastTs == null) lastTs = timestamp;
    sinceStep += timestamp - lastTs;
    lastTs = timestamp;

    if (sinceStep >= SIM_INTERVAL) {
      sinceStep -= SIM_INTERVAL;
      if (sinceStep > SIM_INTERVAL) sinceStep = 0;
      simClock += 1000 / 60;
      ctx.clearRect(0, 0, w, h);
      if (activeImpl && typeof activeImpl.update === 'function') {
        activeImpl.update(simClock, w, h, ctx);
      }
    }

    rAFid = requestAnimationFrame(animationLoop);
  }

  function startAnimation() {
    if (rAFid) return;
    rAFid = requestAnimationFrame(animationLoop);
  }

  function stopAnimation() {
    if (rAFid) {
      cancelAnimationFrame(rAFid);
      rAFid = null;
    }
    lastTs = null;
    sinceStep = 0;
  }

  // ── CSS Particle Suppression ──
  var suppressionStyle = null;

  function enableSuppression() {
    if (suppressionStyle) return;
    suppressionStyle = document.createElement('style');
    suppressionStyle.id = 'particle-suppression';
    suppressionStyle.textContent =
      '[data-particles="none"] .app-main::before,' +
      '[data-particles="none"] .app-main::after {' +
      '  display: none !important;' +
      '}';
    document.head.appendChild(suppressionStyle);
  }

  function disableSuppression() {
    if (suppressionStyle && suppressionStyle.parentNode) {
      suppressionStyle.parentNode.removeChild(suppressionStyle);
    }
    suppressionStyle = null;
  }

  // ── Root Data Attribute ──
  function setParticleAttr(mode) {
    var root = document.documentElement;
    root.setAttribute('data-particles', mode || '');
  }

  // ── Apply Effect ──
  function apply(theme, el, forceCSS) {
    el = el || window.EffectLevel;
    effectLevel = (el && typeof el.snapshot === 'function') ? el.snapshot() : { level: 'full', reducedMotion: false, legible: false };

    var config;
    if (forceCSS) {
      config = { type: 'css', params: {} };
    } else {
      config = getEffectiveConfig(theme.particleConfig || { type: 'css', params: {} });
    }
    var paused = effectLevel.level === 'paused';
    var legible = effectLevel.legible || effectLevel.reducedMotion;

    // Teardown previous
    stopEffect();
    setParticleAttr('');
    disableSuppression();
    document.documentElement.classList.remove(PARTICLE_CLASS, NONE_CLASS);

    if (paused) return;

    if (config.type === 'none') {
      setParticleAttr('none');
      document.documentElement.classList.add(NONE_CLASS);
      enableSuppression();
      return;
    }

    if (config.type === 'css') {
      setParticleAttr('default');
      return;
    }

    // Canvas-based effect
    var factory = effects[config.type];
    if (!factory) {
      setParticleAttr('default');
      return;
    }

    // Build effect
    document.documentElement.classList.add(PARTICLE_CLASS);
    setParticleAttr(config.type);
    ensureCanvas(theme.id);

    activeConfig = config;
    activeEffect = config.type;

    activeImpl = factory(canvas, ctx, config.params || {}, {
      paused: legible,
      signalSnapshot: effectLevel,
    });

    if (activeImpl && typeof activeImpl.start === 'function') {
      activeImpl.start(window.innerWidth, window.innerHeight);
    }
    isRunning = !legible;
    startAnimation();
  }

  function stopEffect() {
    if (activeImpl && typeof activeImpl.stop === 'function') {
      try { activeImpl.stop(); } catch (e) { console.warn('[particles] effect stop error', e); }
    }
    stopAnimation();
    removeCanvas();
    activeEffect = null;
    activeConfig = null;
    isRunning = false;
  }

  function pause() {
    isRunning = false;
  }

  function resume() {
    var s = effectLevel;
    if (s && (s.level === 'paused' || s.legible)) {
      isRunning = false;
      return;
    }
    isRunning = true;
    startAnimation();
  }

  // ── Effect-Level Integration ──
  function onEffectLevelChange(snap) {
    effectLevel = snap;
    if (!activeConfig || activeConfig.type === 'css' || activeConfig.type === 'none') return;
    if (snap.level === 'paused' || snap.legible) {
      pause();
      if (canvas) canvas.style.opacity = '0';
    } else {
      resume();
      if (canvas) canvas.style.opacity = '1';
    }
  }

  // ── Register Effect ──
  function registerEffect(name, factory) {
    if (effects[name]) {
      console.warn('[particles] duplicate effect registered:', name);
    }
    effects[name] = factory;
  }

  /* ═══════════════════════════════════════════════
     Built-in Effects
     ═══════════════════════════════════════════════ */

  // ── Snow Effect (gentle white dots, drifts with wind) ──
  // Driven by CSS var --freeze (set by Glacier theme mapping).
  registerEffect('snow', function (_cvs, _context, _params, env) {
    var BASE_COUNT = 200;
    var MAX_COUNT = 700;
    var flakes = [];
    var w = 0, h = 0;
    var snowBase = 0;
    var driftPhase = 0;
    var freeze = 0;
    var isPaused = env.paused;
    var i, f, radius, targetCount, drift;

    function createFlake(x, y) {
      radius = 1.5 + vrand() * 3.5;
      return {
        x: x != null ? x : vrand() * w * 1.3 - w * 0.15,
        y: y != null ? y : -radius * 2 - vrand() * h * 0.5,
        r: radius,
        speed: 0.15 + vrand() * 0.4,
        opacity: 0.4 + vrand() * 0.55,
        phase: vrand() * Math.PI * 2,
        wobbleAmp: 0.3 + vrand() * 0.8,
        wobbleFreq: 0.002 + vrand() * 0.005,
        drift: -0.08 + vrand() * 0.16,
      };
    }

    function init(width, height) {
      w = width;
      h = height;
      flakes = [];
      for (i = 0; i < BASE_COUNT; i++) {
        flakes.push(createFlake(null, null));
      }
    }

    function resize(width, height) {
      w = width;
      h = height;
    }

    function start(width, height) {
      w = width;
      h = height;
      init(w, h);
      isPaused = false;
      freeze = readSignal('--freeze');
    }

    function stop() {
      flakes = [];
    }

    function update(timestamp, width, height, context) {
      if (isPaused) return;
      w = width;
      h = height;

      freeze = readSignal('--freeze');

      targetCount = Math.round(BASE_COUNT + freeze * (MAX_COUNT - BASE_COUNT));
      while (flakes.length < targetCount) {
        flakes.push(createFlake(null, null));
      }
      while (flakes.length > targetCount) {
        flakes.pop();
      }

      if (timestamp) {
        driftPhase = timestamp * 0.001;
      }

      for (i = 0; i < flakes.length; i++) {
        f = flakes[i];
        if (f.y > h + 15) {
          f.x = vrand() * w * 1.3 - w * 0.15;
          f.y = -f.r * 2 - vrand() * 50;
          f.speed = 0.15 + vrand() * 0.4;
          f.opacity = 0.4 + vrand() * 0.55;
        }

        drift = Math.sin(driftPhase * f.wobbleFreq * 10 + f.phase) * f.wobbleAmp
              + f.drift * (1 + freeze * 1.2);
        f.x += drift * 0.5;
        f.y += f.speed * (0.3 + freeze * 0.7);

        context.beginPath();
        context.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        context.fillStyle = 'rgba(255, 255, 255, ' + f.opacity.toFixed(2) + ')';
        context.fill();
      }

      // Heavy snow cover at bottom when freeze is high
      if (freeze > 0.3) {
        context.fillStyle = 'rgba(255, 255, 255, ' + ((freeze - 0.3) * 0.18).toFixed(3) + ')';
        context.fillRect(0, h - 10, w, 10);
      }
    }

    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Rain Effect (fast angled streaks, wind-driven) ──
  // Driven by CSS var --charge (set by Stormfront mapping from grad_norm).
  registerEffect('rain', function (_cvs, _context, _params, env) {
    var BASE_COUNT = 600;
    var MAX_COUNT = 1800;
    var drops = [];
    var w = 0, h = 0;
    var windBase = 0;
    var gustPhase = 0;
    var windTarget = 0;
    var charge = 0;
    var isPaused = env.paused;
    var i, d, lenVal, speedVal, targetCount, windStrength, windX, windVel, vx, vy, vmag, dx, dy;

    function createDrop(x, y) {
      lenVal = 12 + vrand() * 14;
      speedVal = 3 + vrand() * 4;
      return {
        x: x != null ? x : vrand() * w * 2 - w * 0.5,
        y: y != null ? y : -lenVal - vrand() * h * 0.3,
        length: lenVal,
        speed: speedVal,
        opacity: 0.25 + vrand() * 0.5,
        windPhase: vrand() * Math.PI * 2,
        windAmp: 0.5 + vrand() * 0.8,
        width: 0.5 + vrand() * 0.8,
      };
    }

    function init(width, height) {
      w = width;
      h = height;
      drops = [];
      // Seed across the full screen (not just above the top) so it's raining
      // everywhere immediately — avoids a top-to-bottom "wave" on load.
      for (i = 0; i < BASE_COUNT; i++) {
        drops.push(createDrop(vrand() * w * 2 - w * 0.5, vrand() * h * 1.2 - h * 0.2));
      }
    }

    function resize(width, height) {
      w = width;
      h = height;
    }

    function start(width, height) {
      w = width;
      h = height;
      init(w, h);
      isPaused = false;
      charge = readSignal('--charge');
    }

    function stop() {
      drops = [];
    }

    function update(timestamp, width, height, context) {
      if (isPaused) return;
      w = width;
      h = height;

      charge = readSignal('--charge');

      targetCount = Math.round(BASE_COUNT + charge * (MAX_COUNT - BASE_COUNT));
      while (drops.length < targetCount) {
        drops.push(createDrop(null, null));
      }
      while (drops.length > targetCount) {
        drops.pop();
      }

      if (timestamp) {
        gustPhase = timestamp * 0.001;
      }
      windTarget = Math.sin(gustPhase * 0.4) * 0.5
                 + Math.sin(gustPhase * 0.7 + 1.3) * 0.3
                 + Math.sin(gustPhase * 1.1 + 2.7) * 0.2;
      windBase += (windTarget - windBase) * 0.02;

      windStrength = windBase * (1 + charge * 2.5);

      context.strokeStyle = 'rgba(160, 200, 245, 0.5)';

      for (i = 0; i < drops.length; i++) {
        d = drops[i];
        if (d.y > h + 10) {
          d.x = vrand() * w * 2 - w * 0.5;
          d.y = -d.length - vrand() * 20;
          d.speed = 3 + vrand() * 4;
          d.opacity = 0.25 + vrand() * 0.5;
        }

        windX = Math.sin(gustPhase * 0.3 + d.windPhase) * d.windAmp * windStrength * 2;
        windVel = windStrength * d.speed * 0.6;

        vx = windVel + windX * 0.06;
        vy = d.speed * (1 + charge * 0.6);

        d.x += vx;
        d.y += vy;

        // Horizontal wrap so wind never bares the windward side.
        if (d.x > w + 50) d.x -= w + 100;
        else if (d.x < -50) d.x += w + 100;

        // Streak points along the actual travel vector so it leans with the wind.
        vmag = Math.sqrt(vx * vx + vy * vy) || 1;
        dx = (vx / vmag) * d.length;
        dy = (vy / vmag) * d.length;

        context.beginPath();
        context.moveTo(d.x, d.y);
        context.lineTo(d.x + dx, d.y + dy);
        context.strokeStyle = 'rgba(160, 200, 245, ' + d.opacity.toFixed(2) + ')';
        context.lineWidth = d.width;
        context.lineCap = 'round';
        context.stroke();
      }

      // Splash layer at bottom
      if (charge > 0.2) {
        context.fillStyle = 'rgba(160, 200, 245, ' + (charge * 0.12).toFixed(3) + ')';
        context.fillRect(0, h - 8, w, 8);
      }
    }

    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Ember Effect (rising sparks) ──
  // Reads --ember (Ash, Ember Drift) or --heat (Forge) — fallback chain works.
  registerEffect('ember', function (_cvs, _context, _params, env) {
    var BASE = 60, MAX = 250; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : h + 10 + vrand() * 50, r: 0.8 + vrand() * 2.2, s: 0.2 + vrand() * 0.5, o: 0.3 + vrand() * 0.6, ph: vrand() * 6.28, wa: 0.2 + vrand() * 0.5 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false;       sig = readSignalChain('--ember', '--heat'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignalChain('--ember', '--heat');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y -= q.s * (0.3 + sig * 0.7); q.x += Math.sin(ts * 0.002 + q.ph) * q.wa * 0.3;
        if (q.y < -20) { q.x = vrand() * w; q.y = h + 10 + vrand() * 30; q.s = 0.2 + vrand() * 0.5; q.o = 0.3 + vrand() * 0.6; }
        c.beginPath(); c.arc(q.x, q.y, q.r, 0, 6.28);
        c.fillStyle = 'rgba(255, ' + Math.round(140 + sig * 60) + ', ' + Math.round(60 + sig * 80) + ', ' + (q.o * (0.3 + sig * 0.7)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Aurora Effect (shimmering light motes) ──
  // Driven by --calm (Aurora theme).
  registerEffect('aurora', function (_cvs, _context, _params, env) {
    var BASE = 40, MAX = 180; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, hue;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : vrand() * h, r: 1.2 + vrand() * 3, s: 0.1 + vrand() * 0.3, o: 0.1 + vrand() * 0.4, ph: vrand() * 6.28, hue: 140 + vrand() * 120 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--calm'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--calm');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += Math.sin(ts * 0.0008 + q.ph) * 0.4 + 0.05; q.y += Math.sin(ts * 0.0012 + q.ph * 1.3) * 0.2;
        if (q.x > w + 20) { q.x = -20; q.y = vrand() * h; }
        if (q.x < -20) { q.x = w + 20; q.y = vrand() * h; }
        hue = q.hue + Math.sin(ts * 0.0005 + q.ph) * 30;
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.5 + sig * 0.5), 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(hue) + ', 80%, ' + Math.round(60 + sig * 30) + '%, ' + (q.o * (0.2 + sig * 0.8)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Petal Effect (cherry blossom petals) ──
  // Driven by --open (Bloom theme). Draws sakura petals with the
  // characteristic cleft (notch) at the tip, pale pink gradients.
  registerEffect('petal', function (_cvs, _context, _params, env) {
    var BASE = 25, MAX = 140; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, alpha, lw, lh;

    function create(x, y) {
      return {
        x: x != null ? x : vrand() * w * 1.2 - w * 0.1,
        y: y != null ? y : -10 - vrand() * h * 0.3,
        pw: 8 + vrand() * 12,
        pl: 14 + vrand() * 22,
        s: 0.12 + vrand() * 0.25,
        o: 0.3 + vrand() * 0.5,
        ph: vrand() * 6.28,
        wa: 0.15 + vrand() * 0.5,
        hue: 335 + vrand() * 20,
        rot: vrand() * 6.28,
        rotSpd: -0.012 + vrand() * 0.024,
        sat: 40 + vrand() * 25,
        lgt: 72 + vrand() * 16,
      };
    }

    function drawPetal(c, qx, qy, pw, pl, rotation, hue, sat, lgt, alpha) {
      c.save();
      c.translate(qx, qy);
      c.rotate(rotation);

      lw = pw * 0.5;
      lh = pl * 0.5;

      // Sakura petal: wide upper half with a cleft at tip, narrows to base
      c.beginPath();
      c.moveTo(0, lh);
      // Left side from base up toward the left lobe
      c.bezierCurveTo(-lw * 0.4, lh * 0.2, -lw * 1.0, -lh * 0.05, -lw * 0.55, -lh * 0.5);
      // Left lobe curves into the central cleft
      c.quadraticCurveTo(-lw * 0.18, -lh * 0.25, 0, -lh * 0.55);
      // Cleft curves up into the right lobe
      c.quadraticCurveTo(lw * 0.18, -lh * 0.25, lw * 0.55, -lh * 0.5);
      // Right lobe curves down to base
      c.bezierCurveTo(lw * 1.0, -lh * 0.05, lw * 0.4, lh * 0.2, 0, lh);
      c.closePath();

      // Soft sakura gradient — pale center with subtle pink edge
      var grad = c.createRadialGradient(0, 0, 0, 0, 0, lh);
      grad.addColorStop(0, 'hsla(' + hue + ', ' + sat + '%, ' + Math.min(lgt + 12, 95) + '%, ' + alpha + ')');
      grad.addColorStop(0.7, 'hsla(' + hue + ', ' + (sat + 5) + '%, ' + lgt + '%, ' + (alpha * 0.85) + ')');
      grad.addColorStop(1, 'hsla(' + (hue + 5) + ', ' + (sat + 10) + '%, ' + Math.max(lgt - 8, 60) + '%, ' + (alpha * 0.5) + ')');
      c.fillStyle = grad;
      c.fill();

      c.restore();
    }

    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--open'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--open');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.y += q.s * (0.3 + sig * 0.7);
        q.x += Math.sin(ts * 0.0012 + q.ph) * q.wa * 0.25;
        q.rot += q.rotSpd * (0.5 + sig * 0.5);

        if (q.y > h + 20) {
          q.x = vrand() * w * 1.2 - w * 0.1;
          q.y = -10 - vrand() * 30;
          q.s = 0.12 + vrand() * 0.25;
          q.o = 0.3 + vrand() * 0.5;
          q.rot = vrand() * 6.28;
          q.rotSpd = -0.012 + vrand() * 0.024;
          q.pw = 8 + vrand() * 12;
          q.pl = 14 + vrand() * 22;
        }

        alpha = q.o * (0.3 + sig * 0.6);
        drawPetal(c, q.x, q.y, q.pw, q.pl, q.rot, Math.round(q.hue), Math.round(q.sat), Math.round(q.lgt), alpha.toFixed(3));
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Biolum Effect (glowing deep-sea dots) ──
  // Driven by --depth (Deep Sea theme).
  registerEffect('biolum', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 120; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : h + vrand() * 40, r: 1 + vrand() * 3, s: 0.15 + vrand() * 0.4, o: 0.2 + vrand() * 0.7, ph: vrand() * 6.28, wa: 0.1 + vrand() * 0.3 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--depth'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--depth');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y -= q.s * (0.2 + sig * 0.6); q.x += Math.sin(ts * 0.0015 + q.ph) * q.wa;
        if (q.y < -20) { q.x = vrand() * w; q.y = h + vrand() * 30; q.o = 0.2 + vrand() * 0.7; }
        glow = q.o * (0.2 + sig * 0.8);
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(80, 220, 200, ' + glow.toFixed(2) + ')';
        c.fill();
        // Outer glow ring
        if (sig > 0.3) {
          c.beginPath(); c.arc(q.x, q.y, q.r * 2.5, 0, 6.28);
          c.fillStyle = 'rgba(80, 220, 200, ' + (glow * 0.2).toFixed(2) + ')';
          c.fill();
        }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Ribbon Effect (light-cycle trails on a grid) ──
  // Driven by --focus (Grid theme). Bright heads race axis-aligned, laying glowing trails that turn at right angles; higher focus = more/faster riders. Derez turns them amber.
  registerEffect('ribbon', function (_cvs, _context, _params, env) {
    var BASE = 6, MAX = 22; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    var TRAIL = 26;
    var i, k, q, tc, speed, dir, turnChance, bad, k2, seg, a, riderRGB;
    function derez() { return document.documentElement.getAttribute('data-grid-state') === 'derez'; }
    function spawn() {
      var d = DIRS[(vrand() * 4) | 0];
      return {
        x: vrand() * w,
        y: vrand() * h,
        dx: d[0],
        dy: d[1],
        trail: [],
        sinceTurn: 0,
        o: 0.5 + vrand() * 0.5,
        spd: 1 + vrand() * 1.5,
      };
    }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(spawn()); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--focus'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--focus');
      bad = derez();
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(spawn());
      while (p.length > tc) p.pop();

      speed = (1.4 + sig * 3.2);
      turnChance = 0.012 + sig * 0.03;
      riderRGB = bad ? '255, 159, 28' : '45, 226, 255';
      c.lineCap = 'round';
      c.lineJoin = 'round';

      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.sinceTurn++;
        if (q.sinceTurn > 12 && vrand() < turnChance) {
          dir = (q.dx !== 0)
            ? (vrand() < 0.5 ? [0, 1] : [0, -1])
            : (vrand() < 0.5 ? [1, 0] : [-1, 0]);
          q.dx = dir[0]; q.dy = dir[1]; q.sinceTurn = 0;
        }
        q.x += q.dx * speed * q.spd;
        q.y += q.dy * speed * q.spd;

        if (q.x < -20 || q.x > w + 20 || q.y < -20 || q.y > h + 20) {
          p[i] = spawn();
          continue;
        }

        q.trail.push(q.x, q.y);
        if (q.trail.length > TRAIL * 2) { q.trail.splice(0, q.trail.length - TRAIL * 2); }

        seg = q.trail.length / 2;
        for (k = 1; k < seg; k++) {
          k2 = k * 2;
          a = (k / seg) * q.o * (0.25 + sig * 0.55);
          c.strokeStyle = 'rgba(' + riderRGB + ', ' + a.toFixed(3) + ')';
          c.lineWidth = 1 + (k / seg) * 1.8;
          c.beginPath();
          c.moveTo(q.trail[k2 - 2], q.trail[k2 - 1]);
          c.lineTo(q.trail[k2], q.trail[k2 + 1]);
          c.stroke();
        }

        c.beginPath();
        c.arc(q.x, q.y, 2 + sig * 1.5, 0, 6.28);
        c.fillStyle = 'rgba(' + riderRGB + ', ' + (0.6 + sig * 0.4).toFixed(2) + ')';
        c.fill();
        c.beginPath();
        c.arc(q.x, q.y, 1, 0, 6.28);
        c.fillStyle = 'rgba(255, 255, 255, ' + (0.7 + sig * 0.3).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Streak Effect (warp star streaks) ──
  // Driven by --velocity (Hyperspace theme).
  registerEffect('streak', function (_cvs, _context, _params, env) {
    var BASE = 60, MAX = 350; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
var i, q, tc, cx, cy, dx, dy;
    function create(x, y) { return { x: x != null ? x : vrand() * w * 1.2 - w * 0.1, y: y != null ? y : -10 - vrand() * h * 0.3, r: 1.5 + vrand() * 3.5, s: 0.06 + vrand() * 0.15, o: 0.2 + vrand() * 0.4, ph: vrand() * 6.28, wa: 0.3 + vrand() * 1 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--disturbance'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--disturbance');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 0.7); q.x += Math.sin(ts * 0.0008 + q.ph) * q.wa * (0.1 + sig * 0.3);
        if (q.y > h + 20) { q.x = vrand() * w * 1.2 - w * 0.1; q.y = -10 - vrand() * 30; q.o = 0.2 + vrand() * 0.4; }
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(120, 160, 90, ' + (q.o * (0.1 + sig * 0.5)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Ink Effect (dispersing droplets) ──
  // Driven by --bleed (Inkwash theme).
  registerEffect('ink', function (_cvs, _context, _params, env) {
    var BASE = 20, MAX = 100; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : vrand() * h, r: 0.5 + vrand() * 1.5, s: 0.3 + vrand() * 0.8, o: 0.3 + vrand() * 0.6, ph: vrand() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--bleed'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--bleed');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += Math.sin(ts * 0.001 + q.ph) * q.s * sig * 0.4; q.y += Math.cos(ts * 0.0012 + q.ph) * q.s * sig * 0.4; q.r += sig * 0.02;
        if (q.x < -20 || q.x > w + 20 || q.y < -20 || q.y > h + 20 || q.r > 8) { q.x = vrand() * w; q.y = vrand() * h; q.r = 0.5 + vrand() * 1.5; q.o = 0.3 + vrand() * 0.6; }
        c.beginPath(); c.arc(q.x, q.y, q.r, 0, 6.28);
        c.fillStyle = 'rgba(40, 50, 70, ' + (q.o * sig).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Thread Effect (horizontal shuttle: criss-cross w/ CSS warp) ──
  // Driven by --weft (Loom theme). Horizontal shuttle threads in theme purple/cyan.
  // On snag (divergence), threads tangle into red knots.
  registerEffect('thread', function (_cvs, _context, _params, env) {
    var BASE = 12, MAX = 50; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, alpha, snag;
    function isSnagged() { return document.documentElement.getAttribute('data-loom-state') === 'snag'; }
    function create() {
      return {
        x: vrand() * w * 1.5 - w * 0.25,
        y: vrand() * h,
        l: 30 + vrand() * 80,
        s: 0.3 + vrand() * 0.7,
        o: 0.15 + vrand() * 0.35,
        ph: vrand() * 6.28,
        purple: vrand() < 0.7,
      };
    }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--weft'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--weft');
      snag = isSnagged();
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create());
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.x += q.s * (0.3 + sig * 0.9);
        if (q.x > w + q.l) { q.x = -q.l; q.y = vrand() * h; q.l = 30 + vrand() * 80; q.s = 0.3 + vrand() * 0.7; }
        alpha = q.o * (0.15 + sig * 0.5);
        if (snag) {
          c.strokeStyle = 'rgba(255, 106, 106, ' + alpha.toFixed(2) + ')';
          c.lineWidth = 0.8 + vrand() * 0.8;
          c.beginPath();
          c.moveTo(q.x, q.y);
          c.lineTo(q.x + q.l * Math.sin(ts * 0.01 + q.ph), q.y + q.l * Math.cos(ts * 0.01 + q.ph));
          c.stroke();
        } else {
          c.strokeStyle = q.purple
            ? 'rgba(184, 144, 240, ' + alpha.toFixed(2) + ')'
            : 'rgba(96, 204, 224, ' + (alpha * 0.7).toFixed(2) + ')';
          c.lineWidth = 0.6 + sig * 0.4;
          c.beginPath();
          c.moveTo(q.x, q.y);
          c.lineTo(q.x + q.l, q.y);
          c.stroke();
        }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Matrix Effect (falling digital glyph segments) ──
  // Driven by --activity (Mainframe theme). Right-angled, axis-aligned
  // rectangles snapped to a column grid — falling code, not snow.
  registerEffect('matrix', function (_cvs, _context, _params, env) {
    var BASE = 40, MAX = 200; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var CELL = 12;
    var i, q, tc, interp, k, ty, glyphH, glyphW, alpha, trailW, reshape;
    function snapCol() { var cols = Math.max(1, Math.floor(w / CELL)); return (Math.floor(vrand() * cols) + 0.5) * CELL; }
    function pickShape() {
      var roll = vrand();
      if (roll < 0.55) return { gw: 2 + vrand() * 2, gh: CELL - 2 + vrand() * 6 };
      if (roll < 0.92) return { gw: 3 + vrand() * 2, gh: 3 + vrand() * 3 };
      return { gw: 7 + vrand() * 10, gh: 3 + vrand() * 5 };
    }
    function create(x, y) {
      var shape = pickShape();
      return {
        x: x != null ? x : snapCol(),
        y: y != null ? y : -10 - vrand() * h * 0.3,
        s: 0.3 + vrand() * 0.8,
        o: 0.2 + vrand() * 0.6,
        gw: shape.gw,
        gh: shape.gh,
        trail: 3 + ((vrand() * 7) | 0),
      };
    }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--activity'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--activity');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      c.save();
      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.y += CELL * q.s * (0.18 + sig * 0.55);
        if (q.y > h + CELL) {
          reshape = pickShape();
          q.x = snapCol(); q.y = -CELL - vrand() * 30;
          q.s = 0.3 + vrand() * 0.8; q.gw = reshape.gw; q.gh = reshape.gh;
          q.trail = 3 + ((vrand() * 7) | 0);
        }
        interp = 1 - (q.y / h);
        glyphW = q.gw;
        glyphH = q.gh;
        alpha = q.o * interp * (0.25 + sig * 0.75);
        c.fillStyle = 'rgba(120, 255, 140, ' + alpha.toFixed(2) + ')';
        c.fillRect(Math.round(q.x - glyphW / 2), Math.round(q.y), Math.round(glyphW), Math.round(glyphH));
        trailW = Math.max(2, glyphW * 0.6);
        for (k = 1; k <= q.trail; k++) {
          ty = q.y - k * CELL;
          if (ty < -CELL) break;
          alpha = q.o * interp * (0.2 + sig * 0.7) * (1 - k / (q.trail + 1)) * 0.6;
          if (alpha <= 0.01) continue;
          c.fillStyle = 'rgba(80, 220, 100, ' + alpha.toFixed(2) + ')';
          c.fillRect(Math.round(q.x - trailW / 2), Math.round(ty + 3), Math.round(trailW), 3);
        }
      }
      c.restore();
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Leaf Effect (fireflies crossing the screen) ──
  // Driven by --disturbance (Old Growth theme); blinking warm motes drift horizontally.
  registerEffect('leaf', function (_cvs, _context, _params, env) {
    var BASE = 12, MAX = 48; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, blink, alpha, dir;
    function create(x, y) {
      dir = vrand() < 0.5 ? 1 : -1;
      return {
        bx: x != null ? x : vrand() * w,
        baseY: y != null ? y : vrand() * h,
        x: x != null ? x : vrand() * w,
        y: y != null ? y : vrand() * h,
        r: 1.1 + vrand() * 1.8,
        vx: dir * (0.014 + vrand() * 0.028),
        bobA: 18 + vrand() * 42,
        bobF: 0.00011 + vrand() * 0.00022,
        wanderA: 30 + vrand() * 70,
        wanderF: 0.00018 + vrand() * 0.00036,
        vWanderF: 0.00011 + vrand() * 0.00026,
        blinkF: 0.0009 + vrand() * 0.0018,
        ph: vrand() * 6.28,
        ph2: vrand() * 6.28,
        bph: vrand() * 6.28,
        hue: 70 + vrand() * 22,
      };
    }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--disturbance'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--disturbance');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();

      c.save();
      c.globalCompositeOperation = 'lighter';
      for (i = 0; i < p.length; i++) {
        q = p[i];

        q.bx += q.vx * (0.4 + sig * 0.6);
        q.x = q.bx
            + Math.sin(ts * q.wanderF + q.ph) * q.wanderA
            + Math.sin(ts * q.wanderF * 0.37 + q.ph2) * q.wanderA * 0.5;
        q.y = q.baseY
            + Math.sin(ts * q.bobF + q.ph) * q.bobA
            + Math.sin(ts * q.vWanderF + q.ph2) * q.bobA * 0.4;

        if (q.bx > w + 120) { q.bx = -120; q.baseY = vrand() * h; }
        else if (q.bx < -120) { q.bx = w + 120; q.baseY = vrand() * h; }

        // Smooth sine swell (remapped 0..1) = gentle fade in/out, not a sharp flash.
        blink = Math.sin(ts * q.blinkF * (1 + sig * 0.8) + q.bph) * 0.5 + 0.5;
        alpha = (0.25 + sig * 0.3) + blink * (0.45 + sig * 0.4);
        if (alpha > 1) alpha = 1;

        c.beginPath(); c.arc(q.x, q.y, q.r * 4.5, 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(q.hue) + ', 90%, 60%, ' + (alpha * 0.16).toFixed(3) + ')';
        c.fill();
        c.beginPath(); c.arc(q.x, q.y, q.r * 2, 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(q.hue) + ', 95%, 65%, ' + (alpha * 0.4).toFixed(3) + ')';
        c.fill();
        c.beginPath(); c.arc(q.x, q.y, q.r, 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(q.hue + 8) + ', 100%, 85%, ' + alpha.toFixed(3) + ')';
        c.fill();
      }
      c.restore();
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Prism Effect (spectrum light motes) ──
  // Driven by --prism + --hue (Prism theme).
  registerEffect('prism', function (_cvs, _context, _params, env) {
    var BASE = 40, MAX = 150; var p = [], w = 0, h = 0, sig = 0, hueShift = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : vrand() * h, r: 0.8 + vrand() * 2.5, s: 0.1 + vrand() * 0.3, o: 0.15 + vrand() * 0.4, ph: vrand() * 6.28, hueOff: vrand() * 360 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--prism'); hueShift = parseFloat(document.documentElement.style.getPropertyValue('--hue')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--prism');
      hueShift = parseFloat(document.documentElement.style.getPropertyValue('--hue')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += Math.sin(ts * 0.001 + q.ph) * 0.3; q.y += Math.cos(ts * 0.0008 + q.ph) * 0.2;
        if (q.x < -10 || q.x > w + 10 || q.y < -10 || q.y > h + 10) { q.x = vrand() * w; q.y = vrand() * h; }
        hue = (q.hueOff + hueShift + ts * 0.02) % 360;
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(hue) + ', 90%, ' + Math.round(55 + sig * 25) + '%, ' + (q.o * (0.1 + sig * 0.6)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Pulse Effect (heartbeat pulsing dots) ──
  // Driven by --beat (Pulse theme).
  registerEffect('pulse', function (_cvs, _context, _params, env) {
    var BASE = 20, MAX = 80; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, pulsePhase = 0, beat, expand;
    function create() { return { x: vrand() * w, y: vrand() * h, r: 2 + vrand() * 4, o: 0.2 + vrand() * 0.5, ph: vrand() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--beat'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--beat');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create());
      while (p.length > tc) p.pop();
      pulsePhase = ts * 0.002;
      for (i = 0; i < p.length; i++) {
        q = p[i]; beat = Math.max(0, Math.sin(pulsePhase + q.ph) * (0.2 + sig * 0.8));
        expand = 1 + beat * 2;
        c.beginPath(); c.arc(q.x, q.y, q.r * expand, 0, 6.28);
        c.fillStyle = 'rgba(' + Math.round(200 + sig * 55) + ', ' + Math.round(60 + sig * 40) + ', ' + Math.round(60 + sig * 40) + ', ' + (q.o * beat * (0.5 + sig * 0.5)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Energy Effect (glowing plasma) ──
  // Driven by --throughput (Reactor theme).
  registerEffect('energy', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 150; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, cx, cy, x, y;
    function create() { var a = vrand() * 6.28; return { a: a, r: 10 + vrand() * Math.min(w, h) * 0.4, s: 0.1 + vrand() * 0.3, o: 0.2 + vrand() * 0.5, size: 1 + vrand() * 3, ph: vrand() * 6.28 }; }
    function init(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--throughput'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height; cx = w / 2; cy = h / 2;
      sig = readSignal('--throughput');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create());
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.a += q.s * (0.2 + sig * 0.8) * 0.02;
        x = cx + Math.cos(q.a) * q.r; y = cy + Math.sin(q.a) * q.r;
        glow = q.o * (0.1 + sig * 0.9);
        c.beginPath(); c.arc(x, y, q.size * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(' + Math.round(80 + sig * 100) + ', ' + Math.round(200 + sig * 55) + ', 255, ' + glow.toFixed(2) + ')';
        c.fill();
        if (sig > 0.3) {
          c.beginPath(); c.arc(x, y, q.size * 2, 0, 6.28);
          c.fillStyle = 'rgba(100, 220, 255, ' + (glow * 0.15).toFixed(2) + ')';
          c.fill();
        }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Flare Effect (solar eruption particles) ──
  // Driven by --flare (Solar Flare theme).
  registerEffect('flare', function (_cvs, _context, _params, env) {
    var BASE = 20, MAX = 120; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { var a = -1.5 - vrand() * 0.8; return { x: x != null ? x : vrand() * w, y: y != null ? y : h + 10, r: 1 + vrand() * 3, s: 0.5 + vrand() * 1.5, o: 0.3 + vrand() * 0.6, a: a, spread: (vrand() - 0.5) * 0.8 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--flare'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--flare');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 1.2) * q.a; q.x += q.spread * (0.2 + sig * 0.8);
        if (q.y < -30) { q.x = vrand() * w; q.y = h + 10 + vrand() * 20; q.s = 0.5 + vrand() * 1.5; q.o = 0.3 + vrand() * 0.6; q.spread = (vrand() - 0.5) * 0.8; }
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(255, ' + Math.round(150 + sig * 80) + ', ' + Math.round(50 + sig * 80) + ', ' + (q.o * (0.2 + sig * 0.8)).toFixed(2) + ')';
        c.fill();
        if (sig > 0.4) {
          c.beginPath(); c.arc(q.x - 3, q.y + 2, q.r * 0.4, 0, 6.28);
          c.fillStyle = 'rgba(255, 200, 100, ' + (q.o * sig * 0.3).toFixed(2) + ')';
          c.fill();
        }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Shard Effect (colored light shards) ──
  // Driven by --lumin (Stained Glass theme).
  registerEffect('shard', function (_cvs, _context, _params, env) {
    var BASE = 20, MAX = 100; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w * 1.2 - w * 0.1, y: y != null ? y : -10 - vrand() * h * 0.3, s: 4 + vrand() * 10, hs: 3 + vrand() * 6, sp: 0.15 + vrand() * 0.4, o: 0.2 + vrand() * 0.5, ph: vrand() * 6.28, hue: vrand() * 360, rot: vrand() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--lumin'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--lumin');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.sp * (0.2 + sig * 0.6); q.x += Math.sin(ts * 0.001 + q.ph) * 0.3; q.rot += 0.01;
        if (q.y > h + 20) { q.x = vrand() * w * 1.2 - w * 0.1; q.y = -10 - vrand() * 30; q.s = 4 + vrand() * 10; q.o = 0.2 + vrand() * 0.5; }
        c.save(); c.translate(q.x, q.y); c.rotate(q.rot);
        c.fillStyle = 'hsla(' + q.hue + ', 70%, ' + Math.round(45 + sig * 35) + '%, ' + (q.o * (0.1 + sig * 0.6)).toFixed(2) + ')';
        c.fillRect(-q.s / 2, -q.hs / 2, q.s, q.hs);
        c.restore();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Debris Effect (shaking ground debris) ──
  // Driven by --tremor (Tectonic theme).
  registerEffect('debris', function (_cvs, _context, _params, env) {
    var BASE = 15, MAX = 80; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : h * 0.5 + vrand() * h * 0.5, s: 2 + vrand() * 5, o: 0.2 + vrand() * 0.5, ph: vrand() * 6.28, jx: (vrand() - 0.5) * 2, jy: (vrand() - 0.5) * 2 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--tremor'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--tremor');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; shake = Math.sin(ts * 0.005 + q.ph) * sig * 4;
        q.x += q.jx * sig * 0.2 + shake * 0.1; q.y += q.jy * sig * 0.2 + Math.cos(ts * 0.004 + q.ph) * sig * 2;
        if (q.x < -10 || q.x > w + 10) { q.x = vrand() * w; }
        if (q.y > h + 10) { q.y = h * 0.5 + vrand() * h * 0.4; }
        c.fillStyle = 'rgba(140, 120, 100, ' + (q.o * sig).toFixed(2) + ')';
        c.fillRect(q.x - q.s / 2, q.y - q.s / 2, q.s, q.s);
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Spray Effect (water foam droplets) ──
  // Driven by --surge (Tide theme).
  registerEffect('spray', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 150; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : vrand() * w, y: y != null ? y : h - 20 + vrand() * 20, r: 0.5 + vrand() * 2, s: 0.3 + vrand() * 1, o: 0.2 + vrand() * 0.5, a: -1.8 + vrand() * -0.5, spread: (vrand() - 0.5) * 0.6, ph: vrand() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--surge'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--surge');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * q.a * (0.3 + sig * 1); q.x += q.spread * sig + Math.sin(ts * 0.002 + q.ph) * 0.2;
        if (q.y < -20) { q.x = vrand() * w; q.y = h - 20 + vrand() * 20; q.s = 0.3 + vrand() * 1; q.spread = (vrand() - 0.5) * 0.6; }
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(180, 220, 240, ' + (q.o * sig).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Bubble Effect (air bubbles rise to the top, sway with the wave ripples) ──
  // Driven by --surge (rise speed + sway frequency track the CSS wave swell).
  registerEffect('bubble', function (_cvs, _context, _params, env) {
    var BASE = 10, MAX = 55; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, swayHz, swayAmp, rad, alpha, rim;
    function create(seed) { return { x: vrand() * w, y: seed ? vrand() * h : h + 10 + vrand() * 40, r: 1.5 + vrand() * 4.5, s: 0.25 + vrand() * 0.55, o: 0.25 + vrand() * 0.45, ph: vrand() * 6.28, amp: 0.5 + vrand() * 1.2, wob: 0.85 + vrand() * 0.35 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(true)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--surge'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--surge');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(false));
      while (p.length > tc) p.pop();
      swayHz = 0.0004 + sig * 0.0008;
      swayAmp = 0.25 + sig * 0.6;
      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.y -= q.s * (0.18 + sig * 0.42);
        q.x += Math.sin(ts * swayHz + q.ph) * swayAmp * q.amp;
        if (q.y < -20) { q.x = vrand() * w; q.y = h + 10 + vrand() * 40; q.r = 1.5 + vrand() * 4.5; q.s = 0.25 + vrand() * 0.55; q.o = 0.25 + vrand() * 0.45; }
        if (q.x < -10) q.x = w + 10; else if (q.x > w + 10) q.x = -10;
        rad = q.r * (q.wob + Math.sin(ts * 0.003 + q.ph) * 0.08);
        alpha = q.o * (0.45 + sig * 0.55);
        c.beginPath(); c.arc(q.x, q.y, rad, 0, 6.28);
        c.fillStyle = 'rgba(170, 220, 245, ' + (alpha * 0.4).toFixed(2) + ')'; c.fill();
        c.beginPath(); c.arc(q.x, q.y, rad, 0, 6.28);
        c.strokeStyle = 'rgba(210, 240, 255, ' + alpha.toFixed(2) + ')'; c.lineWidth = 0.8; c.stroke();
        rim = Math.max(0.4, rad * 0.32);
        c.beginPath(); c.arc(q.x - rad * 0.3, q.y - rad * 0.3, rim, 0, 6.28);
        c.fillStyle = 'rgba(255, 255, 255, ' + (alpha * 0.7).toFixed(2) + ')'; c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Spin Effect (rotating vinyl particles) ──
  // Driven by --wobble (Vinyl theme).
  registerEffect('spin', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 100; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, cx, cy, r, th;
    function create() { var a = vrand() * 6.28; return { a: a, r: 10 + vrand() * 140, s: 0.5 + vrand() * 1.5, o: 0.15 + vrand() * 0.4, size: 1 + vrand() * 2.5 }; }
    function init(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--wobble'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height; cx = w / 2; cy = h / 2;
      sig = readSignal('--wobble');
      tc = Math.round(BASE + (1 - sig) * (MAX - BASE));
      while (p.length < tc) p.push(create());
      while (p.length > tc) p.pop();
      r = (1 - sig) * 0.05 + sig * 0.003;
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.a += r;
        q.r += Math.sin(ts * 0.001 + q.a) * sig * 0.3;
        q.r = Math.max(5, Math.min(200, q.r));
        th = q.a + Math.sin(ts * 0.002 + q.a) * sig * 0.3;
        c.beginPath(); c.arc(cx + Math.cos(th) * q.r, cy + Math.sin(th) * q.r, q.size * (0.5 + (1 - sig) * 0.5), 0, 6.28);
        c.fillStyle = 'rgba(40, 40, 50, ' + (q.o * (0.2 + (1 - sig) * 0.5)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Spark Effect (forging anvil sparks) ──
  // Driven by --heat (Forge theme). Fast, bright streaks burst from a bottom anvil band.
  registerEffect('spark', function (_cvs, _context, _params, env) {
    var BASE = 80, MAX = 350; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, life, alpha, r, g, b, dx, dy, len, vmag, a, spd;
    var BAND_Y = 0.92;
    function create(x, y) {
      var a = -Math.PI / 2 + (vrand() - 0.5) * 2.0;
      var spd = 4 + vrand() * 8;
      return {
        x: x != null ? x : vrand() * w,
        y: y != null ? y : h * BAND_Y + vrand() * h * 0.08,
        vx: Math.cos(a) * spd,
        vy: Math.sin(a) * spd,
        life: 0.3 + vrand() * 0.7,
        maxLife: 0.3 + vrand() * 0.7,
        size: 2 + vrand() * 4,
        o: 0.5 + vrand() * 0.5,
        friction: 0.96 + vrand() * 0.03,
      };
    }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = readSignal('--heat'); }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--heat');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.x += q.vx;
        q.y += q.vy;
        q.vx *= q.friction;
        q.vy *= q.friction;
        q.vy += 0.02;
        q.life -= 0.008 * (1 + sig * 0.5);
        if (q.life <= 0 || q.y > h + 10 || q.x < -20 || q.x > w + 20) {
          a = -Math.PI / 2 + (vrand() - 0.5) * 2.0;
          spd = 4 + vrand() * 8;
          q.x = vrand() * w;
          q.y = h * BAND_Y + vrand() * h * 0.08;
          q.vx = Math.cos(a) * spd;
          q.vy = Math.sin(a) * spd;
          q.life = 0.3 + vrand() * 0.7;
          q.maxLife = q.life;
          q.size = 2 + vrand() * 4;
          q.o = 0.5 + vrand() * 0.5;
          q.friction = 0.96 + vrand() * 0.03;
        }
        life = q.life / q.maxLife;
        alpha = q.o * life * (0.3 + sig * 0.7);
        if (life > 0.7) { r = 255; g = 255; b = 220; }
        else if (life > 0.4) { r = 255; g = Math.round(180 + (life - 0.4) / 0.3 * 75); b = Math.round(80 + (life - 0.4) / 0.3 * 140); }
        else { r = 255; g = Math.round(80 + life / 0.4 * 100); b = Math.round(20 + life / 0.4 * 60); }
        len = q.size * (0.3 + life * 0.7);
        vmag = Math.sqrt(q.vx * q.vx + q.vy * q.vy) || 1;
        dx = (q.vx / vmag) * len;
        dy = (q.vy / vmag) * len;
        c.beginPath(); c.moveTo(q.x, q.y); c.lineTo(q.x - dx + (vrand() - 0.5) * 0.5, q.y - dy + (vrand() - 0.5) * 0.5);
        c.strokeStyle = 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha.toFixed(2) + ')';
        c.lineWidth = 0.8 + life * 1.2; c.lineCap = 'round'; c.stroke();
        if (life > 0.3) { c.beginPath(); c.arc(q.x, q.y, 0.6 + life * 1.2, 0, 6.28); c.fillStyle = 'rgba(255, 255, 230, ' + (alpha * 0.5).toFixed(2) + ')'; c.fill(); }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Confetti Effect (neon party confetti) ──
  // Driven by --neon (Arcade theme). Colorful rectangles and strips in
  // hot pink, cyan, yellow, green, and purple — fluttering down like
  // a celebration. Higher neon = thicker, faster, brighter confetti.
  registerEffect('confetti', function (_cvs, _context, _params, env) {
    var BASE = 15, MAX = 120; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc;

    var COLORS = [
      '255,45,120',   // hot pink
      '0,212,255',    // cyan
      '255,224,51',   // yellow
      '0,255,136',    // lime green
      '192,80,255',   // purple
    ];

    function create(x, y) {
      var colorIdx = (vrand() * COLORS.length) | 0;
      var wide = vrand() < 0.4;
      return {
        x: x != null ? x : vrand() * w * 1.3 - w * 0.15,
        y: y != null ? y : -10 - vrand() * h * 0.3,
        w: wide ? 4 + vrand() * 8 : 2 + vrand() * 4,
        h: wide ? 2 + vrand() * 3 : 3 + vrand() * 6,
        s: 0.3 + vrand() * 0.8,
        o: 0.4 + vrand() * 0.5,
        ph: vrand() * 6.28,
        rot: vrand() * 6.28,
        rotSpd: -0.03 + vrand() * 0.06,
        sway: 0.2 + vrand() * 0.6,
        color: COLORS[colorIdx],
      };
    }

    function init(width, height) {
      w = width; h = height; p = [];
      for (i = 0; i < BASE; i++) p.push(create(null, null));
    }

    function resize(width, height) { w = width; h = height; }

    function start(width, height) {
      w = width; h = height; init(w, h); ip = false;
      sig = readSignal('--neon');
    }

    function stop() { p = []; }

    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = readSignal('--neon');
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();

      for (i = 0; i < p.length; i++) {
        q = p[i];
        q.y += q.s * (0.2 + sig * 0.6);
        q.x += Math.sin(ts * 0.001 + q.ph) * q.sway * (0.3 + sig * 0.7);
        q.rot += q.rotSpd * (0.5 + sig * 0.5);

        if (q.y > h + 20) {
          q.x = vrand() * w * 1.3 - w * 0.15;
          q.y = -10 - vrand() * 30;
          q.s = 0.3 + vrand() * 0.8;
          q.o = 0.4 + vrand() * 0.5;
          q.rot = vrand() * 6.28;
          q.color = COLORS[(vrand() * COLORS.length) | 0];
        }

        c.save();
        c.translate(q.x, q.y);
        c.rotate(q.rot);
        c.fillStyle = 'rgba(' + q.color + ', ' + (q.o * (0.15 + sig * 0.6)).toFixed(2) + ')';
        c.fillRect(-q.w / 2, -q.h / 2, q.w, q.h);
        c.restore();
      }
    }

    return { start: start, stop: stop, update: update, resize: resize };
  });

  /* ═══════════════════════════════════════════════
     Public API
     ═══════════════════════════════════════════════ */

  window.ParticleSystem = {
    registerEffect: registerEffect,
    apply: apply,
    stopEffect: stopEffect,
    readPref: readPref,
    writePref: writePref,
    getEffects: function () { return Object.keys(effects); },
    onEffectLevelChange: onEffectLevelChange,
    pause: pause,
    resume: resume,
    getActiveEffect: function () { return activeEffect; },
  };

  // Wire resize
  window.addEventListener('resize', function () {
    resizeCanvas();
  });

  // Wire effect-level changes if available
  if (window.EffectLevel) {
    window.EffectLevel.onChange(onEffectLevelChange);
  }
})();
