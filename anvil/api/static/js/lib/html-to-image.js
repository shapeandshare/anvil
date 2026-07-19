// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

/**
 * Vendored html-to-image UMD build — PLACEHOLDER.
 *
 * TODO: Replace this file with the actual html-to-image npm package
 * built to UMD. The real library provides DOM-to-canvas screenshot
 * capture via foreignObject support.
 *
 * Current implementation: minimal stub that returns a blank canvas
 * data URL. Replace with the real `html-to-image` UMD bundle when
 * available.
 *
 * Usage (once replaced):
 *   window.htmlToImage.toPng(element, { useCORS: true })
 *     .then(function(dataUrl) { ... });
 */

(function(root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.htmlToImage = factory();
  }
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  /**
   * Render a DOM element to a PNG data URL.
   *
   * Placeholder implementation — draws a simple representation of the
   * element dimensions. Replace with the real html-to-image library.
   *
   * @param {HTMLElement} node   The DOM element to capture.
   * @param {Object}      opts   Options (useCORS, cacheBust, etc.).
   * @return {Promise<string>}   Resolves to a PNG data URL.
   */
  function toPng(node, opts) {
    opts = opts || {};
    return new Promise(function(resolve, reject) {
      if (!node) {
        reject(new Error('htmlToImage.toPng: node is required'));
        return;
      }

      // Read container dimensions — fall back to viewport if node has no layout
      var rect;
      try {
        rect = node.getBoundingClientRect();
      } catch (e) {
        rect = { width: 800, height: 600 };
      }
      var w = Math.max(rect.width || 800, 1);
      var h = Math.max(rect.height || 600, 1);

      // Create an offscreen canvas
      var canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      var ctx = canvas.getContext('2d');

      // Fill with a neutral background colour
      var style = getComputedStyle(node);
      var bgColor = style.backgroundColor || 'transparent';
      if (bgColor === 'transparent' || bgColor === 'rgba(0, 0, 0, 0)') {
        bgColor = '#1c1c1e';
      }
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, w, h);

      // Draw a placeholder border
      ctx.strokeStyle = '#007aff';
      ctx.lineWidth = 2;
      ctx.strokeRect(2, 2, w - 4, h - 4);

      // Draw placeholder text
      ctx.fillStyle = '#8e8e93';
      ctx.font = '14px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('Screenshot placeholder', w / 2, h / 2);

      resolve(canvas.toDataURL('image/png'));
    });
  }

  /**
   * Render a DOM element to a canvas element.
   *
   * @param {HTMLElement} node   The DOM element to capture.
   * @param {Object}      opts   Options.
   * @return {Promise<HTMLCanvasElement>}
   */
  function toCanvas(node, opts) {
    opts = opts || {};
    return toPng(node, opts).then(function(dataUrl) {
      return new Promise(function(resolve, reject) {
        var img = new Image();
        img.onload = function() {
          var canvas = document.createElement('canvas');
          canvas.width = img.width;
          canvas.height = img.height;
          var ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0);
          resolve(canvas);
        };
        img.onerror = reject;
        img.src = dataUrl;
      });
    });
  }

  /**
   * Render a DOM element to a JPEG data URL.
   *
   * @param {HTMLElement} node   The DOM element to capture.
   * @param {Object}      opts   Options (quality, etc.).
   * @return {Promise<string>}   Resolves to a JPEG data URL.
   */
  function toJpeg(node, opts) {
    opts = opts || {};
    var quality = opts.quality || 0.92;
    return toCanvas(node, opts).then(function(canvas) {
      return canvas.toDataURL('image/jpeg', quality);
    });
  }

  /**
   * Download a rendered DOM element as a PNG file.
   *
   * @param {HTMLElement} node   The DOM element to capture.
   * @param {Object}      opts   Options passed to toPng.
   * @return {Promise<void>}
   */
  function downloadImage(node, opts) {
    opts = opts || {};
    var filename = opts.filename || 'screenshot.png';
    return toPng(node, opts).then(function(dataUrl) {
      var link = document.createElement('a');
      link.download = filename;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });
  }

  return {
    toPng: toPng,
    toCanvas: toCanvas,
    toJpeg: toJpeg,
    downloadImage: downloadImage
  };
});