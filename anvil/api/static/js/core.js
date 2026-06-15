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
    var raw;
    try {
      raw = sessionStorage.getItem(SS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (_) { return {}; }
  }

  function setSessionState(key, val) {
    var state;
    try {
      state = getSessionState();
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

  /* ── Client-Side Navigation ──────────────────────────── */
  /* Intercepts .tab-item clicks → fetch page HTML → swap <main> content.
   * Preserves page-specific scripts, CSS, and back/forward history. */

  var _origSetInterval = window.setInterval.bind(window);
  var _navIntervalIds = [];

  window.setInterval = function() {
    var id = _origSetInterval.apply(window, arguments);
    _navIntervalIds.push(id);
    return id;
  };

  var _navAbort = null;

  function _clearNavIntervals() {
    _navIntervalIds.forEach(function(id) { clearInterval(id); });
    _navIntervalIds = [];
  }

  function _hasLink(href) {
    var links = document.querySelectorAll('link[rel="stylesheet"]');
    var i;
    for (i = 0; i < links.length; i++) {
      if (links[i].getAttribute('href') === href) return true;
    }
    return false;
  }

  /* Re-executes <script> elements inside a container (scripts in
   * innerHTML are created as DOM nodes but never executed). */
  function _execScripts(container) {
    var scripts = container.querySelectorAll('script');
    var i, j, oldScript, newScript, attr;
    for (i = 0; i < scripts.length; i++) {
      oldScript = scripts[i];
      newScript = document.createElement('script');
      for (j = 0; j < oldScript.attributes.length; j++) {
        attr = oldScript.attributes[j];
        newScript.setAttribute(attr.name, attr.value);
      }
      newScript.textContent = oldScript.textContent;
      oldScript.parentNode.replaceChild(newScript, oldScript);
    }
  }

  function loadContent(url, updateHistory) {
    if (url === window.location.pathname + window.location.search) return;

    if (_navAbort) _navAbort.abort();
    _navAbort = new AbortController();

    _clearNavIntervals();

    fetch(url, {
      signal: _navAbort.signal,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var doc, newMain, currentMain, head, href, clone, afterCore, ns, i, j, link, s, tab, attr;

        doc = new DOMParser().parseFromString(html, 'text/html');

        /* 1. Replace <main> content */
        newMain = doc.querySelector('.app-main');
        currentMain = document.querySelector('.app-main');
        if (!newMain || !currentMain) return;
        currentMain.innerHTML = newMain.innerHTML;

        /* 2. Re-execute inline scripts from the new content */
        _execScripts(currentMain);

        /* 3. Swap page-specific CSS (extra_css block) */
        head = document.head;
        head.querySelectorAll('link[data-nav-css]')
          .forEach(function(el) { el.remove(); });
        doc.querySelectorAll('link[rel="stylesheet"]').forEach(function(link) {
          href = link.getAttribute('href');
          if (!_hasLink(href)) {
            clone = link.cloneNode();
            clone.setAttribute('data-nav-css', '');
            head.appendChild(clone);
          }
        });

        /* 4. Execute scripts from {% block scripts %} (after core.js) */
        afterCore = false;
        doc.querySelectorAll('script').forEach(function(s) {
          if (!afterCore) {
            if (s.getAttribute('src') === '/static/js/core.js') {
              afterCore = true;
            }
            return;
          }
          ns = document.createElement('script');
          for (j = 0; j < s.attributes.length; j++) {
            attr = s.attributes[j];
            ns.setAttribute(attr.name, attr.value);
          }
          ns.textContent = s.textContent;
          document.body.appendChild(ns);
        });

        /* 5. Update browser history */
        if (updateHistory) {
          history.pushState({ path: url }, '', url);
        }

        /* 6. Update active nav tab */
        document.querySelectorAll('.tab-item').forEach(function(tab) {
          tab.classList.toggle('active', tab.getAttribute('href') === url);
        });

        /* 7. Scroll to top */
        window.scrollTo(0, 0);
      })
      .catch(function(err) {
        if (err.name === 'AbortError') return;
        window.location.href = url;
      });
  }

  /* ── Event wiring ─────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    initNav();

    /* Initialise history state so popstate at root works */
    if (!history.state) {
      history.replaceState({ path: window.location.pathname }, '', window.location.href);
    }

    /* Intercept nav clicks */
    document.addEventListener('click', function(e) {
      var tab = e.target.closest('.tab-item');
      if (!tab) return;
      var href = tab.getAttribute('href');
      if (!href || href.indexOf(':') !== -1 || href.charAt(0) === '#') return;
      e.preventDefault();
      loadContent(href, true);
    });

    /* Back / forward */
    window.addEventListener('popstate', function(e) {
      if (e.state && e.state.path) {
        loadContent(e.state.path, false);
      }
    });

    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggleTheme);
  });

  window.core = {
    toggleTheme: toggleTheme,
    getUrlParams: getUrlParams,
    setUrlParams: setUrlParams,
    loadContent: loadContent,
  };
})();