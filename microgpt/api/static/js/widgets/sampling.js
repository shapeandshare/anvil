(function () {
  'use strict';

  function SamplingWidget(container) {
    this.container = container;
    this._temperature = 0.5;
    this._topK = 5;
    this._prompt = 'the';
    this._debounceTimer = null;
    this._render();
  }

  SamplingWidget.prototype._render = function () {
    this.container.innerHTML =
      '<label class="widget-label">Next-token probability distribution — adjust sampling controls:</label>' +
      '<label class="widget-label" style="margin-top:var(--space-2);">Prompt: <span class="text-mono">' + this._prompt + '</span></label>' +
      '<label class="widget-label">Temperature: <span id="temp-value" class="token-value text-mono">' + this._temperature.toFixed(1) + '</span></label>' +
      '<input type="range" class="widget-slider" id="temp-slider" min="0" max="2" step="0.1" value="' + this._temperature + '" aria-label="Temperature">' +
      '<label class="widget-label">Top-K: <span id="topk-value" class="token-value text-mono">' + this._topK + '</span></label>' +
      '<input type="range" class="widget-slider" id="topk-slider" min="1" max="20" step="1" value="' + this._topK + '" aria-label="Top-K">' +
      '<div class="distribution-display" id="distribution" aria-live="polite"></div>' +
      '<div class="widget-empty-state" id="sample-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">Couldn\'t load sampling distribution — <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '</div>';
    var self = this;
    var tempSlider = this.container.querySelector('#temp-slider');
    var topkSlider = this.container.querySelector('#topk-slider');
    this._distEl = this.container.querySelector('#distribution');
    this._emptyEl = this.container.querySelector('#sample-empty');

    tempSlider.addEventListener('input', function () {
      self._temperature = parseFloat(this.value);
      self.container.querySelector('#temp-value').textContent = self._temperature.toFixed(1);
      self._debouncedFetch();
    });
    topkSlider.addEventListener('input', function () {
      self._topK = parseInt(this.value);
      self.container.querySelector('#topk-value').textContent = self._topK;
      self._debouncedFetch();
    });
    this._fetch();
  };

  SamplingWidget.prototype._debouncedFetch = function () {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () {
      self._fetch();
    }, 250);
  };

  SamplingWidget.prototype._fetch = function () {
    var self = this;
    this._distEl.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Sampling...</div>';
    this._emptyEl.style.display = 'none';

    fetch('/v1/inference/sampling-distribution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: this._prompt,
        temperature: this._temperature,
        top_k: this._topK
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error === 'no_model' || data.detail === 'No model available') {
          self._emptyEl.style.display = '';
          self._distEl.innerHTML = '';
          return;
        }
        self._renderDistribution(data);
      })
      .catch(function () {
        self._emptyEl.style.display = '';
        self._distEl.innerHTML = '';
      });
  };

  SamplingWidget.prototype._renderDistribution = function (data) {
    var tokens = data.tokens || [];
    if (tokens.length === 0) {
      this._distEl.innerHTML = '<span class="widget-hint">No distribution data returned</span>';
      return;
    }

    var html = '<div class="dist-bars">';
    var maxProb = 0;
    for (var i = 0; i < tokens.length; i++) {
      if (tokens[i].prob > maxProb) maxProb = tokens[i].prob;
    }
    for (var i = 0; i < tokens.length; i++) {
      var t = tokens[i];
      var char = t.char;
      if (char === '<BOS>') char = 'BOS';
      if (char === ' ') char = '\u2423';
      if (char === '\n') char = '\\n';
      var pct = (t.prob * 100).toFixed(1);
      var barW = maxProb > 0 ? (t.prob / maxProb) * 100 : 0;
      html += '<div class="dist-row">' +
        '<span class="dist-label text-mono">' + this._escapeHtml(char) + '</span>' +
        '<div class="dist-bar-track">' +
        '  <div class="dist-bar-fill" style="width:' + barW + '%"></div>' +
        '</div>' +
        '<span class="dist-prob text-mono">' + pct + '%</span>' +
        '</div>';
    }
    html += '</div>';

    html += '<div class="token-stats-label" style="margin-top:var(--space-2);">' +
      'temperature: ' + data.temperature.toFixed(1) + ' &middot; top-' + (data.top_k || tokens.length) +
      ' &middot; ' + tokens.length + ' tokens shown' +
      '</div>';

    this._distEl.innerHTML = html;
  };

  SamplingWidget.prototype._escapeHtml = function (str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  };

  window.SamplingWidget = SamplingWidget;
})();