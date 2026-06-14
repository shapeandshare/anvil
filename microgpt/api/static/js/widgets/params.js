(function () {
  'use strict';

  function ParamsWidget(container) {
    this.container = container;
    this._data = null;
    this._nEmbd = 16;
    this._nLayer = 1;
    this._render();
  }

  ParamsWidget.prototype._render = function () {
    this.container.innerHTML =
      '<div class="widget-label">Model parameter breakdown — explore how architecture choices affect total count:</div>' +
      '<div class="params-sliders">' +
      '  <label class="param-slider-label">n_embd: <span id="params-nembd-value" class="token-value text-mono">' + this._nEmbd + '</span></label>' +
      '  <input type="range" class="widget-slider" id="params-nembd-slider" min="4" max="64" step="2" value="' + this._nEmbd + '" aria-label="Embedding dimension">' +
      '  <label class="param-slider-label">n_layer: <span id="params-nlayer-value" class="token-value text-mono">' + this._nLayer + '</span></label>' +
      '  <input type="range" class="widget-slider" id="params-nlayer-slider" min="1" max="8" step="1" value="' + this._nLayer + '" aria-label="Number of layers">' +
      '</div>' +
      '<div class="params-total" id="params-total" aria-live="polite"></div>' +
      '<canvas id="params-canvas" class="params-canvas" aria-label="Parameter breakdown stacked horizontal bar"></canvas>' +
      '<div class="params-breakdown" id="params-breakdown" aria-live="polite"></div>' +
      '<div class="widget-empty-state" id="params-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">Couldn\'t load model parameters — <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '</div>' +
      '<p class="widget-hint">Sliders are for illustration — they show how changing architecture affects parameter count without altering the trained model.</p>';
    this._canvas = this.container.querySelector('#params-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._totalEl = this.container.querySelector('#params-total');
    this._breakdownEl = this.container.querySelector('#params-breakdown');
    this._emptyEl = this.container.querySelector('#params-empty');

    var self = this;
    var embdSlider = this.container.querySelector('#params-nembd-slider');
    var layerSlider = this.container.querySelector('#params-nlayer-slider');

    embdSlider.addEventListener('input', function () {
      self._nEmbd = parseInt(this.value);
      self.container.querySelector('#params-nembd-value').textContent = self._nEmbd;
      self._recomputeAndDraw();
    });

    layerSlider.addEventListener('input', function () {
      self._nLayer = parseInt(this.value);
      self.container.querySelector('#params-nlayer-value').textContent = self._nLayer;
      self._recomputeAndDraw();
    });

    this._fetch();
  };

  ParamsWidget.prototype._fetch = function () {
    var self = this;
    this._emptyEl.style.display = 'none';

    fetch('/v1/inference/model-params')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error === 'no_model' || data.detail === 'No model available') {
          self._emptyEl.style.display = '';
          return;
        }
        self._data = data;
        /* Restore slider values from data if available */
        if (data.n_embd) self._nEmbd = data.n_embd;
        if (data.n_layer) self._nLayer = data.n_layer;
        var embdSlider = self.container.querySelector('#params-nembd-slider');
        var layerSlider = self.container.querySelector('#params-nlayer-slider');
        if (embdSlider) embdSlider.value = self._nEmbd;
        if (layerSlider) layerSlider.value = self._nLayer;
        self.container.querySelector('#params-nembd-value').textContent = self._nEmbd;
        self.container.querySelector('#params-nlayer-value').textContent = self._nLayer;
        self._recomputeAndDraw();
      })
      .catch(function () {
        self._emptyEl.style.display = '';
      });
  };

  ParamsWidget.prototype._recomputeAndDraw = function () {
    if (!this._data) return;
    var groups = this._data.groups || [];

    /* Compute scaling factors based on current slider values */
    var baseNEmbd = this._data.n_embd || 16;
    var baseNLayer = this._data.n_layer || 1;
    var embdScale = this._nEmbd / baseNEmbd;
    var layerScale = this._nLayer / baseNLayer;

    var scaledGroups = [];
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      var category = g.category || 'other';
      var count = g.count || 0;
      /* Apply scaling: embedding scales with n_embd^2-ish, attention/MLP with both */
      if (category === 'embedding') {
        count = Math.round(count * embdScale);
      } else if (category === 'attention') {
        count = Math.round(count * embdScale * embdScale * layerScale);
      } else if (category === 'mlp') {
        count = Math.round(count * embdScale * embdScale * layerScale);
      } else if (category === 'output') {
        count = Math.round(count * embdScale);
      }
      scaledGroups.push({
        name: g.name,
        shape: g.shape,
        category: category,
        count: count
      });
    }

    var total = 0;
    for (var i = 0; i < scaledGroups.length; i++) {
      total += scaledGroups[i].count;
    }

    this._renderBar(scaledGroups, total);
  };

  ParamsWidget.prototype._resizeCanvas = function () {
    var w = this.container.clientWidth || 300;
    var h = 36;
    var dpr = window.devicePixelRatio || 1;
    this._canvas.width = w * dpr;
    this._canvas.height = h * dpr;
    this._canvas.style.width = w + 'px';
    this._canvas.style.height = h + 'px';
    this._chartW = w;
    this._chartH = h;
    this._dpr = dpr;
  };

  ParamsWidget.prototype._renderBar = function (groups, total) {
    var ctx = this._ctx;
    if (!ctx || groups.length === 0) return;

    this._resizeCanvas();
    var w = this._chartW;
    var h = this._chartH;
    var dpr = this._dpr || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var style = getComputedStyle(document.documentElement);
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var textColor = style.getPropertyValue('--text').trim() || '#e8eaed';

    var catColors = {
      embedding: '#3b82f6',
      attention: '#06b6d4',
      mlp: '#f97316',
      output: '#a855f7'
    };
    var catLabels = {
      embedding: 'embedding',
      attention: 'attention',
      mlp: 'mlp',
      output: 'output'
    };

    var barX = 0;
    var barY = 8;
    var barH = 20;
    var totalW = w - 20;

    /* Aggregate by category */
    var cats = {};
    for (var i = 0; i < groups.length; i++) {
      var cat = groups[i].category;
      if (!cats[cat]) cats[cat] = 0;
      cats[cat] += groups[i].count;
    }

    /* Draw stacked bar */
    for (var cat in cats) {
      if (!cats.hasOwnProperty(cat)) continue;
      var pct = cats[cat] / total;
      var segW = pct * totalW;
      ctx.fillStyle = catColors[cat] || muted;
      ctx.fillRect(barX + 10, barY, segW, barH);
      /* Label inside segment if wide enough */
      if (segW > 50) {
        ctx.fillStyle = '#fff';
        ctx.font = '9px "SF Mono","Fira Code",monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(catLabels[cat] || cat, barX + 10 + segW / 2, barY + barH / 2);
      }
      barX += segW;
    }

    /* Total params at top */
    var totalLabel = total >= 1000000
      ? (total / 1000000).toFixed(2) + 'M'
      : total >= 1000
        ? (total / 1000).toFixed(1) + 'K'
        : total.toString();
    this._totalEl.innerHTML = '<div class="params-total-label">Total parameters: <span class="token-value text-mono">' + totalLabel + ' (' + total.toLocaleString() + ')</span></div>';

    /* Breakdown list below */
    var html = '<table class="params-table" style="width:100%;border-collapse:collapse;margin-top:var(--space-2);font-size:0.75rem;">' +
      '<thead><tr style="color:' + muted + ';border-bottom:1px solid ' + style.getPropertyValue('--border').trim() + '">' +
      '<th style="text-align:left;padding:2px 4px;">Name</th>' +
      '<th style="text-align:left;padding:2px 4px;">Category</th>' +
      '<th style="text-align:left;padding:2px 4px;">Shape</th>' +
      '<th style="text-align:right;padding:2px 4px;">Count</th>' +
      '<th style="text-align:right;padding:2px 4px;">%</th>' +
      '</tr></thead><tbody>';
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      var pct = total > 0 ? ((g.count / total) * 100).toFixed(1) : '0.0';
      html += '<tr style="border-bottom:1px solid ' + style.getPropertyValue('--border').trim() + '">' +
        '<td style="padding:2px 4px;color:' + textColor + '">' + this._escapeHtml(g.name) + '</td>' +
        '<td style="padding:2px 4px;"><span style="color:' + (catColors[g.category] || muted) + '">' + (catLabels[g.category] || g.category) + '</span></td>' +
        '<td style="padding:2px 4px;color:' + muted + '">' + this._escapeHtml(g.shape) + '</td>' +
        '<td style="padding:2px 4px;text-align:right;color:' + textColor + '">' + g.count.toLocaleString() + '</td>' +
        '<td style="padding:2px 4px;text-align:right;color:' + muted + '">' + pct + '%</td>' +
        '</tr>';
    }
    html += '</tbody></table>';
    this._breakdownEl.innerHTML = html;
  };

  ParamsWidget.prototype._escapeHtml = function (str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  };

  window.ParamsWidget = ParamsWidget;
})();
