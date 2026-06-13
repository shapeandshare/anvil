(function() {
  'use strict';

  function TrainingLoopWidget(container) {
    this.container = container;
    this._step = 0;
    this._render();
  }

  TrainingLoopWidget.prototype._render = function() {
    this.container.innerHTML =
      '<p class="widget-label">Training Step: <span id="tl-step" class="token-value text-mono">' + this._step + '</span></p>' +
      '<input type="range" class="widget-slider" id="tl-scrubber" min="0" max="100" value="0" step="1" aria-label="Training step scrubber">' +
      '<div class="tl-visual" id="tl-visual">' +
      '  <div class="tl-loss" style="width:' + (this._step) + '%;height:4px;background:var(--accent);border-radius:2px;"></div>' +
      '</div>' +
      '<p class="widget-hint text-mono">loss: <span id="tl-loss-value" class="token-value">' + (Math.max(0, 4 - this._step * 0.04)).toFixed(4) + '</span></p>';
    var self = this;
    var slider = this.container.querySelector('#tl-scrubber');
    var stepEl = this.container.querySelector('#tl-step');
    var lossEl = this.container.querySelector('#tl-loss-value');
    var barEl = this.container.querySelector('.tl-loss');
    slider.addEventListener('input', function() {
      self._step = parseInt(this.value);
      stepEl.textContent = self._step;
      var loss = Math.max(0, 4 - self._step * 0.04);
      lossEl.textContent = loss.toFixed(4);
      barEl.style.width = self._step + '%';
    });
  };

  window.TrainingLoopWidget = TrainingLoopWidget;
})();