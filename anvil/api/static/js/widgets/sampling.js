// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var STEP_KEYS = [
    'from-logits-to-probabilities',
    'temperature',
    'top-k-sampling',
    'reading-the-distribution',
    'sampling-in-practice'
  ];

  function reducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function lerp(a, b, t) { return a + (b - a) * t; }

  function softmaxStable(arr) {
    if (!arr.length) return [];
    var m = arr[0];
    for (var i = 1; i < arr.length; i++) { if (arr[i] > m) m = arr[i]; }
    var exps = [];
    var total = 0;
    for (var j = 0; j < arr.length; j++) {
      var e = Math.exp(arr[j] - m);
      exps.push(e);
      total += e;
    }
    for (var k = 0; k < exps.length; k++) { exps[k] = exps[k] / total; }
    return exps;
  }

  function displayChar(c) {
    if (c === '<BOS>') return 'BOS';
    if (c === ' ') return '\u2423';
    if (c === '\n') return '\\n';
    if (c === '\t') return '\\t';
    return c;
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function SamplingWidget(container) {
    this.container = container;
    this._temperature = 1.0;
    this._topK = null;
    this._prompt = 'the';
    this._stepKey = STEP_KEYS[0];
    this._debounceTimer = null;
    this._raf = null;
    this._anim = null;
    this._sampled = null;
    this._data = null;
    this._dpr = window.devicePixelRatio || 1;

    this._onStep = this._handleStep.bind(this);
    this._onResize = this._handleResize.bind(this);
    document.addEventListener('concept:stepchange', this._onStep);
    window.addEventListener('resize', this._onResize);

    this._render();
  }

  SamplingWidget.prototype._render = function () {
    this.container.innerHTML =
      '<div class="sampling-stage">' +
      '  <div class="sampling-head">' +
      '    <span class="sampling-context text-mono">context: <span class="sampling-context-prompt">' + displayChar(this._prompt) + '</span></span>' +
      '    <span class="sampling-hero-chip" id="sampling-hero">most likely: <span class="text-mono">\u2014</span></span>' +
      '  </div>' +
      '  <div class="sampling-controls">' +
      '    <label class="sampling-control" id="ctl-temp">' +
      '      <span class="widget-label">Temperature: <span id="temp-value" class="token-value text-mono">' + this._temperature.toFixed(1) + '</span></span>' +
      '      <input type="range" class="widget-slider" id="temp-slider" min="0.1" max="2" step="0.1" value="' + this._temperature + '" aria-label="Temperature">' +
      '    </label>' +
      '    <label class="sampling-control" id="ctl-topk">' +
      '      <span class="widget-label">Top-K: <span id="topk-value" class="token-value text-mono">\u2014</span></span>' +
      '      <input type="range" class="widget-slider" id="topk-slider" min="1" max="20" step="1" value="20" aria-label="Top-K">' +
      '    </label>' +
      '    <button type="button" class="sampling-btn" id="sample-btn" disabled>Sample a token</button>' +
      '  </div>' +
      '  <canvas id="sampling-canvas" class="sampling-canvas" role="img" aria-label="Next-token probability distribution"></canvas>' +
      '  <div class="sampling-status" id="sampling-status" aria-live="polite"></div>' +
      '  <p class="sr-only" id="sampling-sr" aria-live="polite"></p>' +
      '  <div class="widget-empty-state" id="sample-empty" style="display:none" role="alert">' +
      '    <p class="widget-empty-text">Couldn\'t load sampling distribution \u2014 <a href="/v1/training-page" class="widget-empty-link">train a model first</a></p>' +
      '  </div>' +
      '</div>';

    var self = this;
    this._canvas = this.container.querySelector('#sampling-canvas');
    this._ctx = this._canvas.getContext('2d');
    this._statusEl = this.container.querySelector('#sampling-status');
    this._srEl = this.container.querySelector('#sampling-sr');
    this._emptyEl = this.container.querySelector('#sample-empty');
    this._heroEl = this.container.querySelector('#sampling-hero');
    this._tempSlider = this.container.querySelector('#temp-slider');
    this._topkSlider = this.container.querySelector('#topk-slider');
    this._sampleBtn = this.container.querySelector('#sample-btn');
    this._ctlTemp = this.container.querySelector('#ctl-temp');
    this._ctlTopk = this.container.querySelector('#ctl-topk');

    this._tempSlider.addEventListener('input', function () {
      self._temperature = parseFloat(this.value);
      self.container.querySelector('#temp-value').textContent = self._temperature.toFixed(1);
      self._sampled = null;
      self._debouncedFetch();
    });
    this._topkSlider.addEventListener('input', function () {
      self._topK = parseInt(this.value, 10);
      self.container.querySelector('#topk-value').textContent = self._topK;
      self._sampled = null;
      self._debouncedFetch();
    });
    this._sampleBtn.addEventListener('click', function () { self._sampleOnce(); });

    this._resize();
    this._applyStepControls();
    this._fetch();
  };

  SamplingWidget.prototype._handleStep = function (e) {
    if (!e || !e.detail) return;
    var key = e.detail.stepKey;
    if (STEP_KEYS.indexOf(key) === -1) return;
    this._stepKey = key;
    this._sampled = null;
    this._applyStepControls();
    this._draw();
  };

  SamplingWidget.prototype._stepIndex = function () {
    var i = STEP_KEYS.indexOf(this._stepKey);
    return i === -1 ? 0 : i;
  };

  SamplingWidget.prototype._applyStepControls = function () {
    var step = this._stepIndex();
    var tempOn = true, topkOn = true, sampleOn = false, samplePrimary = false;
    var tempHi = false, topkHi = false;

    if (step === 0) { tempOn = false; topkOn = false; }
    else if (step === 1) { tempOn = true; topkOn = false; tempHi = true; }
    else if (step === 2) { tempOn = false; topkOn = true; topkHi = true; }
    else if (step === 3) { tempOn = true; topkOn = true; sampleOn = true; }
    else if (step === 4) { tempOn = true; topkOn = true; sampleOn = true; samplePrimary = true; }

    this._tempSlider.disabled = !tempOn;
    this._topkSlider.disabled = !topkOn;
    this._sampleBtn.disabled = !sampleOn || !this._data;

    this._ctlTemp.classList.toggle('is-highlight', tempHi);
    this._ctlTopk.classList.toggle('is-highlight', topkHi);
    this._ctlTemp.classList.toggle('is-disabled', !tempOn);
    this._ctlTopk.classList.toggle('is-disabled', !topkOn);
    this._sampleBtn.classList.toggle('is-primary', samplePrimary && sampleOn);
  };

  SamplingWidget.prototype._debouncedFetch = function () {
    var self = this;
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(function () { self._fetch(); }, 250);
  };

  SamplingWidget.prototype._fetch = function () {
    var self = this;
    this._statusEl.innerHTML = '<span class="loading-indicator"><span class="spinner"></span> Sampling\u2026</span>';
    this._emptyEl.style.display = 'none';

    var body = { prompt: this._prompt, temperature: this._temperature };
    if (this._topK != null) body.top_k = this._topK;

    fetch('/v1/inference/sampling-distribution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
      .then(function (res) {
        var data = res.json;
        if (!res.ok || data.error === 'no_model' || data.detail === 'No model available' || !data.tokens || !data.tokens.length) {
          self._showEmpty();
          return;
        }
        self._ingest(data);
      })
      .catch(function () { self._showEmpty(); });
  };

  SamplingWidget.prototype._showEmpty = function () {
    this._data = null;
    this._statusEl.innerHTML = '';
    this._clearCanvas();
    this._emptyEl.style.display = '';
    this._sampleBtn.disabled = true;
  };

  SamplingWidget.prototype._ingest = function (data) {
    var tokens = data.tokens.slice().sort(function (a, b) { return b.raw_logit - a.raw_logit; });
    var rawLogits = tokens.map(function (t) { return t.raw_logit; });

    this._data = {
      tokens: tokens,
      baseProbs: softmaxStable(rawLogits),
      vocabSize: data.vocab_size,
      temperature: data.temperature,
      topK: data.top_k,
      topKEffective: data.top_k_effective
    };

    if (this._topK == null) this._topK = data.top_k;
    this._topkSlider.max = String(data.vocab_size);
    if (this._topK > data.vocab_size) this._topK = data.vocab_size;
    this._topkSlider.value = String(this._topK);
    this.container.querySelector('#topk-value').textContent = this._topK;

    this._statusEl.innerHTML = '';
    this._emptyEl.style.display = 'none';
    this._applyStepControls();
    this._updateHero();
    this._updateSrSummary();
    this._draw();
  };

  SamplingWidget.prototype._updateHero = function () {
    if (!this._data) return;
    var top = this._data.tokens[0];
    this._heroEl.innerHTML = 'most likely: <span class="text-mono">' +
      escapeHtml(displayChar(top.char)) + ' \u00b7 ' + (top.prob_final * 100).toFixed(1) + '%</span>';
  };

  SamplingWidget.prototype._updateSrSummary = function () {
    if (!this._data) { this._srEl.textContent = ''; return; }
    var parts = [];
    var n = Math.min(5, this._data.tokens.length);
    for (var i = 0; i < n; i++) {
      var t = this._data.tokens[i];
      parts.push(displayChar(t.char) + ' ' + (t.prob_final * 100).toFixed(1) + '%');
    }
    this._srEl.textContent = 'Top tokens: ' + parts.join(', ') + '.';
  };

  SamplingWidget.prototype._handleResize = function () {
    this._resize();
    this._draw();
  };

  SamplingWidget.prototype._resize = function () {
    var w = this.container.clientWidth || 320;
    this._mobile = w < 480;
    var h = this._mobile ? 304 : 336;
    this._dpr = window.devicePixelRatio || 1;
    this._canvas.width = Math.round(w * this._dpr);
    this._canvas.height = Math.round(h * this._dpr);
    this._canvas.style.height = h + 'px';
    this._w = w;
    this._h = h;
  };

  SamplingWidget.prototype._clearCanvas = function () {
    if (!this._ctx) return;
    this._ctx.setTransform(1, 0, 0, 1, 0, 0);
    this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
  };

  SamplingWidget.prototype._palette = function () {
    var s = getComputedStyle(document.documentElement);
    return {
      text: s.getPropertyValue('--text').trim() || '#fff',
      textTertiary: s.getPropertyValue('--text-tertiary').trim() || '#8e8e93',
      surface: s.getPropertyValue('--surface').trim() || '#1c1c1e',
      surface2: s.getPropertyValue('--surface-2').trim() || '#2c2c2e',
      separator: s.getPropertyValue('--separator').trim() || '#38383a',
      accent: s.getPropertyValue('--accent').trim() || '#007aff',
      purple: s.getPropertyValue('--accent-purple').trim() || '#af52de',
      green: s.getPropertyValue('--accent-green').trim() || '#34c759'
    };
  };

  SamplingWidget.prototype._visibleCount = function () {
    return this._mobile ? 6 : 8;
  };

  SamplingWidget.prototype._draw = function () {
    if (!this._ctx) return;
    this._clearCanvas();
    if (!this._data) return;

    var ctx = this._ctx;
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    ctx.clearRect(0, 0, this._w, this._h);

    var step = this._stepIndex();
    if (step === 0) {
      this._drawSplit(ctx);
    } else {
      this._drawSkyline(ctx, step);
      this._drawRail(ctx, step);
    }
  };

  SamplingWidget.prototype._drawSplit = function (ctx) {
    var c = this._palette();
    var tokens = this._data.tokens;
    var n = Math.min(this._visibleCount(), tokens.length);
    var pad = 16;
    var gap = 24;
    var colW = (this._w - pad * 2 - gap) / 2;
    var top = 28;
    var plotH = this._h - top - 40;

    ctx.font = '600 12px ' + this._fontBody();
    ctx.fillStyle = c.textTertiary;
    ctx.textAlign = 'center';
    ctx.fillText('raw logits', pad + colW / 2, 18);
    ctx.fillText('probabilities (softmax)', pad + colW + gap + colW / 2, 18);

    var logits = tokens.slice(0, n).map(function (t) { return t.raw_logit; });
    var maxAbs = 0.0001;
    for (var i = 0; i < logits.length; i++) { maxAbs = Math.max(maxAbs, Math.abs(logits[i])); }
    var baseY = top + plotH / 2;
    this._drawBars(ctx, c, pad, colW, n, top, plotH, function (idx) {
      return logits[idx] / maxAbs;
    }, baseY, true);

    var probs = tokens.slice(0, n).map(function (t) { return t.prob_pre_top_k; });
    var maxP = 0.0001;
    for (var j = 0; j < probs.length; j++) { maxP = Math.max(maxP, probs[j]); }
    var rx = pad + colW + gap;
    this._drawBars(ctx, c, rx, colW, n, top, plotH, function (idx) {
      return probs[idx] / maxP;
    }, top + plotH, false);

    this._footer(ctx, c, 'same rank, new scale \u00b7 temperature ' + this._data.temperature.toFixed(1));
  };

  SamplingWidget.prototype._drawBars = function (ctx, c, x0, areaW, n, top, plotH, valueFn, baseY, signed) {
    var tokens = this._data.tokens;
    var slotW = areaW / n;
    var barW = Math.min(slotW * 0.64, 34);
    for (var i = 0; i < n; i++) {
      var cx = x0 + slotW * i + slotW / 2;
      var v = valueFn(i);
      var t = tokens[i];
      var fill = (i === 0) ? c.purple : c.textTertiary;
      var x = cx - barW / 2;
      if (signed) {
        var hh = Math.abs(v) * (plotH / 2 - 4);
        if (v >= 0) this._roundRect(ctx, x, baseY - hh, barW, hh, 4, fill);
        else this._roundRect(ctx, x, baseY, barW, hh, 4, fill);
        ctx.strokeStyle = c.separator;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x0, baseY); ctx.lineTo(x0 + areaW, baseY); ctx.stroke();
      } else {
        var h = clamp(v, 0, 1) * (plotH - 4);
        this._roundRect(ctx, x, baseY - h, barW, h, 4, fill);
      }
      ctx.font = '11px ' + this._fontMono();
      ctx.fillStyle = (i === 0) ? c.text : c.textTertiary;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(displayChar(t.char), cx, top + plotH + 6);
    }
  };

  SamplingWidget.prototype._drawSkyline = function (ctx, step) {
    var c = this._palette();
    var tokens = this._data.tokens;
    var visN = Math.min(this._visibleCount(), tokens.length);
    var hasRest = tokens.length > visN;
    var n = hasRest ? visN + 1 : visN;

    var pad = 16;
    var top = 30;
    var railSpace = (step === 4) ? 58 : 48;
    var plotH = this._h - top - railSpace - 24;
    var slotW = (this._w - pad * 2) / n;
    var barW = Math.min(slotW * 0.62, 40);
    var base = this._data.baseProbs;

    var probOf = function (idx) {
      if (step === 1 || step === 2) return tokens[idx].prob_pre_top_k;
      return tokens[idx].prob_final;
    };
    var restMass = 0, restBase = 0;
    for (var r = visN; r < tokens.length; r++) {
      restMass += (step === 1 || step === 2) ? tokens[r].prob_pre_top_k : tokens[r].prob_final;
      restBase += base[r];
    }

    var maxP = 0.0001;
    for (var m = 0; m < visN; m++) { maxP = Math.max(maxP, probOf(m)); }
    maxP = Math.max(maxP, restMass);

    var cutoffIdx = -1;
    if (step === 2) {
      for (var ci = 0; ci < tokens.length; ci++) { if (tokens[ci].in_top_k) cutoffIdx = ci; }
    }

    var baseLine = top + plotH;
    for (var i = 0; i < n; i++) {
      var isRest = hasRest && i === n - 1;
      var cx = pad + slotW * i + slotW / 2;
      var x = cx - barW / 2;
      var p = isRest ? restMass : probOf(i);
      var bp = isRest ? restBase : base[i];
      var h = clamp(p / maxP, 0, 1) * plotH;

      if (step === 1) {
        var gh = clamp(bp / maxP, 0, 1) * plotH;
        ctx.globalAlpha = 0.55;
        this._roundRect(ctx, x - 3, baseLine - gh, barW + 6, gh, 4, c.separator);
        ctx.globalAlpha = 1;
      }

      var cut = (step === 2) && !isRest && !tokens[i].in_top_k;
      var fill = c.textTertiary;
      if (!isRest && i === 0 && !cut) fill = c.purple;
      if (isRest) fill = c.surface2;
      if (this._sampled && !isRest && this._sampled.rank === i) fill = c.green;

      ctx.globalAlpha = cut ? 0.28 : 1;
      this._roundRect(ctx, x, baseLine - h, barW, h, 4, fill);
      ctx.globalAlpha = 1;
      if (cut) this._hatch(ctx, x, baseLine - h, barW, h, c.separator);

      if (this._sampled && !isRest && this._sampled.rank === i) {
        ctx.strokeStyle = c.green;
        ctx.lineWidth = 2;
        this._strokeRoundRect(ctx, x - 2, baseLine - h - 2, barW + 4, h + 4, 5);
      }

      if ((i < 3 || isRest) && h > 12) {
        ctx.font = '10px ' + this._fontMono();
        ctx.fillStyle = c.textTertiary;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText((p * 100).toFixed(1) + '%', cx, baseLine - h - 3);
      }

      ctx.font = (i === 0 && !isRest ? '600 ' : '') + '11px ' + this._fontMono();
      ctx.fillStyle = (i === 0 && !isRest) ? c.text : c.textTertiary;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(isRest ? 'rest' : displayChar(tokens[i].char), cx, baseLine + 6);
    }

    if (step === 2 && cutoffIdx >= 0 && cutoffIdx < visN) {
      var lineX = pad + slotW * (cutoffIdx + 1);
      ctx.strokeStyle = c.accent;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(lineX, top - 6); ctx.lineTo(lineX, top + plotH); ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = '10px ' + this._fontMono();
      ctx.fillStyle = c.accent;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText('top-' + this._data.topKEffective + ' cutoff', Math.min(lineX + 4, this._w - 90), top - 4);
    }
  };

  SamplingWidget.prototype._drawRail = function (ctx, step) {
    var c = this._palette();
    var tokens = this._data.tokens;
    var pad = 16;
    var railH = (step === 4) ? 30 : 22;
    var railY = this._h - railH - 16;
    var railW = this._w - pad * 2;

    ctx.font = '10px ' + this._fontBody();
    ctx.fillStyle = c.textTertiary;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillText('probability mass', pad, railY - 3);

    this._roundRect(ctx, pad, railY, railW, railH, 4, c.surface2);

    var x = pad;
    for (var i = 0; i < tokens.length; i++) {
      var w = tokens[i].prob_final * railW;
      if (w <= 0.2) continue;
      var fill = (i === 0) ? c.purple : c.textTertiary;
      if (this._sampled && this._sampled.rank === i) fill = c.green;
      ctx.globalAlpha = (step === 4) ? 0.92 : 0.78;
      ctx.fillStyle = fill;
      ctx.fillRect(x, railY, Math.max(w - 1, 0.5), railH);
      ctx.globalAlpha = 1;
      x += w;
    }
    ctx.strokeStyle = c.separator;
    ctx.lineWidth = 1;
    this._strokeRoundRect(ctx, pad, railY, railW, railH, 4);

    this._railGeom = { x: pad, y: railY, w: railW, h: railH };

    if (this._anim) {
      this._drawMarker(ctx, c, this._anim.x, railY, railH);
    } else if (this._sampled && this._sampled.markX != null) {
      this._drawMarker(ctx, c, this._sampled.markX, railY, railH);
    }
  };

  SamplingWidget.prototype._drawMarker = function (ctx, c, mx, railY, railH) {
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.35)';
    ctx.shadowBlur = 6;
    ctx.fillStyle = c.surface;
    ctx.beginPath();
    ctx.arc(mx, railY + railH / 2, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = c.accent;
    ctx.beginPath();
    ctx.arc(mx, railY + railH / 2, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  };

  SamplingWidget.prototype._sampleOnce = function () {
    if (!this._data || this._sampleBtn.disabled) return;
    var tokens = this._data.tokens;
    var r = Math.random();
    var cum = 0, rank = tokens.length - 1;
    for (var i = 0; i < tokens.length; i++) {
      cum += tokens[i].prob_final;
      if (r < cum) { rank = i; break; }
    }
    var chosen = tokens[rank];
    var geom = this._railGeom || { x: 16, y: 0, w: this._w - 32 };
    var targetX = geom.x + geom.w * r;

    if (reducedMotion()) {
      this._finishSample(rank, chosen, targetX);
      return;
    }

    var self = this;
    var start = null;
    var startX = geom.x;
    if (this._raf) cancelAnimationFrame(this._raf);
    this._sampled = null;
    function frame(ts) {
      if (start == null) start = ts;
      var p = clamp((ts - start) / 900, 0, 1);
      var wob = Math.sin(p * Math.PI * 8) * (1 - p) * geom.w * 0.12;
      self._anim = { x: lerp(startX, targetX, p) + wob };
      if (p >= 0.8 && !self._sampled) {
        self._sampled = { rank: rank, char: chosen.char, prob: chosen.prob_final, markX: targetX };
        self._announceSample(chosen);
      }
      self._draw();
      if (p < 1) { self._raf = requestAnimationFrame(frame); }
      else { self._anim = null; self._draw(); }
    }
    this._raf = requestAnimationFrame(frame);
  };

  SamplingWidget.prototype._finishSample = function (rank, chosen, targetX) {
    this._anim = null;
    this._sampled = { rank: rank, char: chosen.char, prob: chosen.prob_final, markX: targetX };
    this._announceSample(chosen);
    this._draw();
  };

  SamplingWidget.prototype._announceSample = function (chosen) {
    var txt = 'sampled: ' + displayChar(chosen.char) + ' \u00b7 ' + (chosen.prob_final * 100).toFixed(1) + '%';
    this._statusEl.innerHTML = '<span class="sampling-result text-mono">' + escapeHtml(txt) + '</span>';
    this._srEl.textContent = txt;
  };

  SamplingWidget.prototype._roundRect = function (ctx, x, y, w, h, r, fill) {
    if (h < 0) { y += h; h = -h; }
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  };

  SamplingWidget.prototype._strokeRoundRect = function (ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    ctx.stroke();
  };

  SamplingWidget.prototype._hatch = function (ctx, x, y, w, h, color) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.5;
    for (var d = -h; d < w; d += 6) {
      ctx.beginPath();
      ctx.moveTo(x + d, y + h);
      ctx.lineTo(x + d + h, y);
      ctx.stroke();
    }
    ctx.restore();
  };

  SamplingWidget.prototype._footer = function (ctx, c, text) {
    ctx.font = '11px ' + this._fontMono();
    ctx.fillStyle = c.textTertiary;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText(text, this._w / 2, this._h - 6);
  };

  SamplingWidget.prototype._fontMono = function () {
    return getComputedStyle(document.documentElement).getPropertyValue('--font-mono').trim() || 'monospace';
  };
  SamplingWidget.prototype._fontBody = function () {
    return getComputedStyle(document.documentElement).getPropertyValue('--font-body').trim() || 'sans-serif';
  };

  SamplingWidget.prototype.destroy = function () {
    document.removeEventListener('concept:stepchange', this._onStep);
    window.removeEventListener('resize', this._onResize);
    if (this._raf) cancelAnimationFrame(this._raf);
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
  };

  window.SamplingWidget = SamplingWidget;
})();
