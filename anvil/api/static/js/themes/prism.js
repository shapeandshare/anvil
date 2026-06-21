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

  function prismMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var hue = 0;
    var flashTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function flash() {
      if (paused) return;
      root.setAttribute('data-prism-flash', 'true');
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(function () {
        root.removeAttribute('data-prism-flash');
      }, 900);
    }

    setVar('--prism', '0.3');
    setVar('--hue', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--prism', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('milestone', function () {
      hue = (hue + 45) % 360;
      setVar('--hue', String(hue));
      flash();
    }));
    unsubs.push(bus.on('complete', function () {
      hue = (hue + 60) % 360;
      setVar('--hue', String(hue));
      flash();
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--prism', '1');
      setVar('--hue', '0');
      root.setAttribute('data-prism-state', 'monochrome');
    }));

    return function teardown() {
      if (flashTimer) clearTimeout(flashTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-prism-flash');
      root.removeAttribute('data-prism-state');
      root.style.removeProperty('--prism');
      root.style.removeProperty('--hue');
    };
  }

  window.ThemeRegistry.register({
    id: 'prism',
    displayName: 'Prism',
    previewHint: 'Loss as spectrum intensity, milestones shift the hue',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/prism.css',
    mapping: prismMapping,
    particleConfig: { type: 'prism' },
  });
})();