(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function reactorMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--throughput', '0');
    setVar('--output', '0.4');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.tokens_per_sec != null) {
        setVar('--throughput', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--output', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-reactor', 'scram');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-reactor');
      root.style.removeProperty('--throughput');
      root.style.removeProperty('--output');
    };
  }

  window.ThemeRegistry.register({
    id: 'reactor',
    displayName: 'Reactor',
    previewHint: 'Throughput drives the core',
    modes: ['single'],
    cssLayer: '/static/css/themes/reactor.css',
    mapping: reactorMapping,
    particleConfig: { type: 'energy' },
  });
})();
