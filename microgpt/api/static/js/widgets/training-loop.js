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
    this.container.innerHTML =
      '<div class="widget-label">Training loss curve — select a completed experiment to replay:</div>' +
      '<div class="tl-select-row">' +
      '  <select id="tl-experiment-select" class="heatmap-select" aria-label="Select experiment">' +
      '    <option value="">— Loading experiments —</option>' +
      '  </select>' +
      '</div>' +
      '<canvas id="tl-canvas" class="tl-canvas" aria-label="Loss curve over training steps"></canvas>' +
      '<div class="scrubber-container" id="tl-scrubber-row" style="display:none">' +
      '  <span class="scrubber-label" id="tl-step-label">Step: 0</span>' +
      '  <input type="range" class="scrubber-slider" id="tl-scrubber" min="0" max="0" value="0" step="1" aria-label="Scrub through training steps">' +
      '  <span class="scrubber-label" id="tl-loss-label">Loss: —</span>' +
      '</div>' +
      '<div class="widget-empty-state" id="tl-empty" style="display:none" role="alert">' +
      '  <p class="widget-empty-text">No training runs yet — <a href="/v1/training-page" class="widget-empty-link">train a model</a> to see real loss curves</p>' +
      '</div>' +
      '<div class="tl-info" id="tl-info" aria-live="polite"></div>';
    this._canvas = this.container.querySelector('#tl-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._selectEl = this.container.querySelector('#tl-experiment-select');
    this._scrubberEl = this.container.querySelector('#tl-scrubber');
    this._scrubberRow = this.container.querySelector('#tl-scrubber-row');
    this._stepLabel = this.container.querySelector('#tl-step-label');
    this._lossLabel = this.container.querySelector('#tl-loss-label');
    this._emptyEl = this.container.querySelector('#tl-empty');
    this._infoEl = this.container.querySelector('#tl-info');

    var self = this;

    this._selectEl.addEventListener('change', function () {
      var val = this.value;
      if (val) {
        self._selectedExpId = parseInt(val);
        self._fetchMetrics(self._selectedExpId);
      }
    });

    this._scrubberEl.addEventListener('input', function () {
      self._currentStep = parseInt(this.value);
      self._updateScrubberDisplay();
      self._drawCurve();
    });

    this._resize();
    this._fetchExperiments();
  };

  TrainingLoopWidget.prototype._resize = function () {
    var w = this.container.clientWidth || 300;
    var h = Math.min(220, Math.max(140, w * 0.4));
    this._canvas.width = w * (window.devicePixelRatio || 1);
    this._canvas.height = h * (window.devicePixelRatio || 1);
    this._canvas.style.width = w + 'px';
    this._canvas.style.height = h + 'px';
    this._chartW = w;
    this._chartH = h;
    this._dpr = window.devicePixelRatio || 1;
  };

  TrainingLoopWidget.prototype._fetchExperiments = function () {
    var self = this;
    this._infoEl.innerHTML = '<div class="loading-indicator"><span class="spinner"></span> Loading experiments...</div>';

    fetch('/v1/experiments')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var exps = data.experiments || [];
        if (exps.length === 0) {
          self._emptyEl.style.display = '';
          self._selectEl.innerHTML = '<option value="">No experiments found</option>';
          self._infoEl.innerHTML = '';
          return;
        }
        self._experiments = exps;
        self._populateSelect(exps);
        self._infoEl.innerHTML = '<span class="token-stats-label">' + exps.length + ' experiment(s) available</span>';
        /* Select first completed experiment by default */
        var completed = exps.filter(function (e) { return e.status === 'completed'; });
        var target = completed.length > 0 ? completed[0] : exps[0];
        self._selectedExpId = target.id;
        self._selectEl.value = target.id;
        self._fetchMetrics(target.id);
      })
      .catch(function () {
        self._emptyEl.style.display = '';
        self._selectEl.innerHTML = '<option value="">Failed to load</option>';
        self._infoEl.innerHTML = '';
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