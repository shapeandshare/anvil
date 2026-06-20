(function () {
  'use strict';

  var LEVEL = { FULL: 'full', MUTED: 'muted', LEGIBLE: 'legible', PAUSED: 'paused' };
  var listeners = [];
  var inApp = { reducedEffects: false, audioOptIn: false };

  function mq(query) {
    return typeof window.matchMedia === 'function' ? window.matchMedia(query) : null;
  }

  var mqMotion = mq('(prefers-reduced-motion: reduce)');
  var mqTransparency = mq('(prefers-reduced-transparency: reduce)');

  function state() {
    return {
      reducedMotion: (mqMotion && mqMotion.matches) || false,
      reducedTransparency: (mqTransparency && mqTransparency.matches) || false,
      reducedEffects: inApp.reducedEffects,
      audioOptIn: inApp.audioOptIn,
      visible: document.visibilityState === 'visible',
    };
  }

  function level() {
    var s = state();
    if (!s.visible) return LEVEL.PAUSED;
    if (s.reducedEffects) return LEVEL.LEGIBLE;
    if (s.reducedMotion || s.reducedTransparency) return LEVEL.MUTED;
    return LEVEL.FULL;
  }

  function snapshot() {
    var s = state();
    s.level = level();
    s.legible = s.reducedEffects;
    return s;
  }

  function notify() {
    var snap = snapshot();
    listeners.forEach(function (cb) {
      try { cb(snap); } catch (e) { console.warn('[theme] effect-level listener failed', e); }
    });
  }

  function onChange(cb) {
    listeners.push(cb);
    return function () {
      var i = listeners.indexOf(cb);
      if (i !== -1) listeners.splice(i, 1);
    };
  }

  function setReducedEffects(on) { inApp.reducedEffects = !!on; notify(); }
  function setAudioOptIn(on) { inApp.audioOptIn = !!on; notify(); }

  function bindMedia(target) {
    if (!target) return;
    if (typeof target.addEventListener === 'function') {
      target.addEventListener('change', notify);
    } else if (typeof target.addListener === 'function') {
      target.addListener(notify);
    }
  }

  bindMedia(mqMotion);
  bindMedia(mqTransparency);
  document.addEventListener('visibilitychange', notify);

  window.EffectLevel = {
    LEVEL: LEVEL,
    snapshot: snapshot,
    level: level,
    onChange: onChange,
    setReducedEffects: setReducedEffects,
    setAudioOptIn: setAudioOptIn,
  };
})();
