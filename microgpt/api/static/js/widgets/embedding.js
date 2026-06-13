(function() {
  'use strict';

  function EmbeddingWidget(container) {
    this.container = container;
    this._angle = 0;
    this._render();
    this._bindKeys();
  }

  EmbeddingWidget.prototype._render = function() {
    this.container.innerHTML =
      '<canvas id="embedding-canvas" class="embedding-canvas" tabindex="0" aria-label="2D embedding projection, use arrow keys to rotate"></canvas>' +
      '<p class="widget-hint text-mono">Arrow keys to rotate projection</p>';
    this._canvas = this.container.querySelector('#embedding-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._resize();
    this._draw();
  };

  EmbeddingWidget.prototype._resize = function() {
    var w = this.container.clientWidth || 300;
    var h = 200;
    this._canvas.width = w;
    this._canvas.height = h;
    this._canvas.style.width = w + 'px';
    this._canvas.style.height = h + 'px';
    this._w = w;
    this._h = h;
  };

  EmbeddingWidget.prototype._draw = function() {
    var ctx = this._ctx;
    var cx = this._w / 2, cy = this._h / 2;
    ctx.clearRect(0, 0, this._w, this._h);
    var words = ['king', 'queen', 'man', 'woman', 'apple', 'orange'];
    var colors = ['#3b82f6', '#ef4444', '#3b82f6', '#ef4444', '#10b981', '#10b981'];
    var points = words.map(function(w, i) {
      var a = (i / words.length) * Math.PI * 2 + this._angle;
      var r = 60 + (i % 3) * 15;
      return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r, label: w, color: colors[i] };
    }, this);
    ctx.font = '14px "SF Mono", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    points.forEach(function(p) {
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#888';
      ctx.fillText(p.label, p.x, p.y - 14);
    });
  };

  EmbeddingWidget.prototype._bindKeys = function() {
    var self = this;
    this._canvas.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowLeft') { self._angle -= 0.1; self._draw(); e.preventDefault(); }
      if (e.key === 'ArrowRight') { self._angle += 0.1; self._draw(); e.preventDefault(); }
    });
  };

  window.EmbeddingWidget = EmbeddingWidget;
})();