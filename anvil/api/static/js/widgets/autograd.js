/* AutogradWidget — renders computation graph with gradient information */
(function () {
  'use strict';

  function AutogradWidget(container) {
    this.container = container;
    this._data = null;
    this._inputVal = 'the quick fox';
    this._debounceTimer = null;
    this._render();
  }

  AutogradWidget.prototype._render = function () {
    this.container.innerHTML =
      '<div class="widget-controls" style="display:flex;gap:var(--space-2);margin-bottom:var(--space-2);">'
      + '<input type="text" class="widget-input" id="ag-input" '
      + '  value="' + this._inputVal + '" placeholder="Type text to trace...">'
      + '<button class="btn btn-secondary btn-sm" id="ag-trace-btn">Trace</button>'
      + '</div>'
      + '<div class="widget-stats" id="ag-stats" style="display:flex;gap:var(--space-4);margin-bottom:var(--space-2);font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);"></div>'
      + '<div class="widget-legend" id="ag-legend" style="display:flex;gap:var(--space-2);flex-wrap:wrap;margin-bottom:var(--space-2);font-size:0.65rem;font-family:var(--font-mono);"></div>'
      + '<canvas id="ag-canvas" class="graph-canvas" style="width:100%;height:300px;"></canvas>';

    this._input = this.container.querySelector('#ag-input');
    this._statsEl = this.container.querySelector('#ag-stats');
    this._legendEl = this.container.querySelector('#ag-legend');
    this._canvas = this.container.querySelector('#ag-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._traceBtn = this.container.querySelector('#ag-trace-btn');

    var self = this;
    this._input.addEventListener('input', function () {
      self._inputVal = this.value;
      self._debouncedFetch();
    });
    this._traceBtn.addEventListener('click', function () {
      self._inputVal = self._input.value;
      self._fetch();
    });

    this._buildLegend();
    this._fetch();
  };

  AutogradWidget.prototype._buildLegend = function () {
    var colors = {
      'input': '#34d399', 'add': '#3b82f6', 'mul': '#f59e0b',
      'pow': '#a78bfa', 'log': '#f59e0b', 'exp': '#ef4444',
      'silu': '#38bdf8', 'combine': '#8a8c94'
    };
    var html = '';
    for (var op in colors) {
      html += '<span style="display:flex;align-items:center;gap:4px;">'
        + '<span style="width:10px;height:10px;border-radius:2px;background:' + colors[op] + ';"></span>'
        + '<span>' + op + '</span></span>';
    }
    this._legendEl.innerHTML = html;
  };

  AutogradWidget.prototype._debouncedFetch = function () {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () { self._fetch(); }, 400);
  };

  AutogradWidget.prototype._fetch = function () {
    var self = this;
    var text = this._inputVal.trim();
    if (!text) return;

    fetch('/v1/inference/backward-graph', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        self._data = data;
        self._renderStats(data);
        self._draw();
      })
      .catch(function () { /* silent fail */ });
  };

  AutogradWidget.prototype._renderStats = function (data) {
    var m = data.metadata || {};
    this._statsEl.innerHTML =
      '<span>nodes: ' + (m.total_nodes || '?') + '</span>'
      + '<span>edges: ' + (m.total_edges || '?') + '</span>'
      + '<span>depth: ' + (m.max_depth || '?') + '</span>'
      + '<span>loss: ' + (m.loss_value != null ? m.loss_value.toFixed(4) : '?') + '</span>';
  };

  AutogradWidget.prototype._draw = function () {
    var data = this._data;
    if (!data || !data.nodes || !data.nodes.length) return;

    var canvas = this._canvas;
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.clientWidth || 400;
    var h = canvas.clientHeight || 300;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    var ctx = this._ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var style = getComputedStyle(document.documentElement);
    var colors = {
      'input': style.getPropertyValue('--accent-green').trim() || '#34d399',
      'add': style.getPropertyValue('--accent').trim() || '#3b82f6',
      'mul': style.getPropertyValue('--accent-warn').trim() || '#f59e0b',
      'pow': style.getPropertyValue('--accent-magenta').trim() || '#a78bfa',
      'log': style.getPropertyValue('--accent-warn').trim() || '#f59e0b',
      'exp': style.getPropertyValue('--accent-error').trim() || '#ef4444',
      'silu': style.getPropertyValue('--accent-cyan').trim() || '#38bdf8',
      'combine': style.getPropertyValue('--text-muted').trim() || '#8a8c94'
    };

    var nodes = data.nodes;
    var edges = data.edges || [];

    // Layout: group by depth
    var depthMap = {};
    var maxDepth = 0;
    nodes.forEach(function (n) {
      if (!depthMap[n.depth]) depthMap[n.depth] = [];
      depthMap[n.depth].push(n);
      if (n.depth > maxDepth) maxDepth = n.depth;
    });

    var pad = 20;
    var nodeW = 100;
    var nodeH = 44;
    var vGap = 20;
    var hGap = 12;
    var depths = Object.keys(depthMap).sort(function (a, b) { return parseInt(a) - parseInt(b); });

    var yPositions = {};
    depths.forEach(function (d) {
      yPositions[d] = pad + parseInt(d) * (nodeH + vGap);
    });

    var nodePositions = {};
    depths.forEach(function (d) {
      var layer = depthMap[d];
      var totalW = layer.length * nodeW + (layer.length - 1) * hGap;
      var startX = (w - totalW) / 2;
      layer.forEach(function (n, i) {
        nodePositions[n.id] = { x: startX + i * (nodeW + hGap), y: yPositions[d] };
      });
    });

    // Draw edges
    ctx.lineWidth = 1;
    edges.forEach(function (e) {
      var from = nodePositions[e.from];
      var to = nodePositions[e.to];
      if (!from || !to) return;
      ctx.beginPath();
      ctx.moveTo(from.x + nodeW / 2, from.y + nodeH);
      ctx.lineTo(to.x + nodeW / 2, to.y);
      ctx.strokeStyle = 'rgba(138,140,148,0.3)';
      ctx.stroke();
    });

    // Draw nodes
    nodes.forEach(function (n) {
      var pos = nodePositions[n.id];
      if (!pos) return;
      var color = colors[n.op] || '#888';
      var bx = pos.x;
      var by = pos.y;

      // Node background
      ctx.fillStyle = 'rgba(24,26,31,0.9)';
      ctx.beginPath();
      ctx.roundRect(bx, by, nodeW, nodeH, 4);
      ctx.fill();

      // Node border
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(bx, by, nodeW, nodeH, 4);
      ctx.stroke();

      // Op label
      ctx.fillStyle = color;
      ctx.font = '9px "SF Mono","Fira Code",monospace';
      ctx.fillText(n.op, bx + 4, by + 12);

      // Value
      ctx.fillStyle = '#e8eaed';
      ctx.font = 'bold 10px "SF Mono","Fira Code",monospace';
      ctx.fillText('v=' + n.value, bx + 4, by + 26);

      // Grad
      if (n.grad !== 0) {
        ctx.fillStyle = n.grad > 0 ? '#34d399' : '#ef4444';
        ctx.font = '9px "SF Mono","Fira Code",monospace';
        ctx.fillText('g=' + n.grad, bx + nodeW - 50, by + 26);
      }
    });
  };

  window.AutogradWidget = AutogradWidget;
})();