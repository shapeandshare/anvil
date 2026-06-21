// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var L0 = 9.8;
  var MAX_TPS = 600000;

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function vinylMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = !!(effectLevel && effectLevel.level === 'paused');
    var legible = !!(effectLevel && effectLevel.legible);
    var reducedMotion = !!(effectLevel && (effectLevel.level === 'muted' || effectLevel.reducedMotion));
    var diverged = false;
    var unsubs = [];
    var peakTimer = null;
    var tapeDeck = null;
    var tps;
    var rpm;
    var warmth;
    var lastLevel = 0.5;
    var lastWarmth = 0.4;

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    /* ── Set at-rest defaults immediately ── */
    setVar('--rpm', '0.33');
    setVar('--level', '0.5');
    setVar('--warmth', '0.4');

    if (legible) {
      root.setAttribute('data-vinyl-steady', 'true');
    }

    /* ── DOM Injection: Build the tape-deck overlay ── */
    function buildTapeDeck() {
      if (tapeDeck || paused || legible || reducedMotion) return;
      tapeDeck = document.createElement('div');
      tapeDeck.className = 'vinyl-tape-deck';
      tapeDeck.setAttribute('aria-hidden', 'true');

      // Left reel
      var leftReel = document.createElement('div');
      leftReel.className = 'vinyl-reel vinyl-reel--left';
      tapeDeck.appendChild(leftReel);

      // Right reel
      var rightReel = document.createElement('div');
      rightReel.className = 'vinyl-reel vinyl-reel--right';
      tapeDeck.appendChild(rightReel);

      // Tape band between reels
      var tapeBand = document.createElement('div');
      tapeBand.className = 'vinyl-tape-band';
      tapeDeck.appendChild(tapeBand);

      // Left VU meter
      var leftVU = document.createElement('div');
      leftVU.className = 'vinyl-vu vinyl-vu--left';
      var leftNeedle = document.createElement('div');
      leftNeedle.className = 'vinyl-vu-needle';
      leftVU.appendChild(leftNeedle);
      tapeDeck.appendChild(leftVU);

      // Right VU meter
      var rightVU = document.createElement('div');
      rightVU.className = 'vinyl-vu vinyl-vu--right';
      var rightNeedle = document.createElement('div');
      rightNeedle.className = 'vinyl-vu-needle';
      rightVU.appendChild(rightNeedle);
      tapeDeck.appendChild(rightVU);

      document.body.appendChild(tapeDeck);
    }

    function removeTapeDeck() {
      if (tapeDeck && tapeDeck.parentNode) {
        tapeDeck.parentNode.removeChild(tapeDeck);
      }
      tapeDeck = null;
    }

    /* ── Build the deck unless paused/legible/reduced ── */
    if (!paused && !legible && !reducedMotion) {
      buildTapeDeck();
    }

    /* ── VU Needle Peak (milestone / complete) ── */
    function triggerPeak(duration) {
      if (paused || legible || diverged || reducedMotion) return;
      // Set state attr for CSS styling
      root.setAttribute('data-vinyl-state', 'peak');
      // Pin the needle to hot (--level = 1.0 → rotate(45deg))
      setVar('--level', '1.0');
      // Warm the glow briefly
      setVar('--warmth', '1.0');
      if (peakTimer) clearTimeout(peakTimer);
      peakTimer = setTimeout(function () {
        // Restore last-known-good values
        setVar('--level', lastLevel.toFixed(3));
        setVar('--warmth', lastWarmth.toFixed(3));
        root.removeAttribute('data-vinyl-state');
        peakTimer = null;
      }, duration || 460);
    }

    /* ── Signal Subscriptions ── */

    // Throughput → reel spin speed (--rpm) + glow intensity (--warmth)
    // Loss → VU needle position (--level): high loss = needle pinned hot
    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused || diverged) return;
      if (typeof m.tokens_per_sec === 'number' && isFinite(m.tokens_per_sec)) {
        tps = clamp01(m.tokens_per_sec / MAX_TPS);
        // --rpm: 0.33 at rest (idle slow spin), 1.0 at full blast
        rpm = 0.33 + tps * 0.67;
        if (legible) {
          rpm = Math.min(rpm, 0.5); // cap spin in legible mode
        }
        // --warmth: 0.3 at min (perceptible amber), 1.0 at max
        warmth = 0.3 + tps * 0.7;
        lastWarmth = warmth;
        setVar('--rpm', rpm.toFixed(3));
        setVar('--warmth', warmth.toFixed(3));
      }
      if (typeof m.loss === 'number' && isFinite(m.loss)) {
        // High loss → needle pinned toward hot (right)
        // Converging loss → needle settles to calm (left)
        lastLevel = clamp01(m.loss / L0);
        setVar('--level', lastLevel.toFixed(3));
      }
    }));

    // Milestone → VU needle peak (brief hot pin, then settle)
    unsubs.push(bus.on('milestone', function () {
      triggerPeak(400);
    }));

    // Complete → needle peak (slightly longer and warmer)
    unsubs.push(bus.on('complete', function () {
      triggerPeak(600);
    }));

    // Divergence → tape snapped: reels stop, needles pinned, glow dies
    unsubs.push(bus.on('divergence', function () {
      diverged = true;
      setVar('--rpm', '0');
      setVar('--level', '1.0');   // needles slam to hot
      setVar('--warmth', '0');     // glow goes dead
      root.setAttribute('data-vinyl-state', 'diverged');
      if (peakTimer) {
        clearTimeout(peakTimer);
        peakTimer = null;
      }
    }));

    /* ── Teardown ── */
    return function teardown() {
      if (peakTimer) {
        clearTimeout(peakTimer);
        peakTimer = null;
      }

      removeTapeDeck();

      unsubs.forEach(function (u) { u(); });
      unsubs = [];

      root.removeAttribute('data-vinyl-state');
      root.removeAttribute('data-vinyl-steady');
      root.style.removeProperty('--rpm');
      root.style.removeProperty('--level');
      root.style.removeProperty('--warmth');

      diverged = false;
    };
  }

  /* ── Registration ── */
  window.ThemeRegistry.register({
    id: 'vinyl',
    displayName: 'Vinyl',
    previewHint: 'Warm analog tape deck — reels spin with throughput, VU meters track loss, milestones peak the needles',
    modes: ['light', 'dark'],
    cssLayer: '/static/css/themes/vinyl.css',
    mapping: vinylMapping,
    particleConfig: { type: 'css' },
  });
})();