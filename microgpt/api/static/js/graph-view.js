(function() {
  'use strict';

  function GraphView(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this._nodes = [];
    this._edges = [];
    this._currentStep = 0;
    this._allSteps = options.steps || [];
    this._renderStep = options.onStepRender || null;
    this._resize();
  }

  GraphView.prototype._resize = function() {
    var rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height || 400;
    this._w = this.canvas.width;
    this._h = this.canvas.height;
  };

  GraphView.prototype.setGraph = function(data) {
    this._nodes = data.nodes || [];
    this._edges = data.edges || [];
    this.draw();
  };

  GraphView.prototype.setStep = function(step) {
    this._currentStep = step;
    this.draw();
  };

  GraphView.prototype.draw = function() {
    var ctx = this.ctx, w = this._w, h = this._h;
    ctx.clearRect(0, 0, w, h);

    var visibleNodes = this._nodes.filter(function(n) { return n.step <= this._currentStep; }.bind(this));
    if (visibleNodes.length === 0) {
      ctx.fillStyle = '#888';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Scrub forward to build the graph', w / 2, h / 2);
      return;
    }

    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue('--accent').trim() || '#3b82f6';
    var muted = style.getPropertyValue('--text-muted').trim() || '#888';
    var border = style.getPropertyValue('--border').trim() || '#333';

    var layers = {};
    visibleNodes.forEach(function(n) {
      var depth = n.depth || 0;
      if (!layers[depth]) layers[depth] = [];
      layers[depth].push(n);
    });

    var keys = Object.keys(layers).sort();
    var nodeW = 100, nodeH = 30;
    keys.forEach(function(d) {
      var nodes = layers[d];
      var totalH = nodes.length * (nodeH + 10);
      var startY = (h - totalH) / 2 + nodeH / 2;
      var x = parseInt(d) * 140 + 30;
      nodes.forEach(function(n, i) {
        var y = startY + i * (nodeH + 10);
        ctx.fillStyle = border;
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(x - nodeW / 2, y - nodeH / 2, nodeW, nodeH, 4);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = accent;
        ctx.font = '11px "SF Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(n.label || n.op || '?', x, y);
      });
    });

    var visibleEdgeNodes = {};
    visibleNodes.forEach(function(n) { visibleEdgeNodes[n.id] = true; });
    this._edges.forEach(function(e) {
      if (!visibleEdgeNodes[e.from] || !visibleEdgeNodes[e.to]) return;
      var fromNode = this._nodes.find(function(n) { return n.id === e.from; });
      var toNode = this._nodes.find(function(n) { return n.id === e.to; });
      if (!fromNode || !toNode) return;
      var fromDepth = fromNode.depth || 0;
      var toDepth = toNode.depth || 0;
      ctx.strokeStyle = muted;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(fromDepth * 140 + 30 + nodeW / 2, fromNode._y || 0);
      ctx.lineTo(toDepth * 140 + 30 - nodeW / 2, toNode._y || 0);
      ctx.stroke();
    }.bind(this));
  };

  window.GraphView = GraphView;
})();