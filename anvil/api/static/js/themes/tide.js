// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function tideMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--level', '0.4');
    setVar('--surge', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--level', clamp01(1 - m.loss / L0).toFixed(3));
      }
      if (m.tokens_per_sec != null) {
        setVar('--surge', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-tide-state', 'riptide');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-tide-state');
      root.style.removeProperty('--level');
      root.style.removeProperty('--surge');
    };
  }

  window.ThemeRegistry.register({
    id: 'tide',
    displayName: 'Tide',
    previewHint: 'Loss as a rising shoreline',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/tide.css',
    mapping: tideMapping,
    particleConfig: { type: 'bubble' },
  });
})();
