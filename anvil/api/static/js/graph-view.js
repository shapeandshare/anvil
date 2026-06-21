// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function GraphView(canvas, _options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this._nodes = [];
    this._edges = [];
    this._resize();
  }

  GraphView.prototype._resize = function () {
    var rect = this.canvas.parentElement.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = (rect.height || 400) * dpr;
    this._w = rect.width;
    this._h = rect.height || 400;
    this._dpr = dpr;
  };

  GraphView.prototype.setGraph = function (data) {
    this._nodes = data.nodes || [];
    this._edges = data.edges || [];
    this.draw();
  };

  GraphView.prototype.setStep = function (step) {
    this._currentStep = step;
    this.draw();
  };

  GraphView.prototype.draw = function () {
    var ctx = this.ctx, w = this._w, h = this._h, dpr = this._dpr || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue('--accent').trim() || '#3b82f6';
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var surface = style.getPropertyValue('--surface').trim() || '#181a1f';

    if (this._nodes.length === 0) {
      ctx.fillStyle = muted;
      ctx.font = '12px "SF Mono","Fira Code",monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('No graph data — train and register a model first', w / 2, h / 2);
      return;
    }

    var step = this._currentStep !== undefined ? this._currentStep : Infinity;
    var visibleNodes = this._nodes.filter(function (n) {
      return n.step <= step;
    });
    var visibleIds = {};
    visibleNodes.forEach(function (n) { visibleIds[n.id] = true; });
    var visibleEdges = this._edges.filter(function (e) {
      return visibleIds[e.from] && visibleIds[e.to];
    });

    /* Group nodes by depth */
    var layers = {};
    visibleNodes.forEach(function (n) {
      var depth = n.depth !== undefined ? n.depth : 0;
      if (!layers[depth]) layers[depth] = [];
      layers[depth].push(n);
    });

    var keys = Object.keys(layers).sort(function (a, b) { return parseInt(a) - parseInt(b); });
    var nodeW = 100, nodeH = 30;

    /* Store node positions for edge drawing */
    var nodePositions = {};

    keys.forEach(function (d) {
      var nodes = layers[d];
      var depth = parseInt(d);
      var totalH = nodes.length * (nodeH + 12) - 12;
      var startY = Math.max(nodeH / 2, (h - totalH) / 2);
      var x = depth * 150 + 60;
      nodes.forEach(function (n, i) {
        var y = startY + i * (nodeH + 12);
        nodePositions[n.id] = { x: x, y: y, depth: depth };

        /* Node rect */
        ctx.fillStyle = surface;
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(x - nodeW / 2, y - nodeH / 2, nodeW, nodeH, 6);
        ctx.fill();
        ctx.stroke();

        /* Node label */
        ctx.fillStyle = accent;
        ctx.font = '10px "SF Mono","Fira Code",monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(n.label || n.op || '?', x, y);

        /* Value display */
        if (n.value !== undefined && n.value !== null) {
          ctx.fillStyle = muted;
          ctx.font = '8px "SF Mono","Fira Code",monospace';
          ctx.textBaseline = 'top';
          var valStr = typeof n.value === 'number' ? n.value.toFixed(4) : String(n.value);
          ctx.fillText(valStr, x, y + nodeH / 2 + 2);
        }
      });
    });

    /* Draw edges */
    ctx.strokeStyle = muted;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.4;
    visibleEdges.forEach(function (e) {
      var fromPos = nodePositions[e.from];
      var toPos = nodePositions[e.to];
      if (!fromPos || !toPos) return;
      ctx.beginPath();
      ctx.moveTo(fromPos.x + nodeW / 2, fromPos.y);
      ctx.lineTo(toPos.x - nodeW / 2, toPos.y);
      ctx.stroke();
    });
    ctx.globalAlpha = 1;
  };

  window.GraphView = GraphView;
})();