// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var L0 = 9.8;

  // A single shared AudioContext, reused across binds (browsers cap the count of
  // live contexts, so we never close/recreate per theme switch — we suspend it).
  var sharedCtx = null;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function getCtx() {
    if (sharedCtx) return sharedCtx;
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    try { sharedCtx = new Ctx(); } catch (e) { sharedCtx = null; }
    return sharedCtx;
  }

  function targetFreq(tone) {
    // Lower loss (higher tone) -> cleaner, higher pitch. 110 Hz ... 440 Hz.
    return 110 + clamp01(tone) * 330;
  }

  function resonanceMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = !!(effectLevel && effectLevel.level === 'paused');
    // The manager re-binds this mapping whenever the effect level changes
    // (audio opt-in, reduce-effects, tab visibility), so a fresh snapshot here
    // is authoritative -- no internal EffectLevel subscription needed.
    var audioWanted = !!(effectLevel && effectLevel.audioOptIn) && !paused;
    var unsubs = [];
    var osc = null;
    var gain = null;
    var amp = 0;
    var tone = 0.4;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    function startAudio() {
      var ctx = getCtx();
      if (!ctx || osc) return;
      try {
        if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
        osc = ctx.createOscillator();
        gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = targetFreq(tone);
        gain.gain.value = 0.0001;
        osc.connect(gain).connect(ctx.destination);
        osc.start();
      } catch (e) {
        console.warn('[theme] resonance audio failed to start', e);
        osc = null;
        gain = null;
      }
    }

    function stopAudio() {
      try {
        if (osc) { osc.stop(); osc.disconnect(); }
        if (gain) gain.disconnect();
      } catch (e) { /* already stopped */ }
      osc = null;
      gain = null;
    }

    function applyAudio() {
      if (!osc || !gain || !sharedCtx) return;
      var now = sharedCtx.currentTime;
      osc.frequency.setTargetAtTime(targetFreq(tone), now, 0.3);
      // Gentle: peak gain ~0.04.
      gain.gain.setTargetAtTime(0.002 + clamp01(amp) * 0.038, now, 0.2);
    }

    setVar('--amp', '0');
    setVar('--tone', '0.4');
    if (audioWanted) startAudio();

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      if (m.grad_norm != null && isFinite(m.grad_norm)) {
        amp = clamp01(m.grad_norm);
        setVar('--amp', amp.toFixed(3));
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        tone = clamp01(1 - m.loss / L0);
        setVar('--tone', tone.toFixed(3));
      }
      applyAudio();
    }));
    unsubs.push(bus.on('divergence', function () {
      amp = 1;
      tone = 0;
      setVar('--amp', '1');
      applyAudio();
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      stopAudio();
      root.style.removeProperty('--amp');
      root.style.removeProperty('--tone');
    };
  }

  window.ThemeRegistry.register({
    id: 'resonance',
    displayName: 'Resonance',
    previewHint: 'Signal as light & (opt-in) sound',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/resonance.css',
    mapping: resonanceMapping,
    particleConfig: { type: 'css' },
  });
})();
