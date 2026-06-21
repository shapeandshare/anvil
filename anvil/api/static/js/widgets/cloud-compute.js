// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  function CloudComputeWidget(container) {
    if (!container) return;
    this.container = container;
    this._stage = -1;
    this._playing = false;
    this._timer = null;
    this._reducedMotion = false;

    this._stages = [
      {
        id: 'submit',
        label: 'Submit Job',
        sub: 'POST /v1/training/start {backend: "modal"}',
        color: '--accent',
        zone: 'async',
      },
      {
        id: 'acknowledged',
        label: 'Job Acknowledged',
        sub: 'SSE event: submitted {remote_job_id}',
        color: '--accent-cyan',
        zone: 'async',
      },
      {
        id: 'polling',
        label: 'Remote Training',
        sub: 'SSE event: status RUNNING / COMPLETED',
        color: '--accent-orange',
        zone: 'sync',
      },
      {
        id: 'artifacts',
        label: 'Artifact Sync',
        sub: 'Remote logs → MLflow → local DB',
        color: '--accent-green',
        zone: 'return',
      },
      {
        id: 'complete',
        label: 'Training Complete',
        sub: 'Model registered in MLflow Model Registry',
        color: '--accent-purple',
        zone: 'persist',
      },
    ];

    this._captions = {
      submit: {
        title: 'Submit Job to Cloud',
        body: 'The training dashboard sends a POST to /v1/training/start with compute_backend="modal". The route resolves the modal backend, creates a remote job via the Modal SDK, and returns immediately with a run_id and a remote_job_id. An SSE stream opens for real-time status updates.',
      },
      acknowledged: {
        title: 'Job Acknowledged',
        body: 'Modal accepts the job and returns a remote_job_id. The SSE stream emits a "submitted" event with the remote job ID and initial status. The browser shows the job as "submitted — waiting for execution". No local training thread is created.',
      },
      polling: {
        title: 'Remote Training Running',
        body: 'While Modal runs the training, the server polls for status transitions. Each poll emits a "status" SSE event to the browser: RUNNING (training started), with step/loss metrics when available. The loss chart updates in real time just like local training, but the computation happens in the cloud.',
      },
      artifacts: {
        title: 'Artifact Sync',
        body: 'When Modal completes training, the remote job logs metrics and artifacts (model.safetensors, config.json, samples.txt) directly to the shared MLflow server. The anvil server picks up the completion event and records metadata in the local SQLite DB (experiment record, model registry entry). No local model download is needed for MLflow tracking.',
      },
      complete: {
        title: 'Training Complete',
        body: 'The final "complete" SSE event fires. The model is registered in the MLflow Model Registry with a runs:/ URI pointing to the remote artifacts. On the training dashboard, the loss curve, metrics, and output panel all show the final results. You can now run inference or export the model.',
      },
    };

    this._render();
  }

  CloudComputeWidget.prototype._token = function (name, fallback) {
    var style = getComputedStyle(document.documentElement);
    return style.getPropertyValue(name).trim() || fallback;
  };

  CloudComputeWidget.prototype._render = function () {
    var self = this;
    var mm = window.matchMedia('(prefers-reduced-motion: reduce)');
    this._reducedMotion = mm.matches;
    mm.addEventListener('change', function (e) {
      self._reducedMotion = e.matches;
    });

    var accent = this._token('--accent', '#007aff');
    var cyan = this._token('--accent-cyan', '#32d74b');
    var orange = this._token('--accent-orange', '#ff9500');
    var green = this._token('--accent-green', '#34c759');
    var purple = this._token('--accent-purple', '#af52de');
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

    /* Build stage HTML */
    var stageHtml = '';
    for (var i = 0; i < this._stages.length; i++) {
      var s = this._stages[i];
      var col = this._resolveColor(s.color, accent);
      stageHtml +=
        '<div class="ccloud-stage" data-ccloud-stage="' + s.id + '" style="background:' + surface + ';border:1px solid ' + col + ';border-radius:' + radiusSm + ';padding:' + space2 + ' ' + space3 + ';text-align:center;min-width:90px;cursor:pointer;transition:box-shadow 0.2s,transform 0.2s;position:relative;" tabindex="0" role="button" aria-label="Cloud stage: ' + s.label + '">' +
        '<div class="ccloud-stage-indicator" style="position:absolute;top:-4px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:' + col + ';opacity:0;transition:opacity 0.3s,box-shadow 0.3s;box-shadow:0 0 6px ' + col + ';"></div>' +
        '<div class="ccloud-stage-label" style="font-size:0.82rem;font-weight:600;color:' + text + ';">' + s.label + '</div>' +
        '<div class="ccloud-stage-sub" style="font-size:0.65rem;color:' + muted + ';margin-top:2px;font-family:' + mono + ';">' + s.sub + '</div>' +
        '</div>';
      if (i < this._stages.length - 1) {
        stageHtml += '<div class="ccloud-arrow" style="color:' + muted + ';font-size:0.65rem;text-align:center;padding:2px 0;opacity:0.5;">&#9654;</div>';
      }
    }

    /* Controls */
    var controlsHtml =
      '<div class="ccloud-controls" style="display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space3 + ';">' +
      '<button id="ccloud-play-btn" class="ccloud-btn" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Play animation">Play</button>' +
      '<button id="ccloud-step-btn" class="ccloud-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Step to next stage">Step</button>' +
      '<button id="ccloud-reset-btn" class="ccloud-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Reset animation">Reset</button>' +
      '</div>';

    var css = '<style>' +
      '.ccloud-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.ccloud-pipeline{display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';}' +
      '.ccloud-stage:hover{box-shadow:0 0 0 2px var(--ccloud-color,' + accent + ')!important;}' +
      '.ccloud-stage.active .ccloud-stage-indicator{opacity:1!important;}' +
      '.ccloud-stage.active{border-color:var(--ccloud-color,' + accent + ')!important;box-shadow:0 0 0 2px var(--ccloud-color,' + accent + '),0 0 12px color-mix(in srgb,var(--ccloud-color,' + accent + ') 25%,transparent)!important;}' +
      '.ccloud-caption{min-height:60px;}' +
      '.ccloud-btn:hover{filter:brightness(1.15);}' +
      '.ccloud-btn:active{filter:brightness(0.9);}' +
      '@media(max-width:600px){.ccloud-pipeline{flex-direction:column;}.ccloud-arrow{transform:rotate(90deg);}}' +
      '</style>';

    this.container.innerHTML =
      '<div class="ccloud-widget">' +
      css +
      '<div class="widget-label" style="display:block;font-size:0.75rem;color:' + muted + ';margin-bottom:' + space2 + ';">Cloud compute submit → poll → artifact flow — click a stage for details:</div>' +
      controlsHtml +
      '<div class="ccloud-pipeline" style="display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';" id="ccloud-pipeline">' +
      stageHtml +
      '</div>' +
      '<div class="ccloud-caption" style="min-height:60px;margin-top:' + space3 + ';padding:' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';" id="ccloud-caption">' +
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a stage above or press Play/Step to explore</div>' +
      '</div>' +
      '</div>';

    this._captionEl = this.container.querySelector('#ccloud-caption');
    this._pipelineEl = this.container.querySelector('#ccloud-pipeline');
    this._stageEls = this.container.querySelectorAll('[data-ccloud-stage]');
    this._playBtn = this.container.querySelector('#ccloud-play-btn');
    this._stepBtn = this.container.querySelector('#ccloud-step-btn');
    this._resetBtn = this.container.querySelector('#ccloud-reset-btn');

    /* Click delegation */
    this.container.addEventListener('click', function (e) {
      var stage = e.target.closest('[data-ccloud-stage]');
      if (stage) {
        var id = stage.getAttribute('data-ccloud-stage');
        var idx = self._findStageIndex(id);
        if (idx >= 0) {
          self._activate(idx);
        }
      }
    });

    /* Keyboard */
    this.container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        var stage = e.target.closest('[data-ccloud-stage]');
        if (stage) {
          e.preventDefault();
          var id = stage.getAttribute('data-ccloud-stage');
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

  CloudComputeWidget.prototype._resolveColor = function (varName, fallback) {
    var c = this._token(varName, fallback);
    return c || fallback;
  };

  CloudComputeWidget.prototype._findStageIndex = function (id) {
    for (var i = 0; i < this._stages.length; i++) {
      if (this._stages[i].id === id) return i;
    }
    return -1;
  };

  CloudComputeWidget.prototype._activate = function (idx) {
    if (idx < 0 || idx >= this._stages.length) return;
    this._stage = idx;

    for (var i = 0; i < this._stageEls.length; i++) {
      var el = this._stageEls[i];
      var stageId = el.getAttribute('data-ccloud-stage');
      var sIdx = this._findStageIndex(stageId);
      if (sIdx <= idx) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
      if (sIdx >= 0) {
        var stageCol = this._resolveColor(this._stages[sIdx].color, '#007aff');
        el.style.setProperty('--ccloud-color', stageCol);
      }
    }

    var stage = this._stages[idx];
    var capText = this._captions[stage.id];
    var textColor = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var col = this._resolveColor(stage.color, '#007aff');

    if (capText) {
      this._captionEl.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
        '<span style="width:8px;height:8px;border-radius:50%;background:' + col + ';flex-shrink:0;"></span>' +
        '<span style="font-size:0.82rem;font-weight:600;color:' + textColor + ';">' + capText.title + '</span>' +
        '<span style="font-size:0.62rem;color:' + muted + ';font-family:ui-monospace,monospace;">#' + (idx + 1) + '</span>' +
        '</div>' +
        '<div style="font-size:0.75rem;color:' + muted + ';line-height:1.5;">' + capText.body + '</div>';
    }
  };

  CloudComputeWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._stop();
    } else {
      this._play();
    }
  };

  CloudComputeWidget.prototype._play = function () {
    var self = this;
    if (this._playing) return;
    if (this._stage >= this._stages.length - 1) {
      this._stage = -1;
    }
    this._playing = true;
    if (this._playBtn) {
      this._playBtn.textContent = 'Pause';
    }

    var interval = this._reducedMotion ? 400 : 800;

    this._timer = setInterval(function () {
      var next = self._stage + 1;
      if (next >= self._stages.length) {
        self._stop();
        return;
      }
      self._activate(next);
    }, interval);
  };

  CloudComputeWidget.prototype._stop = function () {
    this._playing = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  CloudComputeWidget.prototype._step = function () {
    if (this._playing) this._stop();
    var next = this._stage + 1;
    if (next >= this._stages.length) return;
    this._activate(next);
  };

  CloudComputeWidget.prototype._reset = function () {
    if (this._playing) this._stop();
    this._stage = -1;
    for (var i = 0; i < this._stageEls.length; i++) {
      this._stageEls[i].classList.remove('active');
    }
    var muted = this._token('--text-muted', '#8e8e93');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var space3 = this._token('--space-3', '0.75rem');
    this._captionEl.innerHTML =
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a stage above or press Play/Step to explore</div>';
  };

  window.CloudComputeWidget = CloudComputeWidget;
})();