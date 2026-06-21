(function () {
  'use strict';

  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function vinylMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var skipTimer = null;
    var tps;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function skip() {
      if (paused) return;
      root.setAttribute('data-vinyl-state', 'skip');
      if (skipTimer) clearTimeout(skipTimer);
      skipTimer = setTimeout(function () {
        root.removeAttribute('data-vinyl-state');
      }, 500);
    }

    setVar('--wobble', '0.8');
    setVar('--warmth', '0.4');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.tokens_per_sec != null) {
        tps = clamp01(m.tokens_per_sec / MAX_TPS);
        setVar('--wobble', (1 - tps * 0.7).toFixed(3));
        setVar('--warmth', (0.3 + tps * 0.7).toFixed(3));
      }
    }));
    unsubs.push(bus.on('milestone', function () { skip(); }));
    unsubs.push(bus.on('complete', function () { skip(); }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--wobble', '1');
      setVar('--warmth', '0');
      root.setAttribute('data-vinyl-state', 'skip');
    }));

    return function teardown() {
      if (skipTimer) clearTimeout(skipTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-vinyl-state');
      root.style.removeProperty('--wobble');
      root.style.removeProperty('--warmth');
    };
  }

  window.ThemeRegistry.register({
    id: 'vinyl',
    displayName: 'Vinyl',
    previewHint: 'Throughput steadies the turntable wobble',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/vinyl.css',
    mapping: vinylMapping,
    particleConfig: { type: 'spin' },
  });
})();