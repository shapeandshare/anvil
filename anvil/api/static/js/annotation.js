// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function() {
  'use strict';

  /**
   * AnnotationCanvas — manages the annotation overlay on a page element.
   *
   * Captures a screenshot of the target container, draws it onto a
   * canvas overlay, and provides methods for drawing element annotation
   * markers, managing notes, and submitting the report.
   *
   * @param {HTMLElement} container  The DOM element to annotate over.
   * @param {Object}      options    Optional configuration.
   * @param {string}      options.accentColor  Override accent colour (default reads from CSS).
   * @param {string}      options.pageUrl      Override page URL (defaults to window.location.href).
   * @param {function}    options.onSubmit     Callback after successful submission.
   * @param {function}    options.onClose      Callback when annotation mode is closed.
   */
  function AnnotationCanvas(container, options) {
    if (!container) throw new Error('AnnotationCanvas requires a container element');

    this.container = container;
    this.options = options || {};
    this._markers = [];
    this._activeTool = null;
    this._isDrawing = false;
    this._isAnnotating = false;
    this._overlayEl = null;
    this._canvasEl = null;
    this._ctx = null;
    this._screenshotDataUrl = null;
    this._notePopup = null;
    this._currentTarget = null;
    this._hasUnsavedChanges = false;
    this._toolbarEl = null;
    this._toggleBtn = null;
    this._annotationMode = false;

    // Drawing state
    this._drawStart = null;
    this._drawCurrent = null;
    this._drawPath = null;
    this._drawingType = null;
    this._onBoundMouseDown = null;
    this._onBoundMouseMove = null;
    this._onBoundMouseUp = null;

    // Review panel
    this._reviewPanel = null;
    this._selectedMarkerIndex = -1;

    this._accentColor = this.options.accentColor || '';
    this._pageUrl = this.options.pageUrl || window.location.href;

    this._onBoundClick = null;
    this._onBoundKeydown = null;
    this._onBoundBeforeUnload = null;

    this._initColors();
  }

  /**
   * Read CSS custom properties for accent colour.
   */
  AnnotationCanvas.prototype._initColors = function() {
    if (!this._accentColor) {
      var style = getComputedStyle(document.documentElement);
      this._accentColor = style.getPropertyValue('--accent').trim() || '#007aff';
    }
  };

  /**
   * Build the overlay DOM structure (backdrop + canvas) and append it
   * to the document body.
   */
  AnnotationCanvas.prototype._createOverlay = function() {
    var overlay = document.createElement('div');
    overlay.className = 'feedback-annotation-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Annotation overlay');

    var canvas = document.createElement('canvas');
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    overlay.appendChild(canvas);

    this._overlayEl = overlay;
    this._canvasEl = canvas;
    this._ctx = canvas.getContext('2d');
  };

  /**
   * Capture a screenshot of the target container using html-to-image
   * (window.htmlToImage), then initialise the canvas with the result.
   *
   * Falls back to a blank canvas if the library is unavailable.
   *
   * @return {Promise<void>}
   */
  AnnotationCanvas.prototype._captureScreenshot = function() {
    var self = this;
    var el = this.container;

    return new Promise(function(resolve) {
      if (typeof window.htmlToImage !== 'undefined' && window.htmlToImage.toPng) {
        window.htmlToImage.toPng(el, { useCORS: true, cacheBust: true })
          .then(function(dataUrl) {
            self._screenshotDataUrl = dataUrl;
            self._initCanvas(dataUrl);
            resolve();
          })
          .catch(function() {
            self._showToast('Screenshot capture failed, using blank canvas', 'error');
            self._initCanvas(null);
            resolve();
          });
      } else {
        self._showToast('Screenshot library not available', 'error');
        self._initCanvas(null);
        resolve();
      }
    });
  };

  /**
   * Initialise the canvas with the screenshot image (or a solid fill
   * if no image is available), applying DPR scaling.
   *
   * @param {string|null} dataUrl  PNG data URL, or null for a blank canvas.
   */
  AnnotationCanvas.prototype._initCanvas = function(dataUrl) {
    var dpr = window.devicePixelRatio || 1;
    var w = window.innerWidth;
    var h = window.innerHeight;
    var img, self, style, bgColor;

    this._canvasEl.width = w * dpr;
    this._canvasEl.height = h * dpr;
    this._canvasEl.style.width = w + 'px';
    this._canvasEl.style.height = h + 'px';
    this._ctx.scale(dpr, dpr);

    if (dataUrl) {
      img = new Image();
      self = this;
      img.onload = function() {
        self._ctx.drawImage(img, 0, 0, w, h);
        self._drawExistingMarkers();
      };
      img.src = dataUrl;
    } else {
      style = getComputedStyle(document.documentElement);
      bgColor = style.getPropertyValue('--bg').trim() || '#000000';
      this._ctx.fillStyle = bgColor;
      this._ctx.fillRect(0, 0, w, h);
      this._drawExistingMarkers();
    }
  };

  /**
   * Re-draw all stored markers on the canvas.
   */
  AnnotationCanvas.prototype._drawExistingMarkers = function() {
    var ctx = this._ctx;
    var markers = this._markers;
    for (var i = 0; i < markers.length; i++) {
      this._drawMarker(ctx, markers[i]);
    }
  };

  /**
   * Draw a single annotation marker on the canvas.
   * Supports element (circle badge), circle (outlined arc), and
   * freehand (stroked path) types.
   *
   * @param {CanvasRenderingContext2D} ctx
   * @param {Object} marker  Marker object with type, note, order, data.
   */
  AnnotationCanvas.prototype._drawMarker = function(ctx, marker) {
    var index = marker.order !== undefined ? marker.order + 1 : 1;

    if (marker.type === 'circle') {
      this._drawCircleMarker(ctx, marker, index);
    } else if (marker.type === 'freehand') {
      this._drawFreehandMarker(ctx, marker, index);
    } else {
      this._drawElementMarker(ctx, marker, index);
    }
  };

  /**
   * Draw an element-type marker (circle badge with number).
   */
  AnnotationCanvas.prototype._drawElementMarker = function(ctx, marker, index) {
    var cx = marker.x;
    var cy = marker.y;
    var radius = 12;

    ctx.beginPath();
    ctx.arc(cx, cy, radius + 3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 122, 255, 0.2)';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = this._accentColor;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(index), cx, cy);
  };

  /**
   * Draw a circle-type annotation (outlined arc with center badge).
   */
  AnnotationCanvas.prototype._drawCircleMarker = function(ctx, marker, index) {
    var data = marker.data;
    var cx = marker.x, cy = marker.y, radius = 20;
    if (typeof data === 'string') {
      try { var parsed = JSON.parse(data); cx = parsed.cx !== undefined ? parsed.cx : cx; cy = parsed.cy !== undefined ? parsed.cy : cy; radius = parsed.radius !== undefined ? parsed.radius : radius; } catch(e) {}
    } else if (data) {
      cx = data.cx !== undefined ? data.cx : cx;
      cy = data.cy !== undefined ? data.cy : cy;
      radius = data.radius !== undefined ? data.radius : radius;
    }

    // Filled circle annotation
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 122, 255, 0.1)';
    ctx.fill();
    ctx.strokeStyle = this._accentColor;
    ctx.lineWidth = 2.5;
    ctx.setLineDash([6, 3]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Center badge
    ctx.beginPath();
    ctx.arc(cx, cy, 12, 0, Math.PI * 2);
    ctx.fillStyle = this._accentColor;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(index), cx, cy);
  };

  /**
   * Draw a freehand-type annotation (stroked path with start badge).
   */
  AnnotationCanvas.prototype._drawFreehandMarker = function(ctx, marker, index) {
    var data = marker.data;
    var path = null;
    if (typeof data === 'string') {
      try { var parsed = JSON.parse(data); path = parsed.path; } catch(e) {}
    } else if (data) {
      path = data.path;
    }

    if (path && path.length > 0) {
      ctx.beginPath();
      ctx.moveTo(path[0][0], path[0][1]);
      for (var i = 1; i < path.length; i++) {
        ctx.lineTo(path[i][0], path[i][1]);
      }
      ctx.strokeStyle = this._accentColor;
      ctx.lineWidth = 2.5;
      ctx.stroke();
    }

    // Start badge
    var sx = path ? path[0][0] : (marker.x || 0);
    var sy = path ? path[0][1] : (marker.y || 0);
    ctx.beginPath();
    ctx.arc(sx, sy, 12, 0, Math.PI * 2);
    ctx.fillStyle = this._accentColor;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(index), sx, sy);
  };

  /**
   * Set the active drawing tool.
   *
   * @param {string|null} tool  Tool name or null to deactivate.
   */
  AnnotationCanvas.prototype.setTool = function(tool) {
    this._activeTool = tool;
    this._overlayEl.style.cursor = tool ? 'crosshair' : 'default';
  };

  /**
   * Open the annotation overlay and capture the screenshot.
   *
   * @return {Promise<void>}
   */
  AnnotationCanvas.prototype.open = function() {
    var self = this;
    document.body.appendChild(this._overlayEl);
    this._isAnnotating = true;
    return this._captureScreenshot().then(function() {
      self._bindCanvasEvents();
    });
  };

  /**
   * Close the annotation overlay and remove it from the DOM.
   */
  AnnotationCanvas.prototype.close = function() {
    if (this._overlayEl && this._overlayEl.parentNode) {
      this._overlayEl.parentNode.removeChild(this._overlayEl);
    }
    this._isAnnotating = false;
    this.setTool(null);
    this._removeNotePopup();
    this._removeReviewPanel();
    this._unbindCanvasEvents();
  };

  /**
   * Get the current marker data for serialisation.
   *
   * @return {Array<Object>}  Array of marker objects.
   */
  AnnotationCanvas.prototype.getMarkers = function() {
    return this._markers.slice();
  };

  /**
   * Clear all markers and reset the canvas.
   */
  AnnotationCanvas.prototype.clear = function() {
    this._markers = [];
    this._hasUnsavedChanges = true;
    if (this._screenshotDataUrl) {
      this._initCanvas(this._screenshotDataUrl);
    } else {
      this._initCanvas(null);
    }
  };

  /**
   * Remove the last marker (undo).
   */
  AnnotationCanvas.prototype.undo = function() {
    if (this._markers.length === 0) return;
    this._markers.pop();
    this._hasUnsavedChanges = true;
    if (this._screenshotDataUrl) {
      this._initCanvas(this._screenshotDataUrl);
    } else {
      this._initCanvas(null);
    }
  };

  /**
   * Destroy the annotation canvas and clean up.
   */
  AnnotationCanvas.prototype.destroy = function() {
    this.close();
    this._markers = [];
    this._screenshotDataUrl = null;
    this._canvasEl = null;
    this._ctx = null;
    this._overlayEl = null;
    this._removeToolbar();
    this._removeToggleButton();
    this._removeBeforeUnload();
  };

  /**
   * Bind canvas click, drawing, and keydown events.
   */
  AnnotationCanvas.prototype._bindCanvasEvents = function() {
    var self = this;

    this._onBoundClick = function(e) {
      self._onCanvasClick(e);
    };
    this._onBoundKeydown = function(e) {
      self._onKeydown(e);
    };
    this._onBoundMouseDown = function(e) {
      self._onCanvasMouseDown(e);
    };
    this._onBoundMouseMove = function(e) {
      self._onCanvasMouseMove(e);
    };
    this._onBoundMouseUp = function(e) {
      self._onCanvasMouseUp(e);
    };

    this._canvasEl.addEventListener('click', this._onBoundClick);
    this._canvasEl.addEventListener('mousedown', this._onBoundMouseDown);
    this._canvasEl.addEventListener('mousemove', this._onBoundMouseMove);
    this._canvasEl.addEventListener('mouseup', this._onBoundMouseUp);
    document.addEventListener('keydown', this._onBoundKeydown);
  };

  /**
   * Unbind canvas click, drawing, and keydown events.
   */
  AnnotationCanvas.prototype._unbindCanvasEvents = function() {
    if (this._onBoundClick) {
      this._canvasEl.removeEventListener('click', this._onBoundClick);
    }
    if (this._onBoundMouseDown) {
      this._canvasEl.removeEventListener('mousedown', this._onBoundMouseDown);
    }
    if (this._onBoundMouseMove) {
      this._canvasEl.removeEventListener('mousemove', this._onBoundMouseMove);
    }
    if (this._onBoundMouseUp) {
      this._canvasEl.removeEventListener('mouseup', this._onBoundMouseUp);
    }
    if (this._onBoundKeydown) {
      document.removeEventListener('keydown', this._onBoundKeydown);
    }
  };

  /**
   * Handle canvas click — detect the element under cursor in annotation
   * mode, highlight it, and show the note input popup.
   * Only fires for the 'element' tool; circle/freehand use drawing.
   */
  AnnotationCanvas.prototype._onCanvasClick = function(e) {
    // Ignore clicks on note popup or toolbar
    if (this._notePopup && this._notePopup.contains(e.target)) return;
    if (this._toolbarEl && this._toolbarEl.contains(e.target)) return;

    // For circle/freehand tools, clicking is handled by drawing events
    if (this._activeTool === 'circle' || this._activeTool === 'freehand') {
      return;
    }

    // If in review mode (no active tool), check for click on existing marker
    if (!this._activeTool) {
      this._handleMarkerClick(e);
      return;
    }

    this._removeNotePopup();

    var rect = this._canvasEl.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;

    // Save the clicked position
    this._currentTarget = { x: x, y: y };

    // Draw a temporary highlight
    this._drawTemporaryHighlight(x, y);

    // Show note input popup
    this._showNotePopup(x, y);
  };

  /**
   * Handle mousedown on the canvas for circle/freehand drawing.
   */
  AnnotationCanvas.prototype._onCanvasMouseDown = function(e) {
    if (this._activeTool !== 'circle' && this._activeTool !== 'freehand') return;
    if (this._notePopup && this._notePopup.contains(e.target)) return;
    if (this._toolbarEl && this._toolbarEl.contains(e.target)) return;

    this._removeNotePopup();

    var rect = this._canvasEl.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;

    this._isDrawing = true;
    this._drawStart = { x: x, y: y };
    this._drawCurrent = { x: x, y: y };
    this._drawingType = this._activeTool;

    if (this._activeTool === 'freehand') {
      this._drawPath = [{ x: x, y: y }];
    }

    this._drawPreview();
  };

  /**
   * Handle mousemove on the canvas for drawing preview.
   */
  AnnotationCanvas.prototype._onCanvasMouseMove = function(e) {
    if (!this._isDrawing) return;
    if (this._activeTool !== 'circle' && this._activeTool !== 'freehand') return;

    var rect = this._canvasEl.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;

    this._drawCurrent = { x: x, y: y };

    if (this._activeTool === 'freehand' && this._drawPath) {
      this._drawPath.push({ x: x, y: y });
    }

    this._drawPreview();
  };

  /**
   * Handle mouseup on the canvas to finalize drawing.
   */
  AnnotationCanvas.prototype._onCanvasMouseUp = function(e) {
    if (!this._isDrawing) return;
    if (this._activeTool !== 'circle' && this._activeTool !== 'freehand') return;

    this._isDrawing = false;

    var rect = this._canvasEl.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;
    this._drawCurrent = { x: x, y: y };

    // Finalize the drawing
    if (this._drawingType === 'circle') {
      var dx = this._drawCurrent.x - this._drawStart.x;
      var dy = this._drawCurrent.y - this._drawStart.y;
      var radius = Math.round(Math.sqrt(dx * dx + dy * dy));
      this._currentTarget = {
        type: 'circle',
        cx: Math.round(this._drawStart.x),
        cy: Math.round(this._drawStart.y),
        radius: radius,
      };
    } else if (this._drawingType === 'freehand' && this._drawPath) {
      var path = this._drawPath.map(function(p) { return [Math.round(p.x), Math.round(p.y)]; });
      var xs = path.map(function(p) { return p[0]; });
      var ys = path.map(function(p) { return p[1]; });
      var minX = Math.min.apply(null, xs);
      var maxX = Math.max.apply(null, xs);
      var minY = Math.min.apply(null, ys);
      var maxY = Math.max.apply(null, ys);
      this._currentTarget = {
        type: 'freehand',
        path: path,
        bounds: { minX: minX, minY: minY, maxX: maxX, maxY: maxY },
      };
    }

    this._drawStart = null;
    this._drawCurrent = null;
    this._drawPath = null;
    this._drawingType = null;

    // Show the note popup for the finalized annotation
    if (this._currentTarget) {
      this._showNotePopup(this._currentTarget.cx || this._currentTarget.path[0][0] || 0,
                          this._currentTarget.cy || this._currentTarget.path[0][1] || 0);
    }
  };

  /**
   * Draw a preview of the current shape while dragging.
   */
  AnnotationCanvas.prototype._drawPreview = function() {
    var ctx = this._ctx;

    // Re-draw the base image
    if (this._screenshotDataUrl) {
      var img = new Image();
      var self = this;
      img.onload = function() {
        var dpr = window.devicePixelRatio || 1;
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, self._canvasEl.width, self._canvasEl.height);
        ctx.restore();
        ctx.drawImage(img, 0, 0, window.innerWidth, window.innerHeight);
        self._drawExistingMarkers();
        self._renderPreviewShape(ctx);
      };
      img.src = this._screenshotDataUrl;
    } else {
      this._drawExistingMarkers();
      this._renderPreviewShape(ctx);
    }
  };

  /**
   * Render the preview shape (circle or freehand path) on the canvas.
   */
  AnnotationCanvas.prototype._renderPreviewShape = function(ctx) {
    if (!this._drawStart || !this._drawCurrent) return;

    ctx.save();
    ctx.strokeStyle = this._accentColor;
    ctx.lineWidth = 2.5;
    ctx.setLineDash([6, 4]);
    ctx.fillStyle = 'rgba(0, 122, 255, 0.08)';

    if (this._activeTool === 'circle' || this._drawingType === 'circle') {
      var dx = this._drawCurrent.x - this._drawStart.x;
      var dy = this._drawCurrent.y - this._drawStart.y;
      var radius = Math.sqrt(dx * dx + dy * dy);
      ctx.beginPath();
      ctx.arc(this._drawStart.x, this._drawStart.y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else if ((this._activeTool === 'freehand' || this._drawingType === 'freehand') && this._drawPath) {
      ctx.beginPath();
      ctx.moveTo(this._drawPath[0].x, this._drawPath[0].y);
      for (var i = 1; i < this._drawPath.length; i++) {
        ctx.lineTo(this._drawPath[i].x, this._drawPath[i].y);
      }
      ctx.stroke();
    }

    ctx.setLineDash([]);
    ctx.restore();
  };

  /**
   * Handle click on an existing annotation marker to show its note.
   */
  AnnotationCanvas.prototype._handleMarkerClick = function(e) {
    var rect = this._canvasEl.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;

    for (var i = 0; i < this._markers.length; i++) {
      var m = this._markers[i];
      var hit = false;
      if (m.type === 'element') {
        var dx = x - m.x;
        var dy = y - m.y;
        hit = (dx * dx + dy * dy) < 400; // within 20px
      } else if (m.type === 'circle') {
        var data = m.data;
        if (typeof data === 'string') { try { data = JSON.parse(data); } catch(e) { data = {}; } }
        var cx = data.cx !== undefined ? data.cx : (m.x || 0);
        var cy = data.cy !== undefined ? data.cy : (m.y || 0);
        var r = data.radius || 20;
        var dx2 = x - cx;
        var dy2 = y - cy;
        var dist = Math.sqrt(dx2 * dx2 + dy2 * dy2);
        hit = Math.abs(dist - r) < 15;
      } else if (m.type === 'freehand') {
        var data2 = m.data;
        if (typeof data2 === 'string') { try { data2 = JSON.parse(data2); } catch(e) { data2 = {}; } }
        var bounds = data2.bounds;
        if (bounds) {
          hit = x >= bounds.minX && x <= bounds.maxX && y >= bounds.minY && y <= bounds.maxY;
        }
      }

      if (hit) {
        this._selectedMarkerIndex = i;
        this._showAnnotationEditPopup(m, i);
        return;
      }
    }
  };

  /**
   * Show an edit popup for an existing annotation.
   */
  AnnotationCanvas.prototype._showAnnotationEditPopup = function(marker, index) {
    var self = this;
    this._removeNotePopup();

    var popup = document.createElement('div');
    popup.className = 'feedback-note-popup';
    var displayX = marker.type === 'circle' ? 0 : (marker.x || 0);
    var displayY = marker.type === 'circle' ? 0 : (marker.y || 0);

    var offsetX = Math.min(displayX + 20, window.innerWidth - 280);
    var offsetY = Math.min(displayY + 20, window.innerHeight - 220);
    popup.style.left = Math.max(10, offsetX) + 'px';
    popup.style.top = Math.max(10, offsetY) + 'px';

    var typeLabel = document.createElement('div');
    typeLabel.style.cssText = 'font-size:11px;color:var(--text-tertiary);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px;';
    typeLabel.textContent = marker.type + ' annotation';
    popup.appendChild(typeLabel);

    var textarea = document.createElement('textarea');
    textarea.className = 'feedback-note-popup__textarea';
    textarea.value = marker.note || '';
    textarea.maxLength = 2000;
    textarea.placeholder = 'Edit annotation note... (2000 char max)';
    textarea.setAttribute('aria-label', 'Edit annotation note');
    popup.appendChild(textarea);

    var charCount = document.createElement('div');
    charCount.style.cssText = 'font-size:11px;color:var(--text-tertiary);text-align:right;margin-top:4px;';
    charCount.textContent = (marker.note || '').length + ' / 2000';
    popup.appendChild(charCount);

    textarea.addEventListener('input', function() {
      charCount.textContent = textarea.value.length + ' / 2000';
    });

    var actions = document.createElement('div');
    actions.className = 'feedback-note-popup__actions';

    var deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'btn btn--danger';
    deleteBtn.textContent = 'Delete';
    deleteBtn.setAttribute('aria-label', 'Delete annotation');

    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn--ghost';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.setAttribute('aria-label', 'Cancel edit');

    var saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn--primary';
    saveBtn.textContent = 'Save';
    saveBtn.setAttribute('aria-label', 'Save annotation');

    deleteBtn.addEventListener('click', function() {
      self._markers.splice(index, 1);
      // Re-order remaining markers
      for (var i = index; i < self._markers.length; i++) {
        self._markers[i].order = i;
      }
      self._hasUnsavedChanges = true;
      self._removeNotePopup();
      self._redrawCanvas();
      self._renderReviewPanel();
      self._showToast('Annotation deleted', 'info');
    });

    cancelBtn.addEventListener('click', function() {
      self._removeNotePopup();
      self._selectedMarkerIndex = -1;
    });

    saveBtn.addEventListener('click', function() {
      var note = textarea.value.trim();
      marker.note = note || null;
      self._hasUnsavedChanges = true;
      self._removeNotePopup();
      self._selectedMarkerIndex = -1;
      self._redrawCanvas();
      self._renderReviewPanel();
      self._showToast('Annotation updated', 'success');
    });

    actions.appendChild(deleteBtn);
    actions.appendChild(cancelBtn);
    actions.appendChild(saveBtn);
    popup.appendChild(actions);

    this._overlayEl.appendChild(popup);
    this._notePopup = popup;

    setTimeout(function() {
      textarea.focus();
    }, 100);
  };

  /**
   * Create and show the annotation review panel.
   */
  AnnotationCanvas.prototype._createReviewPanel = function() {
    if (this._reviewPanel) {
      this._reviewPanel.parentNode.removeChild(this._reviewPanel);
    }

    var panel = document.createElement('div');
    panel.className = 'feedback-review-panel';
    panel.setAttribute('role', 'region');
    panel.setAttribute('aria-label', 'Annotation review panel');

    var header = document.createElement('div');
    header.className = 'feedback-review-panel__header';
    header.textContent = 'Annotations (' + this._markers.length + ')';
    panel.appendChild(header);

    if (this._markers.length === 0) {
      var empty = document.createElement('div');
      empty.className = 'feedback-review-panel__empty';
      empty.textContent = 'No annotations yet';
      panel.appendChild(empty);
    } else {
      var list = document.createElement('div');
      list.className = 'feedback-review-panel__list';
      list.setAttribute('role', 'list');
      panel.appendChild(list);
    }

    this._overlayEl.appendChild(panel);
    this._reviewPanel = panel;
    this._renderReviewPanel();
  };

  /**
   * Render the annotation review panel content.
   */
  AnnotationCanvas.prototype._renderReviewPanel = function() {
    if (!this._reviewPanel) return;

    var panel = this._reviewPanel;
    var header = panel.querySelector('.feedback-review-panel__header');
    if (header) {
      header.textContent = 'Annotations (' + this._markers.length + ')';
    }

    var list = panel.querySelector('.feedback-review-panel__list');
    if (!list) return;

    // Clear existing items
    while (list.firstChild) {
      list.removeChild(list.firstChild);
    }

    if (this._markers.length === 0) {
      var empty = panel.querySelector('.feedback-review-panel__empty');
      if (!empty) {
        empty = document.createElement('div');
        empty.className = 'feedback-review-panel__empty';
        panel.appendChild(empty);
      }
      empty.textContent = 'No annotations yet';
      return;
    }

    var self = this;
    for (var i = 0; i < this._markers.length; i++) {
      var m = this._markers[i];
      var item = document.createElement('div');
      item.className = 'feedback-review-panel__item' + (this._selectedMarkerIndex === i ? ' feedback-review-panel__item--selected' : '');
      item.setAttribute('role', 'listitem');
      item.setAttribute('tabindex', '0');
      item.setAttribute('aria-label', m.type + ' annotation: ' + (m.note || 'no note'));

      // Type icon
      var icon = document.createElement('span');
      icon.className = 'feedback-review-panel__icon';
      var iconSvg = '';
      if (m.type === 'circle') {
        iconSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>';
      } else if (m.type === 'freehand') {
        iconSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M3 17c3-4 6-1 8-3s4-5 6-6 4 2 3 5-5 10-8 11-5-2-3-5"/></svg>';
      } else {
        iconSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>';
      }
      icon.innerHTML = iconSvg;
      item.appendChild(icon);

      // Note preview
      var noteEl = document.createElement('span');
      noteEl.className = 'feedback-review-panel__note';
      noteEl.textContent = m.note || '(no note)';
      item.appendChild(noteEl);

      // Delete button
      var delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'feedback-review-panel__delete';
      delBtn.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      delBtn.setAttribute('aria-label', 'Delete annotation ' + (i + 1));
      delBtn.setAttribute('title', 'Delete');

      (function(idx) {
        delBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          self._markers.splice(idx, 1);
          for (var j = idx; j < self._markers.length; j++) {
            self._markers[j].order = j;
          }
          self._hasUnsavedChanges = true;
          self._redrawCanvas();
          self._renderReviewPanel();
          self._showToast('Annotation deleted', 'info');
        });

        item.addEventListener('click', function() {
          self._selectedMarkerIndex = idx;
          self._showAnnotationEditPopup(self._markers[idx], idx);
          self._renderReviewPanel();
        });
      })(i);

      item.appendChild(delBtn);
      list.appendChild(item);
    }
  };

  /**
   * Remove the review panel from the DOM.
   */
  AnnotationCanvas.prototype._removeReviewPanel = function() {
    if (this._reviewPanel && this._reviewPanel.parentNode) {
      this._reviewPanel.parentNode.removeChild(this._reviewPanel);
    }
    this._reviewPanel = null;
    this._selectedMarkerIndex = -1;
  };

  /**
   * Draw a temporary highlight circle at the clicked position.
   */
  AnnotationCanvas.prototype._drawTemporaryHighlight = function(x, y) {
    var ctx = this._ctx;

    // Re-draw the base image first
    if (this._screenshotDataUrl) {
      var img = new Image();
      var self = this;
      img.onload = function() {
        var dpr = window.devicePixelRatio || 1;
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, self._canvasEl.width, self._canvasEl.height);
        ctx.restore();
        ctx.drawImage(img, 0, 0, window.innerWidth, window.innerHeight);
        self._drawExistingMarkers();

        // Pulsing highlight
        ctx.beginPath();
        ctx.arc(x, y, 20, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 122, 255, 0.15)';
        ctx.fill();
        ctx.strokeStyle = self._accentColor;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      };
      img.src = this._screenshotDataUrl;
    } else {
      this._drawExistingMarkers();
      ctx.beginPath();
      ctx.arc(x, y, 20, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 122, 255, 0.15)';
      ctx.fill();
      ctx.strokeStyle = this._accentColor;
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  };

  /**
   * Show the note input popup at the given position.
   *
   * @param {number} x  X position relative to canvas.
   * @param {number} y  Y position relative to canvas.
   */
  AnnotationCanvas.prototype._showNotePopup = function(x, y) {
    var self = this;
    this._removeNotePopup();

    var popup = document.createElement('div');
    popup.className = 'feedback-note-popup';

    // Position the popup near the click, offset to avoid covering the marker
    var offsetX = Math.min(x + 20, window.innerWidth - 240);
    var offsetY = Math.min(y + 20, window.innerHeight - 180);
    popup.style.left = Math.max(10, offsetX) + 'px';
    popup.style.top = Math.max(10, offsetY) + 'px';

    var textarea = document.createElement('textarea');
    textarea.className = 'feedback-note-popup__textarea';
    textarea.maxLength = 2000;
    textarea.placeholder = 'Describe the issue... (2000 char max)';
    textarea.setAttribute('aria-label', 'Annotation note');
    popup.appendChild(textarea);

    var charCount = document.createElement('div');
    charCount.style.cssText = 'font-size:11px;color:var(--text-tertiary);text-align:right;margin-top:4px;';
    charCount.textContent = '0 / 2000';
    popup.appendChild(charCount);

    textarea.addEventListener('input', function() {
      charCount.textContent = textarea.value.length + ' / 2000';
    });

    var actions = document.createElement('div');
    actions.className = 'feedback-note-popup__actions';

    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn--ghost';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.setAttribute('aria-label', 'Cancel annotation');

    var confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = 'btn btn--primary';
    confirmBtn.textContent = 'Confirm';
    confirmBtn.setAttribute('aria-label', 'Confirm annotation');

    cancelBtn.addEventListener('click', function() {
      self._removeNotePopup();
      self._currentTarget = null;
      // Re-draw to remove the temporary highlight
      self._redrawCanvas();
    });

    confirmBtn.addEventListener('click', function() {
      var note = textarea.value.trim();
      self._addAnnotation(note);
      self._removeNotePopup();
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    popup.appendChild(actions);

    this._overlayEl.appendChild(popup);
    this._notePopup = popup;

    // Focus the textarea after a short delay
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
  };

  /**
   * Add an annotation marker with the given note.
   * Supports element, circle, and freehand types.
   *
   * @param {string} note  The annotation note text.
   */
  AnnotationCanvas.prototype._addAnnotation = function(note) {
    if (!this._currentTarget) return;
    if (!note) {
      this._showToast('Please enter a note', 'error');
      return;
    }

    var target = this._currentTarget;
    var marker;

    if (target.type === 'circle') {
      marker = {
        type: 'circle',
        x: target.cx,
        y: target.cy,
        note: note,
        order: this._markers.length,
        data: JSON.stringify({
          cx: target.cx,
          cy: target.cy,
          radius: target.radius,
        }),
      };
    } else if (target.type === 'freehand') {
      marker = {
        type: 'freehand',
        x: target.path[0][0],
        y: target.path[0][1],
        note: note,
        order: this._markers.length,
        data: JSON.stringify({
          path: target.path,
          bounds: target.bounds,
        }),
      };
    } else {
      marker = {
        type: 'element',
        x: Math.round(target.x),
        y: Math.round(target.y),
        note: note,
        order: this._markers.length,
        data: JSON.stringify({
          x: Math.round(target.x),
          y: Math.round(target.y),
          note: note,
        }),
      };
    }

    this._markers.push(marker);
    this._hasUnsavedChanges = true;
    this._currentTarget = null;

    // Re-draw canvas with all markers
    this._redrawCanvas();
    this._renderReviewPanel();
  };

  /**
   * Re-draw the canvas with the screenshot and all markers.
   */
  AnnotationCanvas.prototype._redrawCanvas = function() {
    if (this._screenshotDataUrl) {
      this._initCanvas(this._screenshotDataUrl);
    } else {
      this._initCanvas(null);
    }
  };

  /**
   * Handle keyboard events — Escape to close popup, Ctrl+Z to undo.
   */
  AnnotationCanvas.prototype._onKeydown = function(e) {
    if (e.key === 'Escape') {
      if (this._notePopup) {
        this._removeNotePopup();
        this._currentTarget = null;
        this._redrawCanvas();
      }
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      e.preventDefault();
      this.undo();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      // Submit via Ctrl+Enter when popup is open
      if (this._notePopup) {
        var textarea = this._notePopup.querySelector('textarea');
        if (textarea) {
          var note = textarea.value.trim();
          this._addAnnotation(note);
          this._removeNotePopup();
        }
      }
    }
  };

  /**
   * Serialize annotations as JSON and submit the report to /v1/feedback.
   *
   * Posts the screenshot as a file, page metadata, and annotations as
   * JSON. Handles success and error cases.
   */
  AnnotationCanvas.prototype.submit = function() {
    var self = this;

    if (this._markers.length === 0) {
      this._showToast('No annotations to submit', 'error');
      return Promise.resolve(null);
    }

    this._showToast('Submitting report...', 'info');

    return this._captureScreenshotForUpload().then(function(screenshotBlob) {
      return self._uploadReport(screenshotBlob);
    }).then(function(result) {
      if (result) {
        self._hasUnsavedChanges = false;
        self._removeBeforeUnload();
        if (self.options.onSubmit) {
          self.options.onSubmit(result);
        }
      }
      return result;
    }).catch(function(err) {
      self._showToast('Failed to submit: ' + (err.message || 'Network error'), 'error');
      throw err;
    });
  };

  /**
   * Capture the current annotated canvas as a PNG blob for upload.
   *
   * @return {Promise<Blob|null>}
   */
  AnnotationCanvas.prototype._captureScreenshotForUpload = function() {
    var self = this;

    if (this._screenshotDataUrl) {
      // Use the existing screenshot data URL
      return new Promise(function(resolve) {
        var img = new Image();
        img.onload = function() {
          var dpr = window.devicePixelRatio || 1;
          var w = window.innerWidth;
          var h = window.innerHeight;
          var captureCanvas = document.createElement('canvas');
          captureCanvas.width = w * dpr;
          captureCanvas.height = h * dpr;
          var captureCtx = captureCanvas.getContext('2d');
          captureCtx.scale(dpr, dpr);
          captureCtx.drawImage(img, 0, 0, w, h);

          // Draw markers on top
          for (var i = 0; i < self._markers.length; i++) {
            self._drawMarker(captureCtx, self._markers[i]);
          }

          captureCanvas.toBlob(function(blob) {
            resolve(blob);
          }, 'image/png');
        };
        img.src = self._screenshotDataUrl;
      });
    }

    // Fallback: capture container again
    return new Promise(function(resolve) {
      if (typeof window.htmlToImage !== 'undefined' && window.htmlToImage.toPng) {
        window.htmlToImage.toPng(self.container, { useCORS: true, cacheBust: true })
          .then(function(dataUrl) {
            var img = new Image();
            img.onload = function() {
              var captureCanvas = document.createElement('canvas');
              captureCanvas.width = img.width;
              captureCanvas.height = img.height;
              var captureCtx = captureCanvas.getContext('2d');
              captureCtx.drawImage(img, 0, 0);
              captureCanvas.toBlob(function(blob) {
                resolve(blob);
              }, 'image/png');
            };
            img.src = dataUrl;
          })
          .catch(function() {
            resolve(null);
          });
      } else {
        resolve(null);
      }
    });
  };

  /**
   * Upload the report to the server via POST /v1/feedback.
   *
   * @param {Blob|null} screenshotBlob  The screenshot PNG blob.
   * @return {Promise<Object|null>}
   */
  AnnotationCanvas.prototype._uploadReport = function(screenshotBlob) {
    var formData = new FormData();
    formData.append('page_url', this._pageUrl);
    formData.append('viewport_width', String(window.innerWidth));
    formData.append('viewport_height', String(window.innerHeight));
    formData.append('reporter_id', 'default');

    if (this._markers.length > 0) {
      var annotations = [];
      for (var i = 0; i < this._markers.length; i++) {
        annotations.push({
          type: this._markers[i].type,
          note: this._markers[i].note,
          data: this._markers[i].data,
        });
      }
      formData.append('annotations', JSON.stringify(annotations));
    }

    if (screenshotBlob) {
      formData.append('screenshot', screenshotBlob, 'screenshot.png');
    }

    var fetchFn = window.apiFetch || window.fetch;

    return fetchFn('/v1/feedback', {
      method: 'POST',
      body: formData,
    }).then(function(response) {
      if (!response.ok) {
        return response.json().then(function(err) {
          throw new Error(err.detail || 'Server error');
        });
      }
      return response.json();
    }).then(function(data) {
      if (data.ok) {
        self._showToast('Report submitted successfully', 'success');
      }
      return data;
    });
  };

  /**
   * Set up the beforeunload event to warn about unsaved changes.
   */
  AnnotationCanvas.prototype._setupBeforeUnload = function() {
    var self = this;
    this._onBoundBeforeUnload = function(e) {
      if (self._hasUnsavedChanges && self._isAnnotating) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', this._onBoundBeforeUnload);
  };

  /**
   * Remove the beforeunload event.
   */
  AnnotationCanvas.prototype._removeBeforeUnload = function() {
    if (this._onBoundBeforeUnload) {
      window.removeEventListener('beforeunload', this._onBoundBeforeUnload);
      this._onBoundBeforeUnload = null;
    }
  };

  /**
   * Show a toast notification.
   *
   * @param {string} msg   The message to display.
   * @param {string} type  The toast type: 'success', 'error', 'info'.
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
    toast.className = 'toast toast-' + type;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(function() {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
  };

  /**
   * Create the annotation toolbar and wire it to the canvas.
   */
  AnnotationCanvas.prototype._createToolbar = function() {
    // Look for existing toolbar template
    var toolbar = document.getElementById('annotation-toolbar');
    if (!toolbar) {
      toolbar = document.createElement('div');
      toolbar.id = 'annotation-toolbar';
      toolbar.className = 'feedback-annotation-toolbar';
      toolbar.setAttribute('role', 'toolbar');
      toolbar.setAttribute('aria-label', 'Annotation tools');
      toolbar.innerHTML =
        '<button type="button" class="feedback-annotation-toolbar__btn" data-tool="element" aria-label="Element annotation" title="Element">' +
          '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>' +
        '</button>' +
        '<span class="feedback-annotation-toolbar__sep" aria-hidden="true"></span>' +
        '<button type="button" class="feedback-annotation-toolbar__btn" id="annotation-toolbar-undo" aria-label="Undo last annotation" title="Undo">' +
          '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>' +
        '</button>' +
        '<button type="button" class="feedback-annotation-toolbar__btn" id="annotation-toolbar-clear" aria-label="Clear all annotations" title="Clear">' +
          '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
        '</button>' +
        '<span class="feedback-annotation-toolbar__sep" aria-hidden="true"></span>' +
        '<button type="button" class="feedback-annotation-toolbar__btn" id="annotation-toolbar-submit" aria-label="Submit annotations" title="Submit">' +
          '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>' +
        '</button>' +
        '<button type="button" class="feedback-annotation-toolbar__btn" id="annotation-toolbar-close" aria-label="Close annotation mode" title="Close">' +
          '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
        '</button>';
      document.body.appendChild(toolbar);
    }

    this._toolbarEl = toolbar;
    this._wireToolbarEvents();
  };

  /**
   * Wire toolbar button events.
   */
  AnnotationCanvas.prototype._wireToolbarEvents = function() {
    var self = this;

    // Tool buttons
    var toolBtns = this._toolbarEl.querySelectorAll('[data-tool]');
    for (var i = 0; i < toolBtns.length; i++) {
      toolBtns[i].addEventListener('click', function() {
        var tool = this.getAttribute('data-tool');
        self.setTool(tool);
        // Toggle active state
        var allBtns = self._toolbarEl.querySelectorAll('[data-tool]');
        for (var j = 0; j < allBtns.length; j++) {
          allBtns[j].classList.remove('feedback-annotation-toolbar__btn--active');
        }
        this.classList.add('feedback-annotation-toolbar__btn--active');
      });
    }

    var undoBtn = document.getElementById('annotation-toolbar-undo');
    if (undoBtn) {
      undoBtn.addEventListener('click', function() {
        self.undo();
      });
    }

    var clearBtn = document.getElementById('annotation-toolbar-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function() {
        self.clear();
      });
    }

    var submitBtn = document.getElementById('annotation-toolbar-submit');
    if (submitBtn) {
      submitBtn.addEventListener('click', function() {
        self.submit();
      });
    }

    var closeBtn = document.getElementById('annotation-toolbar-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function() {
        self._exitAnnotationMode();
      });
    }
  };

  /**
   * Show the toolbar.
   */
  AnnotationCanvas.prototype._showToolbar = function() {
    if (this._toolbarEl) {
      this._toolbarEl.style.display = '';
    }
  };

  /**
   * Hide the toolbar.
   */
  AnnotationCanvas.prototype._hideToolbar = function() {
    if (this._toolbarEl) {
      this._toolbarEl.style.display = 'none';
    }
  };

  /**
   * Remove the toolbar from the DOM.
   */
  AnnotationCanvas.prototype._removeToolbar = function() {
    if (this._toolbarEl && this._toolbarEl.parentNode) {
      this._toolbarEl.parentNode.removeChild(this._toolbarEl);
    }
    this._toolbarEl = null;
  };

  /**
   * Create the floating toggle button for entering annotation mode.
   */
  AnnotationCanvas.prototype._createToggleButton = function() {
    if (this._toggleBtn) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'feedback-toggle-btn';
    btn.setAttribute('aria-label', 'Toggle annotation mode');
    btn.setAttribute('title', 'Toggle annotation mode');
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';

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

  /**
   * Enter annotation mode — open overlay, show toolbar, bind events.
   */
  AnnotationCanvas.prototype._enterAnnotationMode = function() {
    var self = this;
    this._annotationMode = true;
    this._hasUnsavedChanges = false;

    if (this._toggleBtn) {
      this._toggleBtn.style.display = 'none';
    }

    this._createToolbar();
    this._showToolbar();
    this.open();
    this._createReviewPanel();
    this._setupBeforeUnload();
  };

  /**
   * Exit annotation mode — close overlay, hide toolbar, show toggle.
   */
  AnnotationCanvas.prototype._exitAnnotationMode = function() {
    if (this._markers.length > 0 && this._hasUnsavedChanges) {
      if (!confirm('You have unsaved annotations. Close without submitting?')) {
        return;
      }
    }

    this._annotationMode = false;
    this.close();
    this._hideToolbar();
    this._removeBeforeUnload();

    if (this._toggleBtn) {
      this._toggleBtn.style.display = '';
    }

    if (this.options.onClose) {
      this.options.onClose();
    }
  };

  /**
   * Initialize the annotation system — create the toggle button and
   * set up the overlay.
   */
  AnnotationCanvas.prototype.init = function() {
    this._createOverlay();
    this._createToggleButton();
    return this;
  };

  // ── Expose globally ──
  window.AnnotationCanvas = AnnotationCanvas;

  /**
   * Convenience function to initialize annotation mode on a page.
   *
   * Creates an AnnotationCanvas instance, wires it to the given
   * container element (or the document body), and returns the instance.
   *
   * @param {HTMLElement|string} containerOrSelector  Container element or CSS selector.
   * @param {Object} options  Options passed to AnnotationCanvas.
   * @return {AnnotationCanvas}
   */
  window.initAnnotationMode = function(containerOrSelector, options) {
    options = options || {};
    var container = containerOrSelector;
    if (typeof containerOrSelector === 'string') {
      container = document.querySelector(containerOrSelector);
    }
    if (!container) {
      container = document.body;
    }

    var canvas = new AnnotationCanvas(container, options);
    canvas.init();
    return canvas;
  };
})();