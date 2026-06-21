(function () {
  'use strict';

  var L0 = 9.8;

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

  function bloomMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var recent = [];
    var unsubs = [];
    var flashTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--open', '0.2');
    setVar('--sway', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--open', clamp01(1 - m.loss / L0).toFixed(3));
        recent.push(m.loss);
        if (recent.length > 8) recent.shift();
        setVar('--sway', clamp01(stddev(recent) * 3).toFixed(3));
      }
    }));

    function flower() {
      if (paused) return;
      root.setAttribute('data-bloom', 'flower');
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(function () {
        root.removeAttribute('data-bloom');
      }, 1100);
    }
    unsubs.push(bus.on('milestone', flower));
    unsubs.push(bus.on('complete', flower));

    return function teardown() {
      if (flashTimer) clearTimeout(flashTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-bloom');
      root.style.removeProperty('--open');
      root.style.removeProperty('--sway');
    };
  }

  window.ThemeRegistry.register({
    id: 'bloom',
    displayName: 'Bloom',
    previewHint: 'Convergence opens the garden',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/bloom.css',
    mapping: bloomMapping,
    particleConfig: { type: 'petal' },
  });
})();
