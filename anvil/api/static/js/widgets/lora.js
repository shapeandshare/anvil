// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

/**
 * LoRA low-rank decomposition widget.
 *
 * Teaches the core LoRA insight: a weight matrix W can be approximated
 * by the product of two thin matrices A (n×r) and B (r×n) whose rank r
 * is much smaller than n.  The approximation A×B is the genuine best
 * rank-r approximation of W, computed via a pure-JS truncated SVD
 * (power iteration with deflation) — so reconstruction error decreases
 * monotonically as the rank slider increases, exactly as real low-rank
 * adaptation behaves (Eckart–Young theorem).
 *
 * Purely client-side — no backend API calls.  W is synthetic and
 * intrinsically low-rank-plus-noise so the error drops sharply for the
 * first few ranks and then plateaus, illustrating why small r works.
 */
(function () {
  'use strict';

  var MATRIX_SIZE = 32;
  var CANVAS_PX = 180;
  var MAX_RANK = 16;

  function LoraWidget(container) {
    if (!container) return;
    this.container = container;
    this._rank = 4;
    this._n = MATRIX_SIZE;
    this._reducedMotion = false;
    this._w = null;
    this._singular = null;
    this._render();
  }

  LoraWidget.prototype._render = function () {
    AnvilBase.initReducedMotion(this);

    this.container.innerHTML =
      '<div class="widget-label">Explore how rank r controls the quality of the best low-rank approximation of a weight matrix:</div>' +
      '<div class="lora-controls">' +
      '  <label class="param-slider-label">Rank r: <span id="lora-rank-value" class="token-value text-mono">' + this._rank + '</span></label>' +
      '  <input type="range" class="widget-slider" id="lora-rank-slider" min="1" max="16" step="1" value="' + this._rank + '" aria-label="LoRA rank">' +
      '</div>' +
      '<div class="lora-panels">' +
      '  <div class="lora-panel"><div class="lora-panel-label">Original W</div><canvas id="lora-canvas-w" class="lora-canvas" aria-label="Original weight matrix heatmap"></canvas></div>' +
      '  <div class="lora-panel"><div class="lora-panel-label">Approximation A\u00d7B</div><canvas id="lora-canvas-ab" class="lora-canvas" aria-label="Rank-r approximation heatmap"></canvas></div>' +
      '  <div class="lora-panel"><div class="lora-panel-label">Difference |W \u2013 AB|</div><canvas id="lora-canvas-diff" class="lora-canvas" aria-label="Difference heatmap"></canvas></div>' +
      '</div>' +
      '<div class="lora-info">' +
      '  <span id="lora-params-count" aria-live="polite">Parameters: computing\u2026</span>' +
      '  <span id="lora-error" aria-live="polite">Reconstruction error: computing\u2026</span>' +
      '</div>' +
      '<p class="widget-hint">Higher rank captures more of W (lower error) but costs more parameters. Notice how the first few ranks remove most of the error \u2014 that is why LoRA works.</p>';

    this._canvasW = this.container.querySelector('#lora-canvas-w');
    this._canvasAB = this.container.querySelector('#lora-canvas-ab');
    this._canvasDiff = this.container.querySelector('#lora-canvas-diff');
    this._rankValueEl = this.container.querySelector('#lora-rank-value');
    this._paramsEl = this.container.querySelector('#lora-params-count');
    this._errorEl = this.container.querySelector('#lora-error');

    this._generateMatrix();
    this._computeSvd();

    var self = this;
    var slider = this.container.querySelector('#lora-rank-slider');
    slider.addEventListener('input', function () {
      self._rank = parseInt(this.value);
      self._rankValueEl.textContent = self._rank;
      self._update();
    });

    this._update();
  };

  /**
   * Build a synthetic n×n matrix that is intrinsically low-rank (a small
   * number of dominant outer products) plus light noise, using a seeded
   * LCG so the demo is stable across renders.  The low-rank-plus-noise
   * structure makes the error curve drop sharply for small r and then
   * plateau — the pedagogical point.
   */
  LoraWidget.prototype._generateMatrix = function () {
    var n = this._n;
    var trueRank = 3;
    var seed = 1;
    function rand() {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return (seed / 0x7fffffff) * 2 - 1;
    }

    var factors = [];
    for (var t = 0; t < trueRank; t++) {
      var u = new Float64Array(n);
      var v = new Float64Array(n);
      for (var i = 0; i < n; i++) u[i] = rand();
      for (var j = 0; j < n; j++) v[j] = rand();
      factors.push({ u: u, v: v, weight: 1 / (t + 1) });
    }

    var w = new Float64Array(n * n);
    for (var row = 0; row < n; row++) {
      for (var col = 0; col < n; col++) {
        var val = 0;
        for (var f = 0; f < factors.length; f++) {
          val += factors[f].weight * factors[f].u[row] * factors[f].v[col];
        }
        val += rand() * 0.05;
        w[row * n + col] = val;
      }
    }

    var maxVal = 0;
    for (var k = 0; k < n * n; k++) {
      var abs = Math.abs(w[k]);
      if (abs > maxVal) maxVal = abs;
    }
    if (maxVal > 0) {
      for (var k2 = 0; k2 < n * n; k2++) w[k2] /= maxVal;
    }
    this._w = w;
  };

  /**
   * Truncated SVD via power iteration with deflation.
   *
   * Computes the top singular triplets (u, sigma, v) of W so any rank-r
   * approximation is the sum of the first r rank-one terms
   * sigma_k · u_k · v_k^T.  This is the genuine best rank-r approximation
   * (Eckart–Young), guaranteeing monotonically decreasing error as r grows.
   */
  LoraWidget.prototype._computeSvd = function () {
    var n = this._n;
    var residual = this._w.slice();
    var triplets = [];
    var lcg = 1;

    for (var c = 0; c < MAX_RANK; c++) {
      var v = new Float64Array(n);
      for (var i = 0; i < n; i++) {
        lcg = (lcg * 1103515245 + 12345) & 0x7fffffff;
        v[i] = lcg / 0x7fffffff;
      }
      this._normalize(v);

      var u = new Float64Array(n);
      var sigma = 0;
      for (var iter = 0; iter < 60; iter++) {
        this._matVec(residual, v, u);
        var sigmaU = this._normalize(u);
        this._matVecT(residual, u, v);
        sigma = this._normalize(v);
        if (Math.abs(sigma - sigmaU) < 1e-9) break;
      }

      this._matVec(residual, v, u);
      sigma = this._normalize(u);
      triplets.push({ u: u.slice(), sigma: sigma, v: v.slice() });

      for (var row = 0; row < n; row++) {
        var su = sigma * u[row];
        var base = row * n;
        for (var col = 0; col < n; col++) {
          residual[base + col] -= su * v[col];
        }
      }
    }
    this._singular = triplets;
  };

  LoraWidget.prototype._matVec = function (m, x, out) {
    var n = this._n;
    for (var row = 0; row < n; row++) {
      var sum = 0;
      var base = row * n;
      for (var col = 0; col < n; col++) sum += m[base + col] * x[col];
      out[row] = sum;
    }
  };

  LoraWidget.prototype._matVecT = function (m, x, out) {
    var n = this._n;
    for (var col = 0; col < n; col++) out[col] = 0;
    for (var row = 0; row < n; row++) {
      var xr = x[row];
      var base = row * n;
      for (var col2 = 0; col2 < n; col2++) out[col2] += m[base + col2] * xr;
    }
  };

  LoraWidget.prototype._normalize = function (vec) {
    var norm = 0;
    for (var i = 0; i < vec.length; i++) norm += vec[i] * vec[i];
    norm = Math.sqrt(norm);
    if (norm > 1e-12) {
      for (var j = 0; j < vec.length; j++) vec[j] /= norm;
    }
    return norm;
  };

  LoraWidget.prototype._update = function () {
    var n = this._n;
    var r = Math.min(this._rank, this._singular.length);

    var ab = new Float64Array(n * n);
    for (var k = 0; k < r; k++) {
      var t = this._singular[k];
      var sigma = t.sigma;
      var u = t.u;
      var v = t.v;
      for (var row = 0; row < n; row++) {
        var su = sigma * u[row];
        var base = row * n;
        for (var col = 0; col < n; col++) {
          ab[base + col] += su * v[col];
        }
      }
    }

    var totalError = 0;
    var diff = new Float64Array(n * n);
    for (var i = 0; i < n * n; i++) {
      var d = this._w[i] - ab[i];
      diff[i] = d;
      totalError += d * d;
    }
    var rmse = Math.sqrt(totalError / (n * n));

    this._drawHeatmap(this._canvasW, this._w, 'value');
    this._drawHeatmap(this._canvasAB, ab, 'value');
    this._drawHeatmap(this._canvasDiff, diff, 'diff');

    var fullParams = n * n;
    var loraParams = 2 * this._rank * n;
    this._paramsEl.textContent =
      'Parameters: ' + loraParams + ' (A+B) vs ' + fullParams + ' (full W)';
    this._errorEl.textContent = 'Reconstruction error (RMSE): ' + rmse.toFixed(4);
  };

  /**
   * Draw a matrix heatmap, accounting for devicePixelRatio so cells stay
   * crisp on HiDPI displays.
   *
   * @param {HTMLCanvasElement} canvas  Target canvas.
   * @param {Float64Array} data  Row-major matrix data, length n*n.
   * @param {string} mode  "value" (signed blue scale) or "diff" (red/blue error).
   */
  LoraWidget.prototype._drawHeatmap = function (canvas, data, mode) {
    var n = this._n;
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(CANVAS_PX * dpr);
    canvas.height = Math.round(CANVAS_PX * dpr);
    canvas.style.width = CANVAS_PX + 'px';
    canvas.style.height = CANVAS_PX + 'px';

    var ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, CANVAS_PX, CANVAS_PX);

    var cell = CANVAS_PX / n;
    for (var row = 0; row < n; row++) {
      for (var col = 0; col < n; col++) {
        var val = data[row * n + col];
        ctx.fillStyle = mode === 'diff' ? this._diffColour(val) : this._valueColour(val);
        ctx.fillRect(
          Math.floor(col * cell),
          Math.floor(row * cell),
          Math.ceil(cell),
          Math.ceil(cell)
        );
      }
    }
  };

  LoraWidget.prototype._valueColour = function (val) {
    var normalized = Math.max(0, Math.min(1, (val + 1) / 2));
    var r = Math.round(30 + normalized * 100);
    var g = Math.round(30 + normalized * 60);
    var b = Math.round(200 + normalized * 55);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  };

  LoraWidget.prototype._diffColour = function (val) {
    var intensity = Math.min(1, Math.abs(val) * 3);
    return val >= 0
      ? 'rgba(239,68,68,' + intensity + ')'
      : 'rgba(59,130,246,' + intensity + ')';
  };

  window.LoraWidget = LoraWidget;
})();