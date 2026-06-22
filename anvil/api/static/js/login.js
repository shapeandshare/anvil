// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

// Login page JS — submits API key via POST /login, redirects on success.

(function () {
  'use strict';

  var form = document.getElementById('login-form');
  var input = document.getElementById('api-key');
  var errorEl = document.getElementById('login-error');
  var submitBtn = form.querySelector('button[type="submit"]');

  if (!form || !input || !errorEl || !submitBtn) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var apiKey = input.value.trim();
    if (!apiKey) {
      showError('Please enter your API key.');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Signing in\u2026';
    hideError();

    fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey }),
    })
      .then(function (r) {
        if (r.ok) {
          window.location.href = '/';
        } else if (r.status === 429) {
          showError('Too many attempts. Please wait and try again.');
        } else {
          return r.json().then(function (data) {
            showError(data.detail || 'Invalid API key.');
          });
        }
      })
      .catch(function () {
        showError('Connection error. Please try again.');
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In';
      });
  });

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = false;
  }

  function hideError() {
    errorEl.textContent = '';
    errorEl.hidden = true;
  }
})();
