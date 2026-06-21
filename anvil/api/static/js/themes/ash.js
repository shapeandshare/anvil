(function () {
  'use strict';

  var L0 = 9.8;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function ashMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--ember', '0.6');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--ember', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--ember', '1');
      root.setAttribute('data-ash-state', 'smoke');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-ash-state');
      root.style.removeProperty('--ember');
    };
  }

  window.ThemeRegistry.register({
    id: 'ash',
    displayName: 'Ash',
    previewHint: 'Loss as cooling embers',
    modes: ['single'],
    cssLayer: '/static/css/themes/ash.css',
    mapping: ashMapping,
    particleConfig: { type: 'ember' },
  });
})();