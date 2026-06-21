// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function AdamWidget(container) {
    this.container = container;
    this._beta1 = 0.9;
    this._beta2 = 0.999;
    this._learningRate = 0.01;
    this._numSteps = 1000;
    this._mHistory = [];
    this._vHistory = [];
    this._stepCount = 0;
    this._eventSource = null;
    this._render();
  }

  AdamWidget.prototype._render = function () {
    this.container.innerHTML =
      '<div class="widget-label">Adam optimizer state — tunes in real-time during training:</div>' +
      '<div class="adam-controls">' +
      '  <label class="widget-label">beta1: <span id="adam-beta1-value" class="token-value text-mono">' + this._beta1.toFixed(3) + '</span></label>' +
      '  <input type="range" class="widget-slider" id="adam-beta1-slider" min="0.8" max="0.999" step="0.001" value="' + this._beta1 + '" aria-label="Beta 1">' +
      '  <label class="widget-label">beta2: <span id="adam-beta2-value" class="token-value text-mono">' + this._beta2.toFixed(3) + '</span></label>' +
      '  <input type="range" class="widget-slider" id="adam-beta2-slider" min="0.9" max="0.9999" step="0.0001" value="' + this._beta2 + '" aria-label="Beta 2">' +
      '</div>' +
      '<div class="adam-formula" style="font-size:0.7rem;color:var(--text-muted);text-align:center;padding:var(--space-1) 0;font-family:\'SF Mono\',\'Fira Code\',monospace;">' +
      'lr_t = lr &times; (1 &minus; step / num_steps)' +
      '</div>' +
      '<canvas id="adam-canvas" class="adam-canvas" aria-label="Adam m and v curves over training steps"></canvas>' +
      '<div class="adam-status" id="adam-status" aria-live="polite">' +
      '  <span class="widget-hint" id="adam-status-text">Waiting for training data...</span>' +
      '</div>';
    this._canvas = this.container.querySelector('#adam-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._statusEl = this.container.querySelector('#adam-status-text');

    var self = this;

    var beta1Slider = this.container.querySelector('#adam-beta1-slider');
    var beta2Slider = this.container.querySelector('#adam-beta2-slider');

    beta1Slider.addEventListener('input', function () {
      self._beta1 = parseFloat(this.value);
      self.container.querySelector('#adam-beta1-value').textContent = self._beta1.toFixed(3);
      self._drawChart();
    });

    beta2Slider.addEventListener('input', function () {
      self._beta2 = parseFloat(this.value);
      self.container.querySelector('#adam-beta2-value').textContent = self._beta2.toFixed(3);
      self._drawChart();
    });

    this._connectSSE();
    this._drawChart();
  };

  AdamWidget.prototype._connectSSE = function () {
    var self = this;
    if (this._eventSource) {
      this._eventSource.close();
    }

    this._eventSource = new EventSource('/v1/training/events?stream=optimizer_state');

    this._eventSource.addEventListener('optimizer_state', function (e) {
      try {
        var data = JSON.parse(e.data);
        self._onOptimizerState(data);
      } catch (err) {
        /* ignore parse errors */
      }
    });

    this._eventSource.addEventListener('error', function () {
      self._statusEl.textContent = 'Waiting for training data...';
    });

    this._eventSource.addEventListener('open', function () {
      self._statusEl.textContent = 'Connected — receiving optimizer state';
    });
  };

  AdamWidget.prototype._onOptimizerState = function (data) {
    if (data.m !== undefined && data.v !== undefined) {
      this._mHistory.push(data.m);
      this._vHistory.push(data.v);
    }
    if (data.step !== undefined) {
      this._stepCount = data.step;
    }
    if (data.learning_rate !== undefined) {
      this._learningRate = data.learning_rate;
    }
    if (data.num_steps !== undefined) {
      this._numSteps = data.num_steps;
    }
    this._statusEl.textContent = 'Step ' + this._stepCount + ' — m: ' + data.m.toFixed(6) + ', v: ' + data.v.toFixed(6);
    this._drawChart();
  };

  AdamWidget.prototype._resizeCanvas = function () {
    var w = this.container.clientWidth || 300;
    var h = Math.min(200, Math.max(120, w * 0.35));
    var dpr = window.devicePixelRatio || 1;
    this._canvas.width = w * dpr;
    this._canvas.height = h * dpr;
    this._canvas.style.width = w + 'px';
    this._canvas.style.height = h + 'px';
    this._chartW = w;
    this._chartH = h;
    this._dpr = dpr;
  };

  AdamWidget.prototype._drawChart = function () {
    var ctx = this._ctx;
    if (!ctx) return;

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
    var accent = style.getPropertyValue('--accent').trim() || '#007aff';
    var accentOrange = style.getPropertyValue('--accent-orange').trim() || '#ff9500';

    var pad = { top: 10, right: 10, bottom: 22, left: 48 };
    var plotW = w - pad.left - pad.right;
    var plotH = h - pad.top - pad.bottom;
    if (plotW <= 0 || plotH <= 0) return;

    /* Compute theoretical curves for display */
    var numPoints = Math.max(this._stepCount || 100, 100);
    var mCurve = [];
    var vCurve = [];
    var steps = [];
    for (var i = 0; i <= numPoints; i++) {
      var step = i;
      steps.push(step);
      var mt = 1 - Math.pow(this._beta1, step + 1);
      var vt = 1 - Math.pow(this._beta2, step + 1);
      mCurve.push(mt);
      vCurve.push(vt);
    }

    /* If we have real data, overlay it — otherwise just show theoretical curves */
    var showRealData = this._mHistory.length > 0;

    /* Find y-axis bounds */
    var allY = mCurve.concat(vCurve);
    if (showRealData) {
      allY = allY.concat(this._mHistory).concat(this._vHistory);
    }
    var minY = 0;
    var maxY = Math.max.apply(null, allY) * 1.1 || 1;

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
      var val = minY + (i / yTicks) * (maxY - minY);
      var y = pad.top + plotH - (i / yTicks) * plotH;
      ctx.fillText(val.toFixed(2), pad.left - 4, y);
    }

    /* X-axis labels (step numbers) */
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    var xTicks = Math.min(5, numPoints);
    for (var i = 0; i <= xTicks; i++) {
      var val = Math.round((i / xTicks) * numPoints);
      var x = pad.left + (i / xTicks) * plotW;
      ctx.fillText(val.toString(), x, pad.top + plotH + 4);
    }

    /* Draw theoretical m curve (blue) */
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    for (var i = 0; i < mCurve.length; i++) {
      var x = pad.left + (steps[i] / numPoints) * plotW;
      var y = pad.top + plotH - ((mCurve[i] - minY) / (maxY - minY || 1)) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    /* Draw theoretical v curve (orange) */
    ctx.strokeStyle = accentOrange;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    for (var i = 0; i < vCurve.length; i++) {
      var x = pad.left + (steps[i] / numPoints) * plotW;
      var y = pad.top + plotH - ((vCurve[i] - minY) / (maxY - minY || 1)) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    /* Draw real m data if available */
    if (showRealData) {
      ctx.strokeStyle = accent;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      for (var i = 0; i < this._mHistory.length; i++) {
        var x = pad.left + ((i) / numPoints) * plotW;
        var y = pad.top + plotH - ((this._mHistory[i] - minY) / (maxY - minY || 1)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      /* Draw real v data if available */
      ctx.strokeStyle = accentOrange;
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (var i = 0; i < this._vHistory.length; i++) {
        var x = pad.left + ((i) / numPoints) * plotW;
        var y = pad.top + plotH - ((this._vHistory[i] - minY) / (maxY - minY || 1)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    /* Legend */
    var legendY = pad.top + 2;
    var legendX = pad.left + 4;

    /* m legend entry */
    ctx.fillStyle = accent;
    ctx.fillRect(legendX, legendY + 4, 12, 3);
    ctx.fillStyle = textColor;
    ctx.font = '8px "SF Mono","Fira Code",monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('m (momentum)', legendX + 16, legendY + 6);

    /* v legend entry */
    ctx.fillStyle = accentOrange;
    ctx.fillRect(legendX + 90, legendY + 4, 12, 3);
    ctx.fillStyle = textColor;
    ctx.fillText('v (adaptive LR)', legendX + 106, legendY + 6);

    /* Dashed line note */
    ctx.fillStyle = muted;
    ctx.font = '7px "SF Mono","Fira Code",monospace';
    ctx.fillText('dashed=theoretical, solid=actual', legendX, legendY + 20);
  };

  window.AdamWidget = AdamWidget;
})();
