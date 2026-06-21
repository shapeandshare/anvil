(function () {
  'use strict';

  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function mainframeMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--activity', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.tokens_per_sec != null) {
        setVar('--activity', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-mainframe', 'error');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-mainframe');
      root.style.removeProperty('--activity');
    };
  }

  window.ThemeRegistry.register({
    id: 'mainframe',
    displayName: 'Mainframe',
    previewHint: 'A calm terminal that ticks with throughput',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/mainframe.css',
    mapping: mainframeMapping,
    particleConfig: { type: 'matrix' },
  });
})();
