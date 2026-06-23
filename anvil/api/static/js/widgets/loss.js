// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function LossWidget(container) {
    this.container = container;
    this._data = null;
    this._debounceTimer = null;
    this._render();
  }

  LossWidget.prototype._render = function () {
    this.container.innerHTML =
      '<label class="widget-label">Per-token loss breakdown — type text to see cross-entropy per token:</label>' +
      '<input type="text" class="widget-input" id="loss-input" value="the quick fox" aria-label="Input text for loss breakdown" maxlength="32">' +
      '<canvas id="loss-canvas" class="loss-canvas" aria-label="Per-token cross-entropy bar chart"></canvas>' +
      '<div class="loss-stats" id="loss-stats" aria-live="polite"></div>' +
      '<div class="widget-empty-state" id="loss-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">Couldn\'t load loss data — <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '</div>';
    this._canvas = this.container.querySelector('#loss-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._statsEl = this.container.querySelector('#loss-stats');
    this._emptyEl = this.container.querySelector('#loss-empty');

    var self = this;
    var input = this.container.querySelector('#loss-input');
    input.addEventListener('input', function () {
      self._debouncedFetch(this.value);
    });

    this._fetch(input.value);
  };

  LossWidget.prototype._debouncedFetch = function (text) {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () {
      self._fetch(text);
    }, 250);
  };

  LossWidget.prototype._fetch = function (text) {
    var self = this;
    if (!text) {
      this._clearCanvas();
      this._statsEl.innerHTML = '';
      this._emptyEl.style.display = 'none';
      return;
    }

    this._clearCanvas();
    this._statsEl.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Computing loss...</div>';
    this._emptyEl.style.display = 'none';

    window.apiFetch('/v1/inference/loss-breakdown', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error === 'no_model' || data.detail === 'No model available') {
          self._emptyEl.style.display = '';
          self._statsEl.innerHTML = '';
          return;
        }
        self._data = data;
        self._drawChart();
      })
      .catch(function () {
        self._emptyEl.style.display = '';
        self._statsEl.innerHTML = '';
      });
  };

  LossWidget.prototype._clearCanvas = function () {
    if (this._ctx) {
      this._ctx.setTransform(1, 0, 0, 1, 0, 0);
      this._ctx.clearRect(0, 0, this._canvas.width || 300, this._canvas.height || 200);
    }
  };

  LossWidget.prototype._resizeCanvas = function () {
    var w = this.container.clientWidth || 300;
    var h = Math.min(200, Math.max(120, w * 0.35));
    var dpr = window.devicePixelRatio || 1;
    this._canvas.width = w * dpr;
    this._canvas.height = h * dpr;
    this._canvas.style.width = '100%';
    this._canvas.style.height = h + 'px';
    this._chartW = w;
    this._chartH = h;
    this._dpr = dpr;
  };

  LossWidget.prototype._drawChart = function () {
    var ctx = this._ctx;
    if (!ctx || !this._data) return;
    var tokens_raw = this._data.tokens || [];
    var losses = this._data.losses || [];
    /* Support both string[] and {char, id}[] formats */
    var tokens = tokens_raw.map(function (t) {
      return typeof t === 'string' ? t : t.char;
    });
    var vocabSize = this._data.vocab_size || 0;
    var avgLoss = this._data.average_loss || 0;
    if (tokens.length === 0 || losses.length === 0) {
      this._clearCanvas();
      this._statsEl.innerHTML = '<span class="widget-hint">No loss data returned</span>';
      return;
    }

    this._resizeCanvas();
    var w = this._chartW;
    var h = this._chartH;
    var dpr = this._dpr || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var style = getComputedStyle(document.documentElement);
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var border = style.getPropertyValue('--border').trim() || '#2a2c32';
    var textColor = style.getPropertyValue('--text').trim() || '#e8eaed';
    var randomBaseline = vocabSize > 0 ? Math.log(vocabSize) : 0;
    var maxLoss = Math.max(randomBaseline, Math.max.apply(null, losses)) * 1.15;

    var pad = { top: 10, right: 10, bottom: 24, left: 48 };
    var plotW = w - pad.left - pad.right;
    var plotH = h - pad.top - pad.bottom;
    if (plotW <= 0 || plotH <= 0) return;

    var barW = Math.max(4, Math.min(24, (plotW - (tokens.length - 1) * 2) / tokens.length));

    /* Draw axes */
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left, pad.top + plotH);
    ctx.lineTo(pad.left + plotW, pad.top + plotH);
    ctx.stroke();

    /* Y-axis labels */
    ctx.fillStyle = muted;
    ctx.font = '9px "SF Mono","Fira Code",monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    var yTicks = 4;
    for (var i = 0; i <= yTicks; i++) {
      var val = (i / yTicks) * maxLoss;
      var y = pad.top + plotH - (i / yTicks) * plotH;
      ctx.fillText(val.toFixed(2), pad.left - 4, y);
    }

    /* X-axis labels (token chars) */
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.font = '8px "SF Mono","Fira Code",monospace';

    /* Draw bars */
    for (var i = 0; i < losses.length; i++) {
      var l = losses[i];
      var barH = (l / maxLoss) * plotH;
      var bx = pad.left + i * (barW + 2);
      var by = pad.top + plotH - barH;

      /* Color: green near 0, red near maxLoss */
      var t = Math.min(1, l / maxLoss);
      var r = Math.round(34 + (239 - 34) * t);
      var g = Math.round(197 + (68 - 197) * t);
      var b = Math.round(94 + (68 - 94) * t);
      ctx.fillStyle = 'rgb(' + r + ',' + g + ',' + b + ')';
      ctx.fillRect(bx, by, barW, barH);

      /* Token label below bar */
      var char = tokens[i] === ' ' ? '\u2423' : tokens[i];
      if (char === '<BOS>') char = 'BOS';
      ctx.fillStyle = muted;
      ctx.fillText(char, bx + barW / 2, pad.top + plotH + 4);
    }

    /* Average loss — dashed horizontal line */
    var avgY = pad.top + plotH - (avgLoss / maxLoss) * plotH;
    ctx.strokeStyle = textColor;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, avgY);
    ctx.lineTo(pad.left + plotW, avgY);
    ctx.stroke();
    ctx.setLineDash([]);

    /* Annotate average loss */
    ctx.fillStyle = textColor;
    ctx.font = 'bold 9px "SF Mono","Fira Code",monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillText('avg: ' + avgLoss.toFixed(4), pad.left + 4, avgY - 2);

    /* Random-guess baseline — dotted line */
    var baseY = pad.top + plotH - (randomBaseline / maxLoss) * plotH;
    ctx.strokeStyle = muted;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, baseY);
    ctx.lineTo(pad.left + plotW, baseY);
    ctx.stroke();
    ctx.setLineDash([]);

    /* Annotate random baseline */
    ctx.fillStyle = muted;
    ctx.font = '8px "SF Mono","Fira Code",monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillText('random: ' + randomBaseline.toFixed(2) + ' (-log(1/' + vocabSize + '))', pad.left + plotW - 4, baseY + 2);

    /* Stats below */
    this._statsEl.innerHTML = '<div class="token-stats-label" style="margin-top:var(--space-1);">' +
      'vocab_size: ' + vocabSize + ' &middot; ' +
      'average_loss: ' + avgLoss.toFixed(4) + ' &middot; ' +
      'random_baseline: ' + randomBaseline.toFixed(4) +
      '</div>';
  };

  window.LossWidget = LossWidget;
})();
