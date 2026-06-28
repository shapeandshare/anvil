// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

/**
 * DOM diff/patch utilities — targeted updates to avoid full innerHTML rebuilds.
 *
 * Every function compares old vs new before mutating. This prevents the
 * flicker, animation re-trigger, and focus-loss that comes from wiping and
 * recreating DOM nodes on every poll or action response.
 *
 * Use these in polling loops (ops page), action callbacks (create/delete),
 * and any place where a full ``.innerHTML = ...`` was the old pattern.
 */
(function () {
  'use strict';

  var dom = {};

  // ── Atomic Setters (no-op if unchanged) ──────────────

  /**
   * Set ``textContent`` only if different from the current value.
   *
   * @param {Element} el - Target element
   * @param {string} text - New text content
   */
  dom.setText = function (el, text) {
    if (el.textContent !== text) {
      el.textContent = text;
    }
  };

  /**
   * Set ``innerHTML`` only if the string actually differs.
   * Use sparingly — this should still be rarer than targeted cell updates.
   *
   * @param {Element} el - Target element
   * @param {string} html - New HTML content
   */
  dom.setHtml = function (el, html) {
    if (el.innerHTML !== html) {
      el.innerHTML = html;
    }
  };

  /**
   * Replace ``className`` only if different.
   *
   * @param {Element} el - Target element
   * @param {string} className - Full new class name string
   */
  dom.setClass = function (el, className) {
    if (el.className !== className) {
      el.className = className;
    }
  };

  /**
   * Add/remove a single CSS class on an element without affecting others.
   *
   * @param {Element} el - Target element
   * @param {string} cls - Class to toggle
   * @param {boolean} force - True to add, false to remove
   */
  dom.toggleClass = function (el, cls, force) {
    if (el.classList.contains(cls) !== !!force) {
      el.classList.toggle(cls, force);
    }
  };

  /**
   * Set an attribute only if the value changed.
   *
   * @param {Element} el - Target element
   * @param {string} name - Attribute name
   * @param {string|null|undefined} value - New value (remove attr if null/undefined)
   */
  dom.setAttr = function (el, name, value) {
    if (value === null || value === undefined) {
      if (el.hasAttribute(name)) el.removeAttribute(name);
      return;
    }
    var str = String(value);
    if (el.getAttribute(name) !== str) {
      el.setAttribute(name, str);
    }
  };

  /**
   * Set the ``disabled`` property on a form element only if changed.
   *
   * @param {Element} el - Target element
   * @param {boolean} disabled
   */
  dom.setDisabled = function (el, disabled) {
    if (el.disabled !== disabled) {
      el.disabled = disabled;
    }
  };

  /**
   * Toggle ``display`` between ``''`` and ``'none'``.
   *
   * @param {Element} el - Target element
   * @param {boolean} visible
   */
  dom.setVisible = function (el, visible) {
    var display = visible ? '' : 'none';
    if (el.style.display !== display) {
      el.style.display = display;
    }
  };

  /**
   * Update a badge element's text and colour class.
   *
   * Only ``badge-*`` colour classes are managed: the current ``badge-*``
   * class is swapped for ``colorClass`` while every other class (``badge``,
   * hooks, size/layout classes) is preserved.
   *
   * @param {Element} el - Badge element
   * @param {string} text - Display text
   * @param {string} colorClass - e.g. ``"badge-green"``, ``"badge-red"``
   */
  dom.updateBadge = function (el, text, colorClass) {
    dom.setText(el, text);
    var list = el.classList;
    var stale = [];
    var i, c;
    for (i = 0; i < list.length; i++) {
      c = list[i];
      if (c !== 'badge' && c.indexOf('badge-') === 0 && c !== colorClass) {
        stale.push(c);
      }
    }
    for (i = 0; i < stale.length; i++) {
      list.remove(stale[i]);
    }
    if (colorClass && !list.contains(colorClass)) {
      list.add(colorClass);
    }
  };

  // ── List / Table Sync ────────────────────────────────

  /**
   * In-place keyed reconciliation of a parent's managed child elements.
   *
   * Only elements carrying a ``data-key`` attribute are managed: they are
   * created, updated, reordered (via ``insertBefore``), and removed to match
   * ``items`` by key. Children WITHOUT ``data-key`` are left untouched in
   * place — so placeholders, detail rows, and separators survive.
   *
   * Reused elements are never detached, so focus, caret position, and
   * directly-bound event listeners on managed children are preserved.
   *
   * @param {Element} parent - The element whose children are managed
   * @param {Array} items - Data array
   * @param {Function} keyFn - ``keyFn(item, index) → string|number``
   * @param {Function} createEl - ``createEl(item, index) → Element``
   * @param {Function} updateEl - ``updateEl(el, item, index)``
   * @returns {number} Count of elements created or removed
   */
  function reconcile(parent, items, keyFn, createEl, updateEl) {
    if (!parent) return 0;

    var existing = new Map();
    var child = parent.firstElementChild;
    var key;
    while (child) {
      if (child.hasAttribute('data-key')) {
        existing.set(child.getAttribute('data-key'), child);
      }
      child = child.nextElementSibling;
    }

    var changes = 0;
    var anchor = parent.firstElementChild;
    var i, item, el;

    for (i = 0; i < items.length; i++) {
      item = items[i];
      var rawKey = keyFn(item, i);
      if (rawKey === null || rawKey === undefined || rawKey === '') {
        throw new Error('dom.reconcile: keyFn returned an empty key at index ' + i);
      }
      key = String(rawKey);

      el = existing.get(key);
      if (el) {
        existing.delete(key);
        updateEl(el, item, i);
      } else {
        el = createEl(item, i);
        el.setAttribute('data-key', key);
        changes++;
      }

      if (anchor === el) {
        anchor = el.nextElementSibling;
      } else {
        parent.insertBefore(el, anchor);
      }
    }

    existing.forEach(function (stale) {
      stale.remove();
      changes++;
    });

    return changes;
  }

  /**
   * Sync a ``<tbody>`` with ``items`` using in-place keyed reconciliation.
   * ``createRow(item, index)`` returns a ``<tr>``; ``updateRow(tr, item, index)``
   * patches its cells. Non-keyed rows (e.g. detail rows) are preserved.
   *
   * @param {HTMLTableSectionElement} tbody
   * @param {Array} items
   * @param {Function} keyFn - ``keyFn(item, index) → string|number``
   * @param {Function} createRow - ``createRow(item, index) → HTMLTableRowElement``
   * @param {Function} updateRow - ``updateRow(tr, item, index)``
   * @returns {number} Count of rows created or removed
   */
  dom.syncTableBody = function (tbody, items, keyFn, createRow, updateRow) {
    return reconcile(tbody, items, keyFn, createRow, updateRow);
  };

  /**
   * Sync a container's children with ``items`` using in-place keyed
   * reconciliation. Works for any parent (``<div>``, ``<ul>``, ``<select>``).
   * Non-keyed children are preserved.
   *
   * @param {Element} container
   * @param {Array} items
   * @param {Function} keyFn - ``keyFn(item, index) → string|number``
   * @param {Function} createItem - ``createItem(item, index) → Element``
   * @param {Function} updateItem - ``updateItem(el, item, index)``
   * @returns {number} Count of items created or removed
   */
  dom.syncList = function (container, items, keyFn, createItem, updateItem) {
    return reconcile(container, items, keyFn, createItem, updateItem);
  };

  // ── Table Cell Helpers ───────────────────────────────

  /**
   * Find or create a cell in a row by index.
   * Sets ``data-col`` on first access for stable identity.
   *
   * @param {HTMLTableRowElement} tr
   * @param {number} index - 0-based column index
   * @returns {HTMLTableCellElement}
   */
  dom.cell = function (tr, index) {
    var cells = tr.cells;
    if (index < cells.length) return cells[index];
    // Ensure enough cells exist
    while (tr.cells.length <= index) {
      tr.insertCell();
    }
    return tr.cells[index];
  };

  /**
   * Update a table cell's text content only if changed.
   *
   * @param {HTMLTableRowElement} tr
   * @param {number} col - 0-based column index
   * @param {string} text - New cell text
   */
  dom.setCellText = function (tr, col, text) {
    var cell = dom.cell(tr, col);
    dom.setText(cell, text);
  };

  /**
   * Update a table cell's innerHTML only if changed.
   *
   * @param {HTMLTableRowElement} tr
   * @param {number} col - 0-based column index
   * @param {string} html - New cell HTML
   */
  dom.setCellHtml = function (tr, col, html) {
    var cell = dom.cell(tr, col);
    if (cell.innerHTML !== html) {
      cell.innerHTML = html;
    }
  };

  // ── Animation ────────────────────────────────────────

  /**
   * Apply ``row-entrance`` stagger animation to an element.
   * Only useful for genuinely new rows — never call on refresh.
   *
   * @param {Element} el
   * @param {number} index - Stagger index (``--row-i``)
   */
  dom.animateEntrance = function (el, index) {
    el.style.setProperty('--row-i', String(index));
    el.classList.add('row-entrance');
  };

  window.dom = dom;
})();