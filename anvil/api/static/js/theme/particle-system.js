(function () {
  'use strict';

  /* ═══════════════════════════════════════════════
     Particle System — Canvas-based overlay effects
     ═══════════════════════════════════════════════ */

  var PARTICLE_KEY = 'theme:particle';
  var PARTICLE_CLASS = 'theme-particles-active';
  var NONE_CLASS = 'theme-particles-none';

  // ── Effect Registry ──
  var effects = {};

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
      'position:absolute;inset:0;width:100%;height:100%;' +
      'pointer-events:none;z-index:40;display:block;';
    // Insert inside app-shell as first child so stacking context is shared
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
  function animationLoop(timestamp) {
    if (!ctx || !canvas || !isRunning) {
      rAFid = null;
      return;
    }
    var w = window.innerWidth;
    var h = window.innerHeight;

    ctx.clearRect(0, 0, w, h);

    if (activeImpl && typeof activeImpl.update === 'function') {
      activeImpl.update(timestamp, w, h, ctx);
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
    var BASE_COUNT = 100;
    var MAX_COUNT = 350;
    var flakes = [];
    var w = 0, h = 0;
    var snowBase = 0;
    var driftPhase = 0;
    var freeze = 0;
    var isPaused = env.paused;
    var i, f, radius, targetCount, drift;

    function createFlake(x, y) {
      radius = 0.8 + Math.random() * 2.2;
      return {
        x: x != null ? x : Math.random() * w * 1.3 - w * 0.15,
        y: y != null ? y : -radius * 2 - Math.random() * h * 0.5,
        r: radius,
        speed: 0.12 + Math.random() * 0.3,
        opacity: 0.25 + Math.random() * 0.55,
        phase: Math.random() * Math.PI * 2,
        wobbleAmp: 0.2 + Math.random() * 0.6,
        wobbleFreq: 0.002 + Math.random() * 0.004,
        drift: -0.05 + Math.random() * 0.1,
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
      freeze = parseFloat(
        document.documentElement.style.getPropertyValue('--freeze')
      ) || 0;
    }

    function stop() {
      flakes = [];
    }

    function update(timestamp, width, height, context) {
      if (isPaused) return;
      w = width;
      h = height;

      freeze = parseFloat(
        document.documentElement.style.getPropertyValue('--freeze')
      ) || 0;

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
        if (f.y > h + 10) {
          f.x = Math.random() * w * 1.3 - w * 0.15;
          f.y = -f.r * 2 - Math.random() * 30;
          f.speed = 0.12 + Math.random() * 0.3;
          f.opacity = 0.25 + Math.random() * 0.55;
        }

        drift = Math.sin(driftPhase * f.wobbleFreq * 10 + f.phase) * f.wobbleAmp
              + f.drift * (1 + freeze * 0.5);
        f.x += drift * 0.4;
        f.y += f.speed * (0.5 + freeze * 0.5);

        context.beginPath();
        context.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        context.fillStyle = 'rgba(255, 255, 255, ' + f.opacity.toFixed(2) + ')';
        context.fill();
      }

      // Gentle snow cover at bottom when freeze is high
      if (freeze > 0.5) {
        context.fillStyle = 'rgba(255, 255, 255, ' + ((freeze - 0.5) * 0.08).toFixed(3) + ')';
        context.fillRect(0, h - 6, w, 6);
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
    var i, d, lenVal, speedVal, targetCount, windStrength, windX, windVel, dx, dy;

    function createDrop(x, y) {
      lenVal = 12 + Math.random() * 14;
      speedVal = 3 + Math.random() * 3;
      return {
        x: x != null ? x : Math.random() * w * 1.3 - w * 0.15,
        y: y != null ? y : -lenVal - Math.random() * h * 0.3,
        length: lenVal,
        speed: speedVal,
        opacity: 0.25 + Math.random() * 0.5,
        windPhase: Math.random() * Math.PI * 2,
        windAmp: 0.5 + Math.random() * 0.8,
        width: 0.5 + Math.random() * 0.8,
      };
    }

    function init(width, height) {
      w = width;
      h = height;
      drops = [];
      for (i = 0; i < BASE_COUNT; i++) {
        drops.push(createDrop(null, null));
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
      charge = parseFloat(
        document.documentElement.style.getPropertyValue('--charge')
      ) || 0;
    }

    function stop() {
      drops = [];
    }

    function update(timestamp, width, height, context) {
      if (isPaused) return;
      w = width;
      h = height;

      charge = parseFloat(
        document.documentElement.style.getPropertyValue('--charge')
      ) || 0;

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
          d.x = Math.random() * w * 1.3 - w * 0.15;
          d.y = -d.length - Math.random() * 20;
          d.speed = 3 + Math.random() * 3;
          d.opacity = 0.25 + Math.random() * 0.5;
        }

        windX = Math.sin(gustPhase * 0.3 + d.windPhase) * d.windAmp * windStrength * 2;
        windVel = windStrength * d.speed * 0.6;

        d.x += windVel + windX * 0.06;
        d.y += d.speed * (1 + charge * 0.6);

        // Raindrops are thin angled lines leaning with the wind
        dx = windStrength * 0.3 * d.length * 0.15;
        dy = d.length;

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
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : h + 10 + Math.random() * 50, r: 0.8 + Math.random() * 2.2, s: 0.2 + Math.random() * 0.5, o: 0.3 + Math.random() * 0.6, ph: Math.random() * 6.28, wa: 0.2 + Math.random() * 0.5 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--ember')) || parseFloat(document.documentElement.style.getPropertyValue('--heat')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--ember')) || parseFloat(document.documentElement.style.getPropertyValue('--heat')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y -= q.s * (0.3 + sig * 0.7); q.x += Math.sin(ts * 0.002 + q.ph) * q.wa * 0.3;
        if (q.y < -20) { q.x = Math.random() * w; q.y = h + 10 + Math.random() * 30; q.s = 0.2 + Math.random() * 0.5; q.o = 0.3 + Math.random() * 0.6; }
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
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : Math.random() * h, r: 1.2 + Math.random() * 3, s: 0.1 + Math.random() * 0.3, o: 0.1 + Math.random() * 0.4, ph: Math.random() * 6.28, hue: 140 + Math.random() * 120 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--calm')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--calm')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += Math.sin(ts * 0.0008 + q.ph) * 0.4 + 0.05; q.y += Math.sin(ts * 0.0012 + q.ph * 1.3) * 0.2;
        if (q.x > w + 20) { q.x = -20; q.y = Math.random() * h; }
        if (q.x < -20) { q.x = w + 20; q.y = Math.random() * h; }
        hue = q.hue + Math.sin(ts * 0.0005 + q.ph) * 30;
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.5 + sig * 0.5), 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(hue) + ', 80%, ' + Math.round(60 + sig * 30) + '%, ' + (q.o * (0.2 + sig * 0.8)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Petal Effect (floating blossom) ──
  // Driven by --open (Bloom theme).
  registerEffect('petal', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 150; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : Math.random() * w * 1.2 - w * 0.1, y: y != null ? y : -10 - Math.random() * h * 0.3, r: 1.5 + Math.random() * 3, s: 0.08 + Math.random() * 0.2, o: 0.2 + Math.random() * 0.4, ph: Math.random() * 6.28, wa: 0.3 + Math.random() * 0.8, hue: 320 + Math.random() * 40 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--open')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--open')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 0.7); q.x += Math.sin(ts * 0.001 + q.ph) * q.wa * 0.2;
        if (q.y > h + 20) { q.x = Math.random() * w * 1.2 - w * 0.1; q.y = -10 - Math.random() * 30; q.s = 0.08 + Math.random() * 0.2; q.o = 0.2 + Math.random() * 0.4; }
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.4 + sig * 0.6), 0, 6.28);
        c.fillStyle = 'hsla(' + Math.round(q.hue) + ', 70%, ' + Math.round(60 + sig * 25) + '%, ' + (q.o * (0.2 + sig * 0.6)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Biolum Effect (glowing deep-sea dots) ──
  // Driven by --depth (Deep Sea theme).
  registerEffect('biolum', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 120; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : h + Math.random() * 40, r: 1 + Math.random() * 3, s: 0.15 + Math.random() * 0.4, o: 0.2 + Math.random() * 0.7, ph: Math.random() * 6.28, wa: 0.1 + Math.random() * 0.3 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--depth')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--depth')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y -= q.s * (0.2 + sig * 0.6); q.x += Math.sin(ts * 0.0015 + q.ph) * q.wa;
        if (q.y < -20) { q.x = Math.random() * w; q.y = h + Math.random() * 30; q.o = 0.2 + Math.random() * 0.7; }
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

  // ── Glitch Effect (scanning digital dots) ──
  // Driven by --focus (Hologram theme).
  registerEffect('glitch', function (_cvs, _context, _params, env) {
    var BASE = 40, MAX = 200; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : Math.random() * h, l: 3 + Math.random() * 12, s: 0.3 + Math.random() * 0.8, o: 0.1 + Math.random() * 0.5, ph: Math.random() * 6.28, flick: Math.random() }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--focus')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--focus')) || 0;
      tc = Math.round(BASE + (1 - sig) * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.2 + (1 - sig) * 0.8);
        if (q.y > h + 10) { q.y = -10; q.x = Math.random() * w; q.l = 3 + Math.random() * 12; }
        if (Math.sin(ts * 0.003 + q.ph) > q.flick * 1.5 - 0.5) {
          c.beginPath(); c.moveTo(q.x, q.y); c.lineTo(q.x + q.l, q.y);
          c.strokeStyle = 'rgba(0, 220, 255, ' + (q.o * (0.3 + (1 - sig) * 0.7)).toFixed(2) + ')';
          c.lineWidth = 1 + Math.random(); c.stroke();
        }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Streak Effect (warp star streaks) ──
  // Driven by --velocity (Hyperspace theme).
  registerEffect('streak', function (_cvs, _context, _params, env) {
    var BASE = 60, MAX = 350; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
var i, q, tc, cx, cy, dx, dy;
    function create(x, y) { return { x: x != null ? x : Math.random() * w * 1.2 - w * 0.1, y: y != null ? y : -10 - Math.random() * h * 0.3, r: 1.5 + Math.random() * 3.5, s: 0.06 + Math.random() * 0.15, o: 0.2 + Math.random() * 0.4, ph: Math.random() * 6.28, wa: 0.3 + Math.random() * 1 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--disturbance')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--disturbance')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 0.7); q.x += Math.sin(ts * 0.0008 + q.ph) * q.wa * (0.1 + sig * 0.3);
        if (q.y > h + 20) { q.x = Math.random() * w * 1.2 - w * 0.1; q.y = -10 - Math.random() * 30; q.o = 0.2 + Math.random() * 0.4; }
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
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : Math.random() * h, r: 0.5 + Math.random() * 1.5, s: 0.3 + Math.random() * 0.8, o: 0.3 + Math.random() * 0.6, ph: Math.random() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--bleed')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--bleed')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += Math.sin(ts * 0.001 + q.ph) * q.s * sig * 0.4; q.y += Math.cos(ts * 0.0012 + q.ph) * q.s * sig * 0.4; q.r += sig * 0.02;
        if (q.x < -20 || q.x > w + 20 || q.y < -20 || q.y > h + 20 || q.r > 8) { q.x = Math.random() * w; q.y = Math.random() * h; q.r = 0.5 + Math.random() * 1.5; q.o = 0.3 + Math.random() * 0.6; }
        c.beginPath(); c.arc(q.x, q.y, q.r, 0, 6.28);
        c.fillStyle = 'rgba(40, 50, 70, ' + (q.o * sig).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Thread Effect (weaving cross-lines) ──
  // Driven by --weft (Loom theme).
  registerEffect('thread', function (_cvs, _context, _params, env) {
    var BASE = 20, MAX = 80; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc;
    function create() { return { x: Math.random() * w, y: Math.random() * h, l: 20 + Math.random() * 60, hor: Math.random() > 0.5, s: 0.2 + Math.random() * 0.5, o: 0.1 + Math.random() * 0.3, ph: Math.random() * 6.28, hue: 50 + Math.random() * 40 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--weft')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--weft')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create());
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += q.hor ? q.s * (0.2 + sig * 0.6) : Math.sin(ts * 0.001 + q.ph) * 0.2;
        q.y += q.hor ? Math.sin(ts * 0.001 + q.ph) * 0.2 : q.s * (0.2 + sig * 0.6);
        if ((q.hor && q.x > w + q.l) || (!q.hor && q.y > h + q.l)) { q.x = Math.random() * w * 0.3; q.y = Math.random() * h * 0.3; q.hor = !q.hor; q.l = 20 + Math.random() * 60; }
        c.beginPath();
        if (q.hor) { c.moveTo(q.x, q.y); c.lineTo(q.x + q.l, q.y); } else { c.moveTo(q.x, q.y); c.lineTo(q.x, q.y + q.l); }
        c.strokeStyle = 'hsla(' + Math.round(q.hue) + ', 50%, ' + Math.round(50 + sig * 20) + '%, ' + (q.o * (0.2 + sig * 0.5)).toFixed(2) + ')';
        c.lineWidth = 0.8 + sig; c.stroke();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Matrix Effect (falling data dots) ──
  // Driven by --activity (Mainframe theme).
  registerEffect('matrix', function (_cvs, _context, _params, env) {
    var BASE = 40, MAX = 200; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, interp;
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : -10 - Math.random() * h * 0.3, r: 1 + Math.random() * 2.5, s: 0.3 + Math.random() * 0.8, o: 0.2 + Math.random() * 0.6, trail: 3 + Math.random() * 10 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--activity')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--activity')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 1);
        if (q.y > h + 10) { q.x = Math.random() * w; q.y = -10 - Math.random() * 30; q.s = 0.3 + Math.random() * 0.8; q.r = 1 + Math.random() * 2.5; }
        interp = 1 - (q.y / h);
        c.beginPath(); c.arc(q.x, q.y, q.r, 0, 6.28);
        c.fillStyle = 'rgba(80, 220, 100, ' + (q.o * interp * (0.2 + sig * 0.8)).toFixed(2) + ')';
        c.fill();
        if (interp > 0.3 && sig > 0.2) {
          c.beginPath(); c.arc(q.x, q.y + q.r * 2, q.r * 0.4, 0, 6.28);
          c.fillStyle = 'rgba(80, 220, 100, ' + (q.o * interp * sig * 0.3).toFixed(2) + ')';
          c.fill();
        }
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Leaf Effect (falling organic motes) ──
  // Driven by --disturbance (Old Growth theme).
  registerEffect('leaf', function (_cvs, _context, _params, env) {
    var BASE = 20, MAX = 100; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, cx, cy, dx, dy, glow;
    function create(x, y) { return { x: x != null ? x : Math.random() * w * 1.2 - w * 0.1, y: y != null ? y : -10 - Math.random() * h * 0.3, r: 1.5 + Math.random() * 3.5, s: 0.06 + Math.random() * 0.15, o: 0.2 + Math.random() * 0.4, ph: Math.random() * 6.28, wa: 0.3 + Math.random() * 1 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--disturbance')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--disturbance')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 0.7); q.x += Math.sin(ts * 0.0008 + q.ph) * q.wa * (0.1 + sig * 0.3);
        if (q.y > h + 20) { q.x = Math.random() * w * 1.2 - w * 0.1; q.y = -10 - Math.random() * 30; q.o = 0.2 + Math.random() * 0.4; }
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(120, 160, 90, ' + (q.o * (0.1 + sig * 0.5)).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Prism Effect (spectrum light motes) ──
  // Driven by --prism + --hue (Prism theme).
  registerEffect('prism', function (_cvs, _context, _params, env) {
    var BASE = 40, MAX = 150; var p = [], w = 0, h = 0, sig = 0, hueShift = 0, ip = env.paused;
    var i, q, tc, glow;
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : Math.random() * h, r: 0.8 + Math.random() * 2.5, s: 0.1 + Math.random() * 0.3, o: 0.15 + Math.random() * 0.4, ph: Math.random() * 6.28, hueOff: Math.random() * 360 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--prism')) || 0; hueShift = parseFloat(document.documentElement.style.getPropertyValue('--hue')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--prism')) || 0;
      hueShift = parseFloat(document.documentElement.style.getPropertyValue('--hue')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.x += Math.sin(ts * 0.001 + q.ph) * 0.3; q.y += Math.cos(ts * 0.0008 + q.ph) * 0.2;
        if (q.x < -10 || q.x > w + 10 || q.y < -10 || q.y > h + 10) { q.x = Math.random() * w; q.y = Math.random() * h; }
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
    function create() { return { x: Math.random() * w, y: Math.random() * h, r: 2 + Math.random() * 4, o: 0.2 + Math.random() * 0.5, ph: Math.random() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--beat')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--beat')) || 0;
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
    function create() { var a = Math.random() * 6.28; return { a: a, r: 10 + Math.random() * Math.min(w, h) * 0.4, s: 0.1 + Math.random() * 0.3, o: 0.2 + Math.random() * 0.5, size: 1 + Math.random() * 3, ph: Math.random() * 6.28 }; }
    function init(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--throughput')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height; cx = w / 2; cy = h / 2;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--throughput')) || 0;
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
    function create(x, y) { var a = -1.5 - Math.random() * 0.8; return { x: x != null ? x : Math.random() * w, y: y != null ? y : h + 10, r: 1 + Math.random() * 3, s: 0.5 + Math.random() * 1.5, o: 0.3 + Math.random() * 0.6, a: a, spread: (Math.random() - 0.5) * 0.8 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--flare')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--flare')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * (0.3 + sig * 1.2) * q.a; q.x += q.spread * (0.2 + sig * 0.8);
        if (q.y < -30) { q.x = Math.random() * w; q.y = h + 10 + Math.random() * 20; q.s = 0.5 + Math.random() * 1.5; q.o = 0.3 + Math.random() * 0.6; q.spread = (Math.random() - 0.5) * 0.8; }
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
    function create(x, y) { return { x: x != null ? x : Math.random() * w * 1.2 - w * 0.1, y: y != null ? y : -10 - Math.random() * h * 0.3, s: 4 + Math.random() * 10, hs: 3 + Math.random() * 6, sp: 0.15 + Math.random() * 0.4, o: 0.2 + Math.random() * 0.5, ph: Math.random() * 6.28, hue: Math.random() * 360, rot: Math.random() * 6.28 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--lumin')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--lumin')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.sp * (0.2 + sig * 0.6); q.x += Math.sin(ts * 0.001 + q.ph) * 0.3; q.rot += 0.01;
        if (q.y > h + 20) { q.x = Math.random() * w * 1.2 - w * 0.1; q.y = -10 - Math.random() * 30; q.s = 4 + Math.random() * 10; q.o = 0.2 + Math.random() * 0.5; }
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
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : h * 0.5 + Math.random() * h * 0.5, s: 2 + Math.random() * 5, o: 0.2 + Math.random() * 0.5, ph: Math.random() * 6.28, jx: (Math.random() - 0.5) * 2, jy: (Math.random() - 0.5) * 2 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--tremor')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--tremor')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; shake = Math.sin(ts * 0.005 + q.ph) * sig * 4;
        q.x += q.jx * sig * 0.2 + shake * 0.1; q.y += q.jy * sig * 0.2 + Math.cos(ts * 0.004 + q.ph) * sig * 2;
        if (q.x < -10 || q.x > w + 10) { q.x = Math.random() * w; }
        if (q.y > h + 10) { q.y = h * 0.5 + Math.random() * h * 0.4; }
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
    function create(x, y) { return { x: x != null ? x : Math.random() * w, y: y != null ? y : h - 20 + Math.random() * 20, r: 0.5 + Math.random() * 2, s: 0.3 + Math.random() * 1, o: 0.2 + Math.random() * 0.5, a: -1.8 + Math.random() * -0.5, spread: (Math.random() - 0.5) * 0.6 }; }
    function init(width, height) { w = width; h = height; p = []; for (i = 0; i < BASE; i++) p.push(create(null, null)); }
    function resize(width, height) { w = width; h = height; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--surge')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--surge')) || 0;
      tc = Math.round(BASE + sig * (MAX - BASE));
      while (p.length < tc) p.push(create(null, null));
      while (p.length > tc) p.pop();
      for (i = 0; i < p.length; i++) {
        q = p[i]; q.y += q.s * q.a * (0.3 + sig * 1); q.x += q.spread * sig + Math.sin(ts * 0.002 + q.ph) * 0.2;
        if (q.y < -20) { q.x = Math.random() * w; q.y = h - 20 + Math.random() * 20; q.s = 0.3 + Math.random() * 1; q.spread = (Math.random() - 0.5) * 0.6; }
        c.beginPath(); c.arc(q.x, q.y, q.r * (0.3 + sig * 0.7), 0, 6.28);
        c.fillStyle = 'rgba(180, 220, 240, ' + (q.o * sig).toFixed(2) + ')';
        c.fill();
      }
    }
    return { start: start, stop: stop, update: update, resize: resize };
  });

  // ── Spin Effect (rotating vinyl particles) ──
  // Driven by --wobble (Vinyl theme).
  registerEffect('spin', function (_cvs, _context, _params, env) {
    var BASE = 30, MAX = 100; var p = [], w = 0, h = 0, sig = 0, ip = env.paused;
    var i, q, tc, cx, cy, r, th;
    function create() { var a = Math.random() * 6.28; return { a: a, r: 10 + Math.random() * 140, s: 0.5 + Math.random() * 1.5, o: 0.15 + Math.random() * 0.4, size: 1 + Math.random() * 2.5 }; }
    function init(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; p = []; for (i = 0; i < BASE; i++) p.push(create()); }
    function resize(width, height) { w = width; h = height; cx = w / 2; cy = h / 2; }
    function start(width, height) { w = width; h = height; init(w, h); ip = false; sig = parseFloat(document.documentElement.style.getPropertyValue('--wobble')) || 0; }
    function stop() { p = []; }
    function update(ts, width, height, c) {
      if (ip) return; w = width; h = height; cx = w / 2; cy = h / 2;
      sig = parseFloat(document.documentElement.style.getPropertyValue('--wobble')) || 0;
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
