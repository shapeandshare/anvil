// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var STORAGE_KEY = 'theme';
  var EFFECTS_KEY = 'theme:reduce-effects';
  var AUDIO_KEY = 'theme:audio';
  var EXCITED_KEY = 'theme:excited';
  var LAYER_LINK_ID = 'theme-layer-css';
  var registry = window.ThemeRegistry;

  var activeTeardown = null;
  var bus = window.SignalBus ? window.SignalBus.create() : null;
  var ps = window.ParticleSystem;

  // Picker keyboard-navigation / live-preview state.
  var pickerItems = [];   // theme buttons, in registry order
  var activeIndex = -1;   // currently highlighted item
  var previewBase = null; // committed { themeId, mode } captured when menu opens

  function osMode() {
    if (typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    return 'dark';
  }

  function readPref() {
    var raw = null;
    var parsed = null;
    try { raw = localStorage.getItem(STORAGE_KEY); } catch (e) { raw = null; }
    if (!raw) return { themeId: registry.defaultId, mode: osMode() };
    if (raw === 'light' || raw === 'dark') {
      return { themeId: registry.defaultId, mode: raw };
    }
    try { parsed = JSON.parse(raw); } catch (e) { parsed = null; }
    if (parsed && typeof parsed.themeId === 'string') {
      return { themeId: parsed.themeId, mode: parsed.mode === 'light' ? 'light' : 'dark' };
    }
    return { themeId: registry.defaultId, mode: osMode() };
  }

  function writePref(themeId, mode) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ themeId: themeId, mode: mode }));
    } catch (e) { return; }
  }

  function resolveMode(theme, wantedMode) {
    if (registry.isSingleMode(theme)) return 'dark';
    if (theme.modes.indexOf(wantedMode) !== -1) return wantedMode;
    return theme.modes.indexOf('dark') !== -1 ? 'dark' : theme.modes[0];
  }

  function ensureLayer(cssLayer) {
    var link = document.getElementById(LAYER_LINK_ID);
    var v;
    if (!cssLayer) {
      if (link) link.parentNode.removeChild(link);
      return;
    }
    if (!link) {
      link = document.createElement('link');
      link.id = LAYER_LINK_ID;
      link.rel = 'stylesheet';
      document.head.appendChild(link);
    }
    v = window.ANVIL_VERSION ? '?v=' + window.ANVIL_VERSION : '';
    cssLayer = cssLayer + v;
    if (link.getAttribute('href') !== cssLayer) link.setAttribute('href', cssLayer);
  }

