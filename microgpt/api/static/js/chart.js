(function() {
  'use strict';

  function LossChart(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.options = options || {};
    this.mode = this.options.mode || 'live';
    this.maxPoints = this.options.maxPoints || 2000;
    this.throttleInterval = this.options.throttleInterval || 50;

    this._points = [];
    this._lastPaint = 0;
    this._rafId = null;
    this._dirty = false;

    this._resize();
    this._initColors();
  }

  LossChart.prototype._initColors = function() {
    var style = getComputedStyle(document.documentElement);
    this._accentColor = this.options.accentColor || style.getPropertyValue('--accent').trim() || '#3b82f6';
    this._bgColor = this.options.backgroundColor || style.getPropertyValue('--surface').trim() || '#181a1f';
    this._gridColor = this.options.gridColor || style.getPropertyValue('--border').trim() || '#2a2c32';
    this._textColor = this.options.textColor || style.getPropertyValue('--text-muted').trim() || '#8a8c94';
  };

  LossChart.prototype._resize = function() {
    var rect = this.canvas.parentElement.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    var w = rect.width;
    var h = Math.max(200, rect.height || 300);
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.scale(dpr, dpr);
    this._w = w;
    this._h = h;
    this._dirty = true;
  };

  LossChart.prototype._lttb = function(data, threshold) {
    if (data.length <= threshold || threshold < 3) return data;
    var bucketSize = (data.length - 2) / (threshold - 2);
    var result = [data[0]];
    for (var i = 0; i < threshold - 2; i++) {
      var start = Math.floor((i + 0) * bucketSize) + 1;
      var end = Math.floor((i + 1) * bucketSize) + 1;
      var end2 = Math.floor((i + 2) * bucketSize) + 1;
      var avgX = 0, avgY = 0;
      var count = 0;
      for (var j = end; j < end2 && j < data.length; j++) {
        avgX += data[j].step;
        avgY += data[j].loss;
        count++;
      }
      if (count > 0) { avgX /= count; avgY /= count; }
      var bestArea = -1, bestIdx = start;
      var prev = result[result.length - 1];
      for (var j = start; j < end && j < data.length; j++) {
        var area = Math.abs((prev.step - avgX) * (data[j].loss - prev.loss) - (prev.step - data[j].step) * (avgY - prev.loss)) * 0.5;
        if (area > bestArea) { bestArea = area; bestIdx = j; }
      }
      result.push(data[bestIdx]);
    }
    result.push(data[data.length - 1]);
    return result;
  };

  LossChart.prototype._paint = function() {
    this._dirty = false;
    var ctx = this.ctx;
    var w = this._w, h = this._h;
    var margin = 20;
    var plotW = w - margin * 2;
    var plotH = h - margin * 2;

    var points = this._points;
    if (points.length > this.maxPoints) {
      points = this._lttb(points, this.maxPoints);
    }

    ctx.clearRect(0, 0, w, h);

    if (points.length < 2) {
      ctx.fillStyle = this._textColor;
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(points.length === 0 ? 'Waiting for data...' : 'Collecting points...', w / 2, h / 2);
      return;
    }

    var xs = points.map(function(p) { return p.step; });
    var ys = points.map(function(p) { return p.loss; });
    var minX = xs[0], maxX = xs[xs.length - 1];
    var minY = Math.min.apply(null, ys);
    var maxY = Math.max.apply(null, ys);
    var rangeY = maxY - minY || 1;

    function sx(v) { return margin + ((v - minX) / (maxX - minX || 1)) * plotW; }
    function sy(v) { return margin + plotH - ((v - minY) / rangeY) * plotH; }

    ctx.strokeStyle = this._gridColor;
    ctx.lineWidth = 0.5;
    for (var i = 0; i < 5; i++) {
      var y = margin + (i / 4) * plotH;
      ctx.beginPath(); ctx.moveTo(margin, y); ctx.lineTo(margin + plotW, y); ctx.stroke();
    }

    ctx.strokeStyle = this._accentColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(sx(points[0].step), sy(points[0].loss));
    for (var i = 1; i < points.length; i++) {
      ctx.lineTo(sx(points[i].step), sy(points[i].loss));
    }
    ctx.stroke();

    ctx.fillStyle = this._textColor;
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(minX, margin, h - 4);
    ctx.fillText(maxX, margin + plotW, h - 4);
    ctx.textAlign = 'right';
    ctx.fillText(maxY.toFixed(2), margin - 4, margin + 12);
    ctx.fillText(minY.toFixed(2), margin - 4, margin + plotH);
  };

  LossChart.prototype._schedulePaint = function() {
    var now = Date.now();
    if (now - this._lastPaint >= this.throttleInterval) {
      this._paint();
      this._lastPaint = now;
    } else if (!this._rafId) {
      var self = this;
      this._rafId = requestAnimationFrame(function() {
        self._rafId = null;
        self._paint();
        self._lastPaint = Date.now();
      });
    }
  };

  LossChart.prototype.appendPoint = function(point) {
    this._points.push(point);
    this._schedulePaint();
  };

  LossChart.prototype.setData = function(points) {
    this._points = points.slice();
    this._dirty = true;
    this._paint();
  };

  LossChart.prototype.clear = function() {
    this._points = [];
    this._dirty = true;
    this._paint();
  };

  LossChart.prototype.resize = function() {
    this._resize();
    if (this._dirty) this._paint();
  };

  LossChart.prototype.destroy = function() {
    if (this._rafId) cancelAnimationFrame(this._rafId);
    this._points = [];
    this._rafId = null;
  };

  window.LossChart = LossChart;
})();