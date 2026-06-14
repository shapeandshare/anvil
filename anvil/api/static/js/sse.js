(function() {
  'use strict';

  function SSESession(runId) {
    this.runId = runId;
    this._state = 'idle';
    this._es = null;
    this._retryCount = 0;
    this._maxRetries = 5;
    this._backoff = [1000, 2000, 4000, 8000, 16000];
    this._destroyed = false;

    this.onstatechange = null;
    this.onmetrics = null;
    this.oncomplete = null;
    this.onerror = null;
  }

  SSESession.prototype._setState = function(s) {
    this._state = s;
    if (typeof this.onstatechange === 'function') {
      this.onstatechange(s);
    }
  };

  SSESession.prototype._getUrl = function() {
    return '/v1/training/stream/' + this.runId;
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
    try {
      var d = JSON.parse(e.data);
      if (typeof this.oncomplete === 'function') this.oncomplete(d);
    } catch(_) {}
    this._setState('done');
    if (this._es) this._es.close();
  };

  SSESession.prototype._handleError = function(e) {
    if (this._destroyed) return;

    // SSE error event from backend (event: error with data) — clean terminal
    if (e && e.data) {
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