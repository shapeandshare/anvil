(function() {
  'use strict';

  function initTheme() {
    var theme = localStorage.getItem('theme');
    var osDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (!theme) {
      theme = osDark ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeUI(theme);
  }

  function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeUI(next);
  }

  function updateThemeUI(theme) {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var sun = btn.querySelector('.theme-icon--sun');
    var moon = btn.querySelector('.theme-icon--moon');
    if (sun) sun.classList.toggle('hidden', theme === 'dark');
    if (moon) moon.classList.toggle('hidden', theme === 'light');
  }

  function initNav() {
    var path = window.location.pathname;
    document.querySelectorAll('.tab-item').forEach(function(tab) {
      var href = tab.getAttribute('href');
      if (path === href) {
        tab.classList.add('active');
      }
    });
  }

  function getUrlParams() {
    return new URLSearchParams(window.location.search);
  }

  function setUrlParams(params) {
    var qs = params.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '');
    window.history.replaceState({}, '', url);
  }

  /* ── Session State ────────────────────────────────────── */
  /* Maintains workflow state across page navigations via sessionStorage.
   *
   * Keys (namespaced under 'anvil:workflow'):
   *   training: { runId, experimentId, mlflowRunId, status, config, metrics[], startedAt }
   *   import:   { datasetId, corpusId, status }
   */

  var SS_KEY = 'anvil:workflow';

  function getSessionState() {
    try {
      var raw = sessionStorage.getItem(SS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (_) { return {}; }
  }

  function setSessionState(key, val) {
    try {
      var state = getSessionState();
      if (val === null) {
        delete state[key];
      } else {
        state[key] = val;
      }
      sessionStorage.setItem(SS_KEY, JSON.stringify(state));
    } catch (_) {}
  }

  function getWorkflow(key) {
    return getSessionState()[key] || null;
  }

  window.coreSession = {
    getWorkflow: getWorkflow,
    setWorkflow: function(key, val) { setSessionState(key, val); },
    clearWorkflow: function(key) { setSessionState(key, null); },
    addRun: function(runId, data) {
      var state = getSessionState();
      var runs = state.training && state.training.runs ? state.training.runs : {};
      runs[runId] = data;
      state.training = { runs: runs, currentRunId: runId };
      sessionStorage.setItem(SS_KEY, JSON.stringify(state));
    },
    updateRun: function(runId, data) {
      var state = getSessionState();
      if (!state.training || !state.training.runs || !state.training.runs[runId]) return;
      state.training.runs[runId] = data;
      sessionStorage.setItem(SS_KEY, JSON.stringify(state));
    },
    removeRun: function(runId) {
      var state = getSessionState();
      if (!state.training || !state.training.runs) return;
      delete state.training.runs[runId];
      var remaining = Object.keys(state.training.runs);
      if (remaining.length === 0) {
        delete state.training;
      } else {
        state.training.currentRunId = remaining[remaining.length - 1];
      }
      sessionStorage.setItem(SS_KEY, JSON.stringify(state));
    },
    getActiveRuns: function() {
      var state = getSessionState();
      if (!state.training || !state.training.runs) return {};
      return state.training.runs;
    },
    getCurrentRunId: function() {
      var state = getSessionState();
      return state.training ? state.training.currentRunId : null;
    },
    clearAll: function() {
      try { sessionStorage.removeItem(SS_KEY); } catch (_) {}
    },
  };

  document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    initNav();
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggleTheme);
  });

  window.core = {
    toggleTheme: toggleTheme,
    getUrlParams: getUrlParams,
    setUrlParams: setUrlParams,
  };
})();