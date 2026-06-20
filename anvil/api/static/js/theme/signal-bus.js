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
      chain(session, 'onmetrics', 'metrics');
      chain(session, 'ondivergence', 'divergence');
      chain(session, 'onmilestone', 'milestone');
      chain(session, 'oncomplete', 'complete');
    }

    function chain(session, prop, eventName) {
      var prior = session[prop];
      session[prop] = function (payload) {
        emit(eventName, payload);
        if (typeof prior === 'function') prior(payload);
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
