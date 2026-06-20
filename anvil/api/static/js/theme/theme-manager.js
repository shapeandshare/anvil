(function () {
  'use strict';

  var STORAGE_KEY = 'theme';
  var LAYER_LINK_ID = 'theme-layer-css';
  var registry = window.ThemeRegistry;

  var activeTeardown = null;
  var bus = window.SignalBus ? window.SignalBus.create() : null;

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
    if (link.getAttribute('href') !== cssLayer) link.setAttribute('href', cssLayer);
  }

  function teardownMapping() {
    if (typeof activeTeardown === 'function') {
      try { activeTeardown(); } catch (e) { console.warn('[theme] mapping teardown failed', e); }
    }
    activeTeardown = null;
  }

  function bindMapping(theme) {
    teardownMapping();
    if (!theme.mapping || !bus || !bus.session()) return;
    var snap = window.EffectLevel ? window.EffectLevel.snapshot() : {};
    try {
      activeTeardown = theme.mapping(bus, snap) || null;
    } catch (e) {
      console.warn('[theme] mapping bind failed for', theme.id, e);
      activeTeardown = null;
    }
  }

  function applyAttributes(themeId, mode) {
    var root = document.documentElement;
    root.setAttribute('data-skin', themeId);
    root.setAttribute('data-theme', mode);
  }

  function apply(id, mode, opts) {
    opts = opts || {};
    var theme = registry.get(id);
    if (!theme) {
      theme = registry.get(registry.defaultId);
      id = registry.defaultId;
    }
    var resolved = resolveMode(theme, mode || readPref().mode);

    teardownMapping();
    applyAttributes(theme.id, resolved);
    ensureLayer(theme.cssLayer);
    writePref(theme.id, resolved);
    bindMapping(theme);

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
    var html = registry.list().map(function (t) {
      return '<button type="button" class="theme-picker__item" role="menuitemradio"' +
        ' data-theme-id="' + t.id + '" aria-current="false">' +
        '<span class="theme-picker__name">' + escapeHtml(t.displayName) + '</span>' +
        '<span class="theme-picker__hint">' + escapeHtml(t.previewHint) + '</span>' +
        '</button>';
    }).join('');
    menu.innerHTML = html;
    menu.addEventListener('click', function (e) {
      var item = e.target.closest('[data-theme-id]');
      if (!item) return;
      apply(item.getAttribute('data-theme-id'), current().mode);
      closeMenu();
    });
    updatePickerUI(current().themeId);
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
  }

  function closeMenu() {
    var menu = document.getElementById('theme-picker-menu');
    var trigger = document.getElementById('theme-picker-trigger');
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
  }

  function wirePicker() {
    var trigger = document.getElementById('theme-picker-trigger');
    if (!trigger) return;
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      var menu = document.getElementById('theme-picker-menu');
      if (menu && menu.hidden) { openMenu(); } else { closeMenu(); }
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('#theme-picker')) closeMenu();
    });
  }

  function bindSession(session) {
    if (!bus) return;
    bus.attach(session);
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
    if (theme && theme.mapping) bindMapping(theme);
  }

  function init() {
    var pref = readPref();
    apply(pref.themeId, pref.mode);
    buildPicker();
    wirePicker();
    window.addEventListener('storage', onStorage);
    if (window.EffectLevel) window.EffectLevel.onChange(reapplyEffectLevel);
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
