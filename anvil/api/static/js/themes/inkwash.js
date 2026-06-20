(function () {
  'use strict';

  var L0 = 9.8;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function inkwashMapping(bus, effectLevel) {
    var root = document.documentElement;
    var legible = !!(effectLevel && effectLevel.legible);
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function applyClarity(clarity) {
      setVar('--clarity', clarity.toFixed(3));
      // Legibility-degrading bleed is suppressed at max-legibility (T4).
      setVar('--bleed', legible ? '0' : clamp01(1 - clarity).toFixed(3));
    }

    applyClarity(0.4);

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        applyClarity(clamp01(1 - m.loss / L0));
      }
    }));
    unsubs.push(bus.on('divergence', function () { applyClarity(0); }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--clarity');
      root.style.removeProperty('--bleed');
    };
  }

  window.ThemeRegistry.register({
    id: 'inkwash',
    displayName: 'Inkwash',
    previewHint: 'Loss bleeds the brushstroke',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/inkwash.css',
    mapping: inkwashMapping,
  });
})();
