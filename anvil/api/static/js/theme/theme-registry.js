// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  var DEFAULT_ID = 'default';
  var order = [];
  var byId = {};

  function register(theme) {
    if (!theme || typeof theme.id !== 'string' || !theme.id) {
      console.warn('[theme] register() ignored: missing id', theme);
      return;
    }
    if (Object.prototype.hasOwnProperty.call(byId, theme.id)) {
      console.warn('[theme] duplicate theme id re-registered:', theme.id);
    } else {
      order.push(theme.id);
    }
    byId[theme.id] = {
      id: theme.id,
      displayName: theme.displayName || theme.id,
      previewHint: theme.previewHint || '',
      modes: Array.isArray(theme.modes) && theme.modes.length ? theme.modes : ['dark'],
      cssLayer: theme.cssLayer || null,
      mapping: typeof theme.mapping === 'function' ? theme.mapping : null,
      particleConfig: theme.particleConfig || { type: 'css', params: {} },
    };
  }

  function get(id) {
    return Object.prototype.hasOwnProperty.call(byId, id) ? byId[id] : undefined;
  }

  function has(id) {
    return Object.prototype.hasOwnProperty.call(byId, id);
  }

  function list() {
    return order.map(function (id) { return byId[id]; });
  }

  function isSingleMode(theme) {
    return !!theme && theme.modes.length === 1 && theme.modes[0] === 'single';
  }

  window.ThemeRegistry = {
    defaultId: DEFAULT_ID,
    register: register,
    get: get,
    has: has,
    list: list,
    isSingleMode: isSingleMode,
  };
})();
