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

  function stormMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var charge;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--charge', '0');
    setVar('--clearing', '0.3');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.grad_norm != null && isFinite(m.grad_norm)) {
        charge = clamp01(m.grad_norm);
        setVar('--charge', charge.toFixed(3));
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--clearing', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--charge', '1');
      root.setAttribute('data-storm', 'tempest');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-storm');
      root.style.removeProperty('--charge');
      root.style.removeProperty('--clearing');
    };
  }

  window.ThemeRegistry.register({
    id: 'stormfront',
    displayName: 'Storm Front',
    previewHint: 'Gradient charge, loss clears the sky',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/stormfront.css',
    mapping: stormMapping,
    particleConfig: { type: 'rain', params: {} },
  });
})();
