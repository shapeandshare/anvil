(function () {
  'use strict';

  let _corpusId = null;
  let _entries = [];
  let _compositionPreviewStream = null;

  function escHtml(s) {
    if (s == null) return '';
    return String(s).replaceAll(/&/g, '&amp;').replaceAll(/</g, '&lt;').replaceAll(/>/g, '&gt;').replaceAll(/"/g, '&quot;');
  }

  function toast(msg, type) {
    type = type || 'info';
    let duration = 3000;
    let container = document.getElementById('toast-container');
    if (!container) return;
    let el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, duration);
  }

  function trunc(s, len) {
    if (!s) return '—';
    len = len || 16;
    return s.length > len ? s.slice(0, len) + '…' : s;
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch(path, opts)
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok || body.error) {
            throw new Error(body.detail || body.error || 'Request failed');
          }
          return body.data;
        });
      });
  }

  /* ── Mount Composer ── */
  function mount() {
    let mountEl = document.getElementById('composer-mount');
    if (!mountEl) return;

    mountEl.innerHTML =
      '<div class="section-card section-card--forge" style="--stagger-i: 0">'
      + '<div class="section-card__header">'
      + '<span class="section-card__icon">&#9876;</span>'
      + '<h2 class="section-card__title section-card__title--forge">Ensemble Composer</h2>'
      + '</div>'
      + '<div class="section-card__content">'
      + '<p class="ds-flow-desc">Select a corpus and compose a weighted mix of content entries. Adjust weights to control sampling distribution.</p>'
      + '<div style="display:flex;flex-wrap:wrap;gap:var(--space-2);align-items:center;margin-bottom:var(--space-3);">'
      + '<select class="form-select" id="composer-corpus" style="flex:1;min-width:200px;" onchange="composer.selectCorpus()">'
      + '<option value="">— select corpus —</option>'
      + '</select>'
      + '<button type="button" class="btn btn-secondary btn-sm" id="composer-refresh-entries" onclick="composer.loadEntries()" disabled>Load Entries</button>'
      + '</div>'
      + '<div id="composer-entries" style="margin-top:var(--space-2);">'
      + '<div class="empty-state-card"><span class="empty-state-card__icon">&#9876;</span><span>Select a corpus and load its entries to start composing.</span></div>'
      + '</div>'
      + '<div id="composition-preview" style="display:none;margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px solid var(--separator);">'
      + '<div class="section-card__header" style="margin-bottom:var(--space-2);">'
      + '<span class="section-card__icon">&#128202;</span>'
      + '<h2 class="section-card__title">Mix Distribution</h2>'
      + '</div>'
      + '<div id="dist-bars" style="display:flex;flex-direction:column;gap:var(--space-2);"></div>'
      + '<div id="dist-summary" class="type-caption-1 text-muted" style="margin-top:var(--space-2);"></div>'
      + '</div>'
      + '<div style="display:flex;gap:var(--space-2);margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px solid var(--separator);">'
      + '<button type="button" class="btn btn-accent btn-sm" id="btn-freeze-composition" onclick="composer.freezeComposition()" disabled>&#9874; Freeze Composition</button>'
      + '<button type="button" class="btn btn-secondary btn-sm" onclick="composer.resetWeights()">Reset Weights</button>'
      + '</div>'
      + '<div id="composer-status" class="ds-status-line" style="margin-top:var(--space-2);display:none;"></div>'
      + '</div>'
      + '</div>';

    // Populate corpus selector
    loadCorporaForComposer();
  }

  /* ── Load corpora into composer selector ── */
  function loadCorporaForComposer() {
    api('/v1/content/corpora')
      .then(function (data) {
        let select = document.getElementById('composer-corpus');
        if (!select) return;
        let opts = '<option value="">— select corpus —</option>';
        (data || []).forEach(function (c) {
          opts += '<option value="' + c.id + '">' + escHtml(c.name) + ' (' + c.slug + ')</option>';
        });
        select.innerHTML = opts;
      })
      .catch(function () {});
  }

  /* ── Select corpus ── */
  function selectCorpus() {
    let select = document.getElementById('composer-corpus');
    _corpusId = Number.parseInt(select.value) || null;
    let refreshBtn = document.getElementById('composer-refresh-entries');
    if (refreshBtn) refreshBtn.disabled = !_corpusId;

    // Clear previous entries
    resetEntries();
  }

  /* ── Load entries for selected corpus ── */
  function loadEntries() {
    if (!_corpusId) return;
    let container = document.getElementById('composer-entries');
    let refreshBtn = document.getElementById('composer-refresh-entries');
    if (refreshBtn) refreshBtn.disabled = true;
    if (container) container.innerHTML = '<span class="spinner"></span> Loading entries...';

    api('/v1/content/corpora/' + _corpusId + '/versions')
      .then(function (versions) {
        if (!versions || !versions.length) {
          if (container) container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#128196;</span><span>No versions yet for this corpus.</span></div>';
          if (refreshBtn) refreshBtn.disabled = false;
          return;
        }

        // Use the latest version's entries
        let latest = versions[versions.length - 1];
        api('/v1/content/versions/' + latest.id)
          .then(function (versionDetail) {
            let entries = versionDetail.entries || [];
            if (!entries.length) {
              if (container) container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#128196;</span><span>No entries in the latest version (v' + latest.version_number + ').</span></div>';
              if (refreshBtn) refreshBtn.disabled = false;
              return;
            }

            _entries = entries.map(function (e) {
              return {
                path: e.path,
                content_hash: e.content_hash,
                size_bytes: e.size_bytes,
                weight: 1.0,
              };
            });

            renderEntries();
            connectCompositionPreview();
            if (refreshBtn) refreshBtn.disabled = false;
          })
          .catch(function () {
            if (container) container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9888;</span><span>Failed to load version details.</span></div>';
            if (refreshBtn) refreshBtn.disabled = false;
          });
      })
      .catch(function (err) {
        if (container) container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9888;</span>' + escHtml(err.message) + '</div>';
        if (refreshBtn) refreshBtn.disabled = false;
      });
  }

  /* ── Render entry controls ── */
  function renderEntries() {
    let container = document.getElementById('composer-entries');
    if (!container) return;

    let html = '<div class="grouped-rows">';
    _entries.forEach(function (e, i) {
      let w = e.weight.toFixed(1);
      html += '<div class="grouped-row" style="--row-i: ' + i + ';flex-wrap:wrap;">'
        + '<span class="grouped-row__icon">&#128196;</span>'
        + '<div class="grouped-row__content" style="min-width:120px;">'
        + '<div class="grouped-row__title type-caption-1">' + escHtml(e.path) + '</div>'
        + '<div class="grouped-row__subtitle type-caption-2">' + trunc(e.content_hash, 12) + ' &middot; ' + (e.size_bytes || 0) + ' B</div>'
        + '</div>'
        + '<label style="display:flex;align-items:center;gap:var(--space-1);font-size:var(--text-footnote);color:var(--text-secondary);flex-shrink:0;">'
        + '<span>wt:</span>'
        + '<input type="range" min="0" max="5" step="0.1" value="' + w + '" class="composer-weight-slider" data-idx="' + i + '" style="width:80px;accent-color:var(--accent);" oninput="composer.updateWeight(' + i + ', this.value)">'
        + '<input type="number" min="0" max="5" step="0.1" value="' + w + '" class="form-input composer-weight-input" data-idx="' + i + '" style="width:60px;text-align:center;padding:2px 4px;" onchange="composer.updateWeight(' + i + ', this.value)">'
        + '</label>'
        + '</div>';
    });
    html += '</div>';
    container.innerHTML = html;

    document.getElementById('btn-freeze-composition').disabled = false;

    // Show preview section
    document.getElementById('composition-preview').style.display = '';

    updatePreview();
  }

  /* ── Update weight ── */
  function updateWeight(idx, val) {
    if (idx < 0 || idx >= _entries.length) return;
    let w = parseFloat(val);
    if (isNaN(w)) w = 0;
    w = Math.max(0, Math.min(5, w));
    _entries[idx].weight = w;

    // Sync slider & number input
    let slider = document.querySelector('.composer-weight-slider[data-idx="' + idx + '"]');
    let input = document.querySelector('.composer-weight-input[data-idx="' + idx + '"]');
    if (slider && parseFloat(slider.value) !== w) slider.value = w.toFixed(1);
    if (input && parseFloat(input.value) !== w) input.value = w.toFixed(1);

    updatePreview();
  }

  /* ── Reset all weights to 1.0 ── */
  function resetWeights() {
    _entries.forEach(function (e) { e.weight = 1.0; });
    renderEntries();
  }

  /* ── Update distribution preview ── */
  function updatePreview() {
    let barsEl = document.getElementById('dist-bars');
    let summaryEl = document.getElementById('dist-summary');
    if (!barsEl) return;

    let totalWeight = _entries.reduce(function (sum, e) { return sum + e.weight; }, 0);
    let totalBytes = _entries.reduce(function (sum, e) { return sum + (e.size_bytes || 0) * e.weight; }, 0);
    let estTokens = Math.round(totalBytes / 4); // rough estimate: ~4 bytes per token

    let html = '';
    _entries.forEach(function (e) {
      let pct = totalWeight > 0 ? (e.weight / totalWeight * 100) : 0;
      let barWidth = Math.max(1, pct);
      html += '<div style="display:flex;align-items:center;gap:var(--space-2);">'
        + '<span class="type-caption-2 text-muted" style="min-width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escHtml(e.path.split('/').pop()) + '</span>'
        + '<div style="flex:1;height:12px;background:var(--surface-2);border-radius:6px;overflow:hidden;">'
        + '<div style="width:' + barWidth + '%;min-width:4px;height:100%;background:linear-gradient(90deg, var(--accent-orange), var(--accent-yellow));border-radius:6px;transition:width 0.2s ease;"></div>'
        + '</div>'
        + '<span class="type-caption-1 cell-numeric" style="min-width:60px;color:var(--text);font-weight:600;">' + e.weight.toFixed(1) + 'x</span>'
        + '<span class="type-caption-2 cell-numeric text-muted" style="min-width:50px;">' + pct.toFixed(1) + '%</span>'
        + '</div>';
    });
    barsEl.innerHTML = html;

    if (summaryEl) {
      summaryEl.textContent = 'Total weight: ' + totalWeight.toFixed(1) + ' &middot; '
        + 'Estimated bytes: ' + totalBytes.toLocaleString() + ' &middot; '
        + '~' + estTokens.toLocaleString() + ' estimated tokens'
        + ' &middot; ' + _entries.length + ' entries';
    }

    // Send preview request to backend
    sendCompositionPreview();
  }

  /* ── Send composition preview to backend ── */
  function sendCompositionPreview() {
    if (!_corpusId || !_entries.length) return;

    let body = _entries.map(function (e) {
      return { content_hash: e.content_hash, weight: e.weight };
    });

    api('/v1/content/corpora/' + _corpusId + '/composition/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(function (result) {
        // Update summary with backend-precise numbers
        let summaryEl = document.getElementById('dist-summary');
        if (summaryEl && result) {
          let totalWeight = _entries.reduce(function (s, e) { return s + e.weight; }, 0);
          let parts = [];
          if (result.total_bytes != null) parts.push(result.total_bytes.toLocaleString() + ' bytes');
          if (result.total_tokens != null) parts.push(result.total_tokens.toLocaleString() + ' tokens');
          if (result.entry_count != null) parts.push(result.entry_count + ' docs');
          parts.push('total wt: ' + totalWeight.toFixed(1));
          parts.push(_entries.length + ' entries');
          summaryEl.textContent = parts.join(' &middot; ');
        }
      })
      .catch(function () {
        // Backend preview is best-effort — fall back to client estimate
      });
  }

  /* ── Connect composition-preview SSE ── */
  function connectCompositionPreview() {
    if (_compositionPreviewStream) {
      _compositionPreviewStream.destroy();
      _compositionPreviewStream = null;
    }

    _compositionPreviewStream = { _es: null, _destroyed: false };

    _compositionPreviewStream._es = new EventSource('/v1/content/stream/composition');
    let self = _compositionPreviewStream;

    self._es.addEventListener('composition-preview', function (e) {
      try {
        let d = JSON.parse(e.data);
        let barsEl = document.getElementById('dist-bars');
        let summaryEl = document.getElementById('dist-summary');
        if (d.sources && barsEl) {
          let html = '';
          d.sources.forEach(function (src) {
            let barWidth = Math.max(1, src.percent || 0);
            html += '<div style="display:flex;align-items:center;gap:var(--space-2);">'
              + '<span class="type-caption-2 text-muted" style="min-width:60px;">' + escHtml(src.label || src.name || '?') + '</span>'
              + '<div style="flex:1;height:12px;background:var(--surface-2);border-radius:6px;overflow:hidden;">'
              + '<div style="width:' + barWidth + '%;min-width:4px;height:100%;background:linear-gradient(90deg, var(--accent-cyan), var(--accent));border-radius:6px;transition:width 0.2s;"></div>'
              + '</div>'
              + '<span class="type-caption-2 cell-numeric text-muted">' + src.bytes + ' B</span>'
              + '</div>';
          });
          barsEl.innerHTML = html;
        }
        if (d.summary && summaryEl) {
          summaryEl.textContent = d.summary;
        }
      } catch (_) {}
    });

    self._es.addEventListener('heartbeat', function () {
      // keep-alive — no action needed
    });

    self._es.addEventListener('error', function () {
      // Silent — composition preview is best-effort
    });

    self.destroy = function () {
      self._destroyed = true;
      if (self._es) { self._es.close(); self._es = null; }
    };
  }

  /* ── Freeze composition ── */
  function freezeComposition() {
    if (!_corpusId || !_entries.length) return;

    let freezeBtn = document.getElementById('btn-freeze-composition');
    let statusEl = document.getElementById('composer-status');
    if (freezeBtn) freezeBtn.disabled = true;
    if (statusEl) { statusEl.style.display = 'block'; statusEl.textContent = 'Freezing composition...'; statusEl.style.color = 'var(--text-tertiary)'; }

    let composition = _entries.map(function (e) {
      return { content_hash: e.content_hash, weight: e.weight };
    });

    api('/v1/content/corpora/' + _corpusId + '/freeze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: 'composition-' + Date.now(),
        composition: composition,
      }),
    })
      .then(function (data) {
        if (statusEl) {
          statusEl.innerHTML = '<span style="color:var(--accent-green);font-weight:600;">&#9874; Composition frozen as version #' + data.version_number + '</span>'
            + '<div class="type-caption-2" style="margin-top:2px;">digest: ' + trunc(data.manifest_digest, 20) + '</div>';
        }
        toast('Composition frozen: version #' + data.version_number, 'success');
        if (freezeBtn) freezeBtn.disabled = false;
      })
      .catch(function (err) {
        if (statusEl) { statusEl.textContent = 'Error: ' + err.message; statusEl.style.color = 'var(--accent-orange)'; }
        toast(err.message, 'error');
        if (freezeBtn) freezeBtn.disabled = false;
      });
  }

  /* ── Internal helpers ── */
  function resetEntries() {
    _entries = [];
    let container = document.getElementById('composer-entries');
    if (container) container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9876;</span><span>Select a corpus and load its entries to start composing.</span></div>';
    document.getElementById('composition-preview').style.display = 'none';
    document.getElementById('btn-freeze-composition').disabled = true;
  }

  /* ── Public API ── */
  window.composer = {
    mount: mount,
    selectCorpus: selectCorpus,
    loadEntries: loadEntries,
    updateWeight: updateWeight,
    resetWeights: resetWeights,
    freezeComposition: freezeComposition,
  };

})();