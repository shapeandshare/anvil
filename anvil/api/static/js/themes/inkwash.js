// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var L0 = 9.8;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function inkwashMapping(bus, effectLevel) {
    var root = document.documentElement;
    var legible = !!(effectLevel && effectLevel.legible);
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function applyClarity(clarity) {
      setVar('--clarity', clarity.toFixed(3));
      // Legibility-degrading bleed is suppressed at max-legibility (T4).
      setVar('--bleed', legible ? '0' : clamp01(1 - clarity).toFixed(3));
    }

    function applyRain(loss) {
      setVar('--rain', clamp01(loss / L0).toFixed(3));
    }

    applyClarity(0.4);
    // Constant gentle drizzle; loss drives it heavier
    applyRain(0.4);

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        applyClarity(clamp01(1 - m.loss / L0));
        applyRain(m.loss);
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      applyClarity(0);
      setVar('--rain', '1');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--clarity');
      root.style.removeProperty('--bleed');
      root.style.removeProperty('--rain');
    };
  }

  window.ThemeRegistry.register({
    id: 'inkwash',
    displayName: 'Inkwash',
    previewHint: 'Loss bleeds the brushstroke',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/inkwash.css',
    mapping: inkwashMapping,
    particleConfig: { type: 'ink' },
  });
})();
