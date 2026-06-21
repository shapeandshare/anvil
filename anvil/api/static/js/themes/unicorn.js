(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;
  var MAX_UNICORNS = 12;
  var MAX_RAINBOWS = 6;
  var UNICORN_LIFETIME = 20000;
  var RAINBOW_LIFETIME = 6500;
  var SPAWN_BASE_MS = 2800;
  var RAINBOW_BASE_MS = 3500;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  function randInt(min, max) {
    return Math.floor(rand(min, max + 1));
  }

  /* ── SVG Unicorn Factory ── */
  var HUE_COLORS = ['#ff1744','#ff9100','#ffea00','#00e676','#00b0ff','#651fff','#ff00ff'];

  function createUnicornSVG(size, hueOff) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 80 100');
    svg.setAttribute('width', String(size));
    svg.setAttribute('height', String(size * 1.25));
    svg.style.overflow = 'visible';
    svg.setAttribute('aria-hidden', 'true');

    var defs = document.createElementNS(ns, 'defs');
    // Glow filter
    var filter = document.createElementNS(ns, 'filter');
    filter.setAttribute('id', 'uglow-' + String(Date.now()) + '-' + randInt(0, 9999));
    var blur = document.createElementNS(ns, 'feGaussianBlur');
    blur.setAttribute('stdDeviation', '1.5');
    blur.setAttribute('result', 'blur');
    filter.appendChild(blur);
    var merge = document.createElementNS(ns, 'feMerge');
    var mn1 = document.createElementNS(ns, 'feMergeNode');
    mn1.setAttribute('in', 'blur');
    var mn2 = document.createElementNS(ns, 'feMergeNode');
    mn2.setAttribute('in', 'SourceGraphic');
    merge.appendChild(mn1);
    merge.appendChild(mn2);
    filter.appendChild(merge);
    defs.appendChild(filter);
    svg.appendChild(defs);

    var filterId = filter.getAttribute('id');

    // Body colors: shift by hueOff
    var bodyFill = '#f5eeff';
    var bodyStroke = '#c8b0e8';
    var legFill = '#ede2f7';
    var hornBase = '#ffd700';
    var maneColors = HUE_COLORS.slice();
    if (hueOff) {
      maneColors = maneColors.map(function (c) {
        return hslShift(c, hueOff);
      });
    }

    function el(name, attrs) {
      var e = document.createElementNS(ns, name);
      if (attrs) {
        Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
      }
      return e;
    }

    // Helper: shift a hex color by hue offset (simplified — just cycle the color list)
    function hslShift(hex, off) {
      var i = HUE_COLORS.indexOf(hex);
      if (i === -1) return hex;
      return HUE_COLORS[(i + Math.round(off / 60)) % HUE_COLORS.length];
    }

    var bodyFilter = el('g', { filter: 'url(#' + filterId + ')' });

    // Tail (behind body, right side)
    var tailColors = [maneColors[3], maneColors[4], maneColors[5], maneColors[6], maneColors[0], maneColors[1]];
    tailColors.forEach(function (c, i) {
      var offset = i * 3;
      var tail = el('path', {
        d: 'M 58 52 C 68 ' + (56 + offset * 0.5) + ', 72 ' + (64 + offset) + ', 60 ' + (78 + offset * 0.3),
        stroke: c, 'stroke-width': '3', fill: 'none',
        'stroke-linecap': 'round', opacity: String(0.85 - i * 0.05)
      });
      bodyFilter.appendChild(tail);
    });

    // Body
    bodyFilter.appendChild(el('ellipse', { cx: '40', cy: '58', rx: '20', ry: '15', fill: bodyFill, stroke: bodyStroke, 'stroke-width': '1.2' }));

    // Neck
    bodyFilter.appendChild(el('rect', { x: '30', y: '32', width: '20', height: '20', rx: '8', fill: bodyFill, stroke: bodyStroke, 'stroke-width': '1' }));

    // Head
    bodyFilter.appendChild(el('circle', { cx: '40', cy: '26', r: '14', fill: bodyFill, stroke: bodyStroke, 'stroke-width': '1.2' }));

    svg.appendChild(bodyFilter);

    // Legs (behind body tail area, but in front of tail)
    var legPositions = [
      { x: 22, y: 70 },  // back left
      { x: 30, y: 70 },  // front left
      { x: 42, y: 70 },  // front right (visible)
      { x: 50, y: 70 }   // back right
    ];
    legPositions.forEach(function (lp) {
      svg.appendChild(el('rect', {
        x: String(lp.x), y: String(lp.y),
        width: '8', height: '18', rx: '4',
        fill: legFill, stroke: bodyStroke, 'stroke-width': '0.8'
      }));
      // Tiny hooves
      svg.appendChild(el('rect', {
        x: String(lp.x + 1), y: String(lp.y + 15),
        width: '6', height: '4', rx: '2',
        fill: '#c8b0e8'
      }));
    });

    // Mane (left side, in front of body)
    var maneNodes = [];
    maneColors.forEach(function (c, i) {
      var offset = i * 2;
      var p = el('path', {
        d: 'M 27 ' + (20 + offset * 0.5) + ' C 16 ' + (24 + offset) + ', 14 ' + (32 + offset * 0.8) + ', 22 ' + (42 + offset * 0.3),
        stroke: c, 'stroke-width': '3.5', fill: 'none',
        'stroke-linecap': 'round', opacity: '0.9'
      });
      svg.appendChild(p);
      maneNodes.push(p);
    });

    // Horn
    var horn = el('polygon', { points: '40,12 35,-4 45,-4', fill: hornBase, stroke: '#cc9900', 'stroke-width': '0.8' });
    svg.appendChild(horn);
    // Horn spiral stripes
    var stripeY = [-2, 1, 4, 7];
    stripeY.forEach(function (sy) {
      svg.appendChild(el('line', {
        x1: String(37), y1: String(sy), x2: String(43), y2: String(sy),
        stroke: '#ff8c00', 'stroke-width': '1.2'
      }));
    });

    // Ears
    svg.appendChild(el('polygon', { points: '30,16 26,6 34,14', fill: bodyFill, stroke: bodyStroke, 'stroke-width': '0.8' }));
    svg.appendChild(el('polygon', { points: '50,16 54,6 46,14', fill: bodyFill, stroke: bodyStroke, 'stroke-width': '0.8' }));
    // Inner ear pink
    svg.appendChild(el('polygon', { points: '30,15 27,8 33,14', fill: '#ffc0d0', 'stroke-width': '0' }));
    svg.appendChild(el('polygon', { points: '50,15 53,8 47,14', fill: '#ffc0d0', 'stroke-width': '0' }));

    // Cheek blush
    svg.appendChild(el('ellipse', { cx: '28', cy: '30', rx: '4', ry: '2.5', fill: '#ffb0c8', opacity: '0.4' }));
    svg.appendChild(el('ellipse', { cx: '52', cy: '30', rx: '4', ry: '2.5', fill: '#ffb0c8', opacity: '0.4' }));

    // ── GOOGLY EYES ──
    // Eye positions
    var eyeLeft = { cx: 33, cy: 24 };
    var eyeRight = { cx: 47, cy: 24 };

    function makeGooglyEye(cx, cy, pupilOffX, pupilOffY, delay) {
      var g = el('g', { class: 'unicorn-eye' });
      // Sclera (white)
      g.appendChild(el('circle', { cx: String(cx), cy: String(cy), r: '5.5', fill: '#ffffff', stroke: '#555', 'stroke-width': '0.8' }));
      // Pupil
      var p = el('circle', { cx: String(cx + pupilOffX), cy: String(cy + pupilOffY), r: '2.8', fill: '#1a1a1a' });
      p.style.animationDelay = String(delay) + 's';
      p.setAttribute('class', 'unicorn-pupil');
      g.appendChild(p);
      return g;
    }

    // Randomize googly offsets per eye — mismatched for silliness
    var offLx = rand(-2.2, 2.2);
    var offLy = rand(-2.2, 2.2);
    var offRx = rand(-2.2, 2.2);
    var offRy = rand(-2.2, 2.2);
    // Don't let pupil sit exactly centered
    if (Math.abs(offLx) < 0.3 && Math.abs(offLy) < 0.3) { offLx = 1.5; offLy = 1; }
    if (Math.abs(offRx) < 0.3 && Math.abs(offRy) < 0.3) { offRx = -1.5; offRy = -1; }

    svg.appendChild(makeGooglyEye(eyeLeft.cx, eyeLeft.cy, offLx, offLy, rand(0, 0.5)));
    svg.appendChild(makeGooglyEye(eyeRight.cx, eyeRight.cy, offRx, offRy, rand(0.3, 0.8)));

    // Smile
    svg.appendChild(el('path', {
      d: 'M 35 31 Q 40 34 45 31',
      stroke: '#a080b0', 'stroke-width': '1', fill: 'none', 'stroke-linecap': 'round'
    }));

    return svg;
  }

  /* ── SVG Rainbow Factory ── */
  function createRainbowSVG() {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 240 100');
    svg.setAttribute('width', '240');
    svg.setAttribute('height', '100');
    svg.style.overflow = 'visible';
    svg.setAttribute('aria-hidden', 'true');

    var arcColors = ['#ff1744','#ff9100','#ffea00','#00e676','#00b0ff','#651fff'];
    arcColors.forEach(function (c, i) {
      var r1 = 70 + i * 6;
      var r2 = 70 + (i + 1) * 6;
      var path = document.createElementNS(ns, 'path');
      // Draw an arc band: outer arc then reverse inner arc
      var d = 'M 0 80 A ' + r2 + ' ' + r2 + ' 0 0 1 240 80 L 240 80 A ' + r1 + ' ' + r1 + ' 0 0 0 0 80 Z';
      path.setAttribute('d', d);
      path.setAttribute('fill', c);
      path.setAttribute('opacity', String(0.7 - i * 0.05));
      svg.appendChild(path);
    });

    return svg;
  }

  /* ── Mapping Function ── */
  function unicornMapping(bus, effectLevel) {
    var root = document.documentElement;
    var legible = !!(effectLevel && effectLevel.legible);
    var reducedMotion = !!(effectLevel && (effectLevel.level === 'muted' || effectLevel.reducedMotion));
    var paused = !!(effectLevel && effectLevel.level === 'paused');
    var diverged = false;

    var unsubs = [];
    var overlay = null;
    var unicornNodes = [];   // { el, x, y, dx, dy, phase, wobbleFreq, wobbleAmp, born, removed }
    var rainbowNodes = [];   // { el, born, removed }
    var rAFid = null;
    var spawnTimer = null;
    var rainbowTimer = null;
    var burstTimers = [];
    var hue = 0;
    var burstTimer = null;
    var magic = 0.3;
    var sparkle = 0;
    var ii;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    // Set initial defaults
    setVar('--magic', '0.3');
    setVar('--twinkle', '0');
    setVar('--hue', '0');

    /* ── Overlay Management ── */
    function ensureOverlay() {
      if (overlay) return;
      overlay = document.createElement('div');
      overlay.className = 'unicorn-overlay';
      overlay.setAttribute('aria-hidden', 'true');
      document.body.appendChild(overlay);
    }

    function removeOverlay() {
      if (overlay && overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
      overlay = null;
    }

    /* ── Spawn Methods ── */
    function spawnUnicorn(burstMode) {
      if (diverged || !overlay) return;
      var count = overlay.querySelectorAll('.unicorn-floater').length;
      var max = burstMode ? MAX_UNICORNS + 3 : MAX_UNICORNS;
      if (count >= max) return;

      var vw = window.innerWidth;
      var vh = window.innerHeight;
      var size = rand(48, 96);
      var hueOff = rand(0, 300);

      var svgEl = createUnicornSVG(size, hueOff);

      var wrapper = document.createElement('div');
      wrapper.className = 'unicorn-floater';
      wrapper.setAttribute('aria-hidden', 'true');
      wrapper.style.width = String(size) + 'px';
      wrapper.style.height = String(size * 1.25) + 'px';

      // Random vertical lane: 10% to 80% of viewport
      var y = rand(vh * 0.08, vh * 0.78);
      // Start somewhere within viewport or just off right edge
      var x = rand(-size * 0.5, vw - size * 0.5);

      wrapper.style.left = '0px';
      wrapper.style.top = '0px';
      // Seed transform now so the sprite never flashes at (0,0) pre-first-frame.
      wrapper.style.transform = 'translate3d(' + x.toFixed(1) + 'px, ' + y.toFixed(1) + 'px, 0)';

      wrapper.appendChild(svgEl);
      overlay.appendChild(wrapper);

      var dx = burstMode ? rand(-0.18, -0.06) : rand(-0.10, -0.02);
      var dy = burstMode ? rand(-0.08, -0.02) : rand(-0.05, 0.02);

      unicornNodes.push({
        el: wrapper,
        x: x,
        y: y,
        dx: dx,
        dy: dy,
        phase: rand(0, Math.PI * 2),
        wobbleFreq: rand(0.0015, 0.004),
        wobbleAmp: rand(2, 6),
        born: Date.now(),
        removed: false
      });
    }

    function spawnRainbow(burstMode) {
      if (diverged || !overlay || reducedMotion) return;
      var count = overlay.querySelectorAll('.unicorn-rainbow').length;
      var max = burstMode ? MAX_RAINBOWS + 2 : MAX_RAINBOWS;
      if (count >= max) return;

      var vh = window.innerHeight;
      var svgEl = createRainbowSVG();

      var wrapper = document.createElement('div');
      wrapper.className = 'unicorn-rainbow';
      wrapper.setAttribute('aria-hidden', 'true');

      // Random vertical position
      var top = rand(vh * 0.05, vh * 0.7);
      wrapper.style.top = String(top) + 'px';
      wrapper.style.left = '0px';

      // Random duration for flyby
      var flyDur = burstMode ? rand(2.5, 4) : rand(3.5, 6);
      wrapper.style.animationDuration = String(flyDur) + 's';

      wrapper.appendChild(svgEl);
      overlay.appendChild(wrapper);

      rainbowNodes.push({
        el: wrapper,
        born: Date.now(),
        removed: false,
        timeout: null
      });
    }

    /* ── Burst ── */
    function burst(count, rainbowCount) {
      if (diverged || legible || paused || reducedMotion) return;
      ensureOverlay();
      root.setAttribute('data-unicorn-burst', 'true');
      if (burstTimer) clearTimeout(burstTimer);
      burstTimer = setTimeout(function () {
        root.removeAttribute('data-unicorn-burst');
      }, 1100);

      var i;
      for (i = 0; i < count; i++) {
        spawnUnicorn(true);
      }
      for (i = 0; i < rainbowCount; i++) {
        spawnRainbow(true);
      }
    }

    /* ── Animation Loop ── */
    var lastTime = 0;

    function animate(timestamp) {
      if (paused || diverged || legible) {
        rAFid = null;
        return;
      }
      rAFid = requestAnimationFrame(animate);

      if (!lastTime) { lastTime = timestamp; return; }
      var dt = Math.min(timestamp - lastTime, 50); // cap dt to ~50ms
      lastTime = timestamp;

      var now = Date.now();

      var aliveUnicorns = [];
      unicornNodes.forEach(function (u) {
        if (u.removed) return;
        if (now - u.born > UNICORN_LIFETIME) {
          if (u.el.parentNode) u.el.parentNode.removeChild(u.el);
          u.removed = true;
          return;
        }
        u.x += u.dx * dt;
        u.y += u.dy * dt + Math.sin(u.phase + now * u.wobbleFreq * 0.001) * u.wobbleAmp * 0.1;
        u.el.style.transform = 'translate3d(' + u.x.toFixed(1) + 'px, ' + u.y.toFixed(1) + 'px, 0)';
        aliveUnicorns.push(u);
      });
      unicornNodes = aliveUnicorns;

      var aliveRainbows = [];
      rainbowNodes.forEach(function (r) {
        if (r.removed) return;
        if (now - r.born > RAINBOW_LIFETIME) {
          if (r.el.parentNode) r.el.parentNode.removeChild(r.el);
          r.removed = true;
          return;
        }
        aliveRainbows.push(r);
      });
      rainbowNodes = aliveRainbows;
    }

    function startAnimation() {
      if (rAFid) return;
      lastTime = 0;
      rAFid = requestAnimationFrame(animate);
    }

    function stopAnimation() {
      if (rAFid) {
        cancelAnimationFrame(rAFid);
        rAFid = null;
      }
    }

    /* ── Spawn Cadence ── */
    function startSpawnTimers() {
      if (spawnTimer) clearInterval(spawnTimer);
      if (rainbowTimer) clearInterval(rainbowTimer);

      spawnTimer = setInterval(function () {
        if (diverged || legible || paused) return;
        // Spawn rate scales with magic: at magic=1, interval effectively ~1.4s via double spawn
        var count = 1;
        if (magic > 0.7) count = 2;
        else if (magic > 0.4 && Math.random() < 0.3) count = 2;
        ensureOverlay();
        var si;
        for (si = 0; si < count; si++) {
          spawnUnicorn(false);
        }
      }, SPAWN_BASE_MS);

      rainbowTimer = setInterval(function () {
        if (diverged || legible || paused || reducedMotion) return;
        if (magic > 0.25 && Math.random() < magic) {
          ensureOverlay();
          spawnRainbow(false);
        }
      }, RAINBOW_BASE_MS);
    }

    function stopSpawnTimers() {
      if (spawnTimer) { clearInterval(spawnTimer); spawnTimer = null; }
      if (rainbowTimer) { clearInterval(rainbowTimer); rainbowTimer = null; }
    }

    /* ── Cleanup helpers used before overlay removal ── */
    function removeAllSpawned() {
      unicornNodes.forEach(function (u) {
        if (!u.removed && u.el.parentNode) u.el.parentNode.removeChild(u.el);
        u.removed = true;
      });
      unicornNodes = [];
      rainbowNodes.forEach(function (r) {
        if (!r.removed && r.el.parentNode) r.el.parentNode.removeChild(r.el);
        r.removed = true;
      });
      rainbowNodes = [];
    }

    /* ── Initialize ── */
    if (!legible && !paused) {
      ensureOverlay();
      if (!reducedMotion) {
        // Spawn a few initial unicorns
        for (ii = 0; ii < 3; ii++) {
          spawnUnicorn(false);
        }
        startAnimation();
        startSpawnTimers();
      } else {
        // reduced/muted: spawn static unicorns (no animation)
        for (ii = 0; ii < 3; ii++) {
          spawnUnicorn(false);
        }
        // Position them statically
        unicornNodes.forEach(function (u) {
          u.el.style.transform = 'translate3d(' + u.x.toFixed(1) + 'px, ' + u.y.toFixed(1) + 'px, 0)';
          u.el.style.animation = 'none';
        });
      }
    }

    /* ── Signal Subscriptions ── */
    unsubs.push(bus.on('metrics', function (m) {
      if (!m) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        magic = clamp01(1 - m.loss / L0);
        setVar('--magic', magic.toFixed(3));
      }
      if (typeof m.tokens_per_sec === 'number' && isFinite(m.tokens_per_sec)) {
        sparkle = clamp01(m.tokens_per_sec / MAX_TPS);
        setVar('--twinkle', sparkle.toFixed(3));
      }
    }));

    unsubs.push(bus.on('milestone', function () {
      if (paused || legible) return;
      hue = (hue + 51) % 360;
      setVar('--hue', String(hue));
      burst(3, 2);
    }));

    unsubs.push(bus.on('complete', function () {
      if (paused || legible) return;
      hue = (hue + 102) % 360;
      setVar('--hue', String(hue));
      burst(5, 4);
    }));

    unsubs.push(bus.on('divergence', function () {
      diverged = true;
      setVar('--magic', '0');
      setVar('--twinkle', '0');
      root.setAttribute('data-unicorn-state', 'faded');
      stopSpawnTimers();
      stopAnimation();
    }));

    /* ── Teardown ── */
    return function teardown() {
      if (burstTimer) clearTimeout(burstTimer);
      burstTimers.forEach(function (t) { clearTimeout(t); });
      burstTimers = [];

      stopSpawnTimers();
      stopAnimation();
      removeAllSpawned();
      removeOverlay();

      unsubs.forEach(function (u) { u(); });
      unsubs = [];

      root.removeAttribute('data-unicorn-burst');
      root.removeAttribute('data-unicorn-state');
      root.style.removeProperty('--magic');
      root.style.removeProperty('--twinkle');
      root.style.removeProperty('--hue');
    };
  }

  /* ── Registration ── */
  window.ThemeRegistry.register({
    id: 'unicorn',
    displayName: 'Unicorn',
    previewHint: 'Training brings out the rainbow — loss as magic, throughput as sparkle',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/unicorn.css',
    mapping: unicornMapping,
    particleConfig: { type: 'css' },
  });
})();
