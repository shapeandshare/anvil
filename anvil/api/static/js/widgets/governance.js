// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function GovernanceWidget(container) {
    if (!container) return;
    this.container = container;
    this._stage = 1;
    this._playing = false;
    this._timer = null;
    this._hashTimer = null;
    this._cascadeTimers = [];
    this._reducedMotion = false;
    this._selectedBlock = -1;
    this._tampered = false;
    this._tamperedIndex = -1;
    this._cascadeIdx = -1;
    this._verifyResult = null;

    this._blockDefs = [
      { action: 'upload',   actor: 'alice', color: '--accent' },
      { action: 'curate',   actor: 'alice', color: '--accent-purple' },
      { action: 'train',    actor: 'bob',   color: '--accent-orange' },
      { action: 'export',   actor: 'bob',   color: '--accent-green' },
      { action: 'deploy',   actor: 'carol', color: '--accent' },
      { action: 'inference',actor: 'carol', color: '--accent-purple' },
    ];

    this._blocks = [];
    this._initChain();
    this._render();
  }

  /* ──────────── utils ──────────── */

  GovernanceWidget.prototype._fakeHash = function (seq, action, prevHash) {
    var input = String(seq) + '|' + action + '|' + prevHash;
    var hash = 5381;
    for (var i = 0; i < input.length; i++) {
      hash = ((hash << 5) + hash) + input.charCodeAt(i);
      hash = hash & hash;
    }
    var hex = (hash >>> 0).toString(16);
    while (hex.length < 12) hex = '0' + hex;
    return hex.slice(0, 12);
  };

  GovernanceWidget.prototype._genesisPrev = function () {
    var s = '';
    for (var i = 0; i < 64; i++) s += '0';
    return s;
  };

  GovernanceWidget.prototype._shortHash = function (h) {
    if (!h) return '0000\u20260000';
    if (h.length <= 12) return h;
    return h.slice(0, 6) + '\u2026' + h.slice(-4);
  };

  GovernanceWidget.prototype._shortPrev = function (h) {
    if (!h) return '';
    var allZeros = true;
    for (var i = 0; i < h.length; i++) {
      if (h[i] !== '0') { allZeros = false; break; }
    }
    if (allZeros) return '0\u2026';
    return h.slice(0, 6) + '\u2026' + h.slice(-4);
  };

  GovernanceWidget.prototype._resolveColor = function (varName) {
    var c = window.AnvilBase.token(varName, '');
    return c || window.AnvilBase.token('--accent', '#007aff');
  };

  /* ──────────── chain init / rebuild ──────────── */

  GovernanceWidget.prototype._initChain = function () {
    this._blocks = [];
    var prevHash = this._genesisPrev();
    for (var i = 0; i < this._blockDefs.length; i++) {
      var def = this._blockDefs[i];
      var seq = i + 1;
      var hash = this._fakeHash(seq, def.action, prevHash);
      this._blocks.push({
        seq: seq,
        action: def.action,
        actor: def.actor,
        color: def.color,
        prevHash: prevHash,
        hash: hash,
      });
      prevHash = hash;
    }
  };

  /* ──────────── render ──────────── */

  GovernanceWidget.prototype._render = function () {
    var self = this;
    window.AnvilBase.initReducedMotion(this);

    var accent = window.AnvilBase.token('--accent', '#007aff');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var red = window.AnvilBase.token('--accent-red', '#ff3b30');
    var orange = window.AnvilBase.token('--accent-orange', '#ff9500');
    var purple = window.AnvilBase.token('--accent-purple', '#af52de');
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

    var css = '<style>' +
      '.gov-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.gov-controls{display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space3 + ';flex-wrap:wrap;}' +
      '.gov-btn{background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,opacity 0.15s;}' +
      '.gov-btn:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.gov-btn:hover{filter:brightness(1.15);}' +
      '.gov-btn:active{filter:brightness(0.9);}' +
      '.gov-btn:disabled{opacity:0.4;cursor:default;filter:none;}' +
      '.gov-btn-primary{background:' + accent + ';color:#fff;border:none;}' +
      '.gov-chain{display:flex;flex-direction:column;align-items:center;padding:' + space2 + ' 0;gap:0;}' +
      '.gov-block{border-radius:' + radiusSm + ';padding:' + space2 + ';min-width:200px;max-width:260px;width:100%;cursor:pointer;transition:transform 0.3s,opacity 0.3s;transform-origin:center top;position:relative;}' +
      '.gov-block:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.gov-block-hidden{opacity:0;transform:translateY(-8px);pointer-events:none;}' +
      '.gov-block-visible{opacity:1;transform:translateY(0);}' +
      '.gov-block:hover{box-shadow:0 0 0 2px var(--gov-block-color,' + accent + ');}' +
      '.gov-block-selected{box-shadow:0 0 0 2px var(--gov-block-color,' + accent + '),0 0 12px color-mix(in srgb,var(--gov-block-color,' + accent + ') 30%,transparent)!important;}' +
      '.gov-block-tampered{border-color:' + red + '!important;}' +
      '.gov-block-tampered .gov-block-hash-val{color:' + red + '!important;}' +
      '.gov-block-broken{opacity:0.65;}' +
      '.gov-block-broken .gov-block-hash-val{color:' + red + '!important;}' +
      '.gov-block-header{display:flex;align-items:center;gap:6px;margin-bottom:4px;}' +
      '.gov-block-seq{font-variant-numeric:tabular-nums;font-family:' + mono + ';font-size:0.7rem;font-weight:600;color:' + muted + ';background:' + surface + ';border-radius:50%;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;}' +
      '.gov-block-action{font-size:0.82rem;font-weight:600;color:' + text + ';text-transform:capitalize;}' +
      '.gov-block-body{display:flex;align-items:center;gap:4px;padding:1px 0;}' +
      '.gov-block-label{font-size:0.6rem;color:' + muted + ';text-transform:uppercase;letter-spacing:0.5px;width:32px;flex-shrink:0;}' +
      '.gov-block-hash-val{font-family:' + mono + ';font-size:0.72rem;font-variant-numeric:tabular-nums;color:' + text + ';}' +
      '.gov-block-prev-val{font-family:' + mono + ';font-size:0.65rem;font-variant-numeric:tabular-nums;color:' + muted + ';}' +
      '.gov-link{display:flex;flex-direction:column;align-items:center;padding:2px 0;transition:opacity 0.3s;}' +
      '.gov-link-arrow{font-size:0.6rem;color:' + muted + ';line-height:1;}' +
      '.gov-link-hash{font-family:' + mono + ';font-size:0.6rem;font-variant-numeric:tabular-nums;color:' + muted + ';background:' + surface + ';padding:1px 6px;border-radius:4px;}' +
      '.gov-link-broken .gov-link-arrow{color:' + red + '!important;}' +
      '.gov-link-broken .gov-link-hash{color:' + red + '!important;background:color-mix(in srgb,' + red + ' 12%,transparent);}' +
      '.gov-status{padding:' + space3 + ';text-align:center;min-height:44px;font-size:0.75rem;border-radius:' + radiusSm + ';margin-top:' + space2 + ';}' +
      '@media(max-width:600px){.gov-block{min-width:160px;}}' +
      '</style>';

    var controlsHtml =
      '<div class="gov-controls">' +
      '<button id="gov-play-btn" class="gov-btn gov-btn-primary" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Play animation">Play</button>' +
      '<button id="gov-step-btn" class="gov-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Add next block">Step</button>' +
      '<button id="gov-reset-btn" class="gov-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Reset chain to genesis">Reset</button>' +
      '<button id="gov-tamper-btn" class="gov-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,opacity 0.15s;" aria-label="Tamper with selected block" disabled>Tamper</button>' +
      '<button id="gov-verify-btn" class="gov-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Verify chain integrity">Verify</button>' +
      '</div>';

    this.container.innerHTML =
      '<div class="gov-widget">' +
      css +
      '<div class="widget-label" style="display:block;font-size:0.75rem;color:' + muted + ';margin-bottom:' + space2 + ';text-align:center;">Hash-chained audit trail \u2014 click a block to select for tampering:</div>' +
      controlsHtml +
      '<div class="gov-chain" id="gov-chain">' +
      '</div>' +
      '<div class="gov-status" style="padding:' + space3 + ';text-align:center;min-height:44px;font-size:0.75rem;border-radius:' + radiusSm + ';margin-top:' + space2 + ';background:' + surface2 + ';" id="gov-status" aria-live="polite">' +
      '<span style="color:' + muted + ';">Genesis block ready \u2014 press Play or Step to extend the chain</span>' +
      '</div>' +
      '</div>';

    this._chainEl = this.container.querySelector('#gov-chain');
    this._statusEl = this.container.querySelector('#gov-status');
    this._playBtn = this.container.querySelector('#gov-play-btn');
    this._stepBtn = this.container.querySelector('#gov-step-btn');
    this._resetBtn = this.container.querySelector('#gov-reset-btn');
    this._tamperBtn = this.container.querySelector('#gov-tamper-btn');
    this._verifyBtn = this.container.querySelector('#gov-verify-btn');

    this.container.addEventListener('click', function (e) {
      var block = e.target.closest('[data-gov-seq]');
      if (block) {
        var seq = parseInt(block.getAttribute('data-gov-seq'), 10);
        self._selectBlock(seq - 1);
      }
    });

    this.container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        var block = e.target.closest('[data-gov-seq]');
        if (block) {
          e.preventDefault();
          var seq = parseInt(block.getAttribute('data-gov-seq'), 10);
          self._selectBlock(seq - 1);
        }
      }
    });

    if (this._playBtn) {
      this._playBtn.addEventListener('click', function () { self._togglePlay(); });
    }
    if (this._stepBtn) {
      this._stepBtn.addEventListener('click', function () { self._step(); });
    }
    if (this._resetBtn) {
      this._resetBtn.addEventListener('click', function () { self._reset(); });
    }
    if (this._tamperBtn) {
      this._tamperBtn.addEventListener('click', function () { self._tamper(); });
    }
    if (this._verifyBtn) {
      this._verifyBtn.addEventListener('click', function () { self._verify(); });
    }

    this._clearTimers();
    this._renderChain();
  };

  /* ──────────── chain rendering ──────────── */

  GovernanceWidget.prototype._renderChain = function () {
    var self = this;
    if (!this._chainEl) return;

    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var surface2 = window.AnvilBase.token('--surface-2', '#2c2c2e');
    var accent = window.AnvilBase.token('--accent', '#007aff');
    var red = window.AnvilBase.token('--accent-red', '#ff3b30');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var orange = window.AnvilBase.token('--accent-orange', '#ff9500');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');
    var space2 = window.AnvilBase.token('--space-2', '0.5rem');

    var html = '';
    var revealed = this._stage;

    for (var i = 0; i < revealed && i < this._blocks.length; i++) {
      var block = this._blocks[i];
      var col = this._resolveColor(block.color);
      var isTampered = this._tampered && i === this._tamperedIndex;
      var isBroken = false;
      if (this._tampered && i > this._tamperedIndex) {
        if (this._cascadeIdx >= 0 && i <= this._tamperedIndex + this._cascadeIdx) {
          isBroken = true;
        } else if (this._cascadeIdx < 0) {
          isBroken = true;
        }
      }
      var isSelected = i === this._selectedBlock;
      var borderColor = isTampered ? red : (isBroken ? red : col);
      var blockClasses = 'gov-block gov-block-visible';

      if (isSelected) blockClasses += ' gov-block-selected';
      if (isTampered || isBroken) blockClasses += ' gov-block-tampered';
      if (isBroken) blockClasses += ' gov-block-broken';

      var prevShort = this._shortPrev(block.prevHash);
      var hashShort = this._shortHash(block.hash);

      html +=
        '<div class="' + blockClasses + '" style="background:' + surface + ';border:1px solid ' + borderColor + ';border-left:3px solid ' + borderColor + ';--gov-block-color:' + col + ';" data-gov-seq="' + block.seq + '" role="button" tabindex="0" aria-label="Audit block ' + block.seq + ': ' + block.action + '">' +
        '<div class="gov-block-header">' +
        '<span class="gov-block-seq">' + block.seq + '</span>' +
        '<span class="gov-block-action">' + block.action + '</span>' +
        (isTampered ? '<span style="font-size:0.55rem;color:' + red + ';font-weight:700;margin-left:auto;">EDITED</span>' : '') +
        (isBroken ? '<span style="font-size:0.55rem;color:' + red + ';font-weight:700;margin-left:auto;">BROKEN</span>' : '') +
        '</div>' +
        '<div class="gov-block-body">' +
        '<span class="gov-block-label">hash</span>' +
        '<span class="gov-block-hash-val">' + hashShort + '</span>' +
        '</div>' +
        '<div class="gov-block-body">' +
        '<span class="gov-block-label">prev</span>' +
        '<span class="gov-block-prev-val">' + prevShort + '</span>' +
        '</div>' +
        '</div>';

      if (i < revealed - 1 && i < this._blocks.length - 1) {
        var linkBroken = isTampered || isBroken;
        var linkClasses = 'gov-link' + (linkBroken ? ' gov-link-broken' : '');
        var nextIdx = i + 1;
        var nextBroken = false;
        if (this._tampered && nextIdx > this._tamperedIndex) {
          if (this._cascadeIdx >= 0 && nextIdx <= this._tamperedIndex + this._cascadeIdx) {
            nextBroken = true;
          } else if (this._cascadeIdx < 0) {
            nextBroken = true;
          }
        }
        if (nextBroken) linkClasses = 'gov-link gov-link-broken';
        html +=
          '<div class="' + linkClasses + '">' +
          '<span class="gov-link-hash">' + hashShort + '</span>' +
          '<span class="gov-link-arrow">\u25BC</span>' +
          '</div>';
      }
    }

    this._chainEl.innerHTML = html;

    this._updateTamperBtn();

    var statusHtml = '';
    if (this._verifyResult) {
      if (this._verifyResult.valid) {
        statusHtml =
          '<span style="color:' + green + ';">\u2713 VALID \u2014 ' + this._verifyResult.checked + ' entr' +
          (this._verifyResult.checked === 1 ? 'y' : 'ies') + ' checked</span>';
      } else {
        statusHtml =
          '<span style="color:' + red + ';">\u2717 BROKEN at #' + this._verifyResult.breakAt + ' \u2014 ' + this._verifyResult.checked + ' entr' +
          (this._verifyResult.checked === 1 ? 'y' : 'ies') + ' checked</span>';
      }
    } else if (this._tampered) {
      statusHtml = '<span style="color:' + orange + ';">\u26A0 Chain integrity compromised \u2014 chain broken at #' + (this._tamperedIndex + 1) + '. Click Verify to confirm.</span>';
    } else {
      statusHtml = '<span style="color:' + muted + ';">' +
        (revealed === 1 ? 'Genesis block \u2014 ' : revealed + ' block' + (revealed > 1 ? 's' : '') + ' in chain \u2014 ') +
        'click a block to select, or press Play/Step</span>';
    }
    if (this._statusEl) {
      this._statusEl.innerHTML = statusHtml;
    }
  };

  GovernanceWidget.prototype._updateTamperBtn = function () {
    if (!this._tamperBtn) return;
    if (this._tampered || this._selectedBlock < 0 || this._stage <= 1) {
      this._tamperBtn.disabled = true;
      this._tamperBtn.textContent = 'Tamper';
      return;
    }
    this._tamperBtn.disabled = false;
    this._tamperBtn.textContent = 'Tamper #' + (this._selectedBlock + 1);
  };

  /* ──────────── block selection ──────────── */

  GovernanceWidget.prototype._selectBlock = function (index) {
    if (this._tampered) return;
    if (index < 0 || index >= this._stage || index >= this._blocks.length) return;
    if (index === this._selectedBlock) {
      this._selectedBlock = -1;
    } else {
      this._selectedBlock = index;
    }
    this._renderChain();
  };

  /* ──────────── animation timers ──────────── */

  GovernanceWidget.prototype._clearTimers = function () {
    window.AnvilBase.stop(this);
    if (this._hashTimer) {
      clearInterval(this._hashTimer);
      this._hashTimer = null;
    }
    for (var ci = 0; ci < this._cascadeTimers.length; ci++) {
      clearTimeout(this._cascadeTimers[ci]);
    }
    this._cascadeTimers = [];
  };

  /* ──────────── play / step / reset ──────────── */

  GovernanceWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._stop();
    } else {
      this._play();
    }
  };

  GovernanceWidget.prototype._play = function () {
    var self = this;
    if (this._playing) return;
    if (this._stage >= this._blocks.length) {
      this._stage = 1;
      this._tampered = false;
      this._tamperedIndex = -1;
      this._cascadeIdx = -1;
      this._selectedBlock = -1;
      this._verifyResult = null;
      this._initChain();
    }
    this._playing = true;
    if (this._playBtn) {
      this._playBtn.textContent = 'Pause';
    }

    var interval = this._reducedMotion ? 400 : 800;

    this._timer = setInterval(function () {
      var next = self._stage + 1;
      if (next > self._blocks.length) {
        self._stop();
        return;
      }
      self._stage = next;
      self._renderChain();

      if (!self._reducedMotion) {
        var blockEls = self._chainEl.querySelectorAll('[data-gov-seq]');
        if (blockEls.length > 0) {
          var lastEl = blockEls[blockEls.length - 1];
          self._animateHashSettling(lastEl, self._blocks[next - 1].hash);
        }
      }

      if (next >= self._blocks.length) {
        self._stop();
      }
    }, interval);
  };

  GovernanceWidget.prototype._stop = function () {
    this._playing = false;
    window.AnvilBase.stop(this);
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  GovernanceWidget.prototype._step = function () {
    var self = this;
    if (this._playing) this._stop();
    var next = this._stage + 1;
    if (next > this._blocks.length) return;
    this._stage = next;
    this._renderChain();

    if (!this._reducedMotion) {
      var blockEls = this._chainEl.querySelectorAll('[data-gov-seq]');
      if (blockEls.length > 0) {
        var lastEl = blockEls[blockEls.length - 1];
        this._animateHashSettling(lastEl, this._blocks[next - 1].hash);
      }
    }
  };

  GovernanceWidget.prototype._reset = function () {
    this._clearTimers();
    this._playing = false;
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
    this._stage = 1;
    this._selectedBlock = -1;
    this._tampered = false;
    this._tamperedIndex = -1;
    this._cascadeIdx = -1;
    this._verifyResult = null;
    this._initChain();
    this._renderChain();
  };

  /* ──────────── hash settling animation ──────────── */

  GovernanceWidget.prototype._animateHashSettling = function (blockEl, finalHash) {
    var self = this;
    var hashEl = blockEl.querySelector('.gov-block-hash-val');
    if (!hashEl) return;

    if (this._reducedMotion) {
      hashEl.textContent = this._shortHash(finalHash);
      return;
    }

    if (this._hashTimer) {
      clearInterval(this._hashTimer);
      this._hashTimer = null;
    }

    var steps = 10;
    var step = 0;
    var displayLen = finalHash.length <= 12 ? finalHash.length : 12;

    this._hashTimer = setInterval(function () {
      step++;
      if (step >= steps) {
        clearInterval(self._hashTimer);
        self._hashTimer = null;
        hashEl.textContent = self._shortHash(finalHash);
      } else {
        var random = '';
        for (var i = 0; i < displayLen; i++) {
          var hexChars = '0123456789abcdef';
          random += hexChars[Math.floor(Math.random() * 16)];
        }
        hashEl.textContent = random;
      }
    }, 60);
  };

  /* ──────────── tamper ──────────── */

  GovernanceWidget.prototype._tamper = function () {
    var self = this;
    if (this._tampered) return;
    if (this._selectedBlock < 0 || this._selectedBlock >= this._blocks.length) return;
    if (this._selectedBlock >= this._stage) return;

    if (this._playing) this._stop();
    this._clearTimers();

    var idx = this._selectedBlock;
    var block = this._blocks[idx];

    block.action = block.action + ' [edited]';

    this._tampered = true;
    this._tamperedIndex = idx;
    this._cascadeIdx = 0;

    this._renderChain();

    if (this._reducedMotion) {
      this._cascadeIdx = this._stage - this._tamperedIndex - 1;
      this._renderChain();
      return;
    }

    var total = this._stage - this._tamperedIndex - 1;
    for (var ci = 1; ci <= total; ci++) {
      (function (step) {
        var tid = setTimeout(function () {
          self._cascadeIdx = step;
          self._renderChain();
        }, step * 300);
        self._cascadeTimers.push(tid);
      })(ci);
    }
  };

  /* ──────────── verify ──────────── */

  GovernanceWidget.prototype._verify = function () {
    var revealed = this._stage;
    if (revealed === 0) return;

    var genesisPrev = this._genesisPrev();
    var expectedPrev = genesisPrev;
    var checked = 0;

    for (var i = 0; i < revealed && i < this._blocks.length; i++) {
      var block = this._blocks[i];
      checked++;

      if (block.prevHash !== expectedPrev) {
        this._verifyResult = {
          valid: false,
          breakAt: block.seq,
          checked: checked,
        };
        this._renderChain();
        return;
      }

      var recomputed = this._fakeHash(block.seq, block.action, block.prevHash);
      if (recomputed !== block.hash) {
        this._verifyResult = {
          valid: false,
          breakAt: block.seq,
          checked: checked,
        };
        this._renderChain();
        return;
      }

      expectedPrev = block.hash;
    }

    this._verifyResult = {
      valid: true,
      checked: checked,
    };
    this._renderChain();
  };

  window.GovernanceWidget = GovernanceWidget;
})();
