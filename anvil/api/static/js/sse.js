// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function() {
  'use strict';

  function SSESession(runId, opts) {
    this.runId = runId;
    this._state = 'idle';
    this._es = null;
    this._retryCount = 0;
    this._maxRetries = 5;
    this._backoff = [1000, 2000, 4000, 8000, 16000];
    this._destroyed = false;
    this._urlPrefix = (opts && opts.urlPrefix) || '/v1/training/stream';

    this.onstatechange = null;
    this.onmetrics = null;
    this.oncomplete = null;
    this.onerror = null;
    this.onsubmitted = null;
    this.onstatus = null;
  }

  SSESession.prototype._setState = function(s) {
    this._state = s;
    if (typeof this.onstatechange === 'function') {
      this.onstatechange(s);
    }
  };

  SSESession.prototype._getUrl = function() {
    return this._urlPrefix + '/' + this.runId;
  };

  SSESession.prototype._handleOpen = function() {
    this._retryCount = 0;
    this._setState('streaming');
  };

  SSESession.prototype._handleMetrics = function(e) {
    try {
      var d = JSON.parse(e.data);
      if (typeof this.onmetrics === 'function') this.onmetrics(d);
    } catch(_) {}
  };

  SSESession.prototype._handleComplete = function(e) {
    this._destroyed = true;
    try {
      var d = JSON.parse(e.data);
      if (typeof this.oncomplete === 'function') this.oncomplete(d);
    } catch(_) {}
    this._setState('done');
    if (this._es) this._es.close();
  };

  SSESession.prototype._handleSubmitted = function(e) {
    try {
      var d = JSON.parse(e.data);
      if (typeof this.onsubmitted === 'function') this.onsubmitted(d);
    } catch(_) {}
  };

  SSESession.prototype._handleStatus = function(e) {
    try {
      var d = JSON.parse(e.data);
      if (typeof this.onstatus === 'function') this.onstatus(d);
    } catch(_) {}
  };

  SSESession.prototype._handleMilestone = function(e) {
    try {
      var d = JSON.parse(e.data);
      if (typeof this.onmilestone === 'function') this.onmilestone(d);
    } catch(_) {}
  };

  SSESession.prototype._handleDivergence = function(e) {
    this._destroyed = true;
    try {
      var d = JSON.parse(e.data);
      if (typeof this.ondivergence === 'function') this.ondivergence(d);
    } catch(_) {}
    this._setState('done');
    if (this._es) this._es.close();
  };

  SSESession.prototype._handleError = function(e) {
    if (this._destroyed) return;

    // SSE error event from backend (event: error with data) — clean terminal
    if (e && e.data) {
      this._destroyed = true;
      if (this._es) {
        this._es.close();
        this._es = null;
      }
      this._setState('errored');
      try {
        var d = JSON.parse(e.data);
        if (typeof this.onerror === 'function') this.onerror(d);
      } catch(_) {
        if (typeof this.onerror === 'function') this.onerror({ message: 'Training ended with an error' });
      }
      return;
    }

    // Transport-level error — retry with backoff
    if (this._retryCount < this._maxRetries) {
      this._setState('reconnecting');
      var delay = this._backoff[this._retryCount];
      this._retryCount++;
      var self = this;
      setTimeout(function() {
        if (self._destroyed) return;
        self._connect();
      }, delay);
    } else {
      this._setState('errored');
      if (typeof this.onerror === 'function') {
        this.onerror({ message: 'Connection lost after ' + this._maxRetries + ' retries' });
      }
    }
  };

  SSESession.prototype._connect = function() {
    if (this._destroyed) return;
    if (this._es) this._es.close();
    this._es = new EventSource(this._getUrl());
    this._setState('connecting');
    var self = this;
    this._es.addEventListener('open', function() { self._handleOpen(); });
    this._es.addEventListener('metrics', function(e) { self._handleMetrics(e); });
    this._es.addEventListener('complete', function(e) { self._handleComplete(e); });
    this._es.addEventListener('error', function(e) { self._handleError(e); });
    this._es.addEventListener('submitted', function(e) { self._handleSubmitted(e); });
    this._es.addEventListener('status', function(e) { self._handleStatus(e); });
    this._es.addEventListener('milestone', function(e) { self._handleMilestone(e); });
    this._es.addEventListener('divergence', function(e) { self._handleDivergence(e); });
  };

  SSESession.prototype.start = function() {
    if (this._state !== 'idle' && this._state !== 'errored') return;
    this._retryCount = 0;
    this._connect();
  };

  SSESession.prototype.stop = function() {
    if (this._state !== 'streaming' && this._state !== 'connecting') return;
    if (this._es) {
      this._es.close();
      this._es = null;
    }
    this._setState('done');
  };

  SSESession.prototype.retry = function() {
    if (this._state !== 'errored') return;
    this._retryCount = 0;
    this._connect();
  };

  SSESession.prototype.destroy = function() {
    this._destroyed = true;
    if (this._es) {
      this._es.close();
      this._es = null;
    }
  };

  Object.defineProperty(SSESession.prototype, 'state', {
    get: function() { return this._state; }
  });

  window.SSESession = SSESession;
})();