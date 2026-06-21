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

  function arcadeMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var flashTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    /* At-rest default — mid-glow */
    setVar('--neon', '0.3');

    /* Loss drives neon intensity */
    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--neon', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));

    /* 1UP flash on milestone / complete */
    function oneUp() {
      if (paused) return;
      root.setAttribute('data-arcade-flash', 'true');
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(function () {
        root.removeAttribute('data-arcade-flash');
      }, 1100);
    }
    unsubs.push(bus.on('milestone', oneUp));
    unsubs.push(bus.on('complete', oneUp));

    /* GAME OVER on divergence */
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-arcade-state', 'game-over');
    }));

    return function teardown() {
      if (flashTimer) clearTimeout(flashTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-arcade-flash');
      root.removeAttribute('data-arcade-state');
      root.style.removeProperty('--neon');
    };
  }

  window.ThemeRegistry.register({
    id: 'arcade',
    displayName: 'Arcade',
    previewHint: 'Neon 80s party — loss drives the glow',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/arcade.css',
    mapping: arcadeMapping,
    particleConfig: { type: 'confetti' },
  });
})();
