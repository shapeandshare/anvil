(function () {
  'use strict';

  function ArchitectureWidget(container) {
    if (!container) return;
    this.container = container;
    this._selected = null;
    this._captions = {
      'token-embedding': {
        title: 'Token Embedding (wte)',
        body: 'Maps each token ID to a dense vector of size n_embd. Shape: [vocab_size x n_embd]. This is the only embedding layer in the Llama architecture — no learned position embeddings exist. Position information is injected later via RoPE inside the attention sublayer.',
      },
      'rmsnorm': {
        title: 'RMSNorm',
        body: 'Root Mean Square Layer Normalization. Normalizes hidden states by their RMS value, then scales element-wise by a learned weight vector. Llama uses RMSNorm instead of LayerNorm — no mean subtraction, just RMS scaling. Each occurrence (rms_1, rms_2, rms_final) has its own learned scale initialized to 1.0.',
      },
      'rope': {
        title: 'Rotary Position Encoding (RoPE)',
        body: 'Rotates Q and K vectors by an angle proportional to token position using precomputed cos/sin tables. Uses the half-split (rotate_half) convention: dim i is paired with dim i + head_dim/2. Applied per-head before attention scoring. This is how the model encodes token order — replacing learned position embeddings entirely.',
      },
      'multihead-attention': {
        title: 'Multi-Head Causal Attention',
        body: 'Splits Q, K, V vectors across n_head independent heads. Each head computes scaled dot-product attention (QK^T / sqrt(head_dim)) over all preceding tokens (causal mask prevents attending to future tokens). Head outputs are concatenated and projected back to n_embd. With KV cache, only the current token\'s Q attends to all cached K,V — no recomputation.',
      },
      'residual': {
        title: 'Residual (Skip) Connection',
        body: 'Adds the sublayer\'s input back to its output: output = sublayer(norm(x)) + x. This allows gradients to flow directly through the network without vanishing, and lets the model "fall back" to the identity mapping when the sublayer is not helpful. Every transformer sublayer (attention and MLP) has its own residual connection.',
      },
      'swiglu': {
        title: 'SwiGLU MLP',
        body: 'A gated MLP variant that replaces the standard ReLU MLP. Three projections: gate = SiLU(x . Wgate), up = x . Wup, output = (gate . up) . Wdown. SiLU (Sigmoid Linear Unit) is the gating activation. intermediate_size = int(8 x n_embd / 3) — slightly narrower than the typical 4x expansion, preserving parameter count parity with the old ReLU MLP. All projections are bias-free.',
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
    this._render();
  }

  ArchitectureWidget.prototype._token = function (name, fallback) {
    var style = getComputedStyle(document.documentElement);
    return style.getPropertyValue(name).trim() || fallback;
  };

  ArchitectureWidget.prototype._render = function () {
    var self = this;
    var accent = this._token('--accent', '#007aff');
    var cyan = this._token('--accent-cyan', '#32d74b');
    var orange = this._token('--accent-orange', '#ff9500');
    var purple = this._token('--accent-purple', '#af52de');
    var green = this._token('--accent-green', '#34c759');
    var surface = this._token('--surface', '#1c1c1e');
    var surface2 = this._token('--surface-2', '#2c2c2e');
    var text = this._token('--text', '#ffffff');
    var muted = this._token('--text-muted', '#8e8e93');
    var border = this._token('--border', '#38383a');
    var radius = this._token('--radius', '13px');
    var radiusSm = this._token('--radius-sm', '8px');
    var mono = this._token('--font-mono', 'ui-monospace,SF Mono,Menlo,monospace');
    var body = this._token('--font-body', '-apple-system,BlinkMacSystemFont,system-ui,sans-serif');
    var space3 = this._token('--space-3', '0.75rem');
    var space4 = this._token('--space-4', '1rem');
    var space2 = this._token('--space-2', '0.5rem');

    var css = '<style>' +
      '.arch-widget{font-family:' + body + ';color:' + text + ';width:100%;}' +
      '.arch-legend{display:flex;flex-wrap:wrap;gap:' + space2 + ' ' + space3 + ';margin-bottom:' + space3 + ';padding-bottom:' + space2 + ';border-bottom:1px solid ' + border + ';font-size:0.72rem;}' +
      '.arch-legend-item{display:flex;align-items:center;gap:4px;color:' + muted + ';}' +
      '.arch-legend-swatch{width:10px;height:10px;border-radius:2px;flex-shrink:0;}' +
      '.arch-diagram{display:flex;flex-direction:column;align-items:center;gap:2px;width:100%;}' +
      '.arch-node{cursor:pointer;width:100%;max-width:520px;border-radius:' + radiusSm + ';padding:' + space2 + ' ' + space3 + ';border:1px solid transparent;transition:border-color 0.2s,box-shadow 0.2s;text-align:center;position:relative;}' +
      '.arch-node:hover{border-color:var(--arch-color, ' + accent + ');box-shadow:0 0 0 1px var(--arch-color,' + accent + ');}' +
      '.arch-node.selected{border-color:var(--arch-color,' + accent + ');box-shadow:0 0 0 2px var(--arch-color,' + accent + '),0 0 12px color-mix(in srgb,var(--arch-color,' + accent + ') 30%,transparent);}' +
      '.arch-node-title{font-size:0.82rem;font-weight:600;letter-spacing:-0.01em;}' +
      '.arch-node-sub{font-size:0.65rem;color:' + muted + ';margin-top:2px;font-family:' + mono + ';}' +
      '.arch-arrow{color:' + muted + ';font-size:0.6rem;line-height:1;padding:1px 0;opacity:0.5;}' +
      '.arch-block{width:100%;max-width:520px;border:1px solid ' + border + ';border-radius:' + radius + ';overflow:hidden;margin:2px 0;}' +
      '.arch-block-header{padding:' + space2 + ' ' + space3 + ';font-size:0.72rem;font-weight:600;text-align:center;background:' + surface2 + ';border-bottom:1px solid ' + border + ';color:' + muted + ';letter-spacing:0.02em;}' +
      '.arch-block-body{position:relative;padding:' + space2 + ';display:flex;flex-direction:column;align-items:center;gap:2px;}' +
      '.arch-sublayer-head{font-size:0.68rem;color:' + muted + ';padding:4px 0 2px;font-weight:500;text-align:center;background:' + surface2 + ';border-radius:' + radiusSm + ';width:100%;margin:2px 0;}' +
      '.arch-add{width:100%;max-width:520px;border-radius:' + radiusSm + ';padding:4px ' + space2 + ';text-align:center;font-size:0.72rem;color:' + muted + ';border:1px dashed ' + border + ';position:relative;display:flex;align-items:center;justify-content:center;gap:6px;}' +
      '.arch-residual-vis{position:absolute;left:0;top:0;width:24px;bottom:0;pointer-events:none;}' +
      '.arch-residual-vis svg{width:100%;height:100%;display:block;}' +
      '.arch-caption{border-radius:' + radiusSm + ';padding:' + space3 + ';margin-top:' + space3 + ';background:' + surface2 + ';}' +
      '.arch-caption-title{font-size:0.82rem;font-weight:600;margin-bottom:4px;}' +
      '.arch-caption-body{font-size:0.75rem;color:' + muted + ';line-height:1.5;}' +
      '.arch-caption-empty{font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';}' +
      '.arch-footer{margin-top:' + space3 + ';text-align:center;}' +
      '.arch-footer a{font-size:0.75rem;color:' + accent + ';text-decoration:none;}' +
      '.arch-footer a:hover{text-decoration:underline;}' +
      '@media(max-width:400px){.arch-node{padding:4px ' + space2 + ';}.arch-node-title{font-size:0.75rem;}.arch-node-sub{font-size:0.6rem;}.arch-block-header{font-size:0.68rem;padding:' + space2 + ';}}' +
      '</style>';

    var blockInnerStyled = '<div class="arch-block-body" style="padding:' + space2 + ';display:flex;flex-direction:column;align-items:center;gap:2px;">' +
      /* ── Attention sublayer ── */
      '<div class="arch-sublayer-head" style="font-size:0.68rem;color:' + muted + ';padding:4px 0 2px;font-weight:500;text-align:center;background:' + surface2 + ';border-radius:' + radiusSm + ';width:100%;margin:2px 0;">Attention Sublayer</div>' +

      '<div class="arch-node" data-comp="rmsnorm" style="--arch-color:' + purple + ';border-left:3px solid ' + purple + ';">' +
      '<div class="arch-node-title">RMSNorm (rms_1)</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-node" data-comp="rope" style="--arch-color:' + cyan + ';border-left:3px solid ' + cyan + ';">' +
      '<div class="arch-node-title">Q / K / V Projections</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">bias-free linear layers</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-node" data-comp="rope" style="--arch-color:' + cyan + ';border-left:3px solid ' + cyan + ';">' +
      '<div class="arch-node-title">RoPE rotation (Q, K only)</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">half-split / rotate_half</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-node" data-comp="multihead-attention" style="--arch-color:' + cyan + ';border-left:3px solid ' + cyan + ';">' +
      '<div class="arch-node-title">Multi-Head Causal Attention</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">QK^T / sqrt(head_dim)</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-node" data-comp="multihead-attention" style="--arch-color:' + cyan + ';border-left:3px solid ' + cyan + ';">' +
      '<div class="arch-node-title">Output Projection (Wo)</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">concat heads . Wo</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-add" data-comp="residual" style="border:1px dashed ' + border + ';color:' + muted + ';border-radius:' + radiusSm + ';">' +
      '<span style="font-size:0.82rem;font-weight:600;color:' + cyan + ';">+</span> Residual (skip from input)' +
      '</div>' +

      /* ── MLP sublayer ── */
      '<div class="arch-sublayer-head" style="font-size:0.68rem;color:' + muted + ';padding:4px 0 2px;font-weight:500;text-align:center;background:' + surface2 + ';border-radius:' + radiusSm + ';width:100%;margin:2px 0;">SwiGLU MLP Sublayer</div>' +

      '<div class="arch-node" data-comp="rmsnorm" style="--arch-color:' + purple + ';border-left:3px solid ' + purple + ';">' +
      '<div class="arch-node-title">RMSNorm (rms_2)</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-node" data-comp="swiglu" style="--arch-color:' + orange + ';border-left:3px solid ' + orange + ';">' +
      '<div class="arch-node-title">SwiGLU: SiLU(x-Wg) x-Wu-Wd</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">gate + up + down | intermediate_size = int(8n_embd/3)</div></div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      '<div class="arch-add" data-comp="residual" style="border:1px dashed ' + border + ';color:' + muted + ';border-radius:' + radiusSm + ';">' +
      '<span style="font-size:0.82rem;font-weight:600;color:' + orange + ';">+</span> Residual (skip from input)' +
      '</div>' +
      '</div>';

    this.container.innerHTML =
      '<div class="arch-widget">' +
      css +

      /* Legend */
      '<div class="arch-legend" style="display:flex;flex-wrap:wrap;gap:' + space2 + ' ' + space3 + ';margin-bottom:' + space3 + ';padding-bottom:' + space2 + ';border-bottom:1px solid ' + border + ';font-size:0.72rem;">' +
      '<span class="arch-legend-item" style="display:flex;align-items:center;gap:4px;color:' + muted + ';"><span class="arch-legend-swatch" style="width:10px;height:10px;border-radius:2px;background:' + accent + ';"></span> Embedding</span>' +
      '<span class="arch-legend-item" style="display:flex;align-items:center;gap:4px;color:' + muted + ';"><span class="arch-legend-swatch" style="width:10px;height:10px;border-radius:2px;background:' + cyan + ';"></span> Attention</span>' +
      '<span class="arch-legend-item" style="display:flex;align-items:center;gap:4px;color:' + muted + ';"><span class="arch-legend-swatch" style="width:10px;height:10px;border-radius:2px;background:' + orange + ';"></span> MLP / SwiGLU</span>' +
      '<span class="arch-legend-item" style="display:flex;align-items:center;gap:4px;color:' + muted + ';"><span class="arch-legend-swatch" style="width:10px;height:10px;border-radius:2px;background:' + purple + ';"></span> Norm</span>' +
      '<span class="arch-legend-item" style="display:flex;align-items:center;gap:4px;color:' + muted + ';"><span class="arch-legend-swatch" style="width:10px;height:10px;border-radius:2px;background:' + green + ';"></span> Output</span>' +
      '</div>' +

      /* Diagram */
      '<div class="arch-diagram" style="display:flex;flex-direction:column;align-items:center;gap:2px;width:100%;">' +

      /* Token input */
      '<div style="width:100%;max-width:520px;text-align:center;padding:2px ' + space2 + ';font-size:0.72rem;color:' + muted + ';font-family:' + mono + ';">token_id</div>' +
      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      /* Token Embedding */
      '<div class="arch-node" data-comp="token-embedding" style="--arch-color:' + accent + ';border-left:3px solid ' + accent + ';">' +
      '<div class="arch-node-title">Token Embedding (wte)</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">[vocab_size x n_embd] &middot; no learned position embeddings</div></div>' +

      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      /* Transformer Block */
      '<div class="arch-block" style="border:1px solid ' + border + ';border-radius:' + radius + ';width:100%;max-width:520px;">' +
      '<div class="arch-block-header" style="padding:' + space2 + ' ' + space3 + ';font-size:0.72rem;font-weight:600;text-align:center;background:' + surface2 + ';border-bottom:1px solid ' + border + ';color:' + muted + ';">Transformer Block &times; n_layer</div>' +
      blockInnerStyled +
      '</div>' +

      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      /* Final RMSNorm */
      '<div class="arch-node" data-comp="final-rmsnorm" style="--arch-color:' + purple + ';border-left:3px solid ' + purple + ';">' +
      '<div class="arch-node-title">Final RMSNorm (rms_final)</div></div>' +

      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      /* lm_head */
      '<div class="arch-node" data-comp="lm-head" style="--arch-color:' + green + ';border-left:3px solid ' + green + ';">' +
      '<div class="arch-node-title">lm_head</div>' +
      '<div class="arch-node-sub" style="color:' + muted + ';">[n_embd &rarr; vocab_size] &middot; no weight tying with wte</div></div>' +

      '<div class="arch-arrow" style="color:' + muted + ';font-size:0.6rem;">&#9660;</div>' +

      /* Logits output */
      '<div style="width:100%;max-width:520px;text-align:center;padding:6px ' + space2 + ';font-size:0.72rem;color:' + muted + ';font-family:' + mono + ';border:1px solid ' + border + ';border-radius:' + radiusSm + ';background:' + surface2 + ';">' +
      '<span style="font-weight:600;color:' + green + ';">Logits</span> &rarr; softmax &rarr; next-token probabilities' +
      '</div>' +

      '</div>' + /* .arch-diagram */

      /* Caption */
      '<div class="arch-caption" style="border-radius:' + radiusSm + ';padding:' + space3 + ';margin-top:' + space3 + ';background:' + surface2 + ';" id="arch-caption">' +
      '<div class="arch-caption-empty" style="font-size:0.72rem;color:' + muted + ';text-align:center;padding:' + space3 + ';">Click any component above for details</div>' +
      '</div>' +

      /* Footer */
      '<div class="arch-footer" style="margin-top:' + space3 + ';text-align:center;">' +
      '<a href="/v1/learn/graph" class="widget-empty-link" style="font-size:0.75rem;color:' + accent + ';text-decoration:none;">Open the interactive forward-pass graph explorer &rarr;</a>' +
      '</div>' +

      '</div>'; /* .arch-widget */

    this._captionEl = this.container.querySelector('#arch-caption');

    /* Delegate click events on nodes */
    this.container.addEventListener('click', function (e) {
      var node = e.target.closest('[data-comp]');
      if (node) {
        self._select(node.getAttribute('data-comp'), node);
      }
    });

    /* Keyboard accessibility: nodes are clickable, make them focusable */
    var nodes = this.container.querySelectorAll('[data-comp]');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].setAttribute('tabindex', '0');
      nodes[i].setAttribute('role', 'button');
      nodes[i].setAttribute('aria-label', 'Show details for ' + (nodes[i].getAttribute('data-comp') || 'component'));
    }

    /* Keyboard handler on diagram */
    var diagram = this.container.querySelector('.arch-diagram');
    if (diagram) {
      diagram.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          var target = e.target.closest('[data-comp]');
          if (target) {
            e.preventDefault();
            self._select(target.getAttribute('data-comp'), target);
          }
        }
      });
    }
  };

  ArchitectureWidget.prototype._select = function (comp, el) {
    var prev = this.container.querySelector('.arch-node.selected, .arch-add.selected');
    if (prev) {
      prev.classList.remove('selected');
    }
    if (el) {
      el.classList.add('selected');
    }

    var caption = this._captions[comp];
    if (caption) {
      this._selected = comp;
      var accent = this._token('--accent', '#007aff');
      var text = this._token('--text', '#ffffff');
      var muted = this._token('--text-muted', '#8e8e93');
      this._captionEl.innerHTML =
        '<div class="arch-caption-title" style="font-size:0.82rem;font-weight:600;color:' + text + ';margin-bottom:4px;">' + caption.title + '</div>' +
        '<div class="arch-caption-body" style="font-size:0.75rem;color:' + muted + ';line-height:1.5;">' + caption.body + '</div>';
    }
  };

  window.ArchitectureWidget = ArchitectureWidget;
})();