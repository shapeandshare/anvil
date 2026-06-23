// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function MemoryDivergenceWidget(container) {
    if (!container) return;
    this.container = container;
    this._nEmbed = 16;
    this._nLayer = 1;
    this._step = -1;
    this._playing = false;
    this._timer = null;
    this._reducedMotion = false;
    this._diverged = false;
    this._stage = 0;
    this._available = 4 * 1024 * 1024;

    this._render();
  }

  MemoryDivergenceWidget.prototype._compute = function () {
    var vocabSize = 65;
    var blockSize = 16;
    var fp32 = 4;
    var nEmb = this._nEmbed;
    var nLay = this._nLayer;

    var intermediate = Math.floor(8 * nEmb / 3);
    var paramCount = (vocabSize * nEmb) + (vocabSize * nEmb) + nEmb + nLay * (
      4 * nEmb * nEmb + 3 * intermediate * nEmb + 2 * nEmb
    );
    var weights = paramCount * fp32;
    var gradients = paramCount * fp32;
    var adam = paramCount * fp32 * 2;
    var kv = nLay * 2 * blockSize * nEmb * fp32;
    var total = weights + gradients + adam + kv;
    var peak = total * 2;

    return {
      intermediate: intermediate,
      paramCount: paramCount,
      weights: weights,
      gradients: gradients,
      adam: adam,
      kv: kv,
      total: total,
      peak: peak
    };
  };

  MemoryDivergenceWidget.prototype._formatBytes = function (bytes) {
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
    return (bytes / 1024).toFixed(1) + ' KB';
  };

  MemoryDivergenceWidget.prototype._oomStatus = function (peak) {
    var ratio = peak / this._available;
    if (ratio >= 0.90) {
      return { label: 'would OOM', token: '--accent-red', color: window.AnvilBase.token('--accent-red', '#ff3b30'), cls: 'mdiv-oom-would' };
    }
    if (ratio >= 0.75) {
      return { label: 'close to limit', token: '--accent-orange', color: window.AnvilBase.token('--accent-orange', '#ff9500'), cls: 'mdiv-oom-close' };
    }
    return { label: 'fits', token: '--accent-green', color: window.AnvilBase.token('--accent-green', '#34c759'), cls: 'mdiv-oom-fits' };
  };

  MemoryDivergenceWidget.prototype._genLossData = function () {
    var data = [];
    var val = 4.0 + (Math.random() * 0.5 - 0.25);
    for (var i = 0; i < 30; i++) {
      val = val * 0.87 + (Math.random() * 0.12) + 0.05;
      if (val < 0.3) val = 0.3 + Math.random() * 0.15;
      data.push({ x: i, y: val });
    }
    return data;
  };

  MemoryDivergenceWidget.prototype._render = function () {
    var self = this;
    window.AnvilBase.initReducedMotion(this);

    var accent = window.AnvilBase.token('--accent', '#007aff');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var red = window.AnvilBase.token('--accent-red', '#ff3b30');
    var orange = window.AnvilBase.token('--accent-orange', '#ff9500');
    var purple = window.AnvilBase.token('--accent-purple', '#af52de');
    var cyan = window.AnvilBase.token('--accent-cyan', '#32d74b');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var surface2 = window.AnvilBase.token('--surface-2', '#2c2c2e');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var border = window.AnvilBase.token('--border', '#38383a');
    var radius = window.AnvilBase.token('--radius', '13px');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var body = window.AnvilBase.token('--font-body', '-apple-system,BlinkMacSystemFont,system-ui,sans-serif');
    var space2 = window.AnvilBase.token('--space-2', '0.5rem');
    var space3 = window.AnvilBase.token('--space-3', '0.75rem');
    var space4 = window.AnvilBase.token('--space-4', '1rem');

    var css =
      '<style>' +
      '.mdiv-widget{font-family:' + body + ';color:' + text + ';width:100%;display:flex;flex-direction:column;gap:' + space3 + ';}' +
      '.mdiv-panel{background:' + surface + ';border:1px solid ' + border + ';border-radius:' + radius + ';padding:' + space3 + ' ' + space4 + ';}' +
      '.mdiv-panel-title{font-size:0.85rem;font-weight:600;color:' + text + ';margin-bottom:' + space2 + ';}' +
      '.mdiv-config{display:flex;gap:' + space4 + ';align-items:center;margin-bottom:' + space3 + ';font-size:0.78rem;}' +
      '.mdiv-config-group{display:flex;align-items:center;gap:' + space2 + ';}' +
      '.mdiv-config-label{color:' + muted + ';font-weight:500;}' +
      '.mdiv-stepper{display:inline-flex;background:' + surface2 + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';overflow:hidden;}' +
      '.mdiv-stepper button{background:transparent;border:none;color:' + text + ';padding:4px 10px;font-size:0.78rem;font-weight:500;cursor:pointer;font-family:' + body + ';min-width:32px;text-align:center;transition:background 0.15s;}' +
      '.mdiv-stepper button:hover{background:' + accent + ';color:#fff;}' +
      '.mdiv-stepper button:focus-visible{outline:2px solid ' + accent + ';outline-offset:-2px;}' +
      '.mdiv-stepper button.active-stepper{background:' + accent + ';color:#fff;}' +
      '.mdiv-controls{display:flex;gap:' + space2 + ';margin-bottom:' + space3 + ';}' +
      '.mdiv-btn{background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;}' +
      '.mdiv-btn:hover{filter:brightness(1.15);}' +
      '.mdiv-btn:active{filter:brightness(0.9);}' +
      '.mdiv-btn:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.mdiv-btn-primary{background:' + accent + ';color:#fff;border:none;}' +
      '.mdiv-btn-danger{background:' + red + ';color:#fff;border:none;}' +
      '.mdiv-bar-area{position:relative;margin:' + space2 + ' 0;}' +
      '.mdiv-bar-row{display:flex;align-items:center;gap:' + space2 + ';margin-bottom:6px;}' +
      '.mdiv-bar-track{flex:1;height:28px;border-radius:' + radiusSm + ';background:' + surface2 + ';position:relative;overflow:hidden;display:flex;}' +
      '.mdiv-segment{height:100%;display:flex;align-items:center;justify-content:center;font-size:0.6rem;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;position:relative;transform-origin:left;transition:transform 0.4s,opacity 0.3s;}' +
      '.mdiv-segment-label{position:absolute;left:4px;right:4px;text-align:center;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums;}' +
      '.mdiv-segment-ghost{height:100%;display:flex;align-items:center;justify-content:center;font-size:0.55rem;font-weight:500;white-space:nowrap;overflow:hidden;opacity:0.55;transform-origin:left;transition:transform 0.4s,opacity 0.3s;}' +
      '.mdiv-bar-available-row{display:flex;align-items:center;gap:' + space2 + ';margin-bottom:4px;}' +
      '.mdiv-bar-available-track{flex:1;height:12px;border-radius:' + radiusSm + ';background:' + surface2 + ';position:relative;overflow:hidden;}' +
      '.mdiv-bar-available-fill{height:100%;border-radius:' + radiusSm + ';transition:background 0.3s;}' +
      '.mdiv-bar-available-label{font-size:0.65rem;color:' + muted + ';font-variant-numeric:tabular-nums;font-family:' + mono + ';white-space:nowrap;min-width:72px;text-align:right;}' +
      '.mdiv-bar-label{font-size:0.65rem;color:' + muted + ';font-variant-numeric:tabular-nums;font-family:' + mono + ';white-space:nowrap;min-width:72px;}' +
      '.mdiv-pill{display:inline-flex;align-items:center;gap:6px;padding:3px 12px;border-radius:20px;font-size:0.72rem;font-weight:600;}' +
      '.mdiv-pill-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}' +
      '.mdiv-legend{display:flex;flex-wrap:wrap;gap:6px ' + space3 + ';margin-top:' + space2 + ';}' +
      '.mdiv-legend-item{display:flex;align-items:center;gap:4px;font-size:0.62rem;color:' + muted + ';}' +
      '.mdiv-legend-swatch{width:8px;height:8px;border-radius:2px;flex-shrink:0;}' +
      '.mdiv-curve-wrap{position:relative;margin:' + space2 + ' 0;}' +
      '.mdiv-curve-svg{display:block;width:100%;height:auto;}' +
      '.mdiv-banner{display:flex;align-items:center;gap:' + space2 + ';padding:8px 12px;border-radius:' + radiusSm + ';margin-top:' + space2 + ';font-size:0.78rem;font-weight:500;}' +
      '.mdiv-banner-danger{background:color-mix(in srgb,' + red + ' 15%,transparent);border:1px solid ' + red + ';color:' + red + ';}' +
      '.mdiv-banner-label{font-family:' + mono + ';font-size:0.7rem;opacity:0.8;}' +
      '.mdiv-empty{font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';}' +
      '.mdiv-none{display:none;}' +
      '@media(max-width:500px){.mdiv-config{flex-direction:column;align-items:flex-start;gap:' + space2 + ';}}' +
      '</style>';

    this._lossData = this._genLossData();

    this.container.innerHTML =
      '<div class="mdiv-widget">' +
      css +
      '<div class="mdiv-panel" id="mdiv-panel-a">' +
      '<div class="mdiv-panel-title">Panel A Memory</div>' +
      '<div class="mdiv-config" id="mdiv-config">' +
      '<div class="mdiv-config-group">' +
      '<span class="mdiv-config-label">n_embd</span>' +
      '<span class="mdiv-stepper" id="mdiv-stepper-emb">' +
      '<button class="mdiv-stepper-opt" data-emb="16" aria-label="Set embedding dimension to 16">16</button>' +
      '<button class="mdiv-stepper-opt" data-emb="32" aria-label="Set embedding dimension to 32">32</button>' +
      '<button class="mdiv-stepper-opt" data-emb="64" aria-label="Set embedding dimension to 64">64</button>' +
      '</span>' +
      '</div>' +
      '<div class="mdiv-config-group">' +
      '<span class="mdiv-config-label">n_layer</span>' +
      '<span class="mdiv-stepper" id="mdiv-stepper-lay">' +
      '<button class="mdiv-stepper-lay-opt" data-lay="1" aria-label="Set number of layers to 1">1</button>' +
      '<button class="mdiv-stepper-lay-opt" data-lay="2" aria-label="Set number of layers to 2">2</button>' +
      '<button class="mdiv-stepper-lay-opt" data-lay="4" aria-label="Set number of layers to 4">4</button>' +
      '</span>' +
      '</div>' +
      '</div>' +
      '<div class="mdiv-controls">' +
      '<button class="mdiv-btn mdiv-btn-primary" id="mdiv-play-btn" aria-label="Play memory animation">Play</button>' +
      '<button class="mdiv-btn" id="mdiv-step-btn" aria-label="Step through memory segments">Step</button>' +
      '<button class="mdiv-btn" id="mdiv-reset-btn" aria-label="Reset memory display">Reset</button>' +
      '</div>' +
      '<div id="mdiv-bar-area">' +
      '<div class="mdiv-empty" id="mdiv-empty-msg">Press Play or Step to build the memory bar</div>' +
      '</div>' +
      '<div class="mdiv-legend" id="mdiv-legend">' +
      '<span class="mdiv-legend-item"><span class="mdiv-legend-swatch" style="background:' + accent + ';"></span>Weights</span>' +
      '<span class="mdiv-legend-item"><span class="mdiv-legend-swatch" style="background:' + green + ';"></span>Gradients</span>' +
      '<span class="mdiv-legend-item"><span class="mdiv-legend-swatch" style="background:' + orange + ';"></span>Adam (x2)</span>' +
      '<span class="mdiv-legend-item"><span class="mdiv-legend-swatch" style="background:' + purple + ';"></span>KV cache</span>' +
      '<span class="mdiv-legend-item"><span class="mdiv-legend-swatch" style="background:' + muted + ';opacity:0.55;"></span>2x headroom</span>' +
      '</div>' +
      '</div>' +
      '<div class="mdiv-panel" id="mdiv-panel-b">' +
      '<div class="mdiv-panel-title">Panel B Divergence</div>' +
      '<div class="mdiv-controls">' +
      '<button class="mdiv-btn mdiv-btn-danger" id="mdiv-spike-btn" aria-label="Spike learning rate to simulate divergence">Spike LR</button>' +
      '<button class="mdiv-btn" id="mdiv-curve-reset-btn" aria-label="Reset loss curve to normal">Reset</button>' +
      '</div>' +
      '<div class="mdiv-curve-wrap" id="mdiv-curve-wrap"></div>' +
      '<div id="mdiv-banner-wrap"></div>' +
      '</div>' +
      '</div>';

    this._panelA = this.container.querySelector('#mdiv-panel-a');
    this._barArea = this.container.querySelector('#mdiv-bar-area');
    this._emptyMsg = this.container.querySelector('#mdiv-empty-msg');
    this._legend = this.container.querySelector('#mdiv-legend');
    this._playBtn = this.container.querySelector('#mdiv-play-btn');
    this._stepBtn = this.container.querySelector('#mdiv-step-btn');
    this._resetBtn = this.container.querySelector('#mdiv-reset-btn');
    this._curveWrap = this.container.querySelector('#mdiv-curve-wrap');
    this._bannerWrap = this.container.querySelector('#mdiv-banner-wrap');
    this._spikeBtn = this.container.querySelector('#mdiv-spike-btn');
    this._curveResetBtn = this.container.querySelector('#mdiv-curve-reset-btn');

    this._updateStepperActive();

    var embBtns = this.container.querySelectorAll('.mdiv-stepper-opt');
    var layBtns = this.container.querySelectorAll('.mdiv-stepper-lay-opt');

    for (var ei = 0; ei < embBtns.length; ei++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var val = parseInt(btn.getAttribute('data-emb'), 10);
          if (!isNaN(val) && val !== self._nEmbed) {
            self._clearTimer();
            self._nEmbed = val;
            self._step = -1;
            self._playing = false;
            if (self._playBtn) self._playBtn.textContent = 'Play';
            self._updateStepperActive();
            self._renderEmptyState();
            self._renderBars();
          }
        });
      })(embBtns[ei]);
    }

    for (var li = 0; li < layBtns.length; li++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var val = parseInt(btn.getAttribute('data-lay'), 10);
          if (!isNaN(val) && val !== self._nLayer) {
            self._clearTimer();
            self._nLayer = val;
            self._step = -1;
            self._playing = false;
            if (self._playBtn) self._playBtn.textContent = 'Play';
            self._updateStepperActive();
            self._renderEmptyState();
            self._renderBars();
          }
        });
      })(layBtns[li]);
    }

    if (this._playBtn) {
      this._playBtn.addEventListener('click', function () {
        self._togglePlay();
      });
    }

    if (this._stepBtn) {
      this._stepBtn.addEventListener('click', function () {
        self._doStep();
      });
    }

    if (this._resetBtn) {
      this._resetBtn.addEventListener('click', function () {
        self._resetMemory();
      });
    }

    if (this._spikeBtn) {
      this._spikeBtn.addEventListener('click', function () {
        self._doSpike();
      });
    }

    if (this._curveResetBtn) {
      this._curveResetBtn.addEventListener('click', function () {
        self._resetCurve();
      });
    }

    this._renderCurve();
  };

  MemoryDivergenceWidget.prototype._updateStepperActive = function () {
    var embBtns = this.container.querySelectorAll('.mdiv-stepper-opt');
    var layBtns = this.container.querySelectorAll('.mdiv-stepper-lay-opt');
    var i;

    for (i = 0; i < embBtns.length; i++) {
      var embVal = parseInt(embBtns[i].getAttribute('data-emb'), 10);
      if (embVal === this._nEmbed) {
        embBtns[i].classList.add('active-stepper');
      } else {
        embBtns[i].classList.remove('active-stepper');
      }
    }

    for (i = 0; i < layBtns.length; i++) {
      var layVal = parseInt(layBtns[i].getAttribute('data-lay'), 10);
      if (layVal === this._nLayer) {
        layBtns[i].classList.add('active-stepper');
      } else {
        layBtns[i].classList.remove('active-stepper');
      }
    }
  };

  MemoryDivergenceWidget.prototype._renderEmptyState = function () {
    if (this._emptyMsg) {
      this._emptyMsg.style.display = 'block';
    }
    var existing = this._barArea.querySelectorAll('.mdiv-bar-row, .mdiv-bar-available-row');
    for (var i = 0; i < existing.length; i++) {
      existing[i].parentNode.removeChild(existing[i]);
    }
  };

  MemoryDivergenceWidget.prototype._renderBars = function () {
    if (this._step < 0) {
      return;
    }

    var self = this;
    var mem = this._compute();
    var status = this._oomStatus(mem.peak);
    var statusColor = status.color;
    var avail = this._available;

    var accent = window.AnvilBase.token('--accent', '#007aff');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var orange = window.AnvilBase.token('--accent-orange', '#ff9500');
    var purple = window.AnvilBase.token('--accent-purple', '#af52de');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var surface2 = window.AnvilBase.token('--surface-2', '#2c2c2e');

    var segments = [];
    var segColors = [accent, green, orange, purple];
    var segNames = ['W', 'G', 'A(x2)', 'KV'];
    var segValues = [mem.weights, mem.gradients, mem.adam, mem.kv];
    var showCount = Math.min(this._step + 1, 4);

    for (var i = 0; i < showCount; i++) {
      segments.push({
        name: segNames[i],
        value: segValues[i],
        color: segColors[i],
        pct: (segValues[i] / mem.peak) * 100
      });
    }

    var showGhost = this._step >= 4;
    var showAvailable = this._step >= 5;

    var barRow = document.createElement('div');
    barRow.className = 'mdiv-bar-row';

    var label = document.createElement('span');
    label.className = 'mdiv-bar-label';
    label.textContent = 'Peak';
    barRow.appendChild(label);

    var track = document.createElement('div');
    track.className = 'mdiv-bar-track';

    for (var s = 0; s < segments.length; s++) {
      var seg = segments[s];
      var segEl = document.createElement('div');
      segEl.className = 'mdiv-segment';
      segEl.style.width = seg.pct + '%';
      segEl.style.background = seg.color;
      segEl.style.transform = 'scaleX(1)';

      var segLabel = document.createElement('span');
      segLabel.className = 'mdiv-segment-label';
      segLabel.textContent = seg.name + ' ' + this._formatBytes(seg.value);
      segEl.appendChild(segLabel);

      track.appendChild(segEl);
    }

    var ghostW = (mem.peak - mem.total) / mem.peak * 100;
    if (showGhost && ghostW > 1) {
      var ghostEl = document.createElement('div');
      ghostEl.className = 'mdiv-segment-ghost';
      ghostEl.style.width = ghostW + '%';
      ghostEl.style.background = muted;
      ghostEl.textContent = '2x headroom ' + this._formatBytes(mem.peak - mem.total);
      track.appendChild(ghostEl);
    }

    barRow.appendChild(track);

    var oldBar = this._barArea.querySelectorAll('.mdiv-bar-row, .mdiv-bar-available-row');
    for (var r = 0; r < oldBar.length; r++) {
      oldBar[r].parentNode.removeChild(oldBar[r]);
    }
    if (this._emptyMsg) {
      this._emptyMsg.style.display = 'none';
    }

    this._barArea.appendChild(barRow);

    if (showAvailable) {
      var availRow = document.createElement('div');
      availRow.className = 'mdiv-bar-available-row';

      var availLabel = document.createElement('span');
      availLabel.className = 'mdiv-bar-label';
      availLabel.textContent = 'Avail';
      availRow.appendChild(availLabel);

      var availTrack = document.createElement('div');
      availTrack.className = 'mdiv-bar-available-track';

      var fillPct = Math.min((mem.peak / avail) * 100, 100);
      var availFill = document.createElement('div');
      availFill.className = 'mdiv-bar-available-fill';
      availFill.style.width = fillPct + '%';
      availFill.style.background = status.color;
      availTrack.appendChild(availFill);

      if (mem.peak > avail) {
        var overEl = document.createElement('div');
        overEl.style.cssText += 'position:absolute;right:0;top:0;bottom:0;width:' + Math.min((mem.peak - avail) / avail * 100, 100) + '%;background:' + window.AnvilBase.token('--accent-red', '#ff3b30') + ';opacity:0.15;border-radius:' + window.AnvilBase.token('--radius-sm', '8px') + ';';
        availTrack.appendChild(overEl);
      }

      availRow.appendChild(availTrack);

      var availVal = document.createElement('span');
      availVal.className = 'mdiv-bar-available-label';
      availVal.textContent = this._formatBytes(avail);
      availRow.appendChild(availVal);

      this._barArea.appendChild(availRow);

      var pillRow = document.createElement('div');
      pillRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:8px;';

      var pill = document.createElement('span');
      pill.className = 'mdiv-pill';
      pill.style.background = 'color-mix(in srgb,' + status.color + ' 15%,transparent)';
      pill.style.border = '1px solid ' + status.color;
      pill.style.color = status.color;

      var dot = document.createElement('span');
      dot.className = 'mdiv-pill-dot';
      dot.style.background = status.color;
      pill.appendChild(dot);

      var pillText = document.createElement('span');
      pillText.textContent = status.label;
      pill.appendChild(pillText);

      pillRow.appendChild(pill);

      var utilPct = ((mem.peak / avail) * 100).toFixed(1);
      var utilSpan = document.createElement('span');
      utilSpan.style.cssText = 'font-size:0.65rem;font-family:' + mono + ';color:' + muted + ';font-variant-numeric:tabular-nums;';
      utilSpan.textContent = utilPct + '% of budget';
      pillRow.appendChild(utilSpan);

      this._barArea.appendChild(pillRow);
    }
  };

  MemoryDivergenceWidget.prototype._renderCurve = function () {
    var data = this._lossData;
    var w = 300;
    var h = 140;
    var pad = { t: 10, r: 10, b: 20, l: 30 };
    var pw = w - pad.l - pad.r;
    var ph = h - pad.t - pad.b;

    var minX = 0;
    var maxX = data.length - 1;
    var minY = 0;
    var maxY = 5.0;

    var points = [];
    for (var i = 0; i < data.length; i++) {
      var px = pad.l + (data[i].x / maxX) * pw;
      var py = pad.t + (1 - (data[i].y - minY) / (maxY - minY)) * ph;
      points.push(px.toFixed(1) + ',' + py.toFixed(1));
    }

    var strokeColor = this._diverged ? window.AnvilBase.token('--accent-red', '#ff3b30') : window.AnvilBase.token('--accent', '#007aff');
    var fillColor = this._diverged ? 'rgba(255,59,48,0.08)' : 'rgba(0,122,255,0.08)';

    var fillPoints = points.slice();
    var lastX = pad.l + (maxX / maxX) * pw;
    var bottomY = pad.t + ph;
    fillPoints.push(lastX.toFixed(1) + ',' + bottomY.toFixed(1));
    fillPoints.push(pad.l + ',' + bottomY.toFixed(1));

    var accent = window.AnvilBase.token('--accent', '#007aff');
    var redColor = window.AnvilBase.token('--accent-red', '#ff3b30');
    var mutedColor = window.AnvilBase.token('--text-muted', '#8e8e93');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');

    var svgHtml =
      '<svg class="mdiv-curve-svg" viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Training loss curve showing ' + (this._diverged ? 'divergence spike' : 'healthy downward trend') + '">' +
      '<line x1="' + pad.l + '" y1="' + pad.t + '" x2="' + (w - pad.r) + '" y2="' + pad.t + '" stroke="' + mutedColor + '" stroke-opacity="0.15" stroke-width="1"/>' +
      '<line x1="' + pad.l + '" y1="' + (pad.t + ph * 0.5) + '" x2="' + (w - pad.r) + '" y2="' + (pad.t + ph * 0.5) + '" stroke="' + mutedColor + '" stroke-opacity="0.15" stroke-width="1"/>' +
      '<line x1="' + pad.l + '" y1="' + (pad.t + ph) + '" x2="' + (w - pad.r) + '" y2="' + (pad.t + ph) + '" stroke="' + mutedColor + '" stroke-opacity="0.25" stroke-width="1"/>' +
      '<text x="' + (pad.l - 6) + '" y="' + (pad.t + 4) + '" fill="' + mutedColor + '" font-size="9" font-family="' + mono + '" text-anchor="end" font-variant-numeric="tabular-nums">5.0</text>' +
      '<text x="' + (pad.l - 6) + '" y="' + (pad.t + ph * 0.5 + 4) + '" fill="' + mutedColor + '" font-size="9" font-family="' + mono + '" text-anchor="end" font-variant-numeric="tabular-nums">2.5</text>' +
      '<text x="' + (pad.l - 6) + '" y="' + (pad.t + ph + 4) + '" fill="' + mutedColor + '" font-size="9" font-family="' + mono + '" text-anchor="end" font-variant-numeric="tabular-nums">0.0</text>' +
      '<polygon points="' + fillPoints.join(' ') + '" fill="' + fillColor + '"/>' +
      '<polyline points="' + points.join(' ') + '" fill="none" stroke="' + strokeColor + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>' +
      '</svg>';

    this._curveWrap.innerHTML = svgHtml;

    if (this._diverged) {
      var red = window.AnvilBase.token('--accent-red', '#ff3b30');
      var textColor = window.AnvilBase.token('--text', '#ffffff');
      this._bannerWrap.innerHTML =
        '<div class="mdiv-banner mdiv-banner-danger">' +
        '<span style="font-weight:700;">DivergenceError — LOSS_NAN</span>' +
        '<span class="mdiv-banner-label">run halted</span>' +
        '</div>';
    } else {
      this._bannerWrap.innerHTML = '';
    }
  };

  MemoryDivergenceWidget.prototype._clearTimer = function () {
    window.AnvilBase.stop(this);
    this._playing = false;
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  MemoryDivergenceWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._clearTimer();
    } else {
      this._startPlay();
    }
  };

  MemoryDivergenceWidget.prototype._startPlay = function () {
    var self = this;
    if (this._playing) return;

    if (this._step >= 5) {
      this._step = -1;
    }

    this._playing = true;
    if (this._playBtn) {
      this._playBtn.textContent = 'Pause';
    }

    if (this._reducedMotion) {
      this._step = 5;
      this._playing = false;
      if (this._playBtn) this._playBtn.textContent = 'Play';
      this._renderBars();
      return;
    }

    var interval = 600;

    this._timer = setInterval(function () {
      var next = self._step + 1;
      if (next > 5) {
        self._clearTimer();
        return;
      }
      self._step = next;
      self._renderBars();
    }, interval);
  };

  MemoryDivergenceWidget.prototype._doStep = function () {
    this._clearTimer();
    var next = this._step + 1;
    if (next > 5) return;
    this._step = next;
    this._renderBars();
  };

  MemoryDivergenceWidget.prototype._resetMemory = function () {
    this._clearTimer();
    this._step = -1;
    this._renderEmptyState();
    var existing = this._barArea.querySelectorAll('.mdiv-bar-row, .mdiv-bar-available-row');
    for (var i = 0; i < existing.length; i++) {
      existing[i].parentNode.removeChild(existing[i]);
    }
    if (this._emptyMsg) {
      this._emptyMsg.style.display = 'block';
    }
  };

  MemoryDivergenceWidget.prototype._doSpike = function () {
    this._diverged = true;
    var data = this._genLossData();
    var len = data.length;
    var spikeStart = Math.floor(len * 0.7);
    for (var i = spikeStart; i < len; i++) {
      data[i].y = 4.0 + Math.random() * 1.0;
    }
    data[len - 1].y = 12.0;
    this._lossData = data;
    this._renderCurve();
  };

  MemoryDivergenceWidget.prototype._resetCurve = function () {
    this._diverged = false;
    this._lossData = this._genLossData();
    this._renderCurve();
  };

  window.MemoryDivergenceWidget = MemoryDivergenceWidget;
})();