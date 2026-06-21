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

  function gridMapping(bus, effectLevel) {
    var root = document.documentElement;
    var legible = !!(effectLevel && effectLevel.legible);
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--focus', '0.4');
    setVar('--ghost', legible ? '0' : '0.6');

    unsubs.push(bus.on('metrics', function (m) {
      var focus;
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        focus = clamp01(1 - m.loss / L0);
        setVar('--focus', focus.toFixed(3));
        setVar('--ghost', legible ? '0' : clamp01(1 - focus).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-grid-state', 'derez');
    }));
    unsubs.push(bus.on('complete', function () {
      setVar('--focus', '1');
      setVar('--ghost', '0');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-grid-state');
      root.style.removeProperty('--focus');
      root.style.removeProperty('--ghost');
    };
  }

  window.ThemeRegistry.register({
    id: 'grid',
    displayName: 'Grid',
    previewHint: 'Light-ribbons race the grid',
    modes: ['single'],
    cssLayer: '/static/css/themes/grid.css',
    mapping: gridMapping,
    particleConfig: { type: 'ribbon' },
  });
})();