function teardownMapping() {
    if (typeof activeTeardown === 'function') {
      try { activeTeardown(); } catch (e) { console.warn('[theme] mapping teardown failed', e); }
    }
    activeTeardown = null;
    if (ps) {
      try { ps.stopEffect(); } catch (e) { console.warn('[theme] particle teardown failed', e); }
    }
  }

  function teardownSignalMapping() {
    if (typeof activeTeardown === 'function') {
      try { activeTeardown(); } catch (e) { console.warn('[theme] mapping teardown failed', e); }
    }
    activeTeardown = null;
  }

  function bindMapping(theme) {
    if (!theme.mapping || !bus) return;
    var excitedPref = readExcitedPref();

    if (!bus.session() && excitedPref === 'auto') return;

    var snap = window.EffectLevel ? window.EffectLevel.snapshot() : {};
    try {
      activeTeardown = theme.mapping(bus, snap) || null;
    } catch (e) {
      console.warn('[theme] mapping bind failed for', theme.id, e);
      activeTeardown = null;
    }

    // Apply forced excited/idle state after mapping subscribes.
    // Also emit milestone/complete so themes with visible flash effects
    // provide immediate visual feedback that the mode is active.
    if (excitedPref === 'on') {
      bus.emit('metrics', { tokens_per_sec: 600000, loss: 0.5 });
      bus.emit('milestone', {});
      bus.emit('complete', {});
    } else if (excitedPref === 'off') {
      bus.emit('metrics', { tokens_per_sec: 0, loss: 9.8 });
    }
  }

  function applyAttributes(themeId, mode) {
    var root = document.documentElement;
    root.setAttribute('data-skin', themeId);
    root.setAttribute('data-theme', mode);
  }

  function apply(id, mode, opts) {
    opts = opts || {};
    var persist = opts.persist !== false;
    var theme = registry.get(id);
    if (!theme) {
      theme = registry.get(registry.defaultId);
      id = registry.defaultId;
    }
    var resolved = resolveMode(theme, mode || readPref().mode);

    teardownMapping();
    applyAttributes(theme.id, resolved);
    ensureLayer(theme.cssLayer);
    if (persist) writePref(theme.id, resolved);
    bindMapping(theme);

    // Particles render on every page; idle at base intensity, intensifying once a training session drives the signal vars.
    if (ps) {
      ps.apply(theme, null, false);
    }

    updateToggleState(theme);
    updatePickerUI(theme.id);
    if (typeof window.updateThemeUI === 'function') window.updateThemeUI(resolved);
    return { themeId: theme.id, mode: resolved };
  }

  function current() {
    var root = document.documentElement;
    return {
      themeId: root.getAttribute('data-skin') || registry.defaultId,
      mode: root.getAttribute('data-theme') || 'dark',
    };
  }

  function reset() { return apply(registry.defaultId, current().mode); }

  function toggleMode() {
    var cur = current();
    var theme = registry.get(cur.themeId);
    if (theme && registry.isSingleMode(theme)) return cur;
    return apply(cur.themeId, cur.mode === 'dark' ? 'light' : 'dark');
  }

  function updateToggleState(theme) {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var single = registry.isSingleMode(theme);
    btn.disabled = single;
    btn.setAttribute('aria-disabled', single ? 'true' : 'false');
    btn.title = single ? (theme.displayName + ' is single-mode') : 'Toggle light / dark';
  }

  function updatePickerUI(activeId) {
    var menu = document.getElementById('theme-picker-menu');
    if (!menu) return;
    menu.querySelectorAll('[data-theme-id]').forEach(function (el) {
      el.setAttribute('aria-current', el.getAttribute('data-theme-id') === activeId ? 'true' : 'false');
    });
  }

  function buildPicker() {
    var menu = document.getElementById('theme-picker-menu');
    if (!menu || !registry) return;
    var html = '<div class="theme-picker__grid" role="none">';
    html += registry.list().map(function (t) {
      return '<button type="button" class="theme-picker__item" role="menuitemradio"' +
        ' tabindex="-1" data-theme-id="' + t.id + '" aria-current="false"' +
        ' title="' + escapeHtml(t.displayName + ' \u2014 ' + t.previewHint) + '">' +
        '<span class="theme-picker__name">' + escapeHtml(t.displayName) + '</span>' +
        '<span class="theme-picker__hint">' + escapeHtml(t.previewHint) + '</span>' +
        '</button>';
    }).join('');
    html += '</div>';
    html += '<div class="theme-picker__controls">' +
      '<label class="theme-picker__toggle"><input type="checkbox" id="theme-reduce-effects"> Reduce effects</label>' +
      '<label class="theme-picker__toggle"><input type="checkbox" id="theme-audio-optin"> Enable theme audio</label>' +
      '<div class="theme-picker__excited">' +
      '<label for="theme-excited-select" class="theme-picker__excited-label">Excited</label>' +
      '<select id="theme-excited-select" class="theme-picker__select">' +
      '<option value="auto">Auto</option>' +
      '<option value="on">On</option>' +
      '<option value="off">Off</option>' +
      '</select>' +
      '</div>' +
      '</div>';
    menu.innerHTML = html;

    pickerItems = Array.prototype.slice.call(
      menu.querySelectorAll('.theme-picker__item')
    );

    menu.addEventListener('click', function (e) {
      var item = e.target.closest('[data-theme-id]');
      if (!item) return;
      commitSelection(item.getAttribute('data-theme-id'));
    });
    // Hovering previews too, so mouse exploration is as fast as the keyboard.
    pickerItems.forEach(function (item, i) {
      item.addEventListener('mouseenter', function () { setActive(i, true); });
    });
    menu.addEventListener('keydown', onMenuKeydown);

    wireEffectControls();
    updatePickerUI(current().themeId);
  }

  function colCount() {
    var top, n, i;
    if (pickerItems.length < 2) return 1;
    top = pickerItems[0].offsetTop;
    n = 0;
    for (i = 0; i < pickerItems.length; i++) {
      if (pickerItems[i].offsetTop === top) n++;
      else break;
    }
    return n || 1;
  }

  function indexOfTheme(themeId) {
    var i;
    for (i = 0; i < pickerItems.length; i++) {
      if (pickerItems[i].getAttribute('data-theme-id') === themeId) return i;
    }
    return 0;
  }

  function setActive(i, preview) {
    if (i < 0 || i >= pickerItems.length) return;
    if (activeIndex >= 0 && pickerItems[activeIndex]) {
      pickerItems[activeIndex].tabIndex = -1;
    }
    activeIndex = i;
    var el = pickerItems[i];
    el.tabIndex = 0;
    el.focus();
    if (el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
    if (preview) previewApply(el.getAttribute('data-theme-id'));
  }

  function moveActive(delta) {
    var next = activeIndex + delta;
    if (next < 0 || next >= pickerItems.length) return;
    setActive(next, true);
  }

  function onMenuKeydown(e) {
    var cols = colCount();
    var trigger;
    switch (e.key) {
      case 'ArrowRight': e.preventDefault(); moveActive(1); break;
      case 'ArrowLeft':  e.preventDefault(); moveActive(-1); break;
      case 'ArrowDown':  e.preventDefault(); moveActive(cols); break;
      case 'ArrowUp':    e.preventDefault(); moveActive(-cols); break;
      case 'Home':       e.preventDefault(); setActive(0, true); break;
      case 'End':        e.preventDefault(); setActive(pickerItems.length - 1, true); break;
      case 'Enter':
      case ' ':
        if (activeIndex >= 0) {
          e.preventDefault();
          commitSelection(pickerItems[activeIndex].getAttribute('data-theme-id'));
        }
        break;
      case 'Escape':
        e.preventDefault();
        closeMenu(true);
        trigger = document.getElementById('theme-picker-trigger');
        if (trigger) trigger.focus();
        break;
      default: break;
    }
  }

  function previewApply(themeId) {
    // Live preview: apply visuals WITHOUT persisting, so Escape can revert.
    var mode = previewBase ? previewBase.mode : current().mode;
    apply(themeId, mode, { persist: false });
  }

  function commitSelection(themeId) {
    var mode = previewBase ? previewBase.mode : current().mode;
    apply(themeId, mode, { persist: true });
    previewBase = null; // nothing to revert to
    closeMenu(false);
    var trigger = document.getElementById('theme-picker-trigger');
    if (trigger) trigger.focus();
  }

  function wireEffectControls() {
    var reduce = document.getElementById('theme-reduce-effects');
    var audio = document.getElementById('theme-audio-optin');
    var excited = document.getElementById('theme-excited-select');
    if (reduce) {
      reduce.checked = readFlag(EFFECTS_KEY);
      reduce.addEventListener('change', function () {
        writeFlag(EFFECTS_KEY, reduce.checked);
        if (window.EffectLevel) window.EffectLevel.setReducedEffects(reduce.checked);
      });
    }
    if (audio) {
      audio.checked = readFlag(AUDIO_KEY);
      audio.addEventListener('change', function () {
        writeFlag(AUDIO_KEY, audio.checked);
        if (window.EffectLevel) window.EffectLevel.setAudioOptIn(audio.checked);
      });
    }
    if (excited) {
      excited.value = readExcitedPref();
      excited.addEventListener('change', function () {
        writeExcitedPref(excited.value);
        reapplyEffectLevel();
      });
    }
  }

  function updateGlassDiffusion(snap) {
    var root = document.documentElement;
    if (snap.legible) {
      root.setAttribute('data-glass-diffusion', '');
    } else {
      root.removeAttribute('data-glass-diffusion');
    }
  }

  function readFlag(key) {
    try { return localStorage.getItem(key) === '1'; } catch (e) { return false; }
  }

  function writeFlag(key, on) {
    try { localStorage.setItem(key, on ? '1' : '0'); } catch (e) { return; }
  }

  function readExcitedPref() {
    var v;
    try {
      v = localStorage.getItem(EXCITED_KEY);
      if (v === 'on' || v === 'off') return v;
    } catch (e) {}
    return 'auto';
  }

  function writeExcitedPref(v) {
    try { localStorage.setItem(EXCITED_KEY, v); } catch (e) {}
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function openMenu() {
    var menu = document.getElementById('theme-picker-menu');
    var trigger = document.getElementById('theme-picker-trigger');
    if (menu) menu.hidden = false;
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    // Remember what to revert to if the user cancels (Escape / click-away).
    previewBase = current();
    if (pickerItems.length) {
      setActive(indexOfTheme(previewBase.themeId), false);
    }
  }

  function closeMenu(revert) {
    var menu = document.getElementById('theme-picker-menu');
    var trigger = document.getElementById('theme-picker-trigger');
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    // Cancel path: restore the theme that was committed when the menu opened.
    if (revert && previewBase) {
      apply(previewBase.themeId, previewBase.mode, { persist: true });
    }
    previewBase = null;
  }

  function wirePicker() {
    var trigger = document.getElementById('theme-picker-trigger');
    if (!trigger) return;
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      var menu = document.getElementById('theme-picker-menu');
      if (menu && menu.hidden) { openMenu(); } else { closeMenu(true); }
    });
    document.addEventListener('click', function (e) {
      var menu = document.getElementById('theme-picker-menu');
      if (menu && !menu.hidden && !e.target.closest('#theme-picker')) closeMenu(true);
    });
  }

  function bindSession(session) {
    if (!bus) return;
    bus.attach(session);
    teardownSignalMapping();
    // Only (re)bind the mapping — particles already run from the initial apply().
    // Re-applying here would rebuild the canvas, causing a second wave on load.
    bindMapping(registry.get(current().themeId) || registry.get(registry.defaultId));
  }

  function onStorage(e) {
    if (e.key && e.key !== STORAGE_KEY) return;
    var pref = readPref();
    var cur = current();
    if (pref.themeId !== cur.themeId || pref.mode !== cur.mode) {
      apply(pref.themeId, pref.mode);
    }
  }

  function reapplyEffectLevel() {
    var cur = current();
    var theme = registry.get(cur.themeId);
    if (theme && theme.mapping) {
      teardownSignalMapping();
      bindMapping(theme);
    }
  }

  function init() {
    var pref = readPref();
    var snap;
    if (window.EffectLevel) {
      window.EffectLevel.setReducedEffects(readFlag(EFFECTS_KEY));
      window.EffectLevel.setAudioOptIn(readFlag(AUDIO_KEY));
    }
    apply(pref.themeId, pref.mode);
    buildPicker();
    wirePicker();
    window.addEventListener('storage', onStorage);
    if (window.EffectLevel) {
      window.EffectLevel.onChange(reapplyEffectLevel);
      window.EffectLevel.onChange(updateGlassDiffusion);
      snap = window.EffectLevel.snapshot();
      updateGlassDiffusion(snap);
    }
  }

  window.ThemeManager = {
    init: init,
    apply: apply,
    current: current,
    reset: reset,
    toggleMode: toggleMode,
    bindSession: bindSession,
    bus: bus,
  };
})();
