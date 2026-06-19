(function() {
  'use strict';

  function initTheme() {
    var theme = localStorage.getItem('theme');
    if (!theme) {
      theme = 'dark';
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

        /* 7. Restart did-you-know timer for new page */
        initDidYouKnow();

        /* 8. Re-init tooltips — content was swapped */
        initTooltips();

        /* 9. Scroll to top */
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
    initDidYouKnow();
    initTooltips();

    /* Initialise history state so popstate at root works */
    if (!history.state) {
      history.replaceState({ path: window.location.pathname }, '', window.location.href);
    }

    /* Intercept nav clicks — handles both nav-bar tabs and hero-page cards */
    document.addEventListener('click', function(e) {
      var link = e.target.closest('.tab-item, .hero-card, .hero-cta, .hero-secondary');
      if (!link) return;
      var href = link.getAttribute('href');
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

  /* ── Did You Know? Rotator ───────────────────────────── */
  var DID_YOU_KNOW = [
    'Each training step, the model compares its prediction against the actual next character and adjusts its weights by a tiny amount.',
    'The &ldquo;loss&rdquo; you see is <strong>cross-entropy</strong> &mdash; it measures how surprised the model is by the actual next character.',
    'With <strong>4 heads of attention</strong>, this tiny transformer can focus on up to 4 different positions simultaneously.',
    'RoPE encodes position by <strong>rotating pairs of embedding dimensions</strong> &mdash; no learned position table needed.',
    'The <strong>SwiGLU</strong> activation uses a gating mechanism: one path decides what to pass, another provides the value.',
    '<strong>RMSNorm</strong> normalizes each token&rsquo;s representation by its root-mean-square, then scales by a learned parameter.',
    'The <strong>temperature</strong> parameter controls randomness: 0 = always pick the most likely token, 2 = near-random chaos.',
    'The demo model trains on <strong>medieval guild names</strong> &mdash; &ldquo;The Guild of Witcheraft &amp; Brewers&rdquo; and friends.',
    'Tokenization here is <strong>character-level</strong>: every unique character in the training data gets its own ID.',
    '<strong>Gradient descent</strong> works by taking small steps downhill on a high-dimensional error surface.',
    'The <strong>Adam optimizer</strong> keeps a moving average of both gradients (momentum) and squared gradients (adaptive LR).',
    'A single forward pass through this transformer involves about <strong>50,000 multiply-add operations</strong>.',
    'The <strong>attention mechanism</strong> computes a weighted sum where each token &ldquo;asks&rdquo; how relevant every other token is.',
    'With a context window of <strong>16 tokens</strong>, the model can only see 16 characters ahead at a time.',
  ];
  var _dykIndex = -1;
  var _dykTimer = null;
  var _dykBanner = null;

  function showDidYouKnow() {
    var el = document.getElementById('didyouknow-text');
    if (!el) return;
    _dykIndex = (_dykIndex + 1) % DID_YOU_KNOW.length;
    el.innerHTML = DID_YOU_KNOW[_dykIndex];
  }

  function initDidYouKnow() {
    if (_dykTimer) clearInterval(_dykTimer);
    if (!document.getElementById('didyouknow-banner')) return;
    showDidYouKnow();
    _dykTimer = setInterval(showDidYouKnow, 18000);
  }

  document.addEventListener('click', function(e) {
    if (e.target.closest && e.target.closest('.didyouknow__dismiss')) {
      _dykBanner = document.getElementById('didyouknow-banner');
      if (_dykBanner) _dykBanner.style.display = 'none';
    }
  });

  /* ── Smart Tooltip Positioning ────────────────────────── */

  function initTooltips() {
    document.querySelectorAll('.tooltip-trigger').forEach(function(trigger) {
      var content = trigger.querySelector('.tooltip-content');
      if (!content) return;

      trigger.addEventListener('mouseenter', function() {
        requestAnimationFrame(function() {
          var rect = content.getBoundingClientRect();
          var overflowRight = rect.right - window.innerWidth;
          var overflowLeft = -rect.left;
          var shift;

          if (overflowRight > 0) {
            shift = overflowRight + 12;
            content.style.setProperty('--tooltip-shift', (-shift) + 'px');
            content.style.setProperty('--tooltip-arrow-x', shift + 'px');
          } else if (overflowLeft > 0) {
            shift = overflowLeft + 12;
            content.style.setProperty('--tooltip-shift', shift + 'px');
            content.style.setProperty('--tooltip-arrow-x', (-shift) + 'px');
          }
        });
      });

      trigger.addEventListener('mouseleave', function() {
        content.style.removeProperty('--tooltip-shift');
        content.style.removeProperty('--tooltip-arrow-x');
      });
    });
  }

  window.core = {
    toggleTheme: toggleTheme,
    getUrlParams: getUrlParams,
    setUrlParams: setUrlParams,
    loadContent: loadContent,
    initDidYouKnow: initDidYouKnow,
    initTooltips: initTooltips,
  };
})();