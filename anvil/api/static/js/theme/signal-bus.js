(function () {
  'use strict';

  var EVENTS = ['metrics', 'divergence', 'milestone', 'complete'];

  function createSignalBus() {
    var handlers = {};
    var last = {};
    var boundSession = null;

    function on(eventName, cb) {
      if (!handlers[eventName]) handlers[eventName] = [];
      handlers[eventName].push(cb);
      return function off() {
        var arr = handlers[eventName];
        if (!arr) return;
        var i = arr.indexOf(cb);
        if (i !== -1) arr.splice(i, 1);
      };
    }

    function emit(eventName, payload) {
      last[eventName] = payload;
      var arr = handlers[eventName];
      if (!arr) return;
      arr.slice().forEach(function (cb) {
        try { cb(payload); } catch (e) { console.warn('[theme] signal handler failed', eventName, e); }
      });
    }

    function latest(eventName) {
      return Object.prototype.hasOwnProperty.call(last, eventName) ? last[eventName] : null;
    }

    function attach(session) {
      if (!session) return;
      boundSession = session;
      session.onmetrics = function (m) { emit('metrics', m); };
      session.ondivergence = function (d) { emit('divergence', d); };
      session.onmilestone = function (c) { emit('milestone', c); };
      var priorComplete = session.oncomplete;
      session.oncomplete = function (c) {
        emit('complete', c);
        if (typeof priorComplete === 'function') priorComplete(c);
      };
    }

    function session() { return boundSession; }

    return {
      EVENTS: EVENTS.slice(),
      on: on,
      emit: emit,
      latest: latest,
      attach: attach,
      session: session,
    };
  }

  window.SignalBus = { create: createSignalBus };
})();
