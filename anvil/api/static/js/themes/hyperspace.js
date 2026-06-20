(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function hyperspaceMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var flashTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--velocity', '0');
    setVar('--focus', '0.4');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.tokens_per_sec != null) {
        setVar('--velocity', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--focus', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));

    function jump() {
      if (paused) return;
      root.setAttribute('data-hyper', 'jump');
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(function () {
        root.removeAttribute('data-hyper');
      }, 700);
    }
    unsubs.push(bus.on('milestone', jump));
    unsubs.push(bus.on('complete', jump));

    return function teardown() {
      if (flashTimer) clearTimeout(flashTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-hyper');
      root.style.removeProperty('--velocity');
      root.style.removeProperty('--focus');
    };
  }

  window.ThemeRegistry.register({
    id: 'hyperspace',
    displayName: 'Hyperspace',
    previewHint: 'Throughput stretches the stars',
    modes: ['single'],
    cssLayer: '/static/css/themes/hyperspace.css',
    mapping: hyperspaceMapping,
  });
})();
