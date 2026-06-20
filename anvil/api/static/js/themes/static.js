(function () {
  'use strict';

  var L0 = 9.8;
  var WINDOW = 8;
  var history = [];

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function stddev(arr) {
    var n = arr.length;
    var mean = 0;
    var m2 = 0;
    var i;
    if (n < 2) return 0;
    for (i = 0; i < n; i++) mean += arr[i];
    mean /= n;
    for (i = 0; i < n; i++) m2 += (arr[i] - mean) * (arr[i] - mean);
    return Math.sqrt(m2 / (n - 1));
  }

  function staticMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var vol;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--snow', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        history.push(m.loss);
        if (history.length > WINDOW) history.shift();
        vol = stddev(history) / L0;
        setVar('--snow', clamp01(vol).toFixed(3));
      }
    }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--snow', '1');
      root.setAttribute('data-static-state', 'snowstorm');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-static-state');
      root.style.removeProperty('--snow');
      history = [];
    };
  }

  window.ThemeRegistry.register({
    id: 'static',
    displayName: 'Static',
    previewHint: 'Loss volatility as CRT noise',
    modes: ['single'],
    cssLayer: '/static/css/themes/static.css',
    mapping: staticMapping,
  });
})();