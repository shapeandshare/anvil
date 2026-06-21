// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function solarFlareMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--flare', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.grad_norm != null && isFinite(m.grad_norm)) {
        setVar('--flare', clamp01(m.grad_norm).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--flare', '1');
      root.setAttribute('data-solar-state', 'coronal');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-solar-state');
      root.style.removeProperty('--flare');
    };
  }

  window.ThemeRegistry.register({
    id: 'solarflare',
    displayName: 'Solar Flare',
    previewHint: 'Gradient spikes as coronal eruptions',
    modes: ['single'],
    cssLayer: '/static/css/themes/solarflare.css',
    mapping: solarFlareMapping,
    particleConfig: { type: 'flare' },
  });
})();
