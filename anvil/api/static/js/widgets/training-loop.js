// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function TrainingLoopWidget(container) {
    this.container = container;
    this._experiments = [];
    this._metrics = [];
    this._currentStep = 0;
    this._selectedExpId = null;
    this._render();
  }

  TrainingLoopWidget.prototype._render = function () {
    var self = this;
    this.container.innerHTML =
      '<div class="widget-label">Training loss curve — select a finished experiment to replay:</div>' +
      '<div class="widget-empty-state" id="loop-empty" style="display:none">' +
      '  <p class="widget-empty-text">No experiments yet. ' +
      '    <a href="/v1/training-page" class="widget-empty-link">Go train a model</a>' +
      '    to see your loss curve here.</p>' +
      '</div>' +
      '<div id="loop-controls" style="display:none">' +
      '  <select id="loop-select" class="widget-input" aria-label="Select experiment"></select>' +
      '</div>' +
      '<div id="loop-info"></div>' +
      '<div id="loop-chart" style="margin-top:var(--space-3);">' +
      '  <canvas id="loop-canvas" style="width:100%;height:180px;display:block;"></canvas>' +
      '</div>' +
      '<div id="loop-scrubber-row" style="display:none;" class="scrubber-container">' +
      '  <span id="loop-step-label" class="scrubber-label">Step: —</span>' +
      '  <input type="range" id="loop-scrubber" class="scrubber-slider" min="0" max="0" value="0" aria-label="Scrub through training steps">' +
      '  <span id="loop-loss-label" class="scrubber-label">Loss: —</span>' +
      '</div>';

    this._emptyEl = this.container.querySelector('#loop-empty');
    this._controlsEl = this.container.querySelector('#loop-controls');
    this._selectEl = this.container.querySelector('#loop-select');
    this._infoEl = this.container.querySelector('#loop-info');
    this._canvas = this.container.querySelector('#loop-canvas');
    this._scrubberRow = this.container.querySelector('#loop-scrubber-row');
    this._scrubberEl = this.container.querySelector('#loop-scrubber');
    this._stepLabel = this.container.querySelector('#loop-step-label');
    this._lossLabel = this.container.querySelector('#loop-loss-label');

    var dpr = window.devicePixelRatio || 1;
    this._dpr = dpr;
    var w = this._canvas.clientWidth || 400;
    this._chartW = w;
    this._chartH = 180;
    this._canvas.width = w * dpr;
    this._canvas.height = 180 * dpr;
    this._ctx = this._canvas.getContext('2d');

    this._selectEl.addEventListener('change', function () {
      self._selectedExpId = parseInt(this.value, 10);
      self._fetchMetrics(self._selectedExpId);
    });

    this._scrubberEl.addEventListener('input', function () {
      self._currentStep = parseInt(this.value, 10);
      self._updateScrubberDisplay();
      self._drawCurve();
    });

    fetch('/v1/experiments')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var exps = data.experiments || [];
        if (exps.length === 0) {
          self._emptyEl.style.display = '';
          self._controlsEl.style.display = 'none';
          self._infoEl.innerHTML = '<p class="widget-hint">Run a training experiment first, then return here to inspect the loss curve.</p>';
          return;
        }
        self._experiments = exps;
        self._populateSelect(exps);
        self._controlsEl.style.display = '';

        var finished = exps.filter(function (e) { return e.status === 'finished'; });
        var target = finished.length > 0 ? finished[0] : exps[0];
        self._selectedExpId = target.id;
        self._selectEl.value = target.id;
        self._fetchMetrics(target.id);
      })
      .catch(function () {
        self._emptyEl.style.display = '';
        self._controlsEl.style.display = 'none';
        self._infoEl.innerHTML = '<p class="widget-hint">Could not connect to server.</p>';
      });
  };

  TrainingLoopWidget.prototype._populateSelect = function (exps) {
    this._selectEl.innerHTML = '';
    for (var i = 0; i < exps.length; i++) {
      var e = exps[i];
      var opt = document.createElement('option');
      opt.value = e.id;
      opt.textContent = 'Run #' + e.id + ' (' + e.status + (e.final_loss !== null && e.final_loss !== undefined ? ', loss: ' + e.final_loss.toFixed(4) : '') + ')';
      this._selectEl.appendChild(opt);
    }
  };

  TrainingLoopWidget.prototype._fetchMetrics = function (expId) {
    var self = this;
    this._infoEl.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Loading loss curve...</div>';
    this._emptyEl.style.display = 'none';
    this._controlsEl.style.display = '';

    fetch('/v1/experiments/' + expId + '/metrics')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var metrics = data.metrics || [];
        if (metrics.length === 0) {
          self._infoEl.innerHTML = '<span class="widget-hint">No per-step metrics for this experiment</span>';
          self._scrubberRow.style.display = 'none';
          return;
        }
        self._metrics = metrics;
        self._currentStep = 0;
        self._scrubberEl.max = metrics.length - 1;
        self._scrubberEl.value = 0;
        self._scrubberRow.style.display = 'flex';
        self._updateScrubberDisplay();
        self._drawCurve();
        self._infoEl.innerHTML = '<span class="token-stats-label">' + metrics.length + ' steps recorded</span>';
      })
      .catch(function () {
        self._infoEl.innerHTML = '<span class="widget-hint">Could not load metrics for this experiment</span>';
        self._scrubberRow.style.display = 'none';
      });
  };

  TrainingLoopWidget.prototype._updateScrubberDisplay = function () {
    var idx = this._currentStep;
    var metrics = this._metrics;
    if (!metrics || idx >= metrics.length) {
      this._stepLabel.textContent = 'Step: —';
      this._lossLabel.textContent = 'Loss: —';
      return;
    }
    var m = metrics[idx];
    this._stepLabel.textContent = 'Step: ' + m.step;
    this._lossLabel.textContent = 'Loss: ' + m.loss.toFixed(4);
  };

  TrainingLoopWidget.prototype._drawCurve = function () {
    var ctx = this._ctx;
    if (!ctx || !this._metrics || this._metrics.length === 0) return;

    var w = this._chartW;
    var h = this._chartH;
    var dpr = this._dpr || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue('--accent').trim() || '#3b82f6';
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var border = style.getPropertyValue('--border').trim() || '#2a2c32';
    var textColor = style.getPropertyValue('--text').trim() || '#e8eaed';

    var pad = { top: 10, right: 10, bottom: 22, left: 50 };
    var plotW = w - pad.left - pad.right;
    var plotH = h - pad.top - pad.bottom;

    if (plotW <= 0 || plotH <= 0) return;

    /* Compute bounds */
    var steps = this._metrics.map(function (m) { return m.step; });
    var losses = this._metrics.map(function (m) { return m.loss; });
    var minStep = steps[0];
    var maxStep = steps[steps.length - 1];
    var minLoss = Math.min.apply(null, losses);
    var maxLoss = Math.max.apply(null, losses);
    var lossRange = maxLoss - minLoss || 1;

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
      var val = maxLoss - (i / yTicks) * lossRange;
      var y = pad.top + (i / yTicks) * plotH;
      ctx.fillText(val.toFixed(2), pad.left - 4, y);
    }

    /* X-axis labels */
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    var xTicks = Math.min(5, maxStep - minStep);
    for (var i = 0; i <= xTicks; i++) {
      var val = Math.round(minStep + (i / xTicks) * (maxStep - minStep));
      var x = pad.left + (i / xTicks) * plotW;
      ctx.fillText(val.toString(), x, pad.top + plotH + 4);
    }

    /* Draw loss curve */
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (var i = 0; i < this._metrics.length; i++) {
      var x = pad.left + ((this._metrics[i].step - minStep) / (maxStep - minStep || 1)) * plotW;
      var y = pad.top + ((maxLoss - this._metrics[i].loss) / lossRange) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    /* Draw current step marker */
    var currentIdx = this._currentStep;
    if (currentIdx >= 0 && currentIdx < this._metrics.length) {
      var cur = this._metrics[currentIdx];
      var cx = pad.left + ((cur.step - minStep) / (maxStep - minStep || 1)) * plotW;
      var cy = pad.top + ((maxLoss - cur.loss) / lossRange) * plotH;

      /* Vertical line */
      ctx.strokeStyle = muted;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.4;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(cx, pad.top + plotH);
      ctx.lineTo(cx, cy);
      ctx.lineTo(pad.left, cy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;

      /* Marker dot */
      ctx.fillStyle = accent;
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = textColor;
      ctx.font = 'bold 9px "SF Mono","Fira Code",monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'bottom';
      ctx.fillText('step ' + cur.step + ' loss=' + cur.loss.toFixed(4), cx + 8, cy - 4);
    }
  };

  window.TrainingLoopWidget = TrainingLoopWidget;
})();