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

  function stddev(values) {
    var n = values.length;
    if (n < 2) return 0;
    var mean = values.reduce(function (a, b) { return a + b; }, 0) / n;
    var variance = values.reduce(function (a, b) {
      return a + (b - mean) * (b - mean);
    }, 0) / n;
    return Math.sqrt(variance);
  }

  function tectonicMapping(bus, effectLevel) {
    var root = document.documentElement;
    var legible = !!(effectLevel && effectLevel.legible);
    var paused = effectLevel && effectLevel.level === 'paused';
    var recent = [];
    var unsubs = [];

    function setTremor(value) {
      root.style.setProperty('--tremor', clamp01(value).toFixed(3));
    }

    setTremor(0);

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      var instability = 0;
      if (m.grad_norm != null && isFinite(m.grad_norm)) {
        instability = clamp01(m.grad_norm);
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        recent.push(m.loss);
        if (recent.length > 8) recent.shift();
        instability = Math.max(instability, clamp01(stddev(recent) * 3));
      }
      if (legible) instability = 0;
      setTremor(instability);
    }));
    unsubs.push(bus.on('divergence', function () {
      setTremor(1);
      root.setAttribute('data-tectonic', 'rupture');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-tectonic');
      root.style.removeProperty('--tremor');
    };
  }

  window.ThemeRegistry.register({
    id: 'tectonic',
    displayName: 'Tectonic',
    previewHint: 'Gradient spikes shake the ground',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/tectonic.css',
    mapping: tectonicMapping,
    particleConfig: { type: 'debris' },
  });
})();
