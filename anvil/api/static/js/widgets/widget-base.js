// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

/**
 * Shared helpers for anvil's animated concept widgets.
 *
 * Provides token resolution, reduced-motion detection, and timer
 * management used by all widgets.  Reduces boilerplate duplication
 * across independent widget files.
 */
(function () {
  'use strict';

  window.AnvilBase = {
    /**
     * Resolve a CSS custom property value, falling back to a default.
     *
     * @param {string} name  CSS var name (e.g. "--accent").
     * @param {string} fallback  Colour/value to return if the var is
     *     not set.
     * @return {string}  The resolved CSS value or fallback.
     */
    token: function (name, fallback) {
      var style = getComputedStyle(document.documentElement);
      return style.getPropertyValue(name).trim() || fallback;
    },

    /**
     * Initialise ``prefers-reduced-motion`` detection on a widget
     * instance and keep its ``_reducedMotion`` property in sync.
     *
     * @param {object} self  Widget instance with ``_reducedMotion``.
     */
    initReducedMotion: function (self) {
      var mm = window.matchMedia('(prefers-reduced-motion: reduce)');
      self._reducedMotion = mm.matches;
      mm.addEventListener('change', function (e) {
        self._reducedMotion = e.matches;
      });
    },

    /**
     * Safely clear any running interval timers on a widget instance.
     *
     * @param {object} self  Widget instance with ``_timer``.
     */
    stop: function (self) {
      if (self._timer) {
        clearInterval(self._timer);
        self._timer = null;
      }
    },
  };
})();