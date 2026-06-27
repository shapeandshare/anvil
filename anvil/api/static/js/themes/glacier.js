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

  function glacierMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    // --freeze drives snow intensity (loss-based convergence).
    // __glacierStorm drives blizzard/hail — JS global, no CSP issues.
    setVar('--freeze', '0.3');
    window.__glacierStorm = false;

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      window.__glacierStorm = true;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--freeze', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--freeze', '0');
      window.__glacierStorm = false;
    }));
    unsubs.push(bus.on('complete', function () {
      window.__glacierStorm = false;
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--freeze');
      window.__glacierStorm = false;
    };
  }

  window.ThemeRegistry.register({
    id: 'glacier',
    displayName: 'Glacier',
    previewHint: 'Convergence crystallizes the ice, freeze brings the snow',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/glacier.css',
    mapping: glacierMapping,
    particleConfig: { type: 'glacier', params: {} },
  });
})();