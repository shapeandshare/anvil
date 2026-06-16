(function () {
  'use strict';

  function DataFlowWidget(container) {
    if (!container) return;
    this.container = container;
    this._stage = -1;
    this._playing = false;
    this._timer = null;
    this._reducedMotion = false;

    this._stages = [
      { id: 'browser', label: 'Browser', sub: 'POST /v1/training/start {config}', color: '--accent', zone: 'async' },
      { id: 'fastapi', label: 'FastAPI Route', sub: 'creates asyncio task, returns run_id', color: '--accent-cyan', zone: 'async' },
      { id: 'training-service', label: 'TrainingService', sub: 'reserves run_id, loads docs, resolves device', color: '--accent-cyan', zone: 'async' },
      { id: 'thread-pool', label: 'Thread Pool', sub: 'run_in_executor (sync bridge)', color: '--accent-orange', zone: 'sync' },
      { id: 'core-engine', label: 'Core Engine', sub: 'train() CPU or train_torch() GPU', color: '--accent-orange', zone: 'sync' },
      { id: 'sse-stream', label: 'SSE Stream', sub: 'metrics, loss, ETA events', color: '--accent-green', zone: 'return' },
      { id: 'persistence', label: 'on_complete', sub: 'MLflow + SQLite DB + Disk (safetensors)', color: '--accent-purple', zone: 'persist' },
    ];

    this._captions = {
      'browser': {
        title: 'Browser',
        body: 'The training dashboard sends a POST request to /v1/training/start with the hyperparameter configuration (n_embd, n_layer, n_head, num_steps, learning_rate, etc.). The request body is a JSON config object.',
      },
      'fastapi': {
        title: 'FastAPI Route',
        body: 'The route handler calls TrainingService.start_training(), which creates an asyncio.create_task() for the training coroutine and returns the run_id immediately. The browser receives the run_id and opens an SSE connection to /v1/training/stream/{run_id} to receive real-time progress.',
      },
      'training-service': {
        title: 'TrainingService',
        body: 'Reserves the run_id, creates an asyncio.Queue for SSE events and a stop_event for cancellation. Loads training documents from the configured source (dataset upload, corpus scan, or demo defaults). Resolves the compute device: CUDA > MPS > CPU.',
      },
      'thread-pool': {
        title: 'Thread Pool (run_in_executor)',
        body: 'The sync core engine runs in a thread pool via loop.run_in_executor(None, lambda: train(...)). This is the critical bridge between the async web layer and the synchronous CPU-bound training loop. The event loop remains free to handle SSE streaming and other requests during training.',
      },
      'core-engine': {
        title: 'Core Engine',
        body: 'CPU path: train() from anvil/core/engine.py — pure Python with custom Value autograd. GPU path: train_torch() from anvil/core/torch_engine.py — PyTorch tensors on CUDA or MPS. Both run the same Llama architecture: RoPE, SwiGLU, RMSNorm, Adam optimizer. The progress_callback fires every step to push metrics back to the SSE stream.',
      },
      'sse-stream': {
        title: 'SSE Stream (Return)',
        body: 'During training, the progress_callback (running in the thread pool thread) uses asyncio.run_coroutine_threadsafe() to push {step, loss, steps/sec, ETA} events into the asyncio Queue. The SSE endpoint /v1/training/stream/{run_id} reads from the Queue and sends Server-Sent Events to the browser. Events: metrics (per-step), optimizer_state (snapshots), complete (final), error.',
      },
      'persistence': {
        title: 'on_complete Persistence',
        body: 'After training finishes: (1) MLflow — log_params() with hyperparameters, log_metrics() with final loss and timing, upload model.json + samples.txt, register_model() in Model Registry. (2) SQLite DB — INSERT Experiment record with run metadata and MLflow references. (3) Disk — save experiment_{id}.json, plus safetensors export: model.safetensors, config.json, tokenizer.json.',
      },
    };

    this._render();
  }

  DataFlowWidget.prototype._token = function (name, fallback) {
    var style = getComputedStyle(document.documentElement);
    return style.getPropertyValue(name).trim() || fallback;
  };

  DataFlowWidget.prototype._render = function () {
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
    var space4 = this._token('--space-4', '1rem');

    /* Build stage HTML */
    var stageHtml = '';
    for (var i = 0; i < this._stages.length; i++) {
      var s = this._stages[i];
      var col = this._resolveColor(s.color, accent);
      var zoneClass = 'dflow-zone-' + s.zone;
      stageHtml +=
        '<div class="dflow-stage ' + zoneClass + '" data-flow-stage="' + s.id + '" style="background:' + surface + ';border:1px solid ' + col + ';border-radius:' + radiusSm + ';padding:' + space2 + ' ' + space3 + ';text-align:center;min-width:100px;cursor:pointer;transition:box-shadow 0.2s,transform 0.2s;position:relative;" tabindex="0" role="button" aria-label="Training stage: ' + s.label + '">' +
        '<div class="dflow-stage-indicator" style="position:absolute;top:-4px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:' + col + ';opacity:0;transition:opacity 0.3s,box-shadow 0.3s;box-shadow:0 0 6px ' + col + ';"></div>' +
        '<div class="dflow-stage-label" style="font-size:0.82rem;font-weight:600;color:' + text + ';">' + s.label + '</div>' +
        '<div class="dflow-stage-sub" style="font-size:0.65rem;color:' + muted + ';margin-top:2px;font-family:' + mono + ';">' + s.sub + '</div>' +
        '</div>';
      if (i < this._stages.length - 1) {
        stageHtml += '<div class="dflow-arrow" style="color:' + muted + ';font-size:0.65rem;text-align:center;padding:2px 0;opacity:0.5;">&#9654;</div>';
      }
    }

    /* Build zone labels (async / sync / return / persist) */
    var zoneHtml =
      '<div class="dflow-zones" style="display:flex;flex-direction:column;gap:1px;width:100%;">' +
      '<div class="dflow-zone-label" style="font-size:0.62rem;color:' + muted + ';text-align:center;padding:2px ' + space2 + ';background:' + surface2 + ';border-radius:' + radiusSm + ' ' + radiusSm + ' 0 0;font-family:' + mono + ';">asyncio event loop</div>' +
      '<div class="dflow-zone-label" style="font-size:0.62rem;color:' + muted + ';text-align:center;padding:2px ' + space2 + ';background:' + surface2 + ';font-family:' + mono + ';">thread pool (sync)</div>' +
      '<div class="dflow-zone-label" style="font-size:0.62rem;color:' + muted + ';text-align:center;padding:2px ' + space2 + ';background:' + surface2 + ';font-family:' + mono + ';">SSE return</div>' +
      '<div class="dflow-zone-label" style="font-size:0.62rem;color:' + muted + ';text-align:center;padding:2px ' + space2 + ';background:' + surface2 + ';border-radius:0 0 ' + radiusSm + ' ' + radiusSm + ';font-family:' + mono + ';">persistence</div>' +
      '</div>';

    /* Controls */
    var controlsHtml =
      '<div class="dflow-controls" style="display:flex;gap:' + space2 + ';justify-content:center;margin-bottom:' + space3 + ';">' +
      '<button id="dflow-play-btn" class="dflow-btn" style="background:' + accent + ';color:#fff;border:none;border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Play animation">Play</button>' +
      '<button id="dflow-step-btn" class="dflow-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Step to next stage">Step</button>' +
      '<button id="dflow-reset-btn" class="dflow-btn" style="background:' + surface2 + ';color:' + text + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';padding:6px 16px;font-size:0.8rem;font-weight:500;cursor:pointer;font-family:' + body + ';transition:filter 0.15s;" aria-label="Reset animation">Reset</button>' +
      '</div>';

    var css = '<style>' +
      '.dflow-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.dflow-pipeline{display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';}' +
      '.dflow-stage:hover{box-shadow:0 0 0 2px var(--stage-color,' + accent + ')!important;}' +
      '.dflow-stage.active .dflow-stage-indicator{opacity:1!important;}' +
      '.dflow-stage.active{border-color:var(--stage-color,' + accent + ')!important;box-shadow:0 0 0 2px var(--stage-color,' + accent + '),0 0 12px color-mix(in srgb,var(--stage-color,' + accent + ') 25%,transparent)!important;}' +
      '.dflow-caption{min-height:60px;}' +
      '.dflow-btn:hover{filter:brightness(1.15);}' +
      '.dflow-btn:active{filter:brightness(0.9);}' +
      '@media(max-width:600px){.dflow-pipeline{flex-direction:column;}.dflow-arrow{transform:rotate(90deg);}}' +
      '</style>';

    this.container.innerHTML =
      '<div class="dflow-widget">' +
      css +

      '<div class="widget-label" style="display:block;font-size:0.75rem;color:' + muted + ';margin-bottom:' + space2 + ';">Training request data flow pipeline — click a stage for details:</div>' +

      controlsHtml +

      /* Pipeline */
      '<div class="dflow-pipeline" style="display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 4px;padding:' + space2 + ';border-radius:' + radius + ';" id="dflow-pipeline">' +
      stageHtml +
      '</div>' +

      /* Async/sync zone labels */
      '<div style="margin-top:' + space2 + ';">' + zoneHtml + '</div>' +

      /* Caption area */
      '<div class="dflow-caption" style="min-height:60px;margin-top:' + space3 + ';padding:' + space3 + ';background:' + surface2 + ';border-radius:' + radiusSm + ';" id="dflow-caption">' +
      '<div style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click a stage above or press Play/Step to explore</div>' +
      '</div>' +

      '</div>';

    this._captionEl = this.container.querySelector('#dflow-caption');
    this._pipelineEl = this.container.querySelector('#dflow-pipeline');
    this._stageEls = this.container.querySelectorAll('[data-flow-stage]');
    this._playBtn = this.container.querySelector('#dflow-play-btn');
    this._stepBtn = this.container.querySelector('#dflow-step-btn');
    this._resetBtn = this.container.querySelector('#dflow-reset-btn');

    /* Click delegation on pipeline */
    this.container.addEventListener('click', function (e) {
      var stage = e.target.closest('[data-flow-stage]');
      if (stage) {
        var id = stage.getAttribute('data-flow-stage');
        var idx = self._findStageIndex(id);
        if (idx >= 0) {
          self._activate(idx);
        }
      }
    });

    /* Keyboard handling */
    this.container.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        var stage = e.target.closest('[data-flow-stage]');
        if (stage) {
          e.preventDefault();
          var id = stage.getAttribute('data-flow-stage');
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

  DataFlowWidget.prototype._resolveColor = function (varName, fallback) {
    var c = this._token(varName, fallback);
    return c || fallback;
  };

  DataFlowWidget.prototype._findStageIndex = function (id) {
    for (var i = 0; i < this._stages.length; i++) {
      if (this._stages[i].id === id) return i;
    }
    return -1;
  };

  DataFlowWidget.prototype._activate = function (idx) {
    var self = this;
    if (idx < 0 || idx >= this._stages.length) return;
    this._stage = idx;

    for (var i = 0; i < this._stageEls.length; i++) {
      var el = this._stageEls[i];
      var stageId = el.getAttribute('data-flow-stage');
      var sIdx = this._findStageIndex(stageId);
      if (sIdx <= idx) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
      if (sIdx >= 0) {
        var stageCol = this._resolveColor(this._stages[sIdx].color, '#007aff');
        el.style.setProperty('--stage-color', stageCol);
      }
    }

    var stage = this._stages[idx];
    var capText = this._captions[stage.id];
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var col = this._resolveColor(stage.color, '#007aff');

    if (capText) {
      this._captionEl.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
        '<span style="width:8px;height:8px;border-radius:50%;background:' + col + ';flex-shrink:0;"></span>' +
        '<span style="font-size:0.82rem;font-weight:600;color:' + text + ';">' + capText.title + '</span>' +
        '<span style="font-size:0.62rem;color:' + muted + ';font-family:ui-monospace,monospace;">#' + (idx + 1) + '</span>' +
        '</div>' +
        '<div style="font-size:0.75rem;color:' + muted + ';line-height:1.5;">' + capText.body + '</div>';
    }
  };

  DataFlowWidget.prototype._togglePlay = function () {
    if (this._playing) {
      this._stop();
    } else {
      this._play();
    }
  };

  DataFlowWidget.prototype._play = function () {
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

  DataFlowWidget.prototype._stop = function () {
    var self = this;
    this._playing = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._playBtn) {
      this._playBtn.textContent = 'Play';
    }
  };

  DataFlowWidget.prototype._step = function () {
    if (this._playing) this._stop();
    var next = this._stage + 1;
    if (next >= this._stages.length) {
      return;
    }
    this._activate(next);
  };

  DataFlowWidget.prototype._reset = function () {
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

  window.DataFlowWidget = DataFlowWidget;
})();