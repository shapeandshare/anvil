// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  // ── Inject starfield element ──
  // Create a real DOM element (not a style rule) so it's not blocked by CSP.
  (function injectStars() {
    if (document.documentElement.getAttribute('data-skin') !== 'aurora') return;
    var el = document.createElement('div');
    el.id = 'aurora-starfield';
    el.style.cssText =
      'position:fixed;top:0;left:0;width:100%;height:100%;' +
      'z-index:0;pointer-events:none;' +
      'background:' +
        'radial-gradient(2.5px at 5% 12%,rgba(255,255,255,0.85),transparent),' +
        'radial-gradient(1.5px at 11% 38%,rgba(210,225,255,0.6),transparent),' +
        'radial-gradient(2px at 17% 82%,rgba(255,255,255,0.7),transparent),' +
        'radial-gradient(1px at 22% 15%,rgba(255,255,255,0.4),transparent),' +
        'radial-gradient(2px at 26% 55%,rgba(200,220,255,0.75),transparent),' +
        'radial-gradient(1.5px at 32% 91%,rgba(255,255,255,0.55),transparent),' +
        'radial-gradient(1px at 37% 28%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2.5px at 41% 63%,rgba(220,230,255,0.8),transparent),' +
        'radial-gradient(1px at 46% 8%,rgba(255,255,255,0.4),transparent),' +
        'radial-gradient(2px at 52% 42%,rgba(255,255,255,0.65),transparent),' +
        'radial-gradient(1.5px at 57% 76%,rgba(210,225,255,0.5),transparent),' +
        'radial-gradient(1px at 62% 19%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2px at 68% 50%,rgba(255,255,255,0.7),transparent),' +
        'radial-gradient(1px at 73% 88%,rgba(255,255,255,0.45),transparent),' +
        'radial-gradient(2.5px at 78% 34%,rgba(220,230,255,0.85),transparent),' +
        'radial-gradient(1.5px at 83% 70%,rgba(255,255,255,0.5),transparent),' +
        'radial-gradient(1px at 88% 10%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2px at 93% 46%,rgba(255,255,255,0.65),transparent),' +
        'radial-gradient(1.5px at 98% 95%,rgba(210,225,255,0.55),transparent),' +
        'radial-gradient(1px at 3% 72%,rgba(255,255,255,0.3),transparent),' +
        'radial-gradient(2px at 14% 49%,rgba(220,230,255,0.7),transparent),' +
        'radial-gradient(1px at 21% 96%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2.5px at 30% 8%,rgba(255,255,255,0.8),transparent),' +
        'radial-gradient(1.5px at 38% 44%,rgba(210,225,255,0.55),transparent),' +
        'radial-gradient(2px at 45% 80%,rgba(255,255,255,0.65),transparent),' +
        'radial-gradient(1px at 53% 25%,rgba(255,255,255,0.4),transparent),' +
        'radial-gradient(1.5px at 59% 60%,rgba(255,255,255,0.5),transparent),' +
        'radial-gradient(2px at 65% 14%,rgba(220,230,255,0.75),transparent),' +
        'radial-gradient(1px at 71% 97%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2px at 76% 40%,rgba(255,255,255,0.6),transparent),' +
        'radial-gradient(1.5px at 82% 85%,rgba(210,225,255,0.5),transparent),' +
        'radial-gradient(2.5px at 89% 22%,rgba(255,255,255,0.85),transparent),' +
        'radial-gradient(1px at 95% 58%,rgba(255,255,255,0.4),transparent),' +
        'radial-gradient(2px at 8% 5%,rgba(220,230,255,0.7),transparent),' +
        'radial-gradient(1.5px at 16% 67%,rgba(255,255,255,0.55),transparent),' +
        'radial-gradient(2px at 24% 33%,rgba(255,255,255,0.65),transparent),' +
        'radial-gradient(1px at 34% 78%,rgba(255,255,255,0.3),transparent),' +
        'radial-gradient(2.5px at 42% 20%,rgba(220,230,255,0.8),transparent),' +
        'radial-gradient(1.5px at 49% 54%,rgba(255,255,255,0.5),transparent),' +
        'radial-gradient(2px at 55% 89%,rgba(255,255,255,0.7),transparent),' +
        'radial-gradient(1px at 63% 36%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2px at 70% 74%,rgba(220,230,255,0.6),transparent),' +
        'radial-gradient(1.5px at 79% 7%,rgba(255,255,255,0.55),transparent),' +
        'radial-gradient(2.5px at 86% 52%,rgba(255,255,255,0.85),transparent),' +
        'radial-gradient(1px at 91% 77%,rgba(255,255,255,0.4),transparent),' +
        'radial-gradient(2px at 96% 16%,rgba(210,225,255,0.65),transparent),' +
        'radial-gradient(1.5px at 7% 29%,rgba(255,255,255,0.5),transparent),' +
        'radial-gradient(2.5px at 35% 99%,rgba(220,230,255,0.75),transparent),' +
        'radial-gradient(1px at 60% 3%,rgba(255,255,255,0.35),transparent),' +
        'radial-gradient(2px at 74% 65%,rgba(255,255,255,0.7),transparent)';
    document.body.appendChild(el);
  })();

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function auroraMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--calm', '1');
    setVar('--flow', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--calm', clamp01(1 - m.loss / L0).toFixed(3));
      }
      if (m.tokens_per_sec != null) {
        setVar('--flow', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () { setVar('--calm', '0'); }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--calm');
      root.style.removeProperty('--flow');
      var s = document.getElementById('aurora-starfield');
      if (s && s.parentNode) s.parentNode.removeChild(s);
    };
  }

  window.ThemeRegistry.register({
    id: 'aurora',
    displayName: 'Aurora',
    previewHint: 'Loss as northern lights',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/aurora.css',
    mapping: auroraMapping,
    particleConfig: { type: 'aurora' },
  });
})();
