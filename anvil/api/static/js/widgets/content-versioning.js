// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function ContentVersioningWidget(container) {
    if (!container) return;
    this.container = container;
    this._stage = -1;
    this._playing = false;
    this._timer = null;
    this._reducedMotion = false;

    this._stages = [
      {
        id: 'hash',
        label: 'Hash',
        sub: 'SHA-256 content addressing',
        color: '--accent-cyan',
        zone: 'content',
      },
      {
        id: 'manifest',
        label: 'Manifest',
        sub: 'Canonical digest fingerprint',
        color: '--accent',
        zone: 'content',
      },
      {
        id: 'version',
        label: 'Version Chain',
        sub: 'v1 \u2192 v2 monotonic increments',
        color: '--accent-purple',
        zone: 'content',
      },
      {
        id: 'replication',
        label: 'Weight Replication',
        sub: 'factor = max(1, round(weight))',
        color: '--accent-orange',
        zone: 'content',
      },
      {
        id: 'lineage',
        label: 'Lineage',
        sub: 'Version \u2192 MLflow run trace',
        color: '--accent-green',
        zone: 'content',
      },
    ];

    this._captions = {
      hash: {
        title: 'Content-Addressed Hashing',
        body: 'Every file blob is hashed with SHA-256 to produce a unique content fingerprint. Identical content produces the same hash \u2014 enabling automatic deduplication. The short hex shown here is a 7-character prefix of the full 64-character digest.',
      },
      manifest: {
        title: 'Manifest Assembly',
        body: 'Deduplicated blobs are gathered into a Manifest: a versioned snapshot of the corpus listing each entry\u2019s path, content hash, and sampling weight. The manifest\u2019s own digest (SHA-256 of canonical JSON) serves as an immutable integrity fingerprint for version pinning.',
      },
      version: {
        title: 'Version Chain',
        body: 'Each manifest snapshot becomes a version node with a monotonically increasing version_number (max + 1). Appending a new version links the chain, keeping a full audit trail of how the corpus evolved over time.',
      },
      replication: {
        title: 'Weight-Based Replication',
        body: 'Entries carry a sampling weight. During training, chunks are replicated by factor = max(1, round(weight)) so heavily weighted entries contribute proportionally more examples. A weight of 3 yields 3 copies; a weight of 0.4 still yields 1 copy (floor of 1).',
      },
      lineage: {
        title: 'Provenance Lineage',
        body: 'A VersionRunRef connects every training run back to the exact manifest version that produced it. This means you can trace any model \u2014 any weight, any checkpoint \u2014 back to the exact bytes of source data that shaped it.',
      },
    };

    this._render();
  }

  ContentVersioningWidget.prototype._render = function () {
    var self = this;
    window.AnvilBase.initReducedMotion(this);

    var accent = window.AnvilBase.token('--accent', '#007aff');
    var cyan = window.AnvilBase.token('--accent-cyan', '#32d74b');
    var purple = window.AnvilBase.token('--accent-purple', '#af52de');
    var orange = window.AnvilBase.token('--accent-orange', '#ff9500');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
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

    /* Build stage HTML */
    var stageHtml = '';
    for (var i = 0; i < this._stages.length; i++) {
      var s = this._stages[i];
      var col = this._resolveColor(s.color, accent);
      stageHtml +=
        '<div class="cver-stage" data-cver-stage="' + s.id + '" style="background:' + surface + ';border:1px solid ' + col + ';border-radius:' + radiusSm + ';padding:' + space2 + ' ' + space3 + ';text-align:center;min-width:90px;cursor:pointer;transition:box-shadow 0.2s,transform 0.2s;position:relative;" tabindex="0" role="button" aria-label="Versioning stage: ' + s.label + '">' +
        '<div class="cver-stage-indicator" style="position:absolute;top:-4px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:' + col + ';opacity:0;transition:opacity 0.3s,box-shadow 0.3s;box-shadow:0 0 6px ' + col + ';"></div>' +
        '<div class="cver-stage-label" style="font-size:0.82rem;font-weight:600;color:' + text + ';">' + s.label + '</div>' +
        '<div class="cver-stage-sub" style="font-size:0.65rem;color:' + muted + ';margin-top:2px;font-family:' + mono + ';">' + s.sub + '</div>' +
        '</div>';
      if (i < this._stages.length - 1) {
        stageHtml += '<div class="cver-arrow" style="color:' + muted + ';font-size:0.65rem;text-align:center;padding:2px 0;opacity:0.5;">\u25b6</div>';
      }
    }

    /* Controls */
    var controlsHtml =
      '<div class="cver-controls" style="display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space3 + ';">' +
      '<button id="cver-play-btn" class="cver-btn" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Play animation">Play</button>' +
      '<button id="cver-step-btn" class="cver-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Step to next stage">Step</button>' +
      '<button id="cver-reset-btn" class="cver-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Reset animation">Reset</button>' +
      '</div>';

    var css = '<style>' +
      '.cver-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.cver-pipeline{display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';background:' + surface + ';}' +
      '.cver-stage:hover{box-shadow:0 0 0 2px var(--cver-color,' + accent + ')!important;}' +
      '.cver-stage.active .cver-stage-indicator{opacity:1!important;}' +
      '.cver-stage.active{border-color:var(--cver-color,' + accent + ')!important;box-shadow:0 0 0 2px var(--cver-color,' + accent + '),0 0 12px color-mix(in srgb,var(--cver-color,' + accent + ') 25%,transparent)!important;}' +
      '.cver-btn:hover{filter:brightness(1.15);}' +
      '.cver-btn:active{filter:brightness(0.9);}' +
      '.cver-btn:focus-visible,.cver-stage:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.cver-viz{min-height:160px;margin-top:' + space3 + ';padding:' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';overflow:hidden;position:relative;}' +
      '.cver-caption{min-height:50px;}' +
      '.cver-file-card{display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid var(--cver-file-border,' + border + ');transition:transform 0.4s,opacity 0.4s;font-family:' + mono + ';font-size:0.72rem;}' +
      '.cver-hash-digits{font-variant-numeric:tabular-nums;letter-spacing:0.08em;}' +
      '.cver-hash-digit{display:inline-block;width:0.52em;text-align:center;transition:color 0.15s;}' +
      '.cver-dedup-badge{display:inline-block;font-size:0.62rem;background:' + green + ';color:#000;border-radius:3px;padding:1px 5px;font-weight:600;font-family:' + body + ';}' +
      '.cver-blob-card{display:inline-flex;flex-direction:column;align-items:center;padding:6px 10px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + border + ';transition:transform 0.4s,opacity 0.4s;font-family:' + mono + ';font-size:0.7rem;}' +
      '.cver-manifest-card{display:inline-block;padding:10px 14px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + accent + ';font-family:' + mono + ';font-size:0.7rem;}' +
      '.cver-version-node{display:inline-flex;flex-direction:column;align-items:center;padding:8px 14px;border-radius:' + radiusSm + ';background:' + surface + ';border:2px solid ' + purple + ';transition:transform 0.4s,opacity 0.4s;font-family:' + mono + ';font-size:0.7rem;}' +
      '.cver-rep-entry{display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + orange + ';transition:transform 0.35s,opacity 0.35s;font-family:' + mono + ';font-size:0.72rem;}' +
      '.cver-chunk-copy{display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border-radius:4px;background:' + surface2 + ';border:1px solid ' + border + ';transition:transform 0.35s,opacity 0.35s;font-family:' + mono + ';font-size:0.65rem;}' +
      '.cver-weight-badge{display:inline-block;font-size:0.6rem;background:' + orange + ';color:#000;border-radius:3px;padding:1px 4px;font-weight:600;font-family:' + body + ';}' +
      '.cver-mlflow-badge{display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + green + ';font-family:' + mono + ';font-size:0.7rem;transition:opacity 0.5s,transform 0.5s;}' +
      '@media(max-width:600px){.cver-pipeline{flex-direction:column;}.cver-arrow{transform:rotate(90deg);}}' +
      '</style>';

    this.container.innerHTML =
      '<div class="cver-widget">' +
      css +
      '<div class="widget-label" style="display:block;font-size:0.75rem;color:' + muted + ';margin-bottom:' + space2 + ';">Content versioning walkthrough \u2014 hash, manifest, chain, replicate, trace:</div>' +
      controlsHtml +
      '<div class="cver-pipeline" style="display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';background:' + surface + ';" id="cver-pipeline">' +
      stageHtml +
      '</div>' +
      '<div class="cver-viz" style="min-height:160px;margin-top:' + space3 + ';padding:' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';overflow:hidden;position:relative;" id="cver-viz" role="region" aria-label="Versioning visualization">' +
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a stage above or press Play/Step to explore</div>' +
      '</div>' +
      '<div class="cver-caption" style="min-height:50px;margin-top:' + space2 + ';padding:' + space2 + ' ' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';" id="cver-caption">' +
      '</div>' +
      '</div>';

    this._vizEl = this.container.querySelector('#cver-viz');
    this._captionEl = this.container.querySelector('#cver-caption');
    this._pipelineEl = this.container.querySelector('#cver-pipeline');
    this._stageEls = this.container.querySelectorAll('[data-cver-stage]');
    this._playBtn = this.container.querySelector('#cver-play-btn');
    this._stepBtn = this.container.querySelector('#cver-step-btn');
    this._resetBtn = this.container.querySelector('#cver-reset-btn');

    /* Click delegation */
    this.container.addEventListener('click', function (e) {
      var stage = e.target.closest('[data-cver-stage]');
      if (stage) {
        var id = stage.getAttribute('data-cver-stage');
        var idx = self._findStageIndex(id);
        if (idx >= 0) {
          self._activate(idx);
        }
      }
    });

    /* Keyboard */
    this.container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        var stage = e.target.closest('[data-cver-stage]');
        if (stage) {
          e.preventDefault();
          var id = stage.getAttribute('data-cver-stage');
          var idx = self._findStageIndex(id);
          if (idx >= 0) self._activate(idx);
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
  };

  ContentVersioningWidget.prototype._resolveColor = function (varName, fallback) {
    var c = window.AnvilBase.token(varName, fallback);
    return c || fallback;
  };

  ContentVersioningWidget.prototype._findStageIndex = function (id) {
    for (var i = 0; i < this._stages.length; i++) {
      if (this._stages[i].id === id) return i;
    }
    return -1;
  };

  ContentVersioningWidget.prototype._clearVizTimers = function () {
    if (this._vizTimers) {
      for (var i = 0; i < this._vizTimers.length; i++) {
        var t = this._vizTimers[i];
        if (t !== null) {
          clearTimeout(t);
          clearInterval(t);
        }
      }
    }
    this._vizTimers = [];
  };

  ContentVersioningWidget.prototype._addTimer = function (t) {
    if (!this._vizTimers) this._vizTimers = [];
    this._vizTimers.push(t);
  };

  ContentVersioningWidget.prototype._activate = function (idx) {
    if (idx < 0 || idx >= this._stages.length) return;
    this._clearVizTimers();
    this._stage = idx;

    for (var i = 0; i < this._stageEls.length; i++) {
      var el = this._stageEls[i];
      var stageId = el.getAttribute('data-cver-stage');
      var sIdx = this._findStageIndex(stageId);
      if (sIdx <= idx) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
      if (sIdx >= 0) {
        var stageCol = this._resolveColor(this._stages[sIdx].color, '#007aff');
        el.style.setProperty('--cver-color', stageCol);
      }
    }

    var stage = this._stages[idx];
    var capText = this._captions[stage.id];
    var col = this._resolveColor(stage.color, '#007aff');
    var textColor = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');

    if (capText) {
      this._captionEl.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
        '<span style="width:8px;height:8px;border-radius:50%;background:' + col + ';flex-shrink:0;"></span>' +
        '<span style="font-size:0.82rem;font-weight:600;color:' + textColor + ';">' + capText.title + '</span>' +
        '<span style="font-size:0.62rem;color:' + muted + ';font-family:ui-monospace,monospace;">#' + (idx + 1) + '</span>' +
        '</div>' +
        '<div style="font-size:0.74rem;color:' + muted + ';line-height:1.5;">' + capText.body + '</div>';
    }

    switch (idx) {
      case 0: this._renderVizHash(); break;
      case 1: this._renderVizManifest(); break;
      case 2: this._renderVizVersion(); break;
      case 3: this._renderVizReplication(); break;
      case 4: this._renderVizLineage(); break;
    }
  };

  /* STAGE 0: Hash */
  ContentVersioningWidget.prototype._renderVizHash = function () {
    var self = this;
    var viz = this._vizEl;
    var accent = window.AnvilBase.token('--accent', '#007aff');
    var cyan = window.AnvilBase.token('--accent-cyan', '#32d74b');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');
    var border = window.AnvilBase.token('--border', '#38383a');

    var files = [
      { name: 'alice.txt', content: 'Hello world', hash: 'a3f91e2b', group: 'A' },
      { name: 'bob.txt', content: 'Training data', hash: '7e2b1c4f', group: 'B' },
      { name: 'copy.txt', content: 'Hello world', hash: 'a3f91e2b', group: 'A' },
    ];

    var html = '<div style="display:flex;flex-direction:column;gap:14px;">';
    html += '<div style="font-size:0.68rem;color:' + muted + ';font-family:' + mono + ';text-align:center;">SHA-256 content addressing</div>';
    html += '<div id="cver-hash-row" style="display:flex;flex-wrap:wrap;justify-content:center;gap:16px;">';

    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var hashChars = f.hash.split('');
      var hashHtml = '';
      for (var j = 0; j < hashChars.length; j++) {
        hashHtml += '<span class="cver-hash-digit" data-target="' + hashChars[j] + '" style="font-variant-numeric:tabular-nums;display:inline-block;width:0.52em;text-align:center;">?</span>';
      }
      var fileBorder = f.group === 'A' ? green : border;
      html += '<div class="cver-file-card" style="--cver-file-border:' + fileBorder + ';display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + fileBorder + ';transition:transform 0.4s,opacity 0.4s;font-family:' + mono + ';font-size:0.72rem;" data-file="' + i + '" data-group="' + f.group + '">' +
        '<div style="font-size:0.72rem;font-weight:600;color:' + text + ';">' + f.name + '</div>' +
        '<div style="font-size:0.6rem;color:' + muted + ';margin:2px 0;">' + f.content + '</div>' +
        '<div style="margin-top:4px;padding:2px 6px;background:rgba(0,0,0,0.2);border-radius:4px;">' +
        '<span style="font-size:0.55rem;color:' + muted + ';">SHA256:</span> ' +
        '<span class="cver-hash-digits" style="font-variant-numeric:tabular-nums;letter-spacing:0.08em;font-size:0.65rem;color:' + cyan + ';">' + hashHtml + '</span>' +
        '</div>' +
        '<div class="cver-dedup-badge-wrapper" style="min-height:18px;margin-top:2px;"></div>' +
        '</div>';
    }

    html += '</div>';
    html += '<div id="cver-dedup-result" style="display:none;text-align:center;padding:8px;border-radius:' + radiusSm + ';background:rgba(52,199,89,0.1);border:1px solid ' + green + ';font-size:0.72rem;">' +
      '<span style="font-weight:600;color:' + green + ';">\u2713 Deduplicated:</span> ' +
      '<span style="color:' + text + ';font-family:' + mono + ';">a3f91e2b</span> ' +
      '<span style="color:' + muted + ';font-size:0.65rem;">(identical content resolves to same hash)</span>' +
      '</div>';
    html += '</div>';

    viz.innerHTML = html;

    this._hashSettleCheck = function () {
      var els = viz.querySelectorAll('.cver-hash-digit');
      var allSettled = true;
      for (var ei = 0; ei < els.length; ei++) {
        if (els[ei].textContent !== els[ei].getAttribute('data-target')) {
          allSettled = false;
          break;
        }
      }
      if (allSettled) {
        var groupA = viz.querySelectorAll('.cver-file-card[data-group="A"]');
        var dedupSlot = viz.querySelector('#cver-dedup-result');
        if (groupA.length >= 2 && dedupSlot) {
          for (var gi = 0; gi < groupA.length; gi++) {
            var bw = groupA[gi].querySelector('.cver-dedup-badge-wrapper');
            if (bw) {
              bw.innerHTML = '<span class="cver-dedup-badge">' + (gi === 0 ? 'original' : 'deduplicated') + '</span>';
            }
          }
          dedupSlot.style.display = 'block';
        }
      }
    };

    if (this._reducedMotion) {
      var els = viz.querySelectorAll('.cver-hash-digit');
      for (var ei = 0; ei < els.length; ei++) {
        els[ei].textContent = els[ei].getAttribute('data-target');
      }
      this._hashSettleCheck();
      return;
    }

    var scrambleCounts = {};
    var maxScrambles = 8;
    var digitInterval = 40;

    for (var fi = 0; fi < files.length; fi++) {
      var digits = viz.querySelectorAll('.cver-file-card[data-file="' + fi + '"] .cver-hash-digit');
      for (var di = 0; di < digits.length; di++) {
        (function (digitEl, fileIdx, digIdx) {
          var key = fileIdx + '-' + digIdx;
          scrambleCounts[key] = 0;
          var t = setInterval(function () {
            var target = digitEl.getAttribute('data-target');
            var count = scrambleCounts[key];
            if (count >= maxScrambles) {
              digitEl.textContent = target;
              digitEl.style.color = cyan;
              clearInterval(t);
              for (var ti = 0; ti < self._vizTimers.length; ti++) {
                if (self._vizTimers[ti] === t) {
                  self._vizTimers[ti] = null;
                }
              }
              if (self._hashSettleCheck) self._hashSettleCheck();
              return;
            }
            var hexChars = '0123456789abcdef';
            digitEl.textContent = hexChars[Math.floor(Math.random() * 16)];
            scrambleCounts[key] = count + 1;
          }, digitInterval);
          self._addTimer(t);
        })(digits[di], fi, di);
      }
    }
  };

  /* STAGE 1: Manifest */
  ContentVersioningWidget.prototype._renderVizManifest = function () {
    var viz = this._vizEl;
    var accent = window.AnvilBase.token('--accent', '#007aff');
    var cyan = window.AnvilBase.token('--accent-cyan', '#32d74b');
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var border = window.AnvilBase.token('--border', '#38383a');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');

    var manifestDigest = '8c4da2f17e3b9a05d6f1c8e4a2b7093c1d5f0e6a7b8c9d0e1f2a3b4c5d6e7f8';
    var shortDigest = manifestDigest.slice(0, 12) + '\u2026';

    var entries = [
      { path: 'corpora/alice.txt', hash: 'a3f91e2b', weight: '1.0' },
      { path: 'corpora/bob.txt', hash: '7e2b1c4f', weight: '1.0' },
    ];

    var entryRows = '';
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      entryRows +=
        '<tr style="border-bottom:1px solid ' + border + ';">' +
        '<td style="padding:3px 6px;font-size:0.65rem;font-family:' + mono + ';">' + e.path + '</td>' +
        '<td style="padding:3px 6px;font-size:0.65rem;font-family:' + mono + ';color:' + cyan + ';">' + e.hash + '</td>' +
        '<td style="padding:3px 6px;font-size:0.65rem;font-variant-numeric:tabular-nums;text-align:right;">' + e.weight + '</td>' +
        '</tr>';
    }

    var html = '<div style="display:flex;flex-direction:column;align-items:center;gap:12px;">';
    html += '<div style="font-size:0.68rem;color:' + muted + ';font-family:' + mono + ';">Blobs gathered into versioned manifest</div>';

    html += '<div id="cver-manifest-blobs" style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">';
    html += '<div class="cver-blob-card" style="opacity:1;padding:6px 10px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + green + ';">' +
      '<span style="font-size:0.6rem;color:' + muted + ';">blob</span>' +
      '<span style="font-size:0.7rem;color:' + cyan + ';font-family:' + mono + ';">a3f91e2b</span>' +
      '</div>';
    html += '<div class="cver-blob-card" style="opacity:1;padding:6px 10px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + border + ';">' +
      '<span style="font-size:0.6rem;color:' + muted + ';">blob</span>' +
      '<span style="font-size:0.7rem;color:' + cyan + ';font-family:' + mono + ';">7e2b1c4f</span>' +
      '</div>';
    html += '</div>';

    html += '<div style="font-size:0.7rem;color:' + muted + ';opacity:0.6;">\u25bc</div>';

    html += '<div class="cver-manifest-card" style="display:inline-block;padding:10px 14px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + accent + ';min-width:280px;">';
    html += '<div style="font-size:0.72rem;font-weight:600;color:' + text + ';margin-bottom:6px;text-align:center;">Manifest</div>';
    html += '<table style="width:100%;border-collapse:collapse;">' +
      '<thead><tr style="border-bottom:2px solid ' + accent + ';">' +
      '<th style="padding:3px 6px;font-size:0.6rem;color:' + muted + ';text-align:left;">path</th>' +
      '<th style="padding:3px 6px;font-size:0.6rem;color:' + muted + ';text-align:left;">content_hash</th>' +
      '<th style="padding:3px 6px;font-size:0.6rem;color:' + muted + ';text-align:right;">weight</th>' +
      '</tr></thead>' +
      '<tbody>' + entryRows + '</tbody>' +
      '</table>';
    html += '<div style="margin-top:8px;padding-top:6px;border-top:1px solid ' + border + ';text-align:center;">';
    html += '<span style="font-size:0.6rem;color:' + muted + ';">manifest_digest:</span> ';
    html += '<span style="font-size:0.65rem;color:' + accent + ';font-family:' + mono + ';font-variant-numeric:tabular-nums;">' + shortDigest + '</span>';
    html += '</div></div>';

    html += '<div style="font-size:0.62rem;color:' + muted + ';font-style:italic;">SHA-256 of canonical JSON (sorted entries, sort_keys=True, separators=",":)</div>';
    html += '</div>';

    viz.innerHTML = html;
  };

  /* STAGE 2: Version Chain */
  ContentVersioningWidget.prototype._renderVizVersion = function () {
    var self = this;
    var viz = this._vizEl;
    var purple = window.AnvilBase.token('--accent-purple', '#af52de');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');
    var border = window.AnvilBase.token('--border', '#38383a');

    var html = '<div style="display:flex;flex-direction:column;align-items:center;gap:12px;">';
    html += '<div style="font-size:0.68rem;color:' + muted + ';font-family:' + mono + ';">Monotonically increasing version chain</div>';

    html += '<div id="cver-chain-container" style="display:flex;align-items:center;gap:8px;justify-content:center;flex-wrap:wrap;">';

    html += '<div class="cver-version-node" style="display:inline-flex;flex-direction:column;align-items:center;padding:8px 14px;border-radius:' + radiusSm + ';background:' + surface + ';border:2px solid ' + purple + ';opacity:1;">' +
      '<span style="font-size:0.8rem;font-weight:700;color:' + purple + ';">v1</span>' +
      '<span style="font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';">version #1</span>' +
      '<span style="font-size:0.55rem;color:' + muted + ';font-family:' + mono + ';font-variant-numeric:tabular-nums;">8c4da2f17e\u2026</span>' +
      '</div>';

    html += '<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">';
    html += '<div style="width:36px;height:2px;background:' + muted + ';position:relative;opacity:0.6;"></div>';
    html += '<div style="font-size:0.55rem;color:' + muted + ';font-family:' + mono + ';">append</div>';
    html += '</div>';

    html += '<div id="cver-v2-node" class="cver-version-node" style="display:inline-flex;flex-direction:column;align-items:center;padding:8px 14px;border-radius:' + radiusSm + ';background:' + surface + ';border:2px solid ' + purple + ';opacity:0;transform:translateX(20px);transition:opacity 0.5s,transform 0.5s;">' +
      '<span style="font-size:0.8rem;font-weight:700;color:' + purple + ';">v2</span>' +
      '<span style="font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';">version #2</span>' +
      '<span style="font-size:0.55rem;color:' + muted + ';font-family:' + mono + ';font-variant-numeric:tabular-nums;">fd3e7a21b0\u2026</span>' +
      '</div>';

    html += '</div>';

    html += '<div style="font-size:0.65rem;color:' + muted + ';background:rgba(175,82,222,0.08);padding:6px 12px;border-radius:' + radiusSm + ';text-align:center;font-family:' + mono + ';">' +
      'version_number = max(existing versions) + 1' +
      '</div>';

    html += '<div style="font-size:0.6rem;color:' + muted + ';font-style:italic;">Each manifest snapshot becomes an immutable version node</div>';
    html += '</div>';

    viz.innerHTML = html;

    if (this._reducedMotion) {
      var v2 = viz.querySelector('#cver-v2-node');
      if (v2) {
        v2.style.opacity = '1';
        v2.style.transform = 'translateX(0)';
      }
      return;
    }

    var v2Timer = setTimeout(function () {
      var v2 = viz.querySelector('#cver-v2-node');
      if (v2) {
        v2.style.opacity = '1';
        v2.style.transform = 'translateX(0)';
      }
    }, 400);
    this._addTimer(v2Timer);
  };

  /* STAGE 3: Weight Replication */
  ContentVersioningWidget.prototype._renderVizReplication = function () {
    var self = this;
    var viz = this._vizEl;
    var orange = window.AnvilBase.token('--accent-orange', '#ff9500');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var surface2 = window.AnvilBase.token('--surface-2', '#2c2c2e');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var border = window.AnvilBase.token('--border', '#38383a');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');

    var html = '<div style="display:flex;flex-direction:column;align-items:center;gap:14px;">';

    html += '<div style="font-size:0.72rem;font-family:' + mono + ';color:' + orange + ';background:rgba(255,149,0,0.08);padding:4px 12px;border-radius:' + radiusSm + ';border:1px solid rgba(255,149,0,0.2);font-variant-numeric:tabular-nums;">' +
      'factor = max(1, round(weight))' +
      '</div>';

    html += '<div style="display:flex;flex-direction:column;align-items:center;gap:8px;width:100%;">';
    html += '<div style="font-size:0.65rem;color:' + muted + ';font-family:' + mono + ';">Entry with weight=3</div>';

    html += '<div style="display:flex;align-items:center;gap:12px;justify-content:center;flex-wrap:wrap;">';

    html += '<div class="cver-rep-entry" style="display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + orange + ';">' +
      '<span style="font-size:0.7rem;font-weight:600;color:' + text + ';">alice.txt</span>' +
      '<span class="cver-weight-badge" style="font-size:0.6rem;background:' + orange + ';color:#000;border-radius:3px;padding:1px 4px;font-weight:600;margin-top:2px;">weight: 3</span>' +
      '</div>';

    html += '<div style="font-size:0.7rem;color:' + muted + ';opacity:0.6;">\u25b6</div>';

    html += '<div id="cver-fan-group-3" style="display:flex;flex-direction:column;gap:4px;">';
    for (var c = 0; c < 3; c++) {
      html += '<div class="cver-chunk-copy" data-fan="3" data-copy="' + c + '" style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border-radius:4px;background:' + surface2 + ';border:1px solid ' + border + ';opacity:0;transform:translateX(20px);transition:opacity 0.35s,transform 0.35s;">' +
        '<span style="font-size:0.6rem;color:' + orange + ';">chunk</span>' +
        '<span style="font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';">copy #' + (c + 1) + '</span>' +
        '</div>';
    }
    html += '</div>';

    html += '</div>';
    html += '</div>';

    html += '<div style="display:flex;flex-direction:column;align-items:center;gap:8px;width:100%;">';
    html += '<div style="font-size:0.65rem;color:' + muted + ';font-family:' + mono + ';">Entry with weight=0.4</div>';

    html += '<div style="display:flex;align-items:center;gap:12px;justify-content:center;flex-wrap:wrap;">';

    html += '<div class="cver-rep-entry" style="display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + border + ';">' +
      '<span style="font-size:0.7rem;font-weight:600;color:' + text + ';">bob.txt</span>' +
      '<span class="cver-weight-badge" style="font-size:0.6rem;background:' + orange + ';color:#000;border-radius:3px;padding:1px 4px;font-weight:600;margin-top:2px;">weight: 0.4</span>' +
      '</div>';

    html += '<div style="font-size:0.7rem;color:' + muted + ';opacity:0.6;">\u25b6</div>';

    html += '<div id="cver-fan-group-04" style="display:flex;flex-direction:column;gap:4px;">';
    html += '<div class="cver-chunk-copy" data-fan="04" data-copy="0" style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;border-radius:4px;background:' + surface2 + ';border:1px solid ' + border + ';opacity:0;transform:translateX(20px);transition:opacity 0.35s,transform 0.35s;">' +
      '<span style="font-size:0.6rem;color:' + orange + ';">chunk</span>' +
      '<span style="font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';">copy #1 (floor: max(1, 0))</span>' +
      '</div>';
    html += '</div>';

    html += '</div>';
    html += '</div>';

    html += '</div>';

    viz.innerHTML = html;

    if (this._reducedMotion) {
      var allCopies = viz.querySelectorAll('.cver-chunk-copy');
      for (var ci = 0; ci < allCopies.length; ci++) {
        allCopies[ci].style.opacity = '1';
        allCopies[ci].style.transform = 'translateX(0)';
      }
      return;
    }

    var fanDelay = 150;
    var allCopiesAnim = viz.querySelectorAll('.cver-chunk-copy');
    for (var ci2 = 0; ci2 < allCopiesAnim.length; ci2++) {
      (function (copyEl, delay) {
        var t = setTimeout(function () {
          copyEl.style.opacity = '1';
          copyEl.style.transform = 'translateX(0)';
        }, delay);
        self._addTimer(t);
      })(allCopiesAnim[ci2], 300 + ci2 * fanDelay);
    }
  };

  /* STAGE 4: Lineage */
  ContentVersioningWidget.prototype._renderVizLineage = function () {
    var self = this;
    var viz = this._vizEl;
    var green = window.AnvilBase.token('--accent-green', '#34c759');
    var purple = window.AnvilBase.token('--accent-purple', '#af52de');
    var surface = window.AnvilBase.token('--surface', '#1c1c1e');
    var text = window.AnvilBase.token('--text', '#ffffff');
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var mono = window.AnvilBase.token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var radiusSm = window.AnvilBase.token('--radius-sm', '8px');

    var html = '<div style="display:flex;flex-direction:column;align-items:center;gap:14px;">';
    html += '<div style="font-size:0.68rem;color:' + muted + ';font-family:' + mono + ';">Provenance lineage: content \u2192 model</div>';

    html += '<div id="cver-lineage-row" style="display:flex;align-items:center;gap:8px;justify-content:center;flex-wrap:wrap;">';

    html += '<div class="cver-version-node" style="display:inline-flex;flex-direction:column;align-items:center;padding:8px 14px;border-radius:' + radiusSm + ';background:' + surface + ';border:2px solid ' + purple + ';">' +
      '<span style="font-size:0.75rem;font-weight:700;color:' + purple + ';">v2</span>' +
      '<span style="font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';">version #2</span>' +
      '<span style="font-size:0.55rem;color:' + muted + ';font-family:' + mono + ';font-variant-numeric:tabular-nums;">fd3e7a21b0\u2026</span>' +
      '</div>';

    html += '<div id="cver-lineage-line" style="width:40px;height:2px;background:' + muted + ';position:relative;opacity:0;transition:opacity 0.6s;">' +
      '<div style="position:absolute;right:-4px;top:-3px;border:4px solid transparent;border-left-color:' + muted + ';"></div>' +
      '</div>';

    html += '<div id="cver-mlflow-badge" class="cver-mlflow-badge" style="display:inline-flex;flex-direction:column;align-items:center;padding:8px 12px;border-radius:' + radiusSm + ';background:' + surface + ';border:1px solid ' + green + ';opacity:0;transform:translateX(15px);transition:opacity 0.5s,transform 0.5s;">' +
      '<span style="font-size:0.65rem;font-weight:600;color:' + green + ';">MLflow Run</span>' +
      '<span style="font-size:0.6rem;color:' + muted + ';font-family:' + mono + ';">run: exp_001</span>' +
      '<span style="font-size:0.55rem;color:' + muted + ';font-family:' + mono + ';">model: anvil-llama</span>' +
      '<span style="font-size:0.5rem;color:' + green + ';margin-top:2px;">VersionRunRef</span>' +
      '</div>';

    html += '</div>';

    html += '<div style="font-size:0.72rem;color:' + text + ';text-align:center;max-width:400px;padding:8px 16px;border-radius:' + radiusSm + ';background:rgba(52,199,89,0.08);border:1px solid rgba(52,199,89,0.2);">' +
      'Trace any model back to the exact bytes of source data that shaped it.' +
      '</div>';

    html += '<div style="font-size:0.6rem;color:' + muted + ';font-style:italic;">VersionRunRef connects every training run to its manifest version</div>';
    html += '</div>';

    viz.innerHTML = html;

    if (this._reducedMotion) {
      var line = viz.querySelector('#cver-lineage-line');
      var badge = viz.querySelector('#cver-mlflow-badge');
      if (line) line.style.opacity = '1';
      if (badge) {
        badge.style.opacity = '1';
        badge.style.transform = 'translateX(0)';
      }
      return;
    }

    var lineTimer = setTimeout(function () {
      var line = viz.querySelector('#cver-lineage-line');
      if (line) line.style.opacity = '1';
    }, 300);
    this._addTimer(lineTimer);

    var badgeTimer = setTimeout(function () {
      var badge = viz.querySelector('#cver-mlflow-badge');
      if (badge) {
        badge.style.opacity = '1';
        badge.style.transform = 'translateX(0)';
      }
    }, 600);
    this._addTimer(badgeTimer);
  };

  ContentVersioningWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._stop();
    } else {
      this._play();
    }
  };

  ContentVersioningWidget.prototype._play = function () {
    var self = this;
    if (this._playing) return;
    if (this._stage >= this._stages.length - 1) {
      this._stage = -1;
      this._clearVizTimers();
      if (this._vizEl) {
        this._vizEl.innerHTML = '<div style="font-size:0.72rem;color:' + window.AnvilBase.token('--text-muted', '#8e8e93') + ';text-align:center;padding:' + window.AnvilBase.token('--space-3', '0.75rem') + ';">Click a stage above or press Play/Step to explore</div>';
      }
      for (var ri = 0; ri < this._stageEls.length; ri++) {
        this._stageEls[ri].classList.remove('active');
      }
    }
    this._playing = true;
    if (this._playBtn) {
      this._playBtn.textContent = 'Pause';
    }

    var interval = this._reducedMotion ? 400 : 1400;

    this._timer = setInterval(function () {
      var next = self._stage + 1;
      if (next >= self._stages.length) {
        self._stop();
        return;
      }
      self._activate(next);
    }, interval);
  };

  ContentVersioningWidget.prototype._stop = function () {
    this._playing = false;
    window.AnvilBase.stop(this);
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  ContentVersioningWidget.prototype._step = function () {
    if (this._playing) this._stop();
    var next = this._stage + 1;
    if (next >= this._stages.length) return;
    this._activate(next);
  };

  ContentVersioningWidget.prototype._reset = function () {
    if (this._playing) this._stop();
    this._clearVizTimers();
    this._stage = -1;
    for (var i = 0; i < this._stageEls.length; i++) {
      this._stageEls[i].classList.remove('active');
    }
    var muted = window.AnvilBase.token('--text-muted', '#8e8e93');
    var space3 = window.AnvilBase.token('--space-3', '0.75rem');
    if (this._vizEl) {
      this._vizEl.innerHTML = '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a stage above or press Play/Step to explore</div>';
    }
    if (this._captionEl) {
      this._captionEl.innerHTML = '';
    }
  };

  window.ContentVersioningWidget = ContentVersioningWidget;
})();