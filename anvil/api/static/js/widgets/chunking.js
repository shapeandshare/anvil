// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var SAMPLE = "the quick brown\nfox jumps over\nthe lazy dog.";
  var DISPLAY_TEXT = "the quick brown fox jumps over the lazy dog.";
  var BLOCK_SIZE = 16;

  var CAPTIONS = {
    windowed: {
      title: 'Sliding Window Chunking',
      body: 'A fixed-size window slides across the text by a configurable stride. Overlapping windows capture repeated context, giving the model multiple views of each boundary region.',
    },
    line: {
      title: 'Line-Based Chunking',
      body: 'The text is split by newline boundaries. Each non-empty stripped line becomes an independent chunk \u2014 preserving logical structure like sentences or config entries.',
    },
    file: {
      title: 'File-as-Document Chunking',
      body: 'The entire text is treated as a single monolithic chunk. No splitting occurs. Useful as a baseline strategy or when the input fits within downstream context limits.',
    },
  };

  function ChunkingWidget(container) {
    if (!container) return;
    this.container = container;
    this._strategy = 'windowed';
    this._overlap = 0.5;
    this._windowStart = 0;
    this._chunks = [];
    this._playing = false;
    this._timer = null;
    this._reducedMotion = false;
    this._stripText = DISPLAY_TEXT;
    this._render();
  }

  ChunkingWidget.prototype._token = function (name, fallback) {
    var style = getComputedStyle(document.documentElement);
    return style.getPropertyValue(name).trim() || fallback;
  };

  ChunkingWidget.prototype._computeStride = function () {
    return Math.max(1, Math.round(BLOCK_SIZE * (1 - this._overlap)));
  };

  ChunkingWidget.prototype._getLineChunks = function () {
    var lines = SAMPLE.split('\n');
    var out = [];
    for (var i = 0; i < lines.length; i++) {
      var l = lines[i].trim();
      if (l) out.push(l);
    }
    return out;
  };

  ChunkingWidget.prototype._render = function () {
    var self = this;
    var mm = window.matchMedia('(prefers-reduced-motion: reduce)');
    this._reducedMotion = mm.matches;
    mm.addEventListener('change', function (e) {
      self._reducedMotion = e.matches;
    });

    var accent = this._token('--accent', '#007aff');
    var green = this._token('--accent-green', '#34c759');
    var orange = this._token('--accent-orange', '#ff9500');
    var purple = this._token('--accent-purple', '#af52de');
    var cyan = this._token('--accent-cyan', '#32d74b');
    var surface = this._token('--surface', '#1c1c1e');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var border = this._token('--border', '#38383a');
    var radius = this._token('--radius', '13px');
    var radiusSm = this._token('--radius-sm', '8px');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var body = this._token('--font-body', '-apple-system,BlinkMacSystemFont,system-ui,sans-serif');
    var space2 = this._token('--space-2', '0.5rem');
    var space3 = this._token('--space-3', '0.75rem');

    /* Strategy buttons */
    var stratHtml =
      '<div class="chunking-strategies" style="display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space2 + ';">' +
      '<button class="chunking-strat-btn active" data-strategy="windowed" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,background 0.15s;" aria-label="Switch to windowed chunking strategy">Windowed</button>' +
      '<button class="chunking-strat-btn" data-strategy="line" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,background 0.15s;" aria-label="Switch to line chunking strategy">Line</button>' +
      '<button class="chunking-strat-btn" data-strategy="file" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,background 0.15s;" aria-label="Switch to file chunking strategy">File</button>' +
      '</div>';

    /* Overlap buttons (windowed only) */
    var overlapHtml =
      '<div class="chunking-overlap" id="chunking-overlap" style="display:flex;gap:4px;justify-content:center;align-items:center;margin-bottom:' + space2 + ';">' +
      '<span style="font-size:0.72rem;color:' + muted + ';margin-right:4px;font-family:' + body + ';">Overlap:</span>' +
      '<button class="chunking-ov-btn" data-overlap="0" style="background:' + surface2 + ';color:' + muted + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:3px 10px;font-size:0.72rem;font-weight:500;cursor:pointer;font-family:' + body + ';" aria-label="Set overlap to 0 percent">0.0</button>' +
      '<button class="chunking-ov-btn" data-overlap="0.25" style="background:' + surface2 + ';color:' + muted + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:3px 10px;font-size:0.72rem;font-weight:500;cursor:pointer;font-family:' + body + ';" aria-label="Set overlap to 25 percent">0.25</button>' +
      '<button class="chunking-ov-btn active" data-overlap="0.5" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:3px 10px;font-size:0.72rem;font-weight:500;cursor:pointer;font-family:' + body + ';" aria-label="Set overlap to 50 percent">0.5</button>' +
      '<button class="chunking-ov-btn" data-overlap="0.75" style="background:' + surface2 + ';color:' + muted + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:3px 10px;font-size:0.72rem;font-weight:500;cursor:pointer;font-family:' + body + ';" aria-label="Set overlap to 75 percent">0.75</button>' +
      '</div>';

    /* Text strip */
    var stripId = 'chunking-strip-' + Date.now();
    var stripHtml =
      '<div class="chunking-strip-container" style="position:relative;background:' + surface + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 8px;margin-bottom:' + space2 + ';overflow:hidden;">' +
      '<div class="chunking-strip-text" id="' + stripId + '-text" style="font-family:' + mono + ';font-size:0.85rem;color:' + text + ';white-space:nowrap;letter-spacing:0.01em;user-select:none;line-height:1.6;">' + DISPLAY_TEXT + '</div>' +
      '<div class="chunking-strip-window" id="' + stripId + '-window" style="position:absolute;top:0;left:0;height:100%;width:' + BLOCK_SIZE + 'ch;background:color-mix(in srgb,' + accent + ' 14%,transparent);border:1.5px solid ' + accent + ';border-radius:4px;pointer-events:none;will-change:transform;transition:transform 0.3s cubic-bezier(0.32,0.94,0.6,1);transform:translateX(0ch);"></div>' +
      '<div class="chunking-strip-overlay" id="' + stripId + '-info" style="position:absolute;bottom:2px;right:6px;font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';pointer-events:none;opacity:0.6;">16 chars</div>' +
      '</div>';

    /* Info bar */
    var infoHtml =
      '<div class="chunking-info" style="display:flex;gap:' + space3 + ';justify-content:center;align-items:center;margin-bottom:' + space2 + ';font-size:0.75rem;font-family:' + body + ';color:' + muted + ';">' +
      '<span>Stride: <strong id="chunking-stride-val" style="font-variant-numeric:tabular-nums;color:' + text + ';">8</strong></span>' +
      '<span style="opacity:0.4;">|</span>' +
      '<span>Chunks: <strong id="chunking-count-val" style="font-variant-numeric:tabular-nums;color:' + text + ';">0</strong></span>' +
      '</div>';

    /* Controls */
    var controlsHtml =
      '<div class="chunking-controls" style="display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space3 + ';">' +
      '<button id="chunking-play-btn" class="chunking-ctrl-btn" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Play chunking animation">Play</button>' +
      '<button id="chunking-step-btn" class="chunking-ctrl-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Step one window forward">Step</button>' +
      '<button id="chunking-reset-btn" class="chunking-ctrl-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Reset chunking animation">Reset</button>' +
      '</div>';

    /* Caption */
    var captionHtml =
      '<div class="chunking-caption" id="chunking-caption" style="min-height:52px;margin-bottom:' + space2 + ';padding:' + space2 + ' ' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';">' +
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;">Select a strategy above or press Play to begin</div>' +
      '</div>';

    /* Chunks container */
    var chipsHtml =
      '<div class="chunking-chips" id="chunking-chips" style="display:flex;flex-wrap:wrap;gap:4px;min-height:28px;" role="list" aria-label="Captured chunks"></div>';

    /* Scoped CSS */
    var css = '<style>' +
      '.chunking-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.chunking-strat-btn:hover{filter:brightness(1.15);}' +
      '.chunking-strat-btn:active{filter:brightness(0.9);}' +
      '.chunking-strat-btn:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.chunking-ov-btn:hover{filter:brightness(1.15);}' +
      '.chunking-ov-btn:active{filter:brightness(0.9);}' +
      '.chunking-ov-btn:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.chunking-ctrl-btn:hover{filter:brightness(1.15);}' +
      '.chunking-ctrl-btn:active{filter:brightness(0.9);}' +
      '.chunking-ctrl-btn:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.chunking-chip{' +
        'display:inline-flex;align-items:center;gap:3px;' +
        'padding:3px 8px;' +
        'background:' + surface2 + ';' +
        'border:1px solid ' + border + ';' +
        'border-radius:' + radiusSm + ';' +
        'font-family:' + mono + ';font-size:0.72rem;' +
        'color:' + text + ';' +
        'white-space:nowrap;' +
        'max-width:200px;overflow:hidden;text-overflow:ellipsis;' +
        'transition:transform 0.35s cubic-bezier(0.32,0.94,0.6,1),opacity 0.25s;' +
      '}' +
      '.chunking-chip-bullet{width:6px;height:6px;border-radius:50%;flex-shrink:0;display:inline-block;}' +
      '.chunking-chip-newline{color:' + muted + ';font-size:0.65rem;margin:0 1px;}' +
      '</style>';

    /* Assemble */
    this.container.innerHTML =
      '<div class="chunking-widget">' +
      css +
      stratHtml +
      overlapHtml +
      stripHtml +
      infoHtml +
      controlsHtml +
      captionHtml +
      chipsHtml +
      '</div>';

    /* Cache refs */
    this._stripTextEl = document.getElementById(stripId + '-text');
    this._stripWindowEl = document.getElementById(stripId + '-window');
    this._stripInfoEl = document.getElementById(stripId + '-info');
    this._overlapEl = document.getElementById('chunking-overlap');
    this._captionEl = document.getElementById('chunking-caption');
    this._chipsEl = document.getElementById('chunking-chips');
    this._strideValEl = document.getElementById('chunking-stride-val');
    this._countValEl = document.getElementById('chunking-count-val');
    this._playBtn = document.getElementById('chunking-play-btn');
    this._stepBtn = document.getElementById('chunking-step-btn');
    this._resetBtn = document.getElementById('chunking-reset-btn');

    /* Strategy click delegation */
    this.container.addEventListener('click', function (e) {
      var stratBtn = e.target.closest('.chunking-strat-btn');
      if (stratBtn) {
        var strat = stratBtn.getAttribute('data-strategy');
        if (strat) {
          self._switchStrategy(strat);
        }
        return;
      }

      var ovBtn = e.target.closest('.chunking-ov-btn');
      if (ovBtn) {
        var ov = parseFloat(ovBtn.getAttribute('data-overlap'));
        if (!isNaN(ov)) {
          self._setOverlap(ov);
        }
        return;
      }
    });

    /* Keyboard */
    this.container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        var stratBtn = e.target.closest('.chunking-strat-btn');
        if (stratBtn) {
          e.preventDefault();
          var strat = stratBtn.getAttribute('data-strategy');
          if (strat) self._switchStrategy(strat);
          return;
        }
        var ovBtn = e.target.closest('.chunking-ov-btn');
        if (ovBtn) {
          e.preventDefault();
          var ov = parseFloat(ovBtn.getAttribute('data-overlap'));
          if (!isNaN(ov)) self._setOverlap(ov);
          return;
        }
      }
    });

    /* Button handlers */
    if (this._playBtn) {
      this._playBtn.addEventListener('click', function () {
        self._togglePlay();
      });
    }
    if (this._stepBtn) {
      this._stepBtn.addEventListener('click', function () {
        self._step();
      });
    }
    if (this._resetBtn) {
      this._resetBtn.addEventListener('click', function () {
        self._reset();
      });
    }

    this._updateDisplay();
  };

  ChunkingWidget.prototype._switchStrategy = function (strategy) {
    if (strategy === this._strategy) return;
    this._stop();
    this._strategy = strategy;
    this._windowStart = 0;
    this._chunks = [];
    this._updateOverlapVisibility();
    this._updateDisplay();
  };

  ChunkingWidget.prototype._setOverlap = function (overlap) {
    if (overlap === this._overlap) return;
    this._stop();
    this._overlap = overlap;
    this._windowStart = 0;
    this._chunks = [];
    this._updateOverlapButtons();
    this._updateDisplay();
  };

  ChunkingWidget.prototype._updateOverlapVisibility = function () {
    if (this._overlapEl) {
      this._overlapEl.style.display = (this._strategy === 'windowed') ? 'flex' : 'none';
    }
  };

  ChunkingWidget.prototype._updateOverlapButtons = function () {
    var btns = this._overlapEl ? this._overlapEl.querySelectorAll('.chunking-ov-btn') : [];
    var accent = this._token('--accent', '#007aff');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var border = this._token('--border', '#38383a');
    for (var i = 0; i < btns.length; i++) {
      var btn = btns[i];
      var val = parseFloat(btn.getAttribute('data-overlap'));
      var isActive = (val === this._overlap);
      if (isActive) {
        btn.style.background = accent;
        btn.style.color = '#fff';
        btn.style.border = 'none';
      } else {
        btn.style.background = surface2;
        btn.style.color = muted;
        btn.style.border = '1px solid ' + border;
      }
    }
  };

  ChunkingWidget.prototype._updateStrategyButtons = function () {
    var btns = this.container.querySelectorAll('.chunking-strat-btn');
    var accent = this._token('--accent', '#007aff');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var border = this._token('--border', '#38383a');
    for (var i = 0; i < btns.length; i++) {
      var btn = btns[i];
      var strat = btn.getAttribute('data-strategy');
      if (strat === this._strategy) {
        btn.style.background = accent;
        btn.style.color = '#fff';
        btn.style.border = 'none';
      } else {
        btn.style.background = surface2;
        btn.style.color = text;
        btn.style.border = '1px solid ' + border;
      }
    }
  };

  ChunkingWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._stop();
    } else {
      this._play();
    }
  };

  ChunkingWidget.prototype._play = function () {
    var self = this;
    if (this._playing) return;
    if (this._strategy !== 'windowed') return;
    if (this._windowStart >= SAMPLE.length) {
      this._windowStart = 0;
      this._chunks = [];
      this._updateDisplay();
    }
    this._playing = true;
    if (this._playBtn) {
      this._playBtn.textContent = 'Pause';
    }

    if (this._reducedMotion) {
      var stride = this._computeStride();
      while (this._windowStart < SAMPLE.length) {
        var end = this._windowStart + BLOCK_SIZE;
        this._chunks.push(SAMPLE.substring(this._windowStart, end));
        this._windowStart += stride;
      }
      this._playing = false;
      if (this._playBtn) {
        this._playBtn.textContent = 'Play';
      }
      this._updateDisplay();
      return;
    }

    var interval = 700;

    this._timer = setInterval(function () {
      if (self._windowStart >= SAMPLE.length) {
        self._stop();
        return;
      }
      self._captureWindow();
    }, interval);
  };

  ChunkingWidget.prototype._stop = function () {
    this._playing = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  ChunkingWidget.prototype._step = function () {
    if (this._strategy !== 'windowed') return;
    if (this._playing) this._stop();
    if (this._windowStart >= SAMPLE.length) return;
    this._captureWindow();
  };

  ChunkingWidget.prototype._captureWindow = function () {
    var end = this._windowStart + BLOCK_SIZE;
    var text = SAMPLE.substring(this._windowStart, end);
    this._chunks.push(text);
    this._windowStart += this._computeStride();
    this._updateDisplay();
  };

  ChunkingWidget.prototype._reset = function () {
    this._stop();
    this._windowStart = 0;
    this._chunks = [];
    this._updateDisplay();
  };

  ChunkingWidget.prototype._updateDisplay = function () {
    this._updateStrategyButtons();
    this._updateOverlapVisibility();
    this._renderStrip();
    this._updateInfo();
    this._updateCaption();

    if (this._strategy === 'line') {
      this._chunks = this._getLineChunks();
    } else if (this._strategy === 'file') {
      if (SAMPLE.length > 0) {
        this._chunks = [SAMPLE];
      }
    }

    this._renderChips();
  };

  ChunkingWidget.prototype._renderStrip = function () {
    if (!this._stripTextEl) return;
    var accent = this._token('--accent', '#007aff');

    if (this._strategy === 'line') {
      var lines = SAMPLE.split('\n');
      var html = '';
      for (var i = 0; i < lines.length; i++) {
        html += '<div style="line-height:1.6;">' + this._escapeHtml(lines[i]);
        if (i < lines.length - 1) {
          html += '<span style="color:' + accent + ';opacity:0.5;font-size:0.65rem;margin-left:2px;">\u21B5</span>';
        }
        html += '</div>';
      }
      this._stripTextEl.innerHTML = html;
      this._stripTextEl.style.whiteSpace = '';
    } else {
      this._stripTextEl.textContent = DISPLAY_TEXT;
      this._stripTextEl.style.whiteSpace = 'nowrap';
    }

    if (this._strategy === 'windowed' && this._stripWindowEl) {
      if (this._windowStart >= SAMPLE.length) {
        this._stripWindowEl.style.display = 'none';
      } else {
        this._stripWindowEl.style.display = '';
        var pos = this._windowStart + 'ch';
        this._stripWindowEl.style.transform = 'translateX(' + pos + ')';
      }
    } else if (this._stripWindowEl) {
      this._stripWindowEl.style.display = 'none';
    }

    if (this._stripInfoEl) {
      if (this._strategy === 'windowed') {
        this._stripInfoEl.textContent = BLOCK_SIZE + ' chars';
        this._stripInfoEl.style.display = '';
      } else {
        this._stripInfoEl.style.display = 'none';
      }
    }
  };

  ChunkingWidget.prototype._escapeHtml = function (str) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
  };

  ChunkingWidget.prototype._renderChips = function () {
    if (!this._chipsEl) return;
    var self = this;
    var accent = this._token('--accent', '#007aff');
    var muted = this._token('--text-muted', '#8e8e93');

    this._chipsEl.innerHTML = '';

    if (this._chunks.length === 0) {
      var emptyMsg = (this._strategy === 'windowed')
        ? 'Press Play or Step to capture windows'
        : 'No chunks to display';
      this._chipsEl.innerHTML = '<div style="font-size:0.7rem;color:' + muted + ';font-style:italic;">' + emptyMsg + '</div>';
      return;
    }

    for (var i = 0; i < this._chunks.length; i++) {
      (function (idx) {
        var raw = self._chunks[idx];
        var display = raw.replace(/\n/g, ' \u21B5');
        var chip = document.createElement('div');
        chip.className = 'chunking-chip';
        chip.setAttribute('role', 'listitem');
        chip.setAttribute('aria-label', 'Chunk ' + (idx + 1) + ': ' + display);

        var bullet = document.createElement('span');
        bullet.className = 'chunking-chip-bullet';
        bullet.style.background = accent;
        chip.appendChild(bullet);

        var label = document.createElement('span');
        label.textContent = display;
        chip.appendChild(label);

        var indexLabel = document.createElement('span');
        indexLabel.style.cssText = 'font-size:0.6rem;color:' + muted + ';font-family:inherit;margin-left:auto;';
        indexLabel.textContent = '#' + (idx + 1);
        chip.appendChild(indexLabel);

        self._chipsEl.appendChild(chip);

        if (!self._reducedMotion && self._strategy === 'windowed') {
          chip.style.opacity = '0';
          chip.style.transform = 'translateY(-10px)';
          chip.offsetWidth;
          chip.style.opacity = '1';
          chip.style.transform = 'translateY(0)';
        }
      })(i);
    }

    this._updateCount();
  };

  ChunkingWidget.prototype._updateInfo = function () {
    if (this._strideValEl && this._strategy === 'windowed') {
      this._strideValEl.textContent = '' + this._computeStride();
    } else if (this._strideValEl) {
      this._strideValEl.textContent = '\u2014';
    }
  };

  ChunkingWidget.prototype._updateCount = function () {
    if (this._countValEl) {
      this._countValEl.textContent = '' + this._chunks.length;
    }
  };

  ChunkingWidget.prototype._updateCaption = function () {
    if (!this._captionEl) return;
    var accent = this._token('--accent', '#007aff');
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var space2 = this._token('--space-2', '0.5rem');
    var space3 = this._token('--space-3', '0.75rem');

    var cap = CAPTIONS[this._strategy] || CAPTIONS.windowed;
    var bodyText = cap.body;

    if (this._strategy === 'windowed') {
      var stride = this._computeStride();
      var totalChunks = Math.ceil(Math.max(0, SAMPLE.length - BLOCK_SIZE) / stride) + 1;
      bodyText += ' Block size: ' + BLOCK_SIZE + ', stride: ' + stride + ', ~' + totalChunks + ' total windows.';
    } else if (this._strategy === 'line') {
      var lineCount = this._getLineChunks().length;
      bodyText += ' Found ' + lineCount + ' non-empty line' + (lineCount !== 1 ? 's' : '') + '.';
    } else if (this._strategy === 'file') {
      bodyText += ' Text length: ' + SAMPLE.length + ' characters.';
    }

    this._captionEl.innerHTML =
      '<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">' +
      '<span style="width:7px;height:7px;border-radius:50%;background:' + accent + ';flex-shrink:0;"></span>' +
      '<span style="font-size:0.78rem;font-weight:600;color:' + text + ';">' + cap.title + '</span>' +
      '</div>' +
      '<div style="font-size:0.72rem;color:' + muted + ';line-height:1.5;">' + bodyText + '</div>';
  };

  window.ChunkingWidget = ChunkingWidget;
})();