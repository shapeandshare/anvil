(function () {
  'use strict';

  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function loomMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--weft', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.tokens_per_sec != null) {
        setVar('--weft', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--weft', '1');
      root.setAttribute('data-loom-state', 'snag');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-loom-state');
      root.style.removeProperty('--weft');
    };
  }

  window.ThemeRegistry.register({
    id: 'loom',
    displayName: 'Loom',
    previewHint: 'Throughput as a weaving shuttle',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/loom.css',
    mapping: loomMapping,
  });
})();