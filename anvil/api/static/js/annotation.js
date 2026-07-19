// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

/**
 * Visual feedback annotation — live-page overlay with two modes:
 *   element-select (click-to-highlight) and freehand (SVG drawing).
 *
 * Screenshot is captured ONLY at submit time via window.htmlToImage.
 * The overlay is transparent — the page shows through at all times.
 *
 * Public API:
 *   window.AnnotationCanvas(container, options)
 *   window.initAnnotationMode(containerOrSelector, options)
 *   instance.init()
 */

(function() {
  'use strict';

  /* ── Helpers ────────────────────────────────────────────────── */

  /**
   * Build a robust CSS selector for an element.
   * Prefers #id; otherwise builds a path using tag + nth-of-type
   * up the ancestor chain, stopping at the first id-bearing ancestor.
   *
   * @param {Element} el
   * @return {string}
   */
  function generateSelector(el) {
    if (el.id) {
      return '#' + el.id;
    }

    var parts = [];
    var current = el;

    while (current && current !== document.body && current !== document.documentElement) {
      var tag = current.tagName.toLowerCase();
      var parent = current.parentElement;
      if (!parent) break;

      // Count same-tag siblings and determine nth-of-type position
      var sameTagSiblings = 0;
      var nthOfType = 0;
      var children = parent.children;
      for (var i = 0; i < children.length; i++) {
        if (children[i].tagName === current.tagName) {
          sameTagSiblings++;
          if (children[i] === current) {
            nthOfType = sameTagSiblings;
          }
        }
      }

      var part = tag;
      if (sameTagSiblings > 1) {
        part += ':nth-of-type(' + nthOfType + ')';
      }
      parts.unshift(part);

      current = parent;
      if (current.id) {
        parts.unshift('#' + current.id);
        break;
      }
    }

    return parts.join(' > ');
  }

  /**
   * Check if an element is part of the annotation UI (overlay, toolbar, popup, markers).
   * @param {Element} el
   * @return {boolean}
   */
function isAnnotationUI(el) {
    while (el) {
      if (el.classList && (
        el.classList.contains('feedback-annotation-overlay') ||
        el.classList.contains('feedback-annotation-toolbar') ||
        el.classList.contains('feedback-note-popup') ||
        el.classList.contains('feedback-markers-container') ||
        el.classList.contains('feedback-marker') ||
        el.classList.contains('feedback-toggle-btn')
      )) {
        return true;
      }
      el = el.parentElement;
    }
    return false;
  }

  /**
   * Extract observability data from a DOM element for coding agents.
   * Returns a flat object with outerHTML, textContent, tagName, id,
   * className, and key attributes.
   * @param {Element} el
   * @return {Object}
   */
  function extractElementData(el) {
    var data = {
      tagName: el.tagName ? el.tagName.toLowerCase() : '',
      id: el.id || '',
      className: (el.className && typeof el.className === 'string') ? el.className : '',
      textContent: (el.textContent || '').substring(0, 500),
      outerHTML: (el.outerHTML || '').substring(0, 2000),
      selector: generateSelector(el)
    };

    // Capture key attributes
    var attrs = ['href', 'src', 'alt', 'title', 'value', 'type', 'placeholder',
                 'role', 'aria-label', 'aria-describedby', 'disabled', 'href',
                 'target', 'rel', 'for', 'name'];
    data.attributes = {};
    for (var ai = 0; ai < attrs.length; ai++) {
      var attrName = attrs[ai];
      var attrVal = el.getAttribute(attrName);
      if (attrVal !== null && attrVal !== '') {
        data.attributes[attrName] = attrVal;
      }
    }

    return data;
  }

  /**
   * Read CSS custom property from document root.
   * @param {string} name
   * @return {string}
   */
  function getCSSVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }


  /* ── AnnotationCanvas ──────────────────────────────────────── */

  /**
   * AnnotationCanvas — manages annotation overlay on a live page.
   *
   * Two modes: element-select (click to highlight an element) and
   * freehand (draw strokes on a transparent SVG overlay).
   * Screenshot captured only at submit time.
   *
   * @param {HTMLElement} container  The DOM element to annotate over.
   * @param {Object}      options    Optional configuration.
   * @param {string}      options.pageUrl   Override page URL (defaults to window.location.href).
   * @param {function}    options.onSubmit  Callback after successful submission.
   * @param {function}    options.onClose   Callback when annotation mode is closed.
   */
  function AnnotationCanvas(container, options) {
    if (!container) throw new Error('AnnotationCanvas requires a container element');

    this.container = container;
    this.options = options || {};
    this._annotations = [];
    this._activeTool = null;
    this._isDrawing = false;
    this._hasUnsavedChanges = false;
    this._annotationMode = false;

    // Overlay elements
    this._overlayEl = null;
    this._svgEl = null;
    this._svgPathEl = null;
    this._hoverHighlightEl = null;
    this._markersContainer = null;
    this._counterEl = null;

    // Drawing state
    this._drawPath = null;
    this._pendingAnnotation = null;

    // Note popup
    this._notePopup = null;

    // Manage popup state (element annotations CRUD)
    this._manageAnnotations = null;   // [{index, annotation}, ...] for current element
    this._manageRect = null;          // Bounding rect of clicked element
    this._manageSelector = null;      // CSS selector of clicked element
    this._manageElementInfo = null;   // Enriched element data (outerHTML, etc.)
    this._manageSubMode = null;       // 'edit' or 'add' when in editor sub-mode
    this._manageEditingIdx = -1;      // Index into _manageAnnotations for edit target

    // Toolbar & toggle
    this._toggleBtn = null;

    // Bound handlers for cleanup
    this._onBoundOverlayMouseMove = null;
    this._onBoundOverlayClick = null;
    this._onBoundOverlayMouseDown = null;
    this._onBoundOverlayMouseUp = null;
    this._onBoundKeydown = null;
    this._onBoundBeforeUnload = null;

    this._pageUrl = this.options.pageUrl || window.location.href;
    this._maxContainedElements = this.options.maxContainedElements || 100;
    this._accentColor = getCSSVar('--accent') || '#007aff';
  }

  /**
   * Initialize — create the floating toggle button.
   */
  AnnotationCanvas.prototype.init = function() {
    this._createToggleButton();
  };

  /**
   * Get current annotations (copy).
   * @return {Array<Object>}
   */
  AnnotationCanvas.prototype.getMarkers = function() {
    return this._annotations.slice();
  };

  /**
   * Set the active tool.
   * @param {string|null} tool  'element', 'freehand', or null to deactivate.
   */
  AnnotationCanvas.prototype.setTool = function(tool) {
    this._activeTool = tool;
    if (this._overlayEl) {
      if (tool) {
        this._overlayEl.style.cursor = 'crosshair';
        this._overlayEl.style.pointerEvents = 'auto';
      } else {
        // No active tool: let clicks/hover pass through to the live page so the
        // user can scroll and interact normally. Saved markers stay visible.
        this._overlayEl.style.cursor = 'default';
        this._overlayEl.style.pointerEvents = 'none';
      }
    }
    if (this._hoverHighlightEl && !tool) {
      this._hoverHighlightEl.style.display = 'none';
    }
  };

  /**
   * Remove the last annotation (undo).
   */
  AnnotationCanvas.prototype.undo = function() {
    if (this._annotations.length === 0) return;
    this._annotations.pop();
    this._hasUnsavedChanges = true;
    this._renderMarkers();
    this._updateCounter();
  };

  /**
   * Clear all annotations.
   */
  AnnotationCanvas.prototype.clear = function() {
    if (this._annotations.length === 0) return;
    if (!window.confirm('Clear all annotations?')) return;
    this._annotations = [];
    this._hasUnsavedChanges = true;
    this._renderMarkers();
    this._updateCounter();
  };

  /**
   * Submit annotations — capture screenshot, POST to /v1/feedback.
   * @return {Promise<Object|null>}
   */
  AnnotationCanvas.prototype.submit = function() {
    var self = this;

    if (this._annotations.length === 0) {
      this._showToast('No annotations to submit', 'error');
      return Promise.resolve(null);
    }

    this._showToast('Submitting report…', 'info');

    return this._captureScreenshot().then(function(screenshotBlob) {
      return self._uploadReport(screenshotBlob);
    }).then(function(result) {
      if (result && result.ok) {
        self._hasUnsavedChanges = false;
        self._removeBeforeUnload();
        if (self.options.onSubmit) {
          self.options.onSubmit(result);
        }
        self._showToast('Report submitted successfully', 'success');
        self._annotations = [];
        self._exitAnnotationMode();
      }
      return result;
    }).catch(function(err) {
      self._showToast('Failed to submit: ' + (err.message || 'Network error'), 'error');
      throw err;
    });
  };

  /**
   * Destroy the instance and clean up all DOM.
   */
  AnnotationCanvas.prototype.destroy = function() {
    this._exitAnnotationMode(true);
    this._removeToggleButton();
    this._removeBeforeUnload();
    this._annotations = [];
  };


  /* ── Toggle Button ─────────────────────────────────────────── */

  /**
   * Create the floating toggle button (always visible outside annotation mode).
   */
  AnnotationCanvas.prototype._createToggleButton = function() {
    if (this._toggleBtn) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'feedback-toggle-btn';
    btn.setAttribute('aria-label', 'Toggle annotation mode');
    btn.setAttribute('title', 'Annotate this page');
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">' +
        '<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z"/>' +
        '<path d="M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>' +
      '</svg>';

    var self = this;
    btn.addEventListener('click', function() {
      if (self._annotationMode) {
        self._exitAnnotationMode();
      } else {
        self._enterAnnotationMode();
      }
    });

    document.body.appendChild(btn);
    this._toggleBtn = btn;
  };

  /**
   * Remove the toggle button.
   */
  AnnotationCanvas.prototype._removeToggleButton = function() {
    if (this._toggleBtn && this._toggleBtn.parentNode) {
      this._toggleBtn.parentNode.removeChild(this._toggleBtn);
    }
    this._toggleBtn = null;
  };


  /* ── Enter / Exit Annotation Mode ──────────────────────────── */

  /**
   * Enter annotation mode — create overlay, show toolbar, bind events.
   */
  AnnotationCanvas.prototype._enterAnnotationMode = function() {
    this._annotationMode = true;
    this._hasUnsavedChanges = false;

    if (this._toggleBtn) {
      this._toggleBtn.style.display = 'none';
    }

    this._createOverlay();
    this._showToolbar();
    this._bindEvents();
    this._setupBeforeUnload();
    this._updateCounter();
  };

  /**
   * Exit annotation mode — remove overlay, hide toolbar, show toggle.
   * @param {boolean} force  Skip confirm dialog.
   */
  AnnotationCanvas.prototype._exitAnnotationMode = function(force) {
    if (!force && this._hasUnsavedChanges && this._annotations.length > 0) {
      if (!window.confirm('You have unsaved annotations. Close without submitting?')) {
        return;
      }
    }

    this._annotationMode = false;
    this._activeTool = null;
    this._removeNotePopup();
    this._removeOverlay();
    this._hideToolbar();
    this._removeBeforeUnload();

    if (this._toggleBtn) {
      this._toggleBtn.style.display = '';
    }

    if (this.options.onClose) {
      this.options.onClose();
    }
  };


  /* ── Overlay ────────────────────────────────────────────────── */

  /**
   * Create the transparent full-page overlay and its children.
   */
  AnnotationCanvas.prototype._createOverlay = function() {
    var overlay = document.createElement('div');
    overlay.className = 'feedback-annotation-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Annotation overlay');
    overlay.style.display = '';

    // SVG layer for freehand drawing (pointer-events:none so overlay captures events)
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'feedback-annotation-overlay__svg');
    svg.setAttribute('aria-hidden', 'true');
    overlay.appendChild(svg);
    this._svgEl = svg;

    // Hover highlight for element mode
    var highlight = document.createElement('div');
    highlight.className = 'feedback-hover-highlight';
    highlight.style.display = 'none';
    overlay.appendChild(highlight);
    this._hoverHighlightEl = highlight;

    // Markers container for saved annotation visual markers
    var markers = document.createElement('div');
    markers.className = 'feedback-markers-container';
    markers.setAttribute('aria-hidden', 'true');
    overlay.appendChild(markers);
    this._markersContainer = markers;

    document.body.appendChild(overlay);
    this._overlayEl = overlay;

    // Explicit initial state: no tool active until the user picks one.
    this.setTool(this._activeTool);
  };

  /**
   * Remove the overlay and all children from the DOM.
   */
  AnnotationCanvas.prototype._removeOverlay = function() {
    if (this._overlayEl && this._overlayEl.parentNode) {
      this._overlayEl.parentNode.removeChild(this._overlayEl);
    }
    this._overlayEl = null;
    this._svgEl = null;
    this._svgPathEl = null;
    this._hoverHighlightEl = null;
    this._markersContainer = null;
    this._counterEl = null;
  };


  /* ── Toolbar ────────────────────────────────────────────────── */

  /**
   * Find the toolbar (rendered from annotation-toolbar.html partial) and show it.
   */
  AnnotationCanvas.prototype._showToolbar = function() {
    var toolbar = document.getElementById('annotation-toolbar');
    if (!toolbar) return;
    toolbar.style.display = '';
    this._wireToolbar(toolbar);
  };

  /**
   * Hide the toolbar.
   */
  AnnotationCanvas.prototype._hideToolbar = function() {
    var toolbar = document.getElementById('annotation-toolbar');
    if (toolbar) {
      toolbar.style.display = 'none';
    }
  };

  /**
   * Wire toolbar button events. Idempotent — uses flag to avoid double-wiring.
   * @param {HTMLElement} toolbar
   */
  AnnotationCanvas.prototype._wireToolbar = function(toolbar) {
    if (toolbar._wired) return;
    toolbar._wired = true;

    var self = this;

    // Tool buttons
    var toolBtns = toolbar.querySelectorAll('[data-tool]');
    for (var i = 0; i < toolBtns.length; i++) {
      toolBtns[i].addEventListener('click', function() {
        var tool = this.getAttribute('data-tool');
        var allBtns = toolbar.querySelectorAll('[data-tool]');
        for (var j = 0; j < allBtns.length; j++) {
          allBtns[j].classList.remove('feedback-annotation-toolbar__btn--active');
        }

        // Re-clicking the active tool toggles it off (deselect)
        if (self._activeTool === tool) {
          self.setTool(null);
          return;
        }

        self.setTool(tool);
        this.classList.add('feedback-annotation-toolbar__btn--active');
      });
    }

    // Undo
    var undoBtn = document.getElementById('annotation-toolbar-undo');
    if (undoBtn) {
      undoBtn.addEventListener('click', function() {
        self.undo();
      });
    }

    // Clear
    var clearBtn = document.getElementById('annotation-toolbar-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function() {
        self.clear();
      });
    }

    // Submit
    var submitBtn = document.getElementById('annotation-toolbar-submit');
    if (submitBtn) {
      submitBtn.addEventListener('click', function() {
        self.submit();
      });
    }

    // Close
    var closeBtn = document.getElementById('annotation-toolbar-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function() {
        self._exitAnnotationMode();
      });
    }
  };


  /* ── Event Binding ──────────────────────────────────────────── */

  /**
   * Bind overlay mouse/keyboard events.
   */
  AnnotationCanvas.prototype._bindEvents = function() {
    var self = this;

    this._onBoundOverlayMouseMove = function(e) {
      self._onOverlayMouseMove(e);
    };
    this._onBoundOverlayClick = function(e) {
      self._onOverlayClick(e);
    };
    this._onBoundOverlayMouseDown = function(e) {
      self._onOverlayMouseDown(e);
    };
    this._onBoundOverlayMouseUp = function(e) {
      self._onOverlayMouseUp(e);
    };
    this._onBoundKeydown = function(e) {
      self._onKeydown(e);
    };

    this._overlayEl.addEventListener('mousemove', this._onBoundOverlayMouseMove);
    this._overlayEl.addEventListener('click', this._onBoundOverlayClick);
    this._overlayEl.addEventListener('mousedown', this._onBoundOverlayMouseDown);
    // Bind mouseup to document so release outside overlay still fires
    document.addEventListener('mouseup', this._onBoundOverlayMouseUp);
    document.addEventListener('keydown', this._onBoundKeydown);
  };

  /**
   * Unbind overlay mouse/keyboard events.
   */
  AnnotationCanvas.prototype._unbindEvents = function() {
    if (this._onBoundOverlayMouseMove) {
      this._overlayEl.removeEventListener('mousemove', this._onBoundOverlayMouseMove);
    }
    if (this._onBoundOverlayClick) {
      this._overlayEl.removeEventListener('click', this._onBoundOverlayClick);
    }
    if (this._onBoundOverlayMouseDown) {
      this._overlayEl.removeEventListener('mousedown', this._onBoundOverlayMouseDown);
    }
    if (this._onBoundOverlayMouseUp) {
      document.removeEventListener('mouseup', this._onBoundOverlayMouseUp);
    }
    if (this._onBoundKeydown) {
      document.removeEventListener('keydown', this._onBoundKeydown);
    }

    this._onBoundOverlayMouseMove = null;
    this._onBoundOverlayClick = null;
    this._onBoundOverlayMouseDown = null;
    this._onBoundOverlayMouseUp = null;
    this._onBoundKeydown = null;
  };


  /* ── Element Detection ──────────────────────────────────────── */

  /**
   * Get the real page element under the cursor, ignoring the annotation UI.
   * Temporarily disables overlay pointer-events to query elementFromPoint.
   * @param {MouseEvent} e
   * @return {Element|null}
   */
  AnnotationCanvas.prototype._getElementUnderCursor = function(e) {
    // Temporarily let events pass through so we can find the real element,
    // then restore based on tool state (none when no tool is active).
    this._overlayEl.style.pointerEvents = 'none';
    var el = document.elementFromPoint(e.clientX, e.clientY);
    this._overlayEl.style.pointerEvents = this._activeTool ? 'auto' : 'none';

    // Skip annotation UI elements
    if (el && isAnnotationUI(el)) {
      return null;
    }
    return el;
  };


  /* ── Contained Elements Discovery ─────────────────────────── */

  /**
   * Check whether an element should be excluded from contained-element
   * capture. Excludes script/style tags and hidden/invisible elements.
   * @param {Element} el
   * @return {boolean}
   */
  AnnotationCanvas.prototype._isExcludedElement = function(el) {
    if (!el || !el.tagName) return true;
    var tag = el.tagName.toLowerCase();
    if (tag === 'script' || tag === 'style' || tag === 'html' || tag === 'body') {
      return true;
    }
    var style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' ||
        parseFloat(style.opacity) === 0) {
      return true;
    }
    return false;
  };

  /**
   * Compute spatial data for an element relative to a bounding rect.
   * Returns relX, relY, width, height, and overlapRatio (0.0–1.0).
   * @param {Element} el
   * @param {DOMRect} boundingRect
   * @return {Object}
   */
  AnnotationCanvas.prototype._computeElementSpatialData = function(el, boundingRect) {
    var elRect = el.getBoundingClientRect();

    var overlapLeft = Math.max(elRect.left, boundingRect.left);
    var overlapTop = Math.max(elRect.top, boundingRect.top);
    var overlapRight = Math.min(elRect.right, boundingRect.right);
    var overlapBottom = Math.min(elRect.bottom, boundingRect.bottom);

    var overlapWidth = Math.max(0, overlapRight - overlapLeft);
    var overlapHeight = Math.max(0, overlapBottom - overlapTop);
    var overlapArea = overlapWidth * overlapHeight;
    var elArea = elRect.width * elRect.height;
    var overlapRatio = elArea > 0 ? overlapArea / elArea : 0;

    return {
      relX: Math.round(elRect.left - boundingRect.left),
      relY: Math.round(elRect.top - boundingRect.top),
      width: Math.round(elRect.width),
      height: Math.round(elRect.height),
      overlapRatio: Math.round(overlapRatio * 100) / 100
    };
  };

  /**
   * Find all non-excluded elements that intersect (even partially)
   * with the given bounding rect. Uses grid-based sampling of
   * document.elementsFromPoint() to discover elements, then filters
   * and computes spatial data for each.
   *
   * Results are sorted by overlap ratio (highest first), then by
   * DOM depth (deepest first).
   *
   * @param {DOMRect} rect  Bounding rect in viewport coordinates.
   * @return {Array<Object>}  Array of element info objects with spatial data.
   */
  AnnotationCanvas.prototype._findContainedElements = function(rect) {
    var maxCount = this._maxContainedElements;
    var seen = {};        // Dedup by CSS selector string
    var elements = [];    // [[selector, element], ...]

    // Adaptive step size: at most 10 samples per axis, at least 4px
    var stepX = Math.max(4, Math.floor(rect.width / 10));
    var stepY = Math.max(4, Math.floor(rect.height / 10));

    // Also sample the four corners and center
    var samplePoints = [
      [rect.left, rect.top],
      [rect.left, rect.bottom],
      [rect.right, rect.top],
      [rect.right, rect.bottom],
      [rect.left + rect.width / 2, rect.top + rect.height / 2]
    ];

    // Generate grid points
    for (var gy = rect.top; gy <= rect.bottom; gy += stepY) {
      for (var gx = rect.left; gx <= rect.right; gx += stepX) {
        samplePoints.push([gx, gy]);
      }
    }

    // Collect elements from each sample point
    for (var pi = 0; pi < samplePoints.length; pi++) {
      if (Object.keys(seen).length >= maxCount * 2) break;
      var px = samplePoints[pi][0];
      var py = samplePoints[pi][1];

      // Skip points outside viewport
      if (px < 0 || py < 0 || px > window.innerWidth || py > window.innerHeight) continue;

      var elsAtPoint;
      try {
        elsAtPoint = document.elementsFromPoint(px, py);
      } catch (e) {
        continue;
      }
      if (!elsAtPoint) continue;

      for (var ei = 0; ei < elsAtPoint.length; ei++) {
        var el = elsAtPoint[ei];
        if (this._isExcludedElement(el)) continue;
        var key = generateSelector(el);
        if (!seen[key]) {
          seen[key] = true;
          elements.push(el);
        }
      }
    }

    // Convert to result array with spatial data and element info
    var result = [];
    for (var ri = 0; ri < elements.length; ri++) {
      var el = elements[ri];
      var spatial = this._computeElementSpatialData(el, rect);
      if (spatial.overlapRatio > 0) {
        var info = extractElementData(el);
        info.spatial = spatial;
        result.push(info);
      }
    }

    // Sort by overlap ratio descending, then by DOM depth descending
    result.sort(function(a, b) {
      if (a.spatial.overlapRatio !== b.spatial.overlapRatio) {
        return b.spatial.overlapRatio - a.spatial.overlapRatio;
      }
      var depthA = a.selector ? a.selector.split(' > ').length : 0;
      var depthB = b.selector ? b.selector.split(' > ').length : 0;
      return depthB - depthA;
    });

    return result.slice(0, maxCount);
  };


  /* ── Mouse Handlers ─────────────────────────────────────────── */

  /**
   * Mousemove on overlay — element hover highlight or freehand drawing.
   */
  AnnotationCanvas.prototype._onOverlayMouseMove = function(e) {
    if (this._notePopup) return; // Popup open, don't interfere

    if (this._activeTool === 'element') {
      this._updateHoverHighlight(e);
    } else if (this._activeTool === 'freehand' && this._isDrawing) {
      this._extendFreehandPath(e);
    }
  };

  /**
   * Click on overlay — element selection.
   */
  AnnotationCanvas.prototype._onOverlayClick = function(e) {
    if (this._notePopup) return;
    if (this._activeTool !== 'element') return;

    var el = this._getElementUnderCursor(e);
    if (!el) return;

    // Reject html/body/app-shell targets whose box is the whole page
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    if (tag === 'html' || tag === 'body') {
      this._showToast('Click a specific element, not the page background', 'error');
      return;
    }

    // Get bounding box in viewport coordinates
    var rect = el.getBoundingClientRect();

    // Reject degenerate (too small) or near-full-viewport boxes
    if (rect.width < 4 || rect.height < 4) {
      this._showToast('That element is too small to annotate', 'error');
      return;
    }
    if (rect.width >= window.innerWidth - 4 && rect.height >= window.innerHeight - 4) {
      this._showToast('Click a more specific element', 'error');
      return;
    }

    var selector = generateSelector(el);

    // Check for existing element annotations matching this selector
    var matchingAnnotations = [];
    for (var mi = 0; mi < this._annotations.length; mi++) {
      var ann = this._annotations[mi];
      if (ann.type === 'element' && ann.data.selector === selector) {
        matchingAnnotations.push({ index: mi, annotation: ann });
      }
    }

    if (matchingAnnotations.length > 0) {
      // Show manage popup with existing annotations
      var popupX = rect.left + rect.width + 10;
      var popupY = rect.top;
      this._showManagePopup(popupX, popupY, matchingAnnotations, rect, selector, extractElementData(el));
      return;
    }

    this._pendingAnnotation = {
      type: 'element',
      data: {
        x: Math.round(rect.left),
        y: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        selector: selector,
        elementInfo: extractElementData(el),
        scrollX: window.scrollX || window.pageXOffset || 0,
        scrollY: window.scrollY || window.pageYOffset || 0,
        containedElements: this._findContainedElements(rect)
      }
    };

    // Show note popup near the element
    var popupX = rect.left + rect.width + 10;
    var popupY = rect.top;
    this._showNotePopup(popupX, popupY);
  };

  /**
   * Mousedown on overlay — start freehand drawing.
   */
  AnnotationCanvas.prototype._onOverlayMouseDown = function(e) {
    if (this._notePopup) return;
    if (this._activeTool !== 'freehand') return;

    // Ignore if clicking on toolbar through overlay
    var target = e.target;
    if (target && (target.closest('#annotation-toolbar') || target.closest('.feedback-note-popup'))) {
      return;
    }

    this._isDrawing = true;
    this._drawPath = [[e.clientX, e.clientY]];

    // Create a new SVG path for the live preview
    var svg = this._svgEl;
    svg.innerHTML = '';
    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M ' + e.clientX + ' ' + e.clientY);
    path.setAttribute('class', 'feedback-annotation-overlay__draw-path');
    svg.appendChild(path);
    this._svgPathEl = path;
  };

  /**
   * Mouseup — finalize freehand drawing.
   */
  AnnotationCanvas.prototype._onOverlayMouseUp = function(e) {
    if (!this._isDrawing || !this._drawPath) return;
    this._isDrawing = false;

    // If path is too short, discard
    if (this._drawPath.length < 2) {
      this._drawPath = null;
      if (this._svgEl) this._svgEl.innerHTML = '';
      this._svgPathEl = null;
      return;
    }

    // Compute bounds
    var xs = [];
    var ys = [];
    for (var i = 0; i < this._drawPath.length; i++) {
      xs.push(this._drawPath[i][0]);
      ys.push(this._drawPath[i][1]);
    }
    var minX = Math.min.apply(null, xs);
    var maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, ys);
    var maxY = Math.max.apply(null, ys);

    this._pendingAnnotation = {
      type: 'freehand',
      data: {
        path: this._drawPath,
        bounds: { minX: minX, minY: minY, maxX: maxX, maxY: maxY },
        scrollX: window.scrollX || window.pageXOffset || 0,
        scrollY: window.scrollY || window.pageYOffset || 0
      }
    };

    // Clear the live preview path — the note popup save will render the permanent marker
    this._drawPath = null;
    if (this._svgEl) this._svgEl.innerHTML = '';
    this._svgPathEl = null;

    // Show note popup near the start of the path
    var popupX = Math.min(xs[0] + 10, window.innerWidth - 250);
    var popupY = Math.min(ys[0] + 10, window.innerHeight - 200);
    this._showNotePopup(Math.max(10, popupX), Math.max(10, popupY));
  };


  /* ── Hover Highlight ────────────────────────────────────────── */

  /**
   * Update the hover highlight overlay to match the element under the cursor.
   * @param {MouseEvent} e
   */
  AnnotationCanvas.prototype._updateHoverHighlight = function(e) {
    var el = this._getElementUnderCursor(e);
    if (!el) {
      this._hoverHighlightEl.style.display = 'none';
      return;
    }

    var rect = el.getBoundingClientRect();
    var hl = this._hoverHighlightEl;
    hl.style.display = '';
    hl.style.left = rect.left + 'px';
    hl.style.top = rect.top + 'px';
    hl.style.width = rect.width + 'px';
    hl.style.height = rect.height + 'px';
  };


  /* ── Freehand Drawing ───────────────────────────────────────── */

  /**
   * Extend the freehand path with the current mouse position.
   * @param {MouseEvent} e
   */
  AnnotationCanvas.prototype._extendFreehandPath = function(e) {
    if (!this._drawPath) return;
    this._drawPath.push([e.clientX, e.clientY]);

    // Update SVG path
    var d = 'M ' + this._drawPath[0][0] + ' ' + this._drawPath[0][1];
    for (var i = 1; i < this._drawPath.length; i++) {
      d += ' L ' + this._drawPath[i][0] + ' ' + this._drawPath[i][1];
    }
    if (this._svgPathEl) {
      this._svgPathEl.setAttribute('d', d);
    }
  };


  /* ── Note Popup ─────────────────────────────────────────────── */

  /**
   * Show the note input popup at the given position.
   * @param {number} x  Viewport X coordinate.
   * @param {number} y  Viewport Y coordinate.
   */
  AnnotationCanvas.prototype._showNotePopup = function(x, y) {
    var self = this;
    this._removeNotePopup();

    if (!this._pendingAnnotation) return;

    var popup = document.createElement('div');
    popup.className = 'feedback-note-popup';

    // Position within viewport bounds
    var popupW = 280;
    var popupH = 200;
    var posX = Math.min(x, window.innerWidth - popupW - 10);
    var posY = Math.min(y, window.innerHeight - popupH - 10);
    posX = Math.max(10, posX);
    posY = Math.max(10, posY);
    popup.style.left = posX + 'px';
    popup.style.top = posY + 'px';

    // Type label
    var typeLabel = document.createElement('div');
    typeLabel.className = 'feedback-note-popup__type-label';
    typeLabel.textContent = this._pendingAnnotation.type === 'element' ? 'Element annotation' : 'Freehand drawing';
    popup.appendChild(typeLabel);

    // Textarea
    var textarea = document.createElement('textarea');
    textarea.className = 'feedback-note-popup__textarea';
    textarea.maxLength = 2000;
    textarea.placeholder = 'Describe the issue… (2000 char max)';
    textarea.setAttribute('aria-label', 'Annotation note');
    popup.appendChild(textarea);

    // Character count
    var charCount = document.createElement('div');
    charCount.className = 'feedback-note-popup__charcount';
    charCount.textContent = '0 / 2000';
    popup.appendChild(charCount);

    textarea.addEventListener('input', function() {
      charCount.textContent = textarea.value.length + ' / 2000';
    });

    // Actions
    var actions = document.createElement('div');
    actions.className = 'feedback-note-popup__actions';

    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn--ghost feedback-note-popup__btn';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.setAttribute('aria-label', 'Discard annotation');

    var saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn--primary feedback-note-popup__btn';
    saveBtn.textContent = 'Save';
    saveBtn.setAttribute('aria-label', 'Save annotation');

    cancelBtn.addEventListener('click', function() {
      // Discard pending annotation and its visual marker
      self._pendingAnnotation = null;
      self._removeNotePopup();
    });

    saveBtn.addEventListener('click', function() {
      var note = textarea.value.trim();
      if (!note) {
        self._showToast('Please enter a description', 'error');
        return;
      }
      self._commitAnnotation(note);
      self._removeNotePopup();
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(saveBtn);
    popup.appendChild(actions);

    // Stop popup interactions from bubbling to the overlay's click/mousedown
    // handlers, which would otherwise re-trigger element selection or drawing.
    popup.addEventListener('click', function(ev) { ev.stopPropagation(); });
    popup.addEventListener('mousedown', function(ev) { ev.stopPropagation(); });

    // Append to overlay (so it's inside the fixed-position context)
    this._overlayEl.appendChild(popup);
    this._notePopup = popup;

    // Focus textarea after render
    setTimeout(function() {
      textarea.focus();
    }, 100);
  };

/**
   * Remove the note popup from the DOM.
   */
  AnnotationCanvas.prototype._removeNotePopup = function() {
    if (this._notePopup && this._notePopup.parentNode) {
      this._notePopup.parentNode.removeChild(this._notePopup);
    }
    this._notePopup = null;
    this._manageAnnotations = null;
    this._manageRect = null;
    this._manageSelector = null;
    this._manageSubMode = null;
    this._manageEditingIdx = -1;
  };


  /* ── Manage Popup (element CRUD) ─────────────────────────────── */

  /**
   * Show the manage popup listing existing annotations for a clicked element.
   * @param {number} x  Viewport X.
   * @param {number} y  Viewport Y.
   * @param {Array} matchingAnnotations  [{index, annotation}, ...].
   * @param {Object} rect  Bounding rect of the clicked element.
   * @param {string} selector  CSS selector of the clicked element.
   * @param {Object} elementInfo  Enriched element data for coding agents.
   */
  AnnotationCanvas.prototype._showManagePopup = function(x, y, matchingAnnotations, rect, selector, elementInfo) {
    var self = this;
    this._removeNotePopup();

    this._manageRect = rect;
    this._manageSelector = selector;
    this._manageElementInfo = elementInfo;
    this._manageSubMode = null;
    this._manageEditingIdx = -1;

    this._buildManageList(popup);

    popup.addEventListener('click', function(ev) { ev.stopPropagation(); });
    popup.addEventListener('mousedown', function(ev) { ev.stopPropagation(); });

    this._overlayEl.appendChild(popup);
    this._notePopup = popup;
  };

  /**
   * Build the list view inside the manage popup.
   * @param {HTMLElement} popup
   */
  AnnotationCanvas.prototype._buildManageList = function(popup) {
    var self = this;
    popup.innerHTML = '';

    var matchingAnnotations = this._manageAnnotations;
    var count = matchingAnnotations.length;

    // Type label
    var typeLabel = document.createElement('div');
    typeLabel.className = 'feedback-note-popup__type-label';
    typeLabel.textContent = 'Element annotations (' + count + ')';
    popup.appendChild(typeLabel);

    // List of existing annotations
    if (count > 0) {
      var list = document.createElement('div');
      list.className = 'feedback-note-popup__list';

      for (var li = 0; li < count; li++) {
        var item = matchingAnnotations[li];
        var itemEl = document.createElement('div');
        itemEl.className = 'feedback-note-popup__list-item';

        // Index badge
        var idxBadge = document.createElement('span');
        idxBadge.className = 'feedback-note-popup__item-index';
        idxBadge.textContent = '#' + (li + 1);
        itemEl.appendChild(idxBadge);

        // Note text (truncated)
        var noteEl = document.createElement('span');
        noteEl.className = 'feedback-note-popup__item-note';
        var noteText = item.annotation.note || '(empty)';
        noteEl.textContent = noteText;
        noteEl.title = noteText;
        itemEl.appendChild(noteEl);

        // Action buttons
        var actionsEl = document.createElement('span');
        actionsEl.className = 'feedback-note-popup__item-actions';

        // Edit button — closure captures li
        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'feedback-note-popup__edit-btn';
        editBtn.textContent = 'Edit';
        editBtn.setAttribute('aria-label', 'Edit annotation ' + (li + 1));
        editBtn.addEventListener('click', (function(idx) {
          return function() {
            self._buildManageEditor(popup, idx);
          };
        })(li));

        // Delete button — closure captures li
        var deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'feedback-note-popup__delete-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.setAttribute('aria-label', 'Delete annotation ' + (li + 1));
        deleteBtn.addEventListener('click', (function(idx) {
          return function() {
            self._deleteManageAnnotation(popup, idx);
          };
        })(li));

        actionsEl.appendChild(editBtn);
        actionsEl.appendChild(deleteBtn);
        itemEl.appendChild(actionsEl);

        list.appendChild(itemEl);
      }

      popup.appendChild(list);
    }

    // Add-new button
    var addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'feedback-note-popup__add-btn';
    addBtn.textContent = '+ Add new annotation';
    addBtn.setAttribute('aria-label', 'Add new annotation for this element');
    addBtn.addEventListener('click', function() {
      self._buildManageEditor(popup, -1);
    });
    popup.appendChild(addBtn);

    // Actions bar
    var actionsBar = document.createElement('div');
    actionsBar.className = 'feedback-note-popup__actions';

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn btn--ghost feedback-note-popup__btn';
    closeBtn.textContent = 'Close';
    closeBtn.setAttribute('aria-label', 'Close annotation list');
    closeBtn.addEventListener('click', function() {
      self._pendingAnnotation = null;
      self._removeNotePopup();
    });

    actionsBar.appendChild(closeBtn);
    popup.appendChild(actionsBar);

    this._manageSubMode = null;

    // Focus first actionable control
    setTimeout(function() {
      var firstBtn = popup.querySelector('button');
      if (firstBtn) firstBtn.focus();
    }, 100);
  };

  /**
   * Build the editor view (edit or add mode) inside the manage popup.
   * @param {HTMLElement} popup
   * @param {number} manageIdx  Index into _manageAnnotations, or -1 for add.
   */
  AnnotationCanvas.prototype._buildManageEditor = function(popup, manageIdx) {
    var self = this;
    var isAdd = manageIdx === -1;
    var editingAnnotation = isAdd ? null : this._manageAnnotations[manageIdx].annotation;
    var existingNote = isAdd ? '' : (editingAnnotation.note || '');

    this._manageSubMode = isAdd ? 'add' : 'edit';
    this._manageEditingIdx = manageIdx;

    popup.innerHTML = '';
    popup.style.width = '280px';
    popup.style.maxWidth = '';

    // Type label
    var typeLabel = document.createElement('div');
    typeLabel.className = 'feedback-note-popup__type-label';
    typeLabel.textContent = isAdd ? 'New annotation' : 'Edit annotation';
    popup.appendChild(typeLabel);

    // Textarea
    var textarea = document.createElement('textarea');
    textarea.className = 'feedback-note-popup__textarea';
    textarea.maxLength = 2000;
    textarea.placeholder = 'Describe the issue… (2000 char max)';
    textarea.value = existingNote;
    textarea.setAttribute('aria-label', isAdd ? 'New annotation note' : 'Edit annotation note');
    popup.appendChild(textarea);

    // Character count
    var charCount = document.createElement('div');
    charCount.className = 'feedback-note-popup__charcount';
    charCount.textContent = existingNote.length + ' / 2000';
    popup.appendChild(charCount);

    textarea.addEventListener('input', function() {
      charCount.textContent = textarea.value.length + ' / 2000';
    });

    // Actions
    var actions = document.createElement('div');
    actions.className = 'feedback-note-popup__actions';

    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn--ghost feedback-note-popup__btn';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.setAttribute('aria-label', isAdd ? 'Cancel new annotation' : 'Cancel edit');

    var saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn--primary feedback-note-popup__btn';
    saveBtn.textContent = 'Save';
    saveBtn.setAttribute('aria-label', isAdd ? 'Save new annotation' : 'Save edited annotation');

    cancelBtn.addEventListener('click', function() {
      self._manageSubMode = null;
      self._manageEditingIdx = -1;
      self._rescanManageAnnotations();
      self._buildManageList(popup);
    });

    saveBtn.addEventListener('click', function() {
      var newNote = textarea.value.trim();
      if (!newNote) {
        self._showToast('Please enter a description', 'error');
        return;
      }
      self._handleManageSave(newNote);
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(saveBtn);
    popup.appendChild(actions);

    // Focus textarea after render
    setTimeout(function() {
      textarea.focus();
    }, 100);
  };

  /**
   * Save the currently-edited or newly-created annotation from the manage editor.
   * @param {string} note
   */
  AnnotationCanvas.prototype._handleManageSave = function(note) {
    if (!this._notePopup) return;

    if (this._manageSubMode === 'add') {
      var rect = this._manageRect;
      var addData = {
        x: Math.round(rect.left),
        y: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        selector: this._manageSelector,
        scrollX: window.scrollX || window.pageXOffset || 0,
        scrollY: window.scrollY || window.pageYOffset || 0,
        containedElements: this._findContainedElements(rect)
      };
      if (this._manageElementInfo) {
        addData.elementInfo = this._manageElementInfo;
      }
      this._annotations.push({
        type: 'element',
        note: note,
        data: addData
      });
    } else if (this._manageSubMode === 'edit' && this._manageEditingIdx >= 0) {
      var item = this._manageAnnotations[this._manageEditingIdx];
      if (item) {
        item.annotation.note = note;
      }
    }

    this._hasUnsavedChanges = true;
    this._rescanManageAnnotations();
    this._renderMarkers();
    this._updateCounter();

    this._manageSubMode = null;
    this._manageEditingIdx = -1;
    this._buildManageList(this._notePopup);
  };

  /**
   * Delete an annotation from the manage list and rebuild.
   * @param {HTMLElement} popup
   * @param {number} manageIdx  Index into _manageAnnotations.
   */
  AnnotationCanvas.prototype._deleteManageAnnotation = function(popup, manageIdx) {
    var item = this._manageAnnotations[manageIdx];
    if (!item) return;

    this._annotations.splice(item.index, 1);
    this._hasUnsavedChanges = true;

    this._rescanManageAnnotations();
    this._renderMarkers();
    this._updateCounter();

    if (this._manageAnnotations.length === 0) {
      this._pendingAnnotation = null;
      this._removeNotePopup();
      return;
    }

    this._manageSubMode = null;
    this._manageEditingIdx = -1;
    this._buildManageList(popup);
  };

  /**
   * Re-scan this._annotations for element annotations matching _manageSelector.
   * Updates _manageAnnotations in place.
   */
  AnnotationCanvas.prototype._rescanManageAnnotations = function() {
    var selector = this._manageSelector;
    if (!selector) {
      this._manageAnnotations = [];
      return;
    }
    var matching = [];
    for (var ri = 0; ri < this._annotations.length; ri++) {
      var ann = this._annotations[ri];
      if (ann.type === 'element' && ann.data.selector === selector) {
        matching.push({ index: ri, annotation: ann });
      }
    }
    this._manageAnnotations = matching;
  };


  /* ── Commit Annotation ──────────────────────────────────────── */

  /**
   * Commit the pending annotation with a note and render its marker.
   * @param {string} note
   */
  AnnotationCanvas.prototype._commitAnnotation = function(note) {
    if (!this._pendingAnnotation) return;

    var annotation = {
      type: this._pendingAnnotation.type,
      note: note,
      data: this._pendingAnnotation.data
    };

    this._annotations.push(annotation);
    this._hasUnsavedChanges = true;
    this._pendingAnnotation = null;

    this._renderMarkers();
    this._updateCounter();
  };


  /* ── Markers ────────────────────────────────────────────────── */

  /**
   * Render all saved annotation markers in the markers container.
   * Clears and rebuilds.
   */
  AnnotationCanvas.prototype._renderMarkers = function() {
    if (!this._markersContainer) return;

    this._markersContainer.innerHTML = '';

    for (var i = 0; i < this._annotations.length; i++) {
      var ann = this._annotations[i];
      var markerEl = null;

      if (ann.type === 'element') {
        markerEl = document.createElement('div');
        markerEl.className = 'feedback-marker feedback-marker--rect';
        markerEl.style.left = ann.data.x + 'px';
        markerEl.style.top = ann.data.y + 'px';
        markerEl.style.width = ann.data.width + 'px';
        markerEl.style.height = ann.data.height + 'px';
        markerEl.setAttribute('title', 'Annotation ' + (i + 1) + ': ' + (ann.note || ''));
      } else if (ann.type === 'freehand') {
        // Render freehand path as an SVG
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'feedback-marker feedback-marker--freehand');
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '100%');
        svg.style.position = 'fixed';
        svg.style.inset = '0';
        svg.style.pointerEvents = 'none';
        svg.style.zIndex = '9005';

        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        var d = 'M ' + ann.data.path[0][0] + ' ' + ann.data.path[0][1];
        for (var j = 1; j < ann.data.path.length; j++) {
          d += ' L ' + ann.data.path[j][0] + ' ' + ann.data.path[j][1];
        }
        path.setAttribute('d', d);
        svg.appendChild(path);

        markerEl = svg;
      }

      if (markerEl) {
        this._markersContainer.appendChild(markerEl);
      }
    }
  };

  /**
   * Update the annotation counter badge.
   */
  AnnotationCanvas.prototype._updateCounter = function() {
    if (!this._markersContainer) return;

    // Remove existing counter
    if (this._counterEl && this._counterEl.parentNode) {
      this._counterEl.parentNode.removeChild(this._counterEl);
    }

    var count = this._annotations.length;
    var counter = document.createElement('div');
    counter.className = 'feedback-annotation-counter';
    counter.textContent = count + ' annotation' + (count !== 1 ? 's' : '');
    counter.setAttribute('aria-live', 'polite');

    this._markersContainer.appendChild(counter);
    this._counterEl = counter;
  };


  /* ── Screenshot Capture ─────────────────────────────────────── */

  /**
   * Capture the page as a PNG blob using window.htmlToImage.
   * Called ONLY at submit time.
   * @return {Promise<Blob|null>}
   */
  AnnotationCanvas.prototype._captureScreenshot = function() {
    var self = this;

    return new Promise(function(resolve) {
      if (typeof window.htmlToImage === 'undefined' || !window.htmlToImage.toPng) {
        self._showToast('Screenshot library not available, submitting without image', 'warning');
        resolve(null);
        return;
      }

      // Capture .app-main or fallback to body
      var target = document.querySelector('.app-main') || document.body;

      window.htmlToImage.toPng(target, { cacheBust: true })
        .then(function(dataUrl) {
          // Convert data URL to Blob
          var byteString = atob(dataUrl.split(',')[1]);
          var mimeString = 'image/png';
          var ab = new ArrayBuffer(byteString.length);
          var ia = new Uint8Array(ab);
          for (var i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
          }
          resolve(new Blob([ab], { type: mimeString }));
        })
        .catch(function() {
          self._showToast('Screenshot capture failed, submitting without image', 'warning');
          resolve(null);
        });
    });
  };


  /* ── Upload ─────────────────────────────────────────────────── */

  /**
   * Upload the report to /v1/feedback as multipart FormData.
   *
   * @param {Blob|null} screenshotBlob
   * @return {Promise<Object|null>}
   */
  AnnotationCanvas.prototype._uploadReport = function(screenshotBlob) {
    var formData = new FormData();
    formData.append('page_url', this._pageUrl);
    formData.append('viewport_width', String(window.innerWidth));
    formData.append('viewport_height', String(window.innerHeight));
    formData.append('reporter_id', 'default');
    formData.append('document_title', document.title);
    formData.append('user_agent', navigator.userAgent);

    // Build annotations array
    var annotations = [];
    for (var i = 0; i < this._annotations.length; i++) {
      var ann = this._annotations[i];
      annotations.push({
        type: ann.type,
        note: ann.note,
        data: ann.data
      });
    }
    formData.append('annotations', JSON.stringify(annotations));

    if (screenshotBlob) {
      formData.append('screenshot', screenshotBlob, 'screenshot.png');
    }

    var fetchFn = window.apiFetch || window.fetch;

    return fetchFn('/v1/feedback', {
      method: 'POST',
      body: formData
    }).then(function(response) {
      if (!response.ok) {
        return response.json().then(function(err) {
          throw new Error(err.detail || 'Server error');
        });
      }
      return response.json();
    }).then(function(data) {
      if (data && data.ok) {
        return data;
      }
      return data;
    });
  };


  /* ── Beforeunload ───────────────────────────────────────────── */

  /**
   * Set up beforeunload warning for unsaved changes.
   */
  AnnotationCanvas.prototype._setupBeforeUnload = function() {
    var self = this;
    this._onBoundBeforeUnload = function(e) {
      if (self._hasUnsavedChanges && self._annotationMode) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', this._onBoundBeforeUnload);
  };

  /**
   * Remove the beforeunload handler.
   */
  AnnotationCanvas.prototype._removeBeforeUnload = function() {
    if (this._onBoundBeforeUnload) {
      window.removeEventListener('beforeunload', this._onBoundBeforeUnload);
      this._onBoundBeforeUnload = null;
    }
  };


  /* ── Keyboard ────────────────────────────────────────────────── */

  /**
   * Handle keyboard events.
   */
  AnnotationCanvas.prototype._onKeydown = function(e) {
    // Escape closes note popup and discards pending annotation
    if (e.key === 'Escape') {
      if (this._notePopup) {
        if (this._manageSubMode) {
          // In edit/add sub-mode — return to list
          this._manageSubMode = null;
          this._manageEditingIdx = -1;
          this._rescanManageAnnotations();
          this._buildManageList(this._notePopup);
          return;
        }
        this._pendingAnnotation = null;
        this._removeNotePopup();
      }
      return;
    }

    // Ctrl+Z / Cmd+Z undo
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      e.preventDefault();
      this.undo();
      return;
    }

    // Ctrl+Enter / Cmd+Enter save note popup
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      if (this._notePopup) {
        var textarea = this._notePopup.querySelector('textarea');
        if (textarea) {
          var note = textarea.value.trim();
          if (note) {
            if (this._manageSubMode) {
              this._handleManageSave(note);
            } else {
              this._commitAnnotation(note);
              this._removeNotePopup();
            }
          }
        }
      }
    }
  };


  /* ── Toast ───────────────────────────────────────────────────── */

  /**
   * Show a toast notification.
   * @param {string} msg
   * @param {string} type  'success', 'error', 'info', 'warning'
   */
  AnnotationCanvas.prototype._showToast = function(msg, type) {
    type = type || 'info';
    var container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + (type === 'warning' ? 'error' : type);
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(function() {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(function() {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 300);
    }, 3000);
  };


  /* ── Public API ──────────────────────────────────────────────── */

  window.AnnotationCanvas = AnnotationCanvas;

  /**
   * Convenience factory — creates an AnnotationCanvas instance, calls
   * .init(), and returns it.
   *
   * @param {HTMLElement|string} containerOrSelector  Element or CSS selector.
   * @param {Object}             options               See AnnotationCanvas constructor.
   * @return {AnnotationCanvas}
   */
  window.initAnnotationMode = function(containerOrSelector, options) {
    var container = containerOrSelector;
    if (typeof containerOrSelector === 'string') {
      container = document.querySelector(containerOrSelector);
    }
    if (!container) {
      container = document.body;
    }
    options = options || {};
    var instance = new AnnotationCanvas(container, options);
    instance.init();
    return instance;
  };

})();