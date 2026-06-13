(function() {
  'use strict';

  var TOKENS = ['the', ' ', 'quick', ' ', 'brown', ' ', 'fox'];

  function AttentionWidget(container) {
    this.container = container;
    this._tokens = TOKENS;
    this._activeIndex = -1;
    this._render();
    this._bindKeys();
  }

  AttentionWidget.prototype._render = function() {
    var html = '<div class="attention-heatmap" role="grid" aria-label="Attention heatmap">';
    html += '<div class="attention-tokens" role="row">';
    for (var i = 0; i < this._tokens.length; i++) {
      var active = i === this._activeIndex ? ' active' : '';
      var intensity = this._activeIndex >= 0 ? Math.abs(i - this._activeIndex) / this._tokens.length : 0.3;
      var alpha = 1 - intensity;
      html += '<span class="attention-token' + active + '" data-idx="' + i + '" tabindex="0" role="gridcell" style="opacity:' + alpha + '">' + this._tokens[i] + '</span>';
    }
    html += '</div></div>';
    this.container.innerHTML = html;

    var self = this;
    this.container.querySelectorAll('.attention-token').forEach(function(el) {
      el.addEventListener('click', function() {
        self._activeIndex = parseInt(this.getAttribute('data-idx'));
        self._render();
      });
      el.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          self._activeIndex = parseInt(this.getAttribute('data-idx'));
          self._render();
        }
      });
    });
  };

  AttentionWidget.prototype._bindKeys = function() {
    var self = this;
    this.container.addEventListener('keydown', function(e) {
      var tokens = self.container.querySelectorAll('.attention-token');
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        var next = (self._activeIndex + 1) % tokens.length;
        tokens[next].focus();
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        var prev = (self._activeIndex - 1 + tokens.length) % tokens.length;
        tokens[prev].focus();
      }
    });
  };

  window.AttentionWidget = AttentionWidget;
})();