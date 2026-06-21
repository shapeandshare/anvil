// Copyright © 2026 Josh Burt
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  'use strict';

  /**
   * ArchitectureWidget — two-pane interactive diagram + narration tour.
   * Builds everything inside #arch-experience from #arch-steps JSON.
   * Styling lives entirely in archetypes.css (semantic classes only).
   */
  function ArchitectureWidget(container) {
    if (!container) return;
    this.container = container;
    this._selectedStep = 0;
    this._selectedNode = null;
    this._playTimer = null;
    this._playing = false;

    // Educational captions (preserved from previous version)
    this._captions = {
      'token-embedding': {
        title: 'Token Embedding (wte)',
        body: 'Maps each token ID to a dense vector of size n_embd. Shape: [vocab_size x n_embd]. This is the only embedding layer in the Llama architecture — no learned position embeddings exist. Position information is injected later via RoPE inside the attention sublayer.',
      },
      'rms_1': {
        title: 'RMSNorm (rms_1)',
        body: 'Root Mean Square Layer Normalization. Normalizes hidden states by their RMS value, then scales element-wise by a learned weight vector. Llama uses RMSNorm instead of LayerNorm — no mean subtraction, just RMS scaling. rms_1 normalizes before the attention sublayer, with its own learned scale initialized to 1.0.',
      },
      'qkv': {
        title: 'Q / K / V Projections',
        body: 'Three bias-free linear layers that project the normalized input into Query, Key, and Value vectors. Each produces n_head pairs of vectors, each of dimension head_dim = n_embd / n_head. Llama uses bias-free linear projections throughout.',
      },
      'rope': {
        title: 'Rotary Position Encoding (RoPE)',
        body: 'Rotates Q and K vectors by an angle proportional to token position using precomputed cos/sin tables. Uses the half-split (rotate_half) convention: dim i is paired with dim i + head_dim/2. Applied per-head before attention scoring. This is how the model encodes token order — replacing learned position embeddings entirely.',
      },
      'mha': {
        title: 'Multi-Head Causal Attention',
        body: 'Splits Q, K, V vectors across n_head independent heads. Each head computes scaled dot-product attention (QK^T / sqrt(head_dim)) over all preceding tokens (causal mask prevents attending to future tokens). Head outputs are concatenated and projected back to n_embd. With KV cache, only the current token\'s Q attends to all cached K,V — no recomputation.',
      },
      'wo': {
        title: 'Output Projection (Wo)',
        body: 'Concatenates the outputs from all attention heads and projects the combined vector back to n_embd. This is a linear layer with no bias, matching Llama\'s bias-free design. The output is then added to the sublayer input via the residual connection.',
      },
      'residual-attn': {
        title: 'Residual (Skip) Connection — Attention',
        body: 'Adds the attention sublayer\'s input back to its output: output = attn(norm(x)) + x. This allows gradients to flow directly through the network without vanishing, and lets the model "fall back" to the identity mapping when attention is not helpful.',
      },
      'rms_2': {
        title: 'RMSNorm (rms_2)',
        body: 'Root Mean Square Layer Normalization applied before the SwiGLU MLP sublayer. Same operation as rms_1, with its own learned scale. No mean subtraction — just RMS scaling with element-wise learned weights.',
      },
      'swiglu': {
        title: 'SwiGLU MLP',
        body: 'A gated MLP variant that replaces the standard ReLU MLP. Three projections: gate = SiLU(x . Wgate), up = x . Wup, output = (gate . up) . Wdown. SiLU (Sigmoid Linear Unit) is the gating activation. intermediate_size = int(8 x n_embd / 3) — slightly narrower than the typical 4x expansion, preserving parameter count parity with the old ReLU MLP. All projections are bias-free.',
      },
      'residual-mlp': {
        title: 'Residual (Skip) Connection — MLP',
        body: 'Adds the MLP sublayer\'s input back to its output: output = mlp(norm(x)) + x. This completes the transformer block. After the residual addition, the block\'s output is fed as input to the next transformer block (or to the final RMSNorm).',
      },
      'final-rmsnorm': {
        title: 'Final RMSNorm (rms_final)',
        body: 'Applied just before the output projection, after the last transformer block. Same RMSNorm operation as inside the blocks, with its own learned scale parameters. This final normalization ensures the output projection receives stably-scaled activations.',
      },
      'lm-head': {
        title: 'Language Model Head (lm_head)',
        body: 'Linear projection from n_embd back to vocab_size. Llama does NOT use weight tying — lm_head and wte are separate matrices (no shared parameters). The output is raw logits, which are passed through softmax to produce next-token probabilities for sampling.',
      },
    };

    // Step → diagram node mapping
    this._stepMap = {
      'the-big-picture': [],
      'token-embedding-input': ['token-embedding'],
      'the-transformer-block': ['block-container'],
      'attention-sublayer': ['rms_1', 'qkv', 'rope', 'mha', 'wo', 'residual-attn'],
      'swiglu-sublayer': ['rms_2', 'swiglu', 'residual-mlp'],
      'output-head': ['final-rmsnorm', 'lm-head'],
    };

    // Node → which step key it belongs to (reverse map)
    this._nodeToStep = {};
    var self = this;
    Object.keys(this._stepMap).forEach(function (stepKey) {
      self._stepMap[stepKey].forEach(function (nodeId) {
        self._nodeToStep[nodeId] = stepKey;
      });
    });

    // Parse steps JSON
    var scriptEl = document.getElementById('arch-steps');
    if (!scriptEl) return;
    try {
      this._steps = JSON.parse(scriptEl.textContent);
    } catch (_e) {
      this._steps = [];
    }
    if (!this._steps.length) return;

    this._init();
  }

  /**
   * Read a CSS variable's value.
   */
  ArchitectureWidget.prototype._token = function (name, fallback) {
    var style = getComputedStyle(document.documentElement);
    return style.getPropertyValue(name).trim() || fallback;
  };

  /**
   * Initialize: build DOM, populate steps, wire events.
   */
  ArchitectureWidget.prototype._init = function () {
    this._buildLayout();
    this._populateDiagram();
    this._populateNarration(0);
    this._wireEvents();
  };

  /**
   * Build the two-pane layout shell.
   */
  ArchitectureWidget.prototype._buildLayout = function () {
    this.container.innerHTML =
      '<div class="arch-layout">' +
        '<div class="arch-diagram-pane" id="arch-diagram-pane">' +
          '<div class="arch-legend" aria-label="Component color legend"></div>' +
          '<div class="arch-diagram" id="arch-diagram" role="tree" aria-label="Llama architecture diagram"></div>' +
        '</div>' +
        '<div class="arch-narration-pane" id="arch-narration-pane">' +
          '<div class="arch-narration-content">' +
            '<div class="arch-step-label" id="arch-step-label"></div>' +
            '<h2 class="arch-step-title" id="arch-step-title"></h2>' +
            '<div class="arch-step-body" id="arch-step-body" aria-live="polite"></div>' +
            '<div class="arch-detail" id="arch-detail"></div>' +
            '<div class="arch-narration-foot">' +
              '<div class="arch-nav-row">' +
                '<button type="button" class="arch-btn arch-btn--prev" id="arch-prev" aria-label="Previous step">' +
                  '<span aria-hidden="true">&larr;</span> Back' +
                '</button>' +
                '<div class="arch-dots" id="arch-dots" role="tablist" aria-label="Step dots"></div>' +
                '<button type="button" class="arch-btn arch-btn--next" id="arch-next" aria-label="Next step">' +
                  'Next <span aria-hidden="true">&rarr;</span>' +
                '</button>' +
              '</div>' +
              '<button type="button" class="arch-btn arch-btn--play" id="arch-play" aria-label="Play forward pass auto-tour">' +
                '<span class="arch-play-icon" aria-hidden="true">&#9654;</span> Play forward pass' +
              '</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="arch-footer">' +
        '<a href="/v1/learn/graph">Open the interactive forward-pass graph explorer &rarr;</a>' +
      '</div>';
  };

  /**
   * Populate the legend bar.
   */
  ArchitectureWidget.prototype._populateLegend = function () {
    var legend = this.container.querySelector('.arch-legend');
    if (!legend) return;
    var items = [
      { label: 'Embedding', color: 'var(--accent)' },
      { label: 'Attention', color: 'var(--accent-cyan)' },
      { label: 'MLP·SwiGLU', color: 'var(--accent-orange)' },
      { label: 'Norm', color: 'var(--accent-purple)' },
      { label: 'Output', color: 'var(--accent-green)' },
    ];
    legend.innerHTML = items.map(function (item) {
      return '<span class="arch-legend-item">' +
        '<span class="arch-legend-swatch" style="background:' + item.color + ';"></span> ' +
        item.label +
      '</span>';
    }).join('');
  };

  /**
   * Build the diagram with all components, SVG residual paths, nesting.
   */
  ArchitectureWidget.prototype._populateDiagram = function () {
    this._populateLegend();

    var diagram = this.container.querySelector('#arch-diagram');
    if (!diagram) return;
    var self = this;

    // Categories: Embedding=accent(blue), Attention=accent-cyan(green),
    // MLP=accent-orange, Norm=accent-purple, Output=accent-green
    var C = {
      embedding: this._token('--accent', '#007aff'),
      attention: this._token('--accent-cyan', '#32d74b'),
      mlp: this._token('--accent-orange', '#ff9500'),
      norm: this._token('--accent-purple', '#af52de'),
      output: this._token('--accent-green', '#34c759'),
    };

    function _nodeHtml(id, label, sublabel, color, extra) {
      var shapeHtml = extra && extra.shape ? '<span class="arch-node-shape">' + extra.shape + '</span>' : '';
      var extraCls = extra && extra.cls ? ' ' + extra.cls : '';
      return '<div class="arch-node' + extraCls + '" data-comp="' + id + '" tabindex="0" role="button" aria-label="' + label + '" style="--arch-color:' + color + ';">' +
        '<div class="arch-node-title">' + label + '</div>' +
        (sublabel ? '<div class="arch-node-sub">' + sublabel + '</div>' : '') +
        shapeHtml +
      '</div>';
    }

    function _arrow() {
      return '<div class="arch-arrow" aria-hidden="true"></div>';
    }

    function _residualSvg(id, color) {
      return '<svg class="arch-residual-svg" viewBox="0 0 24 100" preserveAspectRatio="none" aria-hidden="true">' +
        '<path class="arch-residual-path" d="M12,0 C12,30 12,50 12,70 L12,100" stroke="' + color + '" stroke-width="1.5" fill="none" stroke-linecap="round"/>' +
        '<circle cx="12" cy="0" r="2" fill="' + color + '"/>' +
        '<polygon points="8,94 12,100 16,94" fill="' + color + '"/>' +
      '</svg>';
    }

    function _addNode(id, label, color) {
      return '<div class="arch-add" data-comp="' + id + '" tabindex="0" role="button" aria-label="' + label + '" style="--arch-color:' + color + ';">' +
        '<span class="arch-add-sign" aria-hidden="true">+</span> ' + label +
        _residualSvg(id + '-residual', color) +
      '</div>';
    }

    var html = '';

    // 1. Token input chip
    html += '<div class="arch-chip arch-chip--input">token_id</div>';
    html += _arrow();

    // 2. Token Embedding
    html += _nodeHtml('token-embedding', 'Token Embedding (wte)', '[vocab_size &times; n_embd] &middot; no learned position embeddings', C.embedding, {shape: '[T] &rarr; [T, n_embd]'});
    html += _arrow();

    // 3. Transformer Block (nested container)
    html += '<div class="arch-block" data-comp="block-container" id="arch-block" style="--arch-color:' + C.attention + ';">' +
      '<div class="arch-block-header">Transformer Block &times; n_layer</div>' +
      '<div class="arch-block-body">' +

        /* ── Attention Sublayer ── */
        '<div class="arch-sublayer-head">Attention Sublayer</div>' +

        '<div class="arch-sublayer-group" id="arch-attn-group">' +
          '<div class="arch-residual-gutter">' +
            _residualSvg('residual-attn-svg', C.attention) +
          '</div>' +
          '<div class="arch-sublayer-nodes">' +
            _nodeHtml('rms_1', 'RMSNorm (rms_1)', '', C.norm) + _arrow() +
            _nodeHtml('qkv', 'Q / K / V Projections', 'bias-free linear layers', C.attention, {shape: '&rarr; 3&times;[T, n_embd]'}) + _arrow() +
            _nodeHtml('rope', 'RoPE rotation (Q, K only)', 'half-split / rotate_half', C.attention) + _arrow() +
            _nodeHtml('mha', 'Multi-Head Causal Attention', 'QK&sup2; / &radic;head_dim', C.attention, {shape: 'scores [T, T]'}) + _arrow() +
            _nodeHtml('wo', 'Output Projection (Wo)', 'concat heads &middot; Wo', C.attention) + _arrow() +
            _addNode('residual-attn', 'Residual (skip from input)', C.attention) +
          '</div>' +
        '</div>' +

        /* ── MLP Sublayer ── */
        '<div class="arch-sublayer-head">SwiGLU MLP Sublayer</div>' +

        '<div class="arch-sublayer-group" id="arch-mlp-group">' +
          '<div class="arch-residual-gutter">' +
            _residualSvg('residual-mlp-svg', C.mlp) +
          '</div>' +
          '<div class="arch-sublayer-nodes">' +
            _nodeHtml('rms_2', 'RMSNorm (rms_2)', '', C.norm) + _arrow() +
            _nodeHtml('swiglu', 'SwiGLU MLP', 'SiLU(x&middot;Wg) &odot; (x&middot;Wu) &middot; Wd', C.mlp, {shape: 'intermediate = int(8&middot;n_embd/3)'}) + _arrow() +
            _addNode('residual-mlp', 'Residual (skip from input)', C.mlp) +
          '</div>' +
        '</div>' +

      '</div>' +
    '</div>';

    html += _arrow();

    // 4. Final RMSNorm
    html += _nodeHtml('final-rmsnorm', 'Final RMSNorm (rms_final)', '', C.norm);
    html += _arrow();

    // 5. lm_head
    html += _nodeHtml('lm-head', 'lm_head', '[n_embd &rarr; vocab_size] &middot; no weight tying with wte', C.output, {shape: '[T, n_embd] &rarr; [T, vocab_size]'});
    html += _arrow();

    // 6. Logits output chip
    html += '<div class="arch-chip arch-chip--output"><span class="arch-chip-accent">Logits</span> &rarr; softmax &rarr; next-token probabilities</div>';

    diagram.innerHTML = html;

    // Store references to all node elements
    this._nodeEls = {};
    var nodes = diagram.querySelectorAll('[data-comp]');
    for (var i = 0; i < nodes.length; i++) {
      var id = nodes[i].getAttribute('data-comp');
      if (id) this._nodeEls[id] = nodes[i];
    }
  };

  /**
   * Populate narration for a given step index.
   */
  ArchitectureWidget.prototype._populateNarration = function (idx) {
    var step = this._steps[idx];
    if (!step) return;

    var labelEl = document.getElementById('arch-step-label');
    var titleEl = document.getElementById('arch-step-title');
    var bodyEl = document.getElementById('arch-step-body');
    var detailEl = document.getElementById('arch-detail');
    var dotsContainer = document.getElementById('arch-dots');
    var prevBtn = document.getElementById('arch-prev');
    var nextBtn = document.getElementById('arch-next');

    if (labelEl) {
      labelEl.textContent = 'Step ' + (idx + 1) + ' of ' + this._steps.length;
    }
    if (titleEl) {
      titleEl.textContent = step.title;
    }
    if (bodyEl) {
      bodyEl.innerHTML = step.body;
    }

    // Reset detail area
    if (detailEl) {
      detailEl.innerHTML = '';
      detailEl.classList.remove('arch-detail--visible');
    }

    // Dots
    if (dotsContainer) {
      dotsContainer.innerHTML = this._steps.map(function (s, i) {
        return '<button type="button" class="arch-dot' + (i === idx ? ' arch-dot--active' : '') + '" data-step="' + i + '" role="tab" aria-selected="' + (i === idx ? 'true' : 'false') + '" aria-label="Go to step ' + (i + 1) + ': ' + s.title + '"></button>';
      }).join('');
    }

    // Button states
    if (prevBtn) prevBtn.disabled = idx === 0;
    if (nextBtn) nextBtn.disabled = idx === this._steps.length - 1;

    // Update diagram focus
    this._focusDiagram(idx);
    this._selectedStep = idx;
  };

  /**
   * Apply focus/dim states to diagram nodes for a given step.
   */
  ArchitectureWidget.prototype._focusDiagram = function (idx) {
    var self = this;
    var step = this._steps[idx];
    if (!step) return;
    var focusedIds = this._stepMap[step.key] || [];
    var isOverview = focusedIds.length === 0;

    var prevSelected = this.container.querySelector('.arch-node.is-selected, .arch-add.is-selected, .arch-block.is-focused');
    if (prevSelected) {
      prevSelected.classList.remove('is-selected');
    }

    if (!isOverview) {
      var allInteractive = this.container.querySelectorAll('[data-comp]');
      for (var i = 0; i < allInteractive.length; i++) {
        var compId = allInteractive[i].getAttribute('data-comp');
        if (focusedIds.indexOf(compId) !== -1) {
          allInteractive[i].classList.remove('is-dimmed');
          allInteractive[i].classList.add('is-focused');
        } else {
          allInteractive[i].classList.add('is-dimmed');
          allInteractive[i].classList.remove('is-focused');
        }
      }
      var blockEl = this.container.querySelector('#arch-block');
      if (blockEl) {
        if (focusedIds.indexOf('block-container') !== -1) {
          blockEl.classList.add('is-focused');
          blockEl.classList.remove('is-dimmed');
        } else {
          blockEl.classList.remove('is-focused');
          var anyChildFocused = focusedIds.some(function (id) {
            return self._nodeEls[id] && id !== 'block-container';
          });
          if (anyChildFocused) {
            blockEl.classList.remove('is-dimmed');
          }
        }
      }
    } else {
      var allEls = this.container.querySelectorAll('[data-comp]');
      for (var j = 0; j < allEls.length; j++) {
        allEls[j].classList.remove('is-dimmed', 'is-focused');
      }
    }

    if (focusedIds.length > 0) {
      var firstId = focusedIds[0];
      var firstEl = this._nodeEls[firstId];
      if (firstEl) {
        var pane = this.container.querySelector('#arch-diagram-pane');
        if (pane) {
          firstEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
      }
    }
  };

  /**
   * Show a node's detail caption in the narration detail area.
   */
  ArchitectureWidget.prototype._showDetail = function (compId) {
    var detailEl = document.getElementById('arch-detail');
    if (!detailEl) return;
    var caption = this._captions[compId];
    if (caption) {
      detailEl.innerHTML =
        '<div class="arch-detail-title">' + caption.title + '</div>' +
        '<div class="arch-detail-body">' + caption.body + '</div>';
      detailEl.classList.add('arch-detail--visible');
    } else {
      detailEl.innerHTML = '';
      detailEl.classList.remove('arch-detail--visible');
    }
  };

  /**
   * Go to a step index.
   */
  ArchitectureWidget.prototype._goToStep = function (idx, suppressCancel) {
    if (idx < 0 || idx >= this._steps.length) return;
    if (!suppressCancel) {
      this._cancelAutoPlay();
    }
    this._populateNarration(idx);
    var selected = this.container.querySelector('.arch-node.is-selected, .arch-add.is-selected');
    if (selected) selected.classList.remove('is-selected');
    this._selectedNode = null;
    var detailEl = document.getElementById('arch-detail');
    if (detailEl) {
      detailEl.innerHTML = '';
      detailEl.classList.remove('arch-detail--visible');
    }
  };

  /**
   * Select a diagram node by its comp ID.
   */
  ArchitectureWidget.prototype._selectNode = function (compId) {
    this._cancelAutoPlay();

    // Toggle selection visual
    var prevSelected = this.container.querySelector('.arch-node.is-selected, .arch-add.is-selected');
    if (prevSelected) prevSelected.classList.remove('is-selected');

    var el = this._nodeEls[compId];
    if (el) {
      el.classList.add('is-selected');
    }
    this._selectedNode = compId;

    // Show caption
    this._showDetail(compId);

    // Jump narration to the step that contains this node
    var stepKey = this._nodeToStep[compId];
    if (stepKey) {
      for (var i = 0; i < this._steps.length; i++) {
        if (this._steps[i].key === stepKey) {
          this._populateNarration(i);
          break;
        }
      }
    }
  };

  /**
   * Start/stop auto-play forward pass.
   */
  ArchitectureWidget.prototype._toggleAutoPlay = function () {
    var self = this;
    var playBtn = document.getElementById('arch-play');
    if (this._playing) {
      this._cancelAutoPlay();
      return;
    }
    this._playing = true;
    if (playBtn) {
      playBtn.innerHTML = '<span aria-hidden="true">&#9208;</span> Pause';
      playBtn.setAttribute('aria-label', 'Pause forward pass auto-tour');
    }

    this._goToStep(0, true);

    var playInterval = 2200;
    this._playTimer = setInterval(function () {
      var next = self._selectedStep + 1;
      if (next >= self._steps.length) {
        self._cancelAutoPlay();
        return;
      }
      self._goToStep(next, true);
    }, playInterval);
  };

  ArchitectureWidget.prototype._cancelAutoPlay = function () {
    if (this._playTimer) {
      clearInterval(this._playTimer);
      this._playTimer = null;
    }
    if (this._playing) {
      this._playing = false;
      var playBtn = document.getElementById('arch-play');
      if (playBtn) {
        playBtn.innerHTML = '<span class="arch-play-icon" aria-hidden="true">&#9654;</span> Play forward pass';
        playBtn.setAttribute('aria-label', 'Play forward pass auto-tour');
      }
    }
  };

  /**
   * Wire all events: clicks, keyboard, dots, buttons.
   */
  ArchitectureWidget.prototype._wireEvents = function () {
    var self = this;

    // Click delegation on diagram
    var diagram = this.container.querySelector('#arch-diagram');
    if (diagram) {
      diagram.addEventListener('click', function (e) {
        var node = e.target.closest('[data-comp]');
        if (node) {
          var compId = node.getAttribute('data-comp');
          self._selectNode(compId);
        }
      });

      // Keyboard on diagram nodes
      diagram.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          var target = e.target.closest('[data-comp]');
          if (target) {
            e.preventDefault();
            var compId = target.getAttribute('data-comp');
            self._selectNode(compId);
          }
        }
      });
    }

    // Prev / Next
    var prevBtn = document.getElementById('arch-prev');
    var nextBtn = document.getElementById('arch-next');
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        self._goToStep(self._selectedStep - 1);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        self._goToStep(self._selectedStep + 1);
      });
    }

    // Dots (delegated)
    var dotsContainer = document.getElementById('arch-dots');
    if (dotsContainer) {
      dotsContainer.addEventListener('click', function (e) {
        var dot = e.target.closest('.arch-dot');
        if (dot) {
          var idx = parseInt(dot.getAttribute('data-step'), 10);
          if (!isNaN(idx)) self._goToStep(idx);
        }
      });
    }

    // Play button
    var playBtn = document.getElementById('arch-play');
    if (playBtn) {
      playBtn.addEventListener('click', function () {
        self._toggleAutoPlay();
      });
    }

    // Keyboard: ArrowLeft/ArrowRight
    document.addEventListener('keydown', function (e) {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)) return;
      var exp = document.getElementById('arch-experience');
      if (!exp || exp.offsetParent === null) return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        self._goToStep(self._selectedStep - 1);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        self._goToStep(self._selectedStep + 1);
      }
    });
  };

  window.ArchitectureWidget = ArchitectureWidget;

  // Auto-init on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('arch-experience');
    if (container) {
      new ArchitectureWidget(container);
    }
  });
})();