// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function EmbeddingWidget(container) {
    this.container = container;
    this._data = null;
    this._selectedIndex = -1;
    this._debounceTimer = null;
    this._render();
  }

  EmbeddingWidget.prototype._render = function () {
    this.container.innerHTML =
      '<label class="widget-label">Embedding projection — type text to see token vectors in 2D:</label>' +
      '<div class="embedding-controls">' +
      '  <input type="text" class="widget-input" id="embed-input" value="the" aria-label="Input text to embed" maxlength="16">' +
      '</div>' +
      '<canvas id="embedding-canvas" class="embedding-canvas" tabindex="0" aria-label="2D embedding projection of token vectors"></canvas>' +
      '<div class="embedding-info" id="embedding-info" aria-live="polite"></div>' +
      '<p class="widget-hint text-mono">Arrow keys to highlight tokens &middot; labels show real token characters</p>' +
      '<div class="widget-empty-state" id="embed-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">Couldn\'t load embedding data — <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '</div>';
    this._canvas = this.container.querySelector('#embedding-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._infoEl = this.container.querySelector('#embedding-info');
    this._emptyEl = this.container.querySelector('#embed-empty');
    this._resize();
    this._bindKeys();
    var self = this;
    var input = this.container.querySelector('#embed-input');
    input.addEventListener('input', function () {
      self._debouncedFetch(this.value);
    });
    this._fetch(input.value);
  };

  EmbeddingWidget.prototype._resize = function () {
    var w = this.container.clientWidth || 300;
    var h = Math.min(280, Math.max(200, w * 0.55));
    this._canvas.width = w * window.devicePixelRatio || 1;
    this._canvas.height = h * window.devicePixelRatio || 1;
    this._canvas.style.height = h + 'px';
    this._w = w;
    this._h = h;
    this._dpr = window.devicePixelRatio || 1;
  };

  EmbeddingWidget.prototype._debouncedFetch = function (text) {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () {
      self._fetch(text);
    }, 250);
  };

  EmbeddingWidget.prototype._fetch = function (text) {
    var self = this;
    if (!text) { this._clearCanvas(); this._infoEl.innerHTML = ''; this._emptyEl.style.display = 'none'; return; }

    this._clearCanvas();
    this._infoEl.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Computing embeddings...</div>';
    this._emptyEl.style.display = 'none';

    window.apiFetch('/v1/inference/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (err) {
            throw new Error(err.detail || 'Embedding request failed');
          });
        }
        return r.json();
      })
      .then(function (data) {
        self._data = data;
        self._selectedIndex = -1;
        self._draw();
      })
      .catch(function (err) {
        var msg = err && err.message ? err.message : 'Embedding request failed';
        self._emptyEl.style.display = 'none';
        self._clearCanvas();
        self._infoEl.innerHTML = '<span class="widget-error">' + msg + '</span>';
      });
  };

  EmbeddingWidget.prototype._clearCanvas = function () {
    if (this._ctx) {
      this._ctx.setTransform(1, 0, 0, 1, 0, 0);
      this._ctx.clearRect(0, 0, this._canvas.width || 300, this._canvas.height || 200);
    }
  };

  EmbeddingWidget.prototype._draw = function () {
    var ctx = this._ctx;
    if (!ctx || !this._data) return;
    var projection = this._data.projection || [];
    if (projection.length === 0) {
      this._clearCanvas();
      this._infoEl.innerHTML = '<span class="widget-hint">No projection data for this input</span>';
      return;
    }

    var dpr = this._dpr || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, this._w, this._h);

    /* Compute bounds of projection points */
    var xs = projection.map(function (p) { return p.x; });
    var ys = projection.map(function (p) { return p.y; });
    var minX = Math.min.apply(null, xs);
    var maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, ys);
    var maxY = Math.max.apply(null, ys);

    /* Add padding */
    var padX = (maxX - minX) * 0.15 || 1;
    var padY = (maxY - minY) * 0.15 || 1;
    minX -= padX;
    maxX += padX;
    minY -= padY;
    maxY += padY;

    var scaleX = (this._w - 60) / (maxX - minX || 1);
    var scaleY = (this._h - 60) / (maxY - minY || 1);
    var scale = Math.min(scaleX, scaleY);

    var cx = this._w / 2;
    var cy = this._h / 2;
    var midX = (minX + maxX) / 2;
    var midY = (minY + maxY) / 2;

    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue('--accent').trim() || '#3b82f6';
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var textColor = style.getPropertyValue('--text').trim() || '#e8eaed';

    /* Draw grid lines */
    ctx.strokeStyle = muted;
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.15;
    for (var i = -5; i <= 5; i++) {
      var gx = cx + i * 30;
      ctx.beginPath();
      ctx.moveTo(gx, 10);
      ctx.lineTo(gx, this._h - 10);
      ctx.stroke();
      var gy = cy + i * 30;
      ctx.beginPath();
      ctx.moveTo(10, gy);
      ctx.lineTo(this._w - 10, gy);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    /* Draw connecting lines between consecutive tokens */
    for (var i = 1; i < projection.length; i++) {
      var p0 = this._project(projection[i - 1], cx, cy, midX, midY, scale);
      var p1 = this._project(projection[i], cx, cy, midX, midY, scale);
      ctx.strokeStyle = accent;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.3;
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.lineTo(p1.x, p1.y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    /* Draw each projection point */
    for (var i = 0; i < projection.length; i++) {
      var p = projection[i];
      var pos = this._project(p, cx, cy, midX, midY, scale);
      var isSelected = i === this._selectedIndex;

      /* Draw glow for selected */
      if (isSelected) {
        ctx.shadowColor = accent;
        ctx.shadowBlur = 12;
      }

      ctx.fillStyle = accent;
      ctx.globalAlpha = isSelected ? 1 : 0.7;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, isSelected ? 6 : 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;

      /* Label */
      ctx.fillStyle = isSelected ? textColor : muted;
      ctx.font = (isSelected ? 'bold ' : '') + '11px "SF Mono","Fira Code",monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      var label = p.label === ' ' ? '\u2423' : p.label;
      if (label === '<BOS>') label = 'BOS';
      var labelY = pos.y - (isSelected ? 12 : 8);
      ctx.fillText(label, pos.x, labelY);
    }

    /* Info panel */
    var nEmbd = this._data.n_embd || '—';
    this._infoEl.innerHTML = '<span class="token-stats-label">' + projection.length + ' tokens &middot; ' + nEmbd + '-dim vectors</span>';
  };

  EmbeddingWidget.prototype._project = function (p, cx, cy, midX, midY, scale) {
    return {
      x: cx + (p.x - midX) * scale,
      y: cy + (p.y - midY) * scale
    };
  };

  EmbeddingWidget.prototype._bindKeys = function () {
    var self = this;
    this._canvas.addEventListener('keydown', function (e) {
      if (!self._data) return;
      var projection = self._data.projection || [];
      if (projection.length === 0) return;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        self._selectedIndex = (self._selectedIndex - 1 + projection.length) % projection.length;
        self._draw();
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        self._selectedIndex = (self._selectedIndex + 1) % projection.length;
        self._draw();
      }
    });
  };

  window.EmbeddingWidget = EmbeddingWidget;
})();