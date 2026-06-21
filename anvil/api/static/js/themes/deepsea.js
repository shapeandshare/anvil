(function () {
  'use strict';

  var L0 = 9.8;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function deepSeaMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var flashTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function flash() {
      if (paused) return;
      root.setAttribute('data-deepsea-flash', 'true');
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(function () {
        root.removeAttribute('data-deepsea-flash');
      }, 700);
    }

    setVar('--depth', '0.3');
    setVar('--glow', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--depth', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('milestone', function () { flash(); }));
    unsubs.push(bus.on('complete', function () { flash(); }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--depth', '0');
      root.setAttribute('data-deepsea-state', 'abyss');
    }));

    return function teardown() {
      if (flashTimer) clearTimeout(flashTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-deepsea-state');
      root.removeAttribute('data-deepsea-flash');
      root.style.removeProperty('--depth');
      root.style.removeProperty('--glow');
    };
  }

  window.ThemeRegistry.register({
    id: 'deepsea',
    displayName: 'Deep Sea',
    previewHint: 'Loss as bioluminescent depth',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/deepsea.css',
    mapping: deepSeaMapping,
    particleConfig: { type: 'biolum' },
  });
})();
