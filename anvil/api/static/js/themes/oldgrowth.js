(function () {
  'use strict';

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function stddev(values) {
    var n = values.length;
    if (n < 2) return 0;
    var mean = values.reduce(function (a, b) { return a + b; }, 0) / n;
    var variance = values.reduce(function (a, b) {
      return a + (b - mean) * (b - mean);
    }, 0) / n;
    return Math.sqrt(variance);
  }

  function oldGrowthMapping(bus, effectLevel) {
    var root = document.documentElement;
    var legible = !!(effectLevel && effectLevel.legible);
    var paused = effectLevel && effectLevel.level === 'paused';
    var recent = [];
    var unsubs = [];

    function setDisturbance(value) {
      root.style.setProperty('--disturbance', clamp01(value).toFixed(3));
    }

    setDisturbance(0);

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      var instability = 0;
      if (m.grad_norm != null && isFinite(m.grad_norm)) {
        instability = clamp01(m.grad_norm);
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        recent.push(m.loss);
        if (recent.length > 8) recent.shift();
        instability = Math.max(instability, clamp01(stddev(recent) * 3));
      }
      if (legible) instability = 0;
      setDisturbance(instability);
    }));
    unsubs.push(bus.on('divergence', function () { setDisturbance(1); }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.style.removeProperty('--disturbance');
    };
  }

  window.ThemeRegistry.register({
    id: 'oldgrowth',
    displayName: 'Old Growth',
    previewHint: 'Signal degrades with instability',
    modes: ['single'],
    cssLayer: '/static/css/themes/oldgrowth.css',
    mapping: oldGrowthMapping,
  });
})();
