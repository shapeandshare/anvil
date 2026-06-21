// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function AttentionWidget(container) {
    this.container = container;
    this._data = null;
    this._activeLayer = 0;
    this._activeHead = 0;
    this._debounceTimer = null;
    this._highlightedQuery = -1;
    this._render();
  }

  AttentionWidget.prototype._render = function () {
    this.container.innerHTML =
      '<label class="widget-label">Attention heatmap — type text to see real attention weights:</label>' +
      '<textarea class="widget-input widget-textarea" id="attn-input" aria-label="Input text for attention" rows="2">the quick fox</textarea>' +
      '<div class="heatmap-controls" id="heatmap-controls" style="display:none">' +
      '  <label class="heatmap-select-label">Layer: <select id="layer-select" class="heatmap-select" aria-label="Select attention layer"></select></label>' +
      '  <label class="heatmap-select-label">Head: <select id="head-select" class="heatmap-select" aria-label="Select attention head"></select></label>' +
      '</div>' +
      '<div class="heatmap-wrapper">' +
      '  <canvas id="attn-canvas" class="attn-canvas" tabindex="0" aria-label="Attention weight heatmap grid, use arrow keys to navigate"></canvas>' +
      '</div>' +
      '<div class="heatmap-legend" id="heatmap-legend" aria-hidden="true">' +
      '  <span class="legend-label">0</span>' +
      '  <div class="legend-bar"></div>' +
      '  <span class="legend-label">1</span>' +
      '</div>' +
      '<div class="attn-info" id="attn-info" aria-live="polite"></div>' +
      '<div class="widget-empty-state" id="attn-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">Couldn\'t load attention data — <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '</div>';
    this._canvas = this.container.querySelector('#attn-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._infoEl = this.container.querySelector('#attn-info');
    this._emptyEl = this.container.querySelector('#attn-empty');
    this._controlsEl = this.container.querySelector('#heatmap-controls');
    this._layerSelect = this.container.querySelector('#layer-select');
    this._headSelect = this.container.querySelector('#head-select');

    var self = this;
    var input = this.container.querySelector('#attn-input');

    function autoResize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    }

    input.addEventListener('input', function () {
      autoResize();
      self._debouncedFetch(this.value);
    });

    if (this._layerSelect) {
      this._layerSelect.addEventListener('change', function () {
        self._activeLayer = parseInt(this.value);
        self._drawHeatmap();
      });
    }
    if (this._headSelect) {
      this._headSelect.addEventListener('change', function () {
        self._activeHead = parseInt(this.value);
        self._drawHeatmap();
      });
    }

    this._bindKeys();

    /* Set initial textarea height for default value */
    autoResize();

    this._fetch(input.value);
  };

  AttentionWidget.prototype._debouncedFetch = function (text) {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () {
      self._fetch(text);
    }, 250);
  };

  AttentionWidget.prototype._fetch = function (text) {
    var self = this;
    if (!text) {
      this._clearCanvas();
      this._infoEl.innerHTML = '';
      this._emptyEl.style.display = 'none';
      this._controlsEl.style.display = 'none';
      return;
    }

    this._clearCanvas();
    this._infoEl.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Computing attention...</div>';
    this._emptyEl.style.display = 'none';

    fetch('/v1/inference/attention', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error === 'no_model' || data.detail === 'No model available') {
          self._emptyEl.style.display = '';
          self._infoEl.innerHTML = '';
          self._controlsEl.style.display = 'none';
          return;
        }
        self._data = data;
        self._activeLayer = 0;
        self._activeHead = 0;
        self._highlightedQuery = -1;
        self._populateSelectors();
        self._drawHeatmap();
      })
      .catch(function () {
        self._emptyEl.style.display = '';
        self._infoEl.innerHTML = '';
        self._controlsEl.style.display = 'none';
      });
  };

  AttentionWidget.prototype._populateSelectors = function () {
    if (!this._data) return;
    var nLayer = this._data.n_layer || 1;
    var nHead = this._data.n_head || 1;

    if (nLayer > 1 || nHead > 1) {
      this._controlsEl.style.display = 'flex';
    } else {
      this._controlsEl.style.display = 'none';
    }

    /* Populate layer select */
    if (this._layerSelect) {
      this._layerSelect.innerHTML = '';
      for (var i = 0; i < nLayer; i++) {
        var opt = document.createElement('option');
        opt.value = i;
        opt.textContent = 'Layer ' + (i + 1);
        if (i === this._activeLayer) opt.selected = true;
        this._layerSelect.appendChild(opt);
      }
    }

    /* Populate head select */
    if (this._headSelect) {
      this._headSelect.innerHTML = '';
      for (var i = 0; i < nHead; i++) {
        var opt = document.createElement('option');
        opt.value = i;
        opt.textContent = 'Head ' + (i + 1);
        if (i === this._activeHead) opt.selected = true;
        this._headSelect.appendChild(opt);
      }
    }
  };

  AttentionWidget.prototype._clearCanvas = function () {
    if (this._ctx) {
      this._ctx.setTransform(1, 0, 0, 1, 0, 0);
      this._ctx.clearRect(0, 0, this._canvas.width || 300, this._canvas.height || 200);
    }
  };

  AttentionWidget.prototype._drawHeatmap = function () {
    var ctx = this._ctx;
    if (!ctx || !this._data) return;
    var weights = this._data.weights;
    if (!weights || weights.length === 0) {
      this._clearCanvas();
      this._infoEl.innerHTML = '<span class="widget-hint">No attention weights available</span>';
      return;
    }

    var tokens = this._data.tokens || [];
    var layerWeights = weights[this._activeLayer];
    if (!layerWeights || !layerWeights[this._activeHead]) {
      this._clearCanvas();
      return;
    }
    var headWeights = layerWeights[this._activeHead];
    var n = headWeights.length;
    if (n === 0) return;

    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue('--accent').trim() || '#3b82f6';
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var textColor = style.getPropertyValue('--text').trim() || '#e8eaed';
    var bg = style.getPropertyValue('--surface').trim() || '#181a1f';

    /* Layout */
    var labelW = 36;
    var labelH = 14;
    var cellSize = Math.max(22, Math.min(40, Math.floor((this.container.clientWidth - labelW - 20) / n)));
    var gridW = cellSize * n;
    var gridH = cellSize * n;
    var totalW = labelW + gridW + 10;
    var totalH = labelH + gridH + 10;

    var dpr = window.devicePixelRatio || 1;
    this._canvas.width = totalW * dpr;
    this._canvas.height = totalH * dpr;
    this._canvas.style.width = totalW + 'px';
    this._canvas.style.height = totalH + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, totalW, totalH);

    /* Column labels (key tokens) along top */
    ctx.fillStyle = muted;
    ctx.font = '9px "SF Mono","Fira Code",monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    for (var j = 0; j < n; j++) {
      var label = this._tokenLabel(tokens, j);
      var lx = labelW + j * cellSize + cellSize / 2;
      ctx.save();
      ctx.translate(lx, labelH - 2);
      ctx.rotate(-Math.PI / 4);
      ctx.fillText(label, 0, 0);
      ctx.restore();
    }

    /* Row labels (query tokens) on left */
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.font = '9px "SF Mono","Fira Code",monospace';
    for (var i = 0; i < n; i++) {
      var label = this._tokenLabel(tokens, i);
      ctx.fillStyle = (i === this._highlightedQuery) ? textColor : muted;
      ctx.fillText(label, labelW - 4, labelH + i * cellSize + cellSize / 2);
    }

    /* Heatmap cells — lower triangular (causal) attention */
    for (var qi = 0; qi < n; qi++) {
      var rowLen = headWeights[qi] ? headWeights[qi].length : 0;
      for (var ki = 0; ki < n; ki++) {
        var x = labelW + ki * cellSize;
        var y = labelH + qi * cellSize;
        var isHighlighted = qi === this._highlightedQuery;

        if (ki <= qi && ki < rowLen) {
          /* Real attention weight cell */
          var w = headWeights[qi][ki];
          var val = (typeof w === 'object' && w !== null && 'data' in w) ? w.data : w;
          if (val === undefined || val === null) val = 0;

          var fillColor = this._interpolateColor(bg, accent, val);
          ctx.fillStyle = fillColor;
          ctx.fillRect(x + 1, y + 1, cellSize - 2, cellSize - 2);

          if (isHighlighted) {
            ctx.strokeStyle = textColor;
            ctx.lineWidth = 1.5;
            ctx.strokeRect(x + 1, y + 1, cellSize - 2, cellSize - 2);
          }

          ctx.fillStyle = val > 0.5 ? '#fff' : muted;
          ctx.font = '8px "SF Mono","Fira Code",monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText((val * 100).toFixed(0), x + cellSize / 2, y + cellSize / 2);
        } else {
          /* Empty cell — future token not yet attended to at this query position */
          if (isHighlighted) {
            ctx.strokeStyle = muted;
            ctx.lineWidth = 0.5;
            ctx.setLineDash([2, 3]);
            ctx.strokeRect(x + 1.5, y + 1.5, cellSize - 3, cellSize - 3);
            ctx.setLineDash([]);
          } else {
            ctx.strokeStyle = muted;
            ctx.lineWidth = 0.5;
            ctx.setLineDash([1, 3]);
            ctx.strokeRect(x + 1.5, y + 1.5, cellSize - 3, cellSize - 3);
            ctx.setLineDash([]);
          }
        }
      }
    }

    this._infoEl.innerHTML = '<span class="token-stats-label">' + n + ' tokens &middot; ' +
      (this._data.n_layer || 1) + ' layers &middot; ' + (this._data.n_head || 1) + ' heads' +
      '<br><span style="font-size:0.6rem;color:var(--text-muted);">Each token attends to itself and all preceding tokens (causal/prefix attention). ' +
      'Upper-right cells with dotted outlines are future positions that do not exist yet for that query.</span>' +
      (this._highlightedQuery >= 0 ? '<br>query token: "' + this._tokenLabel(tokens, this._highlightedQuery) + '" highlighted' : '') +
      '</span>';
  };

  AttentionWidget.prototype._tokenLabel = function (tokens, idx) {
    if (!tokens || idx >= tokens.length) return '?';
    var t = tokens[idx];
    var char = t.char;
    if (char === '<BOS>') return 'BOS';
    if (char === ' ') return '\u2423';
    return char;
  };

  AttentionWidget.prototype._interpolateColor = function (colorA, colorB, t) {
    /* Parse hex colors to RGB, interpolate by t (0-1) */
    var r1 = parseInt(colorA.slice(1, 3), 16) || 24;
    var g1 = parseInt(colorA.slice(3, 5), 16) || 26;
    var b1 = parseInt(colorA.slice(5, 7), 16) || 31;
    var r2 = parseInt(colorB.slice(1, 3), 16) || 59;
    var g2 = parseInt(colorB.slice(3, 5), 16) || 130;
    var b2 = parseInt(colorB.slice(5, 7), 16) || 246;
    var r = Math.round(r1 + (r2 - r1) * t);
    var g = Math.round(g1 + (g2 - g1) * t);
    var b = Math.round(b1 + (b2 - b1) * t);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  };

  AttentionWidget.prototype._bindKeys = function () {
    var self = this;
    this._canvas.addEventListener('keydown', function (e) {
      if (!self._data) return;
      var weights = self._data.weights;
      if (!weights || weights.length === 0) return;
      var headWeights = weights[self._activeLayer] && weights[self._activeLayer][self._activeHead];
      if (!headWeights) return;
      var n = headWeights.length;
      if (n === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        self._highlightedQuery = Math.min(n - 1, self._highlightedQuery + 1);
        self._drawHeatmap();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        self._highlightedQuery = Math.max(-1, self._highlightedQuery - 1);
        self._drawHeatmap();
      }
    });
  };

  window.AttentionWidget = AttentionWidget;
})();