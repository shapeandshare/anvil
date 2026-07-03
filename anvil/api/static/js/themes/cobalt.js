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

  function cobaltMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--elevation', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--elevation', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-cobalt-state', 'diverged');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-cobalt-state');
      root.style.removeProperty('--elevation');
    };
  }

  window.ThemeRegistry.register({
    id: 'cobalt',
    displayName: 'Cobalt',
    previewHint: 'Loss as a rising elevation line',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/cobalt.css',
    mapping: cobaltMapping,
  });
})();