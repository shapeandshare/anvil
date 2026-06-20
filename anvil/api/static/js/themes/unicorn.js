(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function unicornMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var hue = 0;
    var burstTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function burst() {
      if (paused) return;
      root.setAttribute('data-unicorn-burst', 'true');
      if (burstTimer) clearTimeout(burstTimer);
      burstTimer = setTimeout(function () {
        root.removeAttribute('data-unicorn-burst');
      }, 1100);
    }

    setVar('--magic', '0.3');
    setVar('--twinkle', '0');
    setVar('--hue', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--magic', clamp01(1 - m.loss / L0).toFixed(3));
      }
      if (typeof m.tokens_per_sec === 'number' && isFinite(m.tokens_per_sec)) {
        setVar('--twinkle', clamp01(m.tokens_per_sec / MAX_TPS).toFixed(3));
      }
    }));
    unsubs.push(bus.on('milestone', function () {
      hue = (hue + 51) % 360;
      setVar('--hue', String(hue));
      burst();
    }));
    unsubs.push(bus.on('complete', function () {
      hue = (hue + 102) % 360;
      setVar('--hue', String(hue));
      burst();
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--magic', '0');
      setVar('--twinkle', '0');
      root.setAttribute('data-unicorn-state', 'faded');
    }));

    return function teardown() {
      if (burstTimer) clearTimeout(burstTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-unicorn-burst');
      root.removeAttribute('data-unicorn-state');
      root.style.removeProperty('--magic');
      root.style.removeProperty('--twinkle');
      root.style.removeProperty('--hue');
    };
  }

  window.ThemeRegistry.register({
    id: 'unicorn',
    displayName: 'Unicorn',
    previewHint: 'Training brings out the rainbow — loss as magic, throughput as sparkle',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/unicorn.css',
    mapping: unicornMapping,
  });
})();
