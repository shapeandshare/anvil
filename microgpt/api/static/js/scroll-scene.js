(function() {
  'use strict';

  function ScrollScene(options) {
    this.container = options.container;
    this.pinnedVisual = options.pinnedVisual;
    this._threshold = options.threshold || 0.5;
    this._rootMargin = options.rootMargin || '0px';
    this._steps = {};
    this._activeKey = options.initialStep || null;
    this._observer = null;
    this.onstepchange = null;
    this._init();
  }

  ScrollScene.prototype._init = function() {
    var self = this;
    this._observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var key = entry.target.getAttribute('data-step-key');
          if (key && key !== self._activeKey) {
            self._activeKey = key;
            if (typeof self.onstepchange === 'function') {
              self.onstepchange(key);
            }
          }
        }
      });
    }, { threshold: this._threshold, rootMargin: this._rootMargin });
  };

  Object.defineProperty(ScrollScene.prototype, 'activeStep', {
    get: function() { return this._activeKey; }
  });

  ScrollScene.prototype.observeStep = function(key, element) {
    this._steps[key] = element;
    if (this._observer) {
      this._observer.observe(element);
    }
    if (!this._activeKey) {
      this._activeKey = key;
    }
  };

  ScrollScene.prototype.unobserveStep = function(key) {
    var el = this._steps[key];
    if (el && this._observer) {
      this._observer.unobserve(el);
    }
    delete this._steps[key];
  };

  ScrollScene.prototype.destroy = function() {
    if (this._observer) {
      this._observer.disconnect();
      this._observer = null;
    }
    this._steps = {};
  };

  window.ScrollScene = ScrollScene;
})();