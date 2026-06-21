(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function forgeMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var flashTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function flash(state) {
      if (paused) return;
      root.setAttribute('data-forge-state', state);
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(function () {
        if (root.getAttribute('data-forge-state') === state) {
          root.removeAttribute('data-forge-state');
        }
      }, 900);
    }

    setVar('--heat', '0');
    setVar('--prog', '1');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--prog', clamp01(1 - m.loss / L0).toFixed(3));
      }
      if (m.tokens_per_sec != null) {
        setVar('--heat', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('milestone', function () { flash('quench'); }));
    unsubs.push(bus.on('complete', function () { flash('quench'); }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--heat', '1');
      root.setAttribute('data-forge-state', 'diverged');
    }));

    return function teardown() {
      if (flashTimer) clearTimeout(flashTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-forge-state');
    };
  }

  window.ThemeRegistry.register({
    id: 'forge',
    displayName: 'Forge',
    previewHint: 'Loss as cooling metal',
    modes: ['dark'],
    cssLayer: '/static/css/themes/forge.css',
    mapping: forgeMapping,
    particleConfig: { type: 'ember' },
  });
})();
