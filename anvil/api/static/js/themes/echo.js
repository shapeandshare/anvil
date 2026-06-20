(function () {
  'use strict';

  var L0 = 9.8;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function echoMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];
    var burstTimer = null;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function burst(isMilestone) {
      if (paused) return;
      if (isMilestone) {
        root.setAttribute('data-echo-milestone', 'true');
      } else {
        root.setAttribute('data-echo-state', 'sonic-boom');
      }
      if (burstTimer) clearTimeout(burstTimer);
      burstTimer = setTimeout(function () {
        root.removeAttribute('data-echo-milestone');
        root.removeAttribute('data-echo-state');
      }, 1200);
    }

    setVar('--ping', '0');
    setVar('--ring', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.grad_norm != null && isFinite(m.grad_norm)) {
        setVar('--ping', clamp01(m.grad_norm).toFixed(3));
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        setVar('--ring', clamp01(1 - m.loss / L0).toFixed(3));
      }
    }));
    unsubs.push(bus.on('milestone', function () { burst(true); }));
    unsubs.push(bus.on('complete', function () { burst(true); }));
    unsubs.push(bus.on('divergence', function () {
      setVar('--ping', '1');
      burst(false);
    }));

    return function teardown() {
      if (burstTimer) clearTimeout(burstTimer);
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-echo-milestone');
      root.removeAttribute('data-echo-state');
      root.style.removeProperty('--ping');
      root.style.removeProperty('--ring');
    };
  }

  window.ThemeRegistry.register({
    id: 'echo',
    displayName: 'Echo',
    previewHint: 'Gradient spikes as sonar pings',
    modes: ['single'],
    cssLayer: '/static/css/themes/echo.css',
    mapping: echoMapping,
  });
})();