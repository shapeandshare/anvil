(function() {
  'use strict';

  function SamplingWidget(container) {
    this.container = container;
    this._temperature = 0.5;
    this._topK = 5;
    this._render();
  }

  SamplingWidget.prototype._render = function() {
    this.container.innerHTML =
      '<label class="widget-label">Temperature: <span id="temp-value" class="token-value text-mono">' + this._temperature.toFixed(1) + '</span></label>' +
      '<input type="range" id="temp-slider" min="0" max="2" step="0.1" value="' + this._temperature + '" aria-label="Temperature">' +
      '<label class="widget-label">Top-K: <span id="topk-value" class="token-value text-mono">' + this._topK + '</span></label>' +
      '<input type="range" id="topk-slider" min="1" max="20" step="1" value="' + this._topK + '" aria-label="Top-K">' +
      '<div class="distribution-display" id="distribution" aria-live="polite"></div>';
    var self = this;
    this.container.querySelector('#temp-slider').addEventListener('input', function() {
      self._temperature = parseFloat(this.value);
      self.container.querySelector('#temp-value').textContent = self._temperature.toFixed(1);
      self._update();
    });
    this.container.querySelector('#topk-slider').addEventListener('input', function() {
      self._topK = parseInt(this.value);
      self.container.querySelector('#topk-value').textContent = self._topK;
      self._update();
    });
    this._update();
  };

  SamplingWidget.prototype._update = function() {
    var tokens = ['the', 'a', 'an', 'and', 'of', 'to', 'in'];
    var raw = tokens.map(function(_, i) {
      return Math.exp(-i / (this._temperature * 2 + 0.1)) * (0.5 + Math.random() * 0.5);
    }, this);
    var sum = raw.reduce(function(a, b) { return a + b; }, 0);
    var probs = raw.map(function(v) { return v / sum; });
    var sorted = tokens.map(function(t, i) { return { token: t, prob: probs[i] }; })
      .sort(function(a, b) { return b.prob - a.prob; })
      .slice(0, this._topK);
    var html = '<div class="dist-bars">';
    sorted.forEach(function(s) {
      html += '<div class="dist-row">' +
        '<span class="dist-label text-mono">' + s.token + '</span>' +
        '<div class="dist-bar-track"><div class="dist-bar-fill" style="width:' + (s.prob * 100) + '%"></div></div>' +
        '<span class="dist-prob text-mono">' + (s.prob * 100).toFixed(1) + '%</span>' +
        '</div>';
    });
    html += '</div>';
    this.container.querySelector('#distribution').innerHTML = html;
  };

  window.SamplingWidget = SamplingWidget;
})();