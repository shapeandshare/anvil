(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function emberMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--warmth', '0.3');
    setVar('--density', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--warmth', clamp01(1 - m.loss / L0).toFixed(3));
      }
      if (m.tokens_per_sec != null) {
        setVar('--density', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () { setVar('--warmth', '1'); }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--warmth');
      root.style.removeProperty('--density');
    };
  }

  window.ThemeRegistry.register({
    id: 'emberdrift',
    displayName: 'Ember Drift',
    previewHint: 'Drifting sparks, quietly forging',
    modes: ['single'],
    cssLayer: '/static/css/themes/emberdrift.css',
    mapping: emberMapping,
    particleConfig: { type: 'ember' },
  });
})();
