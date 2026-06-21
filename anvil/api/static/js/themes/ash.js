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

  function ashMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--ash', '0.3');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        // High loss = heavy soot fall
        setVar('--ash', clamp01(m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--ash', '1');
      root.setAttribute('data-ash-state', 'ashfall');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-ash-state');
      root.style.removeProperty('--ash');
    };
  }

  window.ThemeRegistry.register({
    id: 'ash',
    displayName: 'Ash',
    previewHint: 'Loss as falling black soot — training gone wrong',
    modes: ['single'],
    cssLayer: '/static/css/themes/ash.css',
    mapping: ashMapping,
    particleConfig: { type: 'css' },
  });
})();