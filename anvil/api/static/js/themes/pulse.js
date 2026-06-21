// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function pulseMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--beat', '0.5');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.tokens_per_sec != null) {
        setVar('--beat', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-pulse-state', 'flatline');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-pulse-state');
      root.style.removeProperty('--beat');
    };
  }

  window.ThemeRegistry.register({
    id: 'pulse',
    displayName: 'Pulse',
    previewHint: 'Throughput as a heartbeat rhythm',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/pulse.css',
    mapping: pulseMapping,
    particleConfig: { type: 'pulse' },
  });
})();
