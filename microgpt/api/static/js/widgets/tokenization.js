(function () {
  'use strict';

  function TokenizationWidget(container) {
    this.container = container;
    this._debounceTimer = null;
    this._render();
  }

  TokenizationWidget.prototype._render = function () {
    this.container.innerHTML =
      '<label class="widget-label">Type text to tokenize — model splits it into known tokens:</label>' +
      '<input type="text" class="widget-input" id="token-input" value="Hello" aria-label="Input text to tokenize" maxlength="32">' +
      '<div class="token-stats" id="token-stats" aria-live="polite"></div>' +
      '<div class="token-output" id="token-output" aria-live="polite"></div>' +
      '<div class="widget-empty-state" id="token-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">Couldn\'t load tokenizer data — <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '</div>';
    var self = this;
    var input = this.container.querySelector('#token-input');
    input.addEventListener('input', function () {
      self._debouncedFetch(this.value);
    });
    this._fetchTokens(input.value);
  };

  TokenizationWidget.prototype._debouncedFetch = function (text) {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () {
      self._fetchTokens(text);
    }, 250);
  };

  TokenizationWidget.prototype._fetchTokens = function (text) {
    var self = this;
    var output = this.container.querySelector('#token-output');
    var stats = this.container.querySelector('#token-stats');
    var empty = this.container.querySelector('#token-empty');
    if (!text) {
      output.innerHTML = '';
      stats.innerHTML = '';
      empty.style.display = 'none';
      return;
    }

    output.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Tokenizing...</div>';
    stats.innerHTML = '';
    empty.style.display = 'none';

    fetch('/v1/inference/tokenize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error === 'no_model' || data.detail === 'No model available') {
          empty.style.display = '';
          output.innerHTML = '';
          stats.innerHTML = '';
          return;
        }
        self._renderTokens(data, stats, output);
      })
      .catch(function () {
        empty.style.display = '';
        output.innerHTML = '';
        stats.innerHTML = '';
      });
  };

  TokenizationWidget.prototype._renderTokens = function (data, statsEl, outputEl) {
    var tokens = data.tokens || [];
    var html = '<div class="token-list">';
    for (var i = 0; i < tokens.length; i++) {
      var t = tokens[i];
      var isBOS = t.char === '<BOS>';
      var displayChar = isBOS ? 'BOS' : (t.char === ' ' ? '\u2423' : t.char);
      html += '<span class="token-chip' + (isBOS ? ' token-chip-bos' : '') + '">' +
        '<span class="token-value">' + this._escapeHtml(displayChar) + '</span>' +
        '<span class="token-id">' + t.id + '</span></span>';
    }
    html += '</div>';
    outputEl.innerHTML = html;
    statsEl.innerHTML = '<span class="token-stats-label">vocab: ' + data.vocab_size + ' tokens &middot; BOS id: ' + (data.bos_id !== undefined ? data.bos_id : '—') + '</span>';
  };

  TokenizationWidget.prototype._escapeHtml = function (str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  };

  window.TokenizationWidget = TokenizationWidget;
})();