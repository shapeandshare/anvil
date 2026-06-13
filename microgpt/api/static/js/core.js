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
    if (btn) btn.textContent = theme;
  }

  function initNav() {
    var path = window.location.pathname;
    document.querySelectorAll('.app-tab').forEach(function(tab) {
      var target = tab.getAttribute('data-target');
      if (path === target || (target === '/v1' && (path === '/' || path === '/v1'))) {
        tab.classList.add('active');
      }
      tab.addEventListener('click', function() {
        window.location.href = this.getAttribute('data-target');
      });
    });
  }

  function initClock() {
    function update() {
      var now = new Date();
      var h = now.getHours().toString().padStart(2, '0');
      var m = now.getMinutes().toString().padStart(2, '0');
      var s = now.getSeconds().toString().padStart(2, '0');
      var el = document.getElementById('status-time');
      if (el) el.textContent = h + ':' + m + ':' + s;
    }
    setInterval(update, 1000);
    update();
  }

  function initStatusBar() {
    function fetchStats() {
      fetch('/v1/registry/models').then(function(r) { return r.json(); }).then(function(d) {
        var el = document.getElementById('status-models');
        if (el) el.textContent = 'models: ' + (d.models ? d.models.length : 0);
      }).catch(function() {});
      fetch('/v1/experiments').then(function(r) { return r.json(); }).then(function(d) {
        var el = document.getElementById('status-experiments');
        if (el) el.textContent = 'exps: ' + (d.experiments ? d.experiments.length : 0);
      }).catch(function() {});
      fetch('/v1/datasets').then(function(r) { return r.json(); }).then(function(d) {
        var el = document.getElementById('status-datasets');
        if (el) el.textContent = 'datasets: ' + (d.datasets ? d.datasets.length : 0);
      }).catch(function() {});
    }
    fetchStats();
    setInterval(fetchStats, 15000);
  }

  function getUrlParams() {
    return new URLSearchParams(window.location.search);
  }

  function setUrlParams(params) {
    var qs = params.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '');
    window.history.replaceState({}, '', url);
  }

  document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    initNav();
    initClock();
    initStatusBar();
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggleTheme);
  });

  window.core = {
    toggleTheme: toggleTheme,
    getUrlParams: getUrlParams,
    setUrlParams: setUrlParams,
  };
})();