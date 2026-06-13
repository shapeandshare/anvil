(function() {
  'use strict';

  function TokenizationWidget(container) {
    this.container = container;
    this._render();
  }

  TokenizationWidget.prototype._render = function() {
    this.container.innerHTML =
      '<label class="widget-label">Type text to tokenize:</label>' +
      '<input type="text" id="token-input" class="widget-input" value="Hello world" aria-label="Input text to tokenize">' +
      '<div class="token-output" id="token-output" aria-live="polite"></div>';
    var self = this;
    var input = this.container.querySelector('#token-input');
    input.addEventListener('input', function() {
      self._split(this.value);
    });
    this._split(input.value);
  };

  TokenizationWidget.prototype._split = function(text) {
    var tokens = [];
    for (var i = 0; i < text.length; i++) {
      tokens.push({ char: text[i], id: text.charCodeAt(i) });
    }
    var html = '<div class="token-list">';
    tokens.forEach(function(t) {
      html += '<span class="token-chip"><span class="token-value">' + t.char + '</span><span class="token-id">' + t.id + '</span></span>';
    });
    html += '</div>';
    var output = this.container.querySelector('#token-output');
    if (output) output.innerHTML = html;
  };

  window.TokenizationWidget = TokenizationWidget;
})();