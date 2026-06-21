(function () {
  'use strict';

  var L0 = 9.8;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function stainedGlassMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var litTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    setVar('--lumin', '0.3');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--lumin', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));

    function lightPane() {
      if (paused) return;
      root.setAttribute('data-glass', 'lit');
      if (litTimer) clearTimeout(litTimer);
      litTimer = setTimeout(function () {
        root.removeAttribute('data-glass');
      }, 1400);
    }
    unsubs.push(bus.on('milestone', lightPane));
    unsubs.push(bus.on('complete', lightPane));

    return function teardown() {
      if (litTimer) clearTimeout(litTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-glass');
      root.style.removeProperty('--lumin');
    };
  }

  window.ThemeRegistry.register({
    id: 'stainedglass',
    displayName: 'Stained Glass',
    previewHint: 'Milestones light the cathedral',
    modes: ['single'],
    cssLayer: '/static/css/themes/stainedglass.css',
    mapping: stainedGlassMapping,
    particleConfig: { type: 'shard' },
  });
})();
