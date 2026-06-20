(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function auroraMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--calm', '1');
    setVar('--flow', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--calm', clamp01(1 - m.loss / L0).toFixed(3));
      }
      if (m.tokens_per_sec != null) {
        setVar('--flow', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () { setVar('--calm', '0'); }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--calm');
      root.style.removeProperty('--flow');
    };
  }

  window.ThemeRegistry.register({
    id: 'aurora',
    displayName: 'Aurora',
    previewHint: 'Loss as northern lights',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/aurora.css',
    mapping: auroraMapping,
  });
})();
