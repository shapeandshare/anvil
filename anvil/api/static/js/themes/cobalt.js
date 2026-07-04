// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  const L0 = 9.8;

  function clamp01(x) {
    if (!Number.isFinite(x)) return 0;
    return Math.min(1, Math.max(0, x));
  }

  function cobaltMapping(bus, effectLevel) {
    const root = document.documentElement;
    const paused = effectLevel?.level === 'paused';
    let unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--elevation', '0');

    unsubs = [...unsubs,
      bus.on('metrics', function (m) {
        if (!m || paused) return;
        if (typeof m.loss === 'number' && Number.isFinite(m.loss)) {
          setVar('--elevation', clamp01(1 - m.loss / L0).toFixed(3));
        }
      }),
      bus.on('divergence', function () {
        root.dataset.cobaltState = 'diverged';
      }),
    ];

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      delete root.dataset.cobaltState;
      root.style.removeProperty('--elevation');
    };
  }

  globalThis.ThemeRegistry.register({
    id: 'cobalt',
    displayName: 'Cobalt',
    previewHint: 'Loss as a rising elevation line',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/cobalt.css',
    mapping: cobaltMapping,
  });
})();