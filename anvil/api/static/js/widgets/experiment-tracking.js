// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function ExperimentTrackingWidget(container) {
    if (!container) return;
    this.container = container;
    this._stage = -1;
    this._playing = false;
    this._timer = null;
    this._trainingTimer = null;
    this._trainPt = 0;
    this._reducedMotion = false;
    this._degraded = false;

    this._lossSeries = [
      4.50, 4.20, 3.90, 3.65, 3.45, 3.25, 3.08, 2.92, 2.78, 2.65,
      2.53, 2.42, 2.32, 2.23, 2.15, 2.08, 2.02, 1.87, 1.82, 1.78
    ];

    this._stages = [
      {
        id: 'start',
        label: 'START',
        sub: 'Params logged',
        color: '--accent',
        zone: 'params'
      },
      {
        id: 'training',
        label: 'TRAINING',
        sub: 'Loss curve',
        color: '--accent-orange',
        zone: 'training'
      },
      {
        id: 'final',
        label: 'FINAL',
        sub: 'final\_loss metric',
        color: '--accent-green',
        zone: 'metric'
      },
      {
        id: 'artifacts',
        label: 'ARTIFACTS',
        sub: 'Files logged',
        color: '--accent-purple',
        zone: 'artifacts'
      },
      {
        id: 'registry',
        label: 'REGISTRY',
        sub: 'Model registered',
        color: '--accent-cyan',
        zone: 'registry'
      }
    ];

    this._captions = {
      start: {
        title: 'Parameters Logged to MLflow',
        body: 'When a training run starts, hyperparameters are logged as MLflow params. The TrackingService calls start_run() with n_embd, n_layer, n_head, lr, and num_steps. These params are visible in the MLflow UI and used to identify and compare runs. If MLflow is unreachable, the service enters degraded mode and silently skips logging \u2014 training continues unaffected.'
      },
      training: {
        title: 'Training \u2014 Per-Step Loss Metrics',
        body: 'During training, the service logs a loss metric at every step via log_metric("loss", value, step=N). The loss curve streams from the server to the browser over SSE. In the real system, this is how you watch your model learn in real time. The curve typically descends rapidly at first then plateaus.'
      },
      final: {
        title: 'Final Loss Metric',
        body: 'When training completes, the service logs a final_loss metric with no step number (log_final_metric). This value represents the model\u2019s best achieved loss and is used for comparing experiments side-by-side in the experiments dashboard.'
      },
      artifacts: {
        title: 'Artifacts Logged to MLflow',
        body: 'After training, the service logs file artifacts via log_artifacts(): model.safetensors (the trained weights in HuggingFace format), config.json (architecture params), tokenizer.json (vocabulary), MLmodel (model signature), and conda.yaml (reproducible environment). These are stored in the MLflow artifact store under runs:/<run_id>/artifacts/.'
      },
      registry: {
        title: 'Model Registered in Model Registry',
        body: 'Finally, the service calls register_source_model() which creates a versioned model entry in the MLflow Model Registry with a runs:/<run_id>/model.json source URI. The registered model links back to the experiment run, enabling version tracking, stage promotion (staging \u2192 production), and deployment. The model name is auto-derived from the dataset (e.g. dataset-42) or corpus (e.g. corpus-3).'
      }
    };

    this._paramChips = [
      { key: 'n_embd', value: '16' },
      { key: 'n_layer', value: '1' },
      { key: 'n_head', value: '4' },
      { key: 'lr', value: '0.01' },
      { key: 'num_steps', value: '1000' }
    ];

    this._artifactChips = [
      'model.safetensors',
      'config.json',
      'tokenizer.json',
      'MLmodel',
      'conda.yaml'
    ];

    this._render();
  }

  ExperimentTrackingWidget.prototype._token = function (name, fallback) {
    var style = getComputedStyle(document.documentElement);
    return style.getPropertyValue(name).trim() || fallback;
  };

  ExperimentTrackingWidget.prototype._render = function () {
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
    var space1 = this._token('--space-1', '0.25rem');

    var stageHtml = '';
    for (var i = 0; i < this._stages.length; i++) {
      var s = this._stages[i];
      var col = this._resolveColor(s.color, accent);
      stageHtml +=
        '<div class="et-stage" data-et-stage="' + s.id + '" style="background:' + surface + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:' + space2 + ' ' + space3 + ';text-align:center;min-width:80px;cursor:pointer;transition:transform 0.2s,box-shadow 0.2s,opacity 0.2s,border-color 0.2s;position:relative;" tabindex="0" role="button" aria-label="Experiment phase: ' + s.label + '">' +
        '<div class="et-stage-indicator" style="position:absolute;top:-4px;left:50%;transform:translateX(-50%);width:8px;height:8px;border-radius:50%;background:' + col + ';opacity:0;transition:opacity 0.3s,box-shadow 0.3s;box-shadow:0 0 6px ' + col + ';"></div>' +
        '<div class="et-stage-label" style="font-size:0.72rem;font-weight:600;color:' + text + ';font-variant-numeric:tabular-nums;">' + s.label + '</div>' +
        '<div class="et-stage-sub" style="font-size:0.6rem;color:' + muted + ';margin-top:1px;font-family:' + mono + ';">' + s.sub + '</div>' +
        '</div>';
      if (i < this._stages.length - 1) {
        stageHtml += '<div class="et-arrow" style="color:' + muted + ';font-size:0.6rem;text-align:center;padding:1px 0;opacity:0.4;">&#9654;</div>';
      }
    }

    var controlsHtml =
      '<div class="et-controls" style="display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space2 + ';flex-wrap:wrap;">' +
      '<button id="et-play-btn" class="et-btn" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.78rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,transform 0.15s;" aria-label="Play animation">Play</button>' +
      '<button id="et-step-btn" class="et-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.78rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,transform 0.15s;" aria-label="Step to next phase">Step</button>' +
      '<button id="et-reset-btn" class="et-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.78rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,transform 0.15s;" aria-label="Reset animation">Reset</button>' +
      '<button id="et-degrade-btn" class="et-btn" style="background:' + surface2 + ';color:' + muted + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:5px 14px;font-size:0.72rem;cursor:pointer;font-family:' + body + ';transition:filter 0.15s,transform 0.15s,background 0.2s,color 0.2s;" aria-label="Toggle MLflow offline degraded mode" data-degraded="false">MLflow offline</button>' +
      '</div>';

    var css = '<style>' +
      '.et-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.et-pipeline{display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';}' +
      '.et-stage:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.et-stage:hover{border-color:var(--et-color,' + accent + ')!important;}' +
      '.et-stage.active .et-stage-indicator{opacity:1!important;}' +
      '.et-stage.active{border-color:var(--et-color,' + accent + ')!important;box-shadow:0 0 0 2px var(--et-color,' + accent + '),0 0 10px color-mix(in srgb,var(--et-color,' + accent + ') 25%,transparent)!important;}' +
      '.et-content{min-height:80px;transition:opacity 0.25s;}' +
      '.et-chip{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:var(--radius-sm,' + radiusSm + ');font-family:' + mono + ';font-size:0.7rem;font-variant-numeric:tabular-nums;background:' + surface2 + ';border:1px solid ' + border + ';color:' + text + ';opacity:0;transform:scale(0.9);transition:opacity 0.3s,transform 0.3s;}' +
      '.et-chip.visible{opacity:1;transform:scale(1);}' +
      '.et-chip .et-chip-key{color:' + muted + ';}' +
      '.et-chip .et-chip-val{color:' + text + ';font-weight:600;}' +
      '.et-svg-wrap{opacity:0;transition:opacity 0.4s;}' +
      '.et-svg-wrap.visible{opacity:1;}' +
      '.et-loss-readout{font-family:' + mono + ';font-size:0.9rem;font-variant-numeric:tabular-nums;font-weight:600;}' +
      '.et-final-metric{font-family:' + mono + ';font-variant-numeric:tabular-nums;}' +
      '.et-registry-uri{font-family:' + mono + ';font-size:0.68rem;color:' + muted + ';}' +
      '.et-registry-badge{display:inline-flex;align-items:center;gap:6px;}' +
      '.et-degraded .et-chip{opacity:0.5!important;}' +
      '.et-degraded .et-chip .et-chip-degraded-label{display:inline;color:var(--accent-orange,' + orange + ');font-size:0.6rem;margin-left:4px;}' +
      '.et-degraded .et-final-value{opacity:0.5!important;}' +
      '.et-degraded .et-registry-badge{opacity:0.5!important;}' +
      '.et-degraded .et-svg-wrap{opacity:1!important;}' +  
      '.et-btn:focus-visible{outline:2px solid ' + accent + ';outline-offset:2px;}' +
      '.et-btn:active{transform:scale(0.96);}' +
      '.et-caption-text{font-size:0.75rem;color:' + muted + ';line-height:1.5;}' +
      '.et-caption-title{font-size:0.82rem;font-weight:600;color:' + text + ';}' +
      '.et-caption-num{font-size:0.62rem;color:' + muted + ';font-family:' + mono + ';}' +
      '.et-degrade-btn.active{background:' + orange + '!important;color:#fff!important;border-color:' + orange + '!important;}' +
      '.et-chip-degraded-label{display:none;}' +
      '@media(max-width:600px){.et-pipeline{flex-direction:column;}.et-arrow{transform:rotate(90deg);}}' +
      '</style>';

    this.container.innerHTML =
      '<div class="et-widget">' +
      css +
      '<div class="widget-label" style="display:block;font-size:0.75rem;color:' + muted + ';margin-bottom:' + space2 + ';">MLflow experiment run lifecycle \u2014 click a phase or press Play/Step:</div>' +
      controlsHtml +
      '<div class="et-pipeline" style="display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';" id="et-pipeline">' +
      stageHtml +
      '</div>' +
      '<div class="et-content" style="min-height:80px;transition:opacity 0.25s;margin-top:' + space2 + ';padding:' + space2 + ' ' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';" id="et-content">' +
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a phase or press Play/Step to explore the experiment run lifecycle</div>' +
      '</div>' +
      '<div class="et-caption" style="min-height:40px;margin-top:' + space2 + ';padding:' + space2 + ' ' + space3 + ';border-radius:' + radiusSm + ';" id="et-caption">' +
      '</div>' +
      '</div>';

    this._pipelineEl = this.container.querySelector('#et-pipeline');
    this._stageEls = this.container.querySelectorAll('[data-et-stage]');
    this._contentEl = this.container.querySelector('#et-content');
    this._captionEl = this.container.querySelector('#et-caption');
    this._playBtn = this.container.querySelector('#et-play-btn');
    this._stepBtn = this.container.querySelector('#et-step-btn');
    this._resetBtn = this.container.querySelector('#et-reset-btn');
    this._degradeBtn = this.container.querySelector('#et-degrade-btn');

    this.container.addEventListener('click', function (e) {
      var stage = e.target.closest('[data-et-stage]');
      if (stage) {
        var id = stage.getAttribute('data-et-stage');
        var idx = self._findStageIndex(id);
        if (idx >= 0) {
          self._activate(idx);
        }
      }
    });

    this.container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        var stage = e.target.closest('[data-et-stage]');
        if (stage) {
          e.preventDefault();
          var id = stage.getAttribute('data-et-stage');
          var idx = self._findStageIndex(id);
          if (idx >= 0) self._activate(idx);
        }
      }
    });

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
    if (this._degradeBtn) {
      this._degradeBtn.addEventListener('click', function () {
        self._toggleDegraded();
      });
    }
  };

  ExperimentTrackingWidget.prototype._resolveColor = function (varName, fallback) {
    var c = this._token(varName, fallback);
    return c || fallback;
  };

  ExperimentTrackingWidget.prototype._findStageIndex = function (id) {
    for (var i = 0; i < this._stages.length; i++) {
      if (this._stages[i].id === id) return i;
    }
    return -1;
  };

  ExperimentTrackingWidget.prototype._activate = function (idx) {
    var self = this;
    if (idx < 0 || idx >= this._stages.length) return;

    if (this._trainingTimer) {
      clearInterval(this._trainingTimer);
      this._trainingTimer = null;
    }

    this._stage = idx;

    for (var i = 0; i < this._stageEls.length; i++) {
      var el = this._stageEls[i];
      var stageId = el.getAttribute('data-et-stage');
      var sIdx = this._findStageIndex(stageId);
      if (sIdx <= idx) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
      if (sIdx >= 0) {
        var stageCol = this._resolveColor(this._stages[sIdx].color, '#007aff');
        el.style.setProperty('--et-color', stageCol);
      }
    }

    this._renderContent(idx);
    this._renderCaption(idx);

    var stage = this._stages[idx];
    if (stage.id === 'training') {
      this._trainPt = 0;
      var delay = this._reducedMotion ? 1 : 120;
      if (this._reducedMotion) {
        this._trainPt = this._lossSeries.length;
        this._drawTrainingFrame();
      } else {
        this._trainingTimer = setInterval(function () {
          self._trainPt++;
          self._drawTrainingFrame();
          if (self._trainPt >= self._lossSeries.length) {
            clearInterval(self._trainingTimer);
            self._trainingTimer = null;
            if (self._playing) {
              self._timerAutoAdvance = setTimeout(function () {
                if (self._playing) {
                  self._activate(2);
                }
              }, 300);
            }
          }
        }, delay);
      }
    }
  };

  ExperimentTrackingWidget.prototype._renderContent = function (idx) {
    var stage = this._stages[idx];
    var content = '';
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var border = this._token('--border', '#38383a');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var radiusSm = this._token('--radius-sm', '8px');
    var space1 = this._token('--space-1', '0.25rem');
    var space2 = this._token('--space-2', '0.5rem');

    switch (stage.id) {
      case 'start':
        content = this._renderChips(this._paramChips, 'et-param-chips');
        break;
      case 'training':
        content = this._renderSparkline();
        break;
      case 'final':
        content = this._renderFinalMetric();
        break;
      case 'artifacts':
        content = this._renderChips(
          this._artifactChips.map(function (name) {
            return { key: '', value: name };
          }),
          'et-artifact-chips'
        );
        break;
      case 'registry':
        content = this._renderRegistryBadge();
        break;
    }

    this._contentEl.innerHTML = content;

    if (stage.id === 'start' || stage.id === 'artifacts') {
      var chips = this._contentEl.querySelectorAll('.et-chip');
      for (var i = 0; i < chips.length; i++) {
        (function (chip, delay) {
          setTimeout(function () {
            chip.classList.add('visible');
          }, delay);
        })(chips[i], 100 + i * 80);
      }
    }

    if (this._degraded && (stage.id === 'start' || stage.id === 'final' || stage.id === 'artifacts' || stage.id === 'registry')) {
      this._contentEl.classList.add('et-degraded');
    } else {
      this._contentEl.classList.remove('et-degraded');
    }
  };

  ExperimentTrackingWidget.prototype._renderChips = function (chips, id) {
    var html = '<div id="' + id + '" style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;padding:8px 0;">';
    for (var i = 0; i < chips.length; i++) {
      var chip = chips[i];
      if (chip.key) {
        html += '<span class="et-chip" style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:var(--radius-sm,' + this._token('--radius-sm', '8px') + ');font-family:' + this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace') + ';font-size:0.7rem;font-variant-numeric:tabular-nums;background:' + this._token('--surface-2', '#2c2c2e') + ';border:1px solid ' + this._token('--border', '#38383a') + ';color:' + this._token('--text', '#ffffff') + ';opacity:0;transform:scale(0.9);transition:opacity 0.3s,transform 0.3s;">' +
          '<span class="et-chip-key" style="color:' + this._token('--text-muted', '#8e8e93') + ';">' + chip.key + '</span>' +
          '<span class="et-chip-val" style="color:' + this._token('--text', '#ffffff') + ';font-weight:600;">' + chip.value + '</span>' +
          '<span class="et-chip-degraded-label" style="display:none;">(degraded)</span>' +
          '</span>';
      } else {
        html += '<span class="et-chip" style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:var(--radius-sm,' + this._token('--radius-sm', '8px') + ');font-family:' + this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace') + ';font-size:0.7rem;font-variant-numeric:tabular-nums;background:' + this._token('--surface-2', '#2c2c2e') + ';border:1px solid ' + this._token('--border', '#38383a') + ';color:' + this._token('--text', '#ffffff') + ';opacity:0;transform:scale(0.9);transition:opacity 0.3s,transform 0.3s;">' +
          '<span>' + chip.value + '</span>' +
          '<span class="et-chip-degraded-label" style="display:none;">(skipped)</span>' +
          '</span>';
      }
    }
    html += '</div>';
    return html;
  };

  ExperimentTrackingWidget.prototype._renderSparkline = function () {
    var width = 280;
    var height = 72;
    var pad = { top: 8, bottom: 22, left: 8, right: 8 };
    var plotW = width - pad.left - pad.right;
    var plotH = height - pad.top - pad.bottom;

    var losses = this._lossSeries;
    var maxLoss = 4.5;
    var minLoss = 1.78;
    var range = maxLoss - minLoss;

    var accent = this._resolveColor('--accent-orange', '#ff9500');
    var muted = this._token('--text-muted', '#8e8e93');
    var text = this._token('--text', '#ffffff');
    var border = this._token('--border', '#38383a');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var green = this._resolveColor('--accent-green', '#34c759');

    var html =
      '<div class="et-svg-wrap visible" style="opacity:1;transition:opacity 0.4s;">' +
      '<div style="display:flex;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap;">' +
      '<svg viewBox="0 0 ' + width + ' ' + height + '" style="width:100%;max-width:300px;height:72px;" role="img" aria-label="Training loss curve sparkline: loss decreases from ' + losses[0] + ' to ' + losses[losses.length - 1] + ' over ' + losses.length + ' steps">' +
      '<rect x="0" y="0" width="' + width + '" height="' + height + '" fill="transparent" rx="6"/>' +
      '<polyline id="et-sparkline" fill="none" stroke="' + accent + '" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" points=""/>' +
      '</svg>' +
      '<div style="text-align:center;min-width:80px;">' +
      '<div style="font-size:0.6rem;color:' + muted + ';margin-bottom:2px;">Loss</div>' +
      '<div id="et-loss-value" class="et-loss-readout" style="font-family:' + mono + ';font-size:0.9rem;font-variant-numeric:tabular-nums;font-weight:600;color:' + text + ';">' + losses[0].toFixed(2) + '</div>' +
      '<div style="font-size:0.55rem;color:' + muted + ';margin-top:2px;">step ' + (losses.length - 1) + '</div>' +
      '</div>' +
      '</div>' +
      '<div style="margin-top:6px;font-size:0.62rem;color:' + muted + ';text-align:center;font-family:' + mono + ';font-variant-numeric:tabular-nums;">' +
      'Initial <span style="color:' + muted + ';">' + losses[0].toFixed(2) + '</span>' +
      ' \u2014 Final <span style="color:' + green + ';">' + losses[losses.length - 1].toFixed(2) + '</span>' +
      '</div>' +
      '</div>';

    this._sparklinePolyline = null;

    return html;
  };

  ExperimentTrackingWidget.prototype._drawTrainingFrame = function () {
    var svg = this._contentEl.querySelector('#et-sparkline');
    var readout = this._contentEl.querySelector('#et-loss-value');

    if (!svg) return;

    var losses = this._lossSeries;
    var count = Math.min(this._trainPt + 1, losses.length);
    var width = 280;
    var height = 72;
    var pad = { top: 8, bottom: 22, left: 8, right: 8 };
    var plotW = width - pad.left - pad.right;
    var plotH = height - pad.top - pad.bottom;
    var maxLoss = 4.5;
    var minLoss = 1.78;
    var range = maxLoss - minLoss;

    var points = '';
    for (var i = 0; i < count; i++) {
      var px = pad.left + (i / (losses.length - 1)) * plotW;
      var py = pad.top + plotH - ((losses[i] - minLoss) / range) * plotH;
      points += px + ',' + py + ' ';
    }

    svg.setAttribute('points', points.trim());

    if (readout) {
      var currentLoss = losses[Math.min(this._trainPt, losses.length - 1)];
      readout.textContent = currentLoss.toFixed(2);
    }
  };

  ExperimentTrackingWidget.prototype._renderFinalMetric = function () {
    var finalLoss = this._lossSeries[this._lossSeries.length - 1];
    var muted = this._token('--text-muted', '#8e8e93');
    var text = this._token('--text', '#ffffff');
    var green = this._resolveColor('--accent-green', '#34c759');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var border = this._token('--border', '#38383a');
    var radiusSm = this._token('--radius-sm', '8px');

    var degradedLabel = this._degraded
      ? '<span style="color:' + this._resolveColor('--accent-orange', '#ff9500') + ';font-size:0.65rem;margin-left:6px;">(degraded \u2014 skipped)</span>'
      : '';

    return '<div style="display:flex;align-items:center;justify-content:center;gap:8px;padding:10px 0;flex-wrap:wrap;" class="et-final-metric">' +
      '<span style="font-size:0.72rem;color:' + muted + ';">final_loss:</span>' +
      '<span class="et-final-value" style="font-size:1.1rem;font-weight:700;color:' + green + ';font-family:' + mono + ';font-variant-numeric:tabular-nums;background:' + surface2 + ';padding:4px 12px;border-radius:' + radiusSm + ';border:1px solid ' + green + ';">' + finalLoss.toFixed(4) + '</span>' +
      degradedLabel +
      '</div>';
  };

  ExperimentTrackingWidget.prototype._renderRegistryBadge = function () {
    var muted = this._token('--text-muted', '#8e8e93');
    var text = this._token('--text', '#ffffff');
    var green = this._resolveColor('--accent-green', '#34c759');
    var cyan = this._resolveColor('--accent-cyan', '#32d74b');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var border = this._token('--border', '#38383a');
    var radiusSm = this._token('--radius-sm', '8px');
    var space2 = this._token('--space-2', '0.5rem');

    var degradedLabel = this._degraded
      ? '<div style="color:' + this._resolveColor('--accent-orange', '#ff9500') + ';font-size:0.65rem;margin-top:6px;">(degraded \u2014 skipped)</div>'
      : '';

    return '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:8px 0;" class="et-registry-badge">' +
      '<div style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:' + surface2 + ';border:1px solid ' + cyan + ';border-radius:' + radiusSm + ';">' +
      '<span style="font-size:0.75rem;font-weight:600;color:' + text + ';font-family:' + mono + ';">dataset-42</span>' +
      '<span style="font-size:0.6rem;color:' + muted + ';">&middot;</span>' +
      '<span style="font-size:0.7rem;color:' + green + ';font-weight:600;">v3</span>' +
      '</div>' +
      '<div class="et-registry-uri" style="font-family:' + mono + ';font-size:0.68rem;color:' + muted + ';background:' + surface2 + ';padding:3px 8px;border-radius:' + radiusSm + ';border:1px solid ' + border + ';font-variant-numeric:tabular-nums;">runs:/abc123def456/model.json</div>' +
      degradedLabel +
      '</div>';
  };

  ExperimentTrackingWidget.prototype._renderCaption = function (idx) {
    var stage = this._stages[idx];
    var capText = this._captions[stage.id];
    var textColor = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var col = this._resolveColor(stage.color, '#007aff');

    if (capText) {
      this._captionEl.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
        '<span style="width:8px;height:8px;border-radius:50%;background:' + col + ';flex-shrink:0;"></span>' +
        '<span class="et-caption-title" style="font-size:0.82rem;font-weight:600;color:' + textColor + ';">' + capText.title + '</span>' +
        '<span class="et-caption-num" style="font-size:0.62rem;color:' + muted + ';font-family:ui-monospace,monospace;">#' + (idx + 1) + '</span>' +
        '</div>' +
        '<div class="et-caption-text" style="font-size:0.75rem;color:' + muted + ';line-height:1.5;">' + capText.body + '</div>';
    }
  };

  ExperimentTrackingWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._stop();
    } else {
      this._play();
    }
  };

  ExperimentTrackingWidget.prototype._play = function () {
    var self = this;
    if (this._playing) return;
    if (this._stage >= this._stages.length - 1) {
      this._stage = -1;
    }
    this._playing = true;
    if (this._playBtn) {
      this._playBtn.textContent = 'Pause';
    }

    if (this._trainingTimer) {
      clearInterval(this._trainingTimer);
      this._trainingTimer = null;
    }

    var interval = this._reducedMotion ? 500 : 1200;

    this._timer = setInterval(function () {
      if (self._trainingTimer !== null) return;

      var next = self._stage + 1;
      if (next >= self._stages.length) {
        self._stop();
        return;
      }
      self._activate(next);
    }, interval);
  };

  ExperimentTrackingWidget.prototype._stop = function () {
    this._playing = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._timerAutoAdvance) {
      clearTimeout(this._timerAutoAdvance);
      this._timerAutoAdvance = null;
    }
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  ExperimentTrackingWidget.prototype._step = function () {
    if (this._playing) this._stop();

    if (this._trainingTimer) {
      clearInterval(this._trainingTimer);
      this._trainingTimer = null;
      this._trainPt = this._lossSeries.length;
      this._drawTrainingFrame();
      this._activate(2);
      return;
    }

    var next = this._stage + 1;
    if (next >= this._stages.length) return;
    this._activate(next);
  };

  ExperimentTrackingWidget.prototype._reset = function () {
    if (this._playing) this._stop();

    if (this._trainingTimer) {
      clearInterval(this._trainingTimer);
      this._trainingTimer = null;
    }
    if (this._timerAutoAdvance) {
      clearTimeout(this._timerAutoAdvance);
      this._timerAutoAdvance = null;
    }

    this._stage = -1;
    this._trainPt = 0;

    for (var i = 0; i < this._stageEls.length; i++) {
      this._stageEls[i].classList.remove('active');
    }

    var muted = this._token('--text-muted', '#8e8e93');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var space3 = this._token('--space-3', '0.75rem');
    this._contentEl.innerHTML =
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a phase or press Play/Step to explore the experiment run lifecycle</div>';
    this._captionEl.innerHTML = '';
  };

  ExperimentTrackingWidget.prototype._toggleDegraded = function () {
    this._degraded = !this._degraded;

    if (this._degradeBtn) {
      if (this._degraded) {
        this._degradeBtn.classList.add('active');
        this._degradeBtn.setAttribute('data-degraded', 'true');
        this._degradeBtn.textContent = 'MLflow offline \u2713';
      } else {
        this._degradeBtn.classList.remove('active');
        this._degradeBtn.setAttribute('data-degraded', 'false');
        this._degradeBtn.textContent = 'MLflow offline';
      }
    }

    if (this._stage >= 0 && this._stage < this._stages.length) {
      var stage = this._stages[this._stage];
      if (stage.id === 'start' || stage.id === 'final' || stage.id === 'artifacts' || stage.id === 'registry') {
        this._renderContent(this._stage);
        this._renderCaption(this._stage);
      }
    }
  };

  window.ExperimentTrackingWidget = ExperimentTrackingWidget;
})();
