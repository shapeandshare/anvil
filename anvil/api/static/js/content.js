(function () {
  'use strict';

  /* ── State ── */
  let corporaCache = {};
  let sourcesCache = {};
  let sessionsCache = {};
  let _currentSessionId = null;

  let _injectionMonitor = null;

  /* ── Helpers ── */
  function escHtml(s) {
    if (s == null) return '';
    return String(s).replaceAll(/&/g, '&amp;').replaceAll(/</g, '&lt;').replaceAll(/>/g, '&gt;').replaceAll(/"/g, '&quot;');
  }

  function trunc(s, len) {
    if (!s) return '—';
    len = len || 16;
    return s.length > len ? s.slice(0, len) + '…' : s;
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

  function api(path, opts) {
    opts = opts || {};
    return (window.apiFetch || fetch)(path, opts)
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok || body.error) {
            throw new Error(body.detail || body.error || 'Request failed');
          }
          return body.data;
        });
      });
  }

  /* ── Toast variants ── */
  function toastSuccess(msg) { toast(msg, 'success'); }
  function toastError(msg) { toast(msg, 'error'); }

  /* ── Status line helper ── */
  function setStatus(id, msg, ok) {
    let el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
    el.style.color = ok ? 'var(--accent-green)' : 'var(--accent-orange)';
  }

  /* ── Corpus Form ── */
  function showCorpusForm() {
    let card = document.getElementById('corpus-form-card');
    if (card) card.style.display = '';
  }

  function hideCorpusForm() {
    let card = document.getElementById('corpus-form-card');
    if (card) card.style.display = 'none';
  }

  function createCorpus() {
    let name = document.getElementById('corpus-name').value.trim();
    if (!name) { setStatus('corpus-form-status', 'Name is required', false); return; }
    let slug = document.getElementById('corpus-slug').value.trim() || null;
    let desc = document.getElementById('corpus-desc').value.trim() || null;
    let chunking = document.getElementById('corpus-chunking').value;
    let blockSize = Number.parseInt(document.getElementById('corpus-block-size').value) || 16;
    let overlap = parseFloat(document.getElementById('corpus-overlap').value) || 0.5;

    api('/v1/content/corpora', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        slug: slug,
        description: desc,
        chunking_strategy: chunking,
        block_size: blockSize,
        chunk_overlap: overlap,
      }),
    })
      .then(function (data) {
        toastSuccess('Corpus "' + data.name + '" created');
        hideCorpusForm();
        document.getElementById('corpus-name').value = '';
        document.getElementById('corpus-slug').value = '';
        document.getElementById('corpus-desc').value = '';
        loadCorpora();
      })
      .catch(function (err) {
        setStatus('corpus-form-status', err.message, false);
      });
  }

  /* ── Load Corpora ── */
  function loadCorpora() {
    api('/v1/content/corpora')
      .then(function (data) {
        corporaCache = {};
        let list = document.getElementById('corpus-list');
        if (!list) return;

        // Populate both corpus selectors
        let ingestSelect = document.getElementById('ingest-corpus');
        let timelineSelect = document.getElementById('timeline-corpus');

        if (!data || !data.length) {
          list.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#128193;</span><span>No corpora yet.</span></div>';
          return;
        }

        let html = '<div class="grouped-rows">';
        data.forEach(function (c, i) {
          corporaCache[c.id] = c;
          let statusBadge = c.status === 'active' ? 'badge-green' : 'badge';
          html += '<div class="grouped-row" style="--row-i: ' + i + '">'
            + '<span class="grouped-row__icon">&#128193;</span>'
            + '<div class="grouped-row__content">'
            + '<div class="grouped-row__title">' + escHtml(c.name) + ' <span class="badge ' + statusBadge + '" style="font-size:var(--text-caption-2);padding:1px 6px;">' + escHtml(c.status) + '</span></div>'
            + '<div class="grouped-row__subtitle">slug: ' + escHtml(c.slug) + ' &middot; ' + (c.file_count || 0) + ' files &middot; ' + (c.document_count || 0) + ' docs &middot; ' + escHtml(c.chunking_strategy) + '</div>'
            + '</div>'
            + '<div class="grouped-row__action">'
            + '<button class="btn btn-sm btn-secondary" onclick="content.showVersions(' + c.id + ')">versions</button>'
            + '</div>'
            + '</div>';
        });
        html += '</div>';
        list.innerHTML = html;

        // Populate selectors
        let opts = '<option value="">— select corpus —</option>';
        data.forEach(function (c) {
          opts += '<option value="' + c.id + '">' + escHtml(c.name) + ' (' + c.slug + ')</option>';
        });
        if (ingestSelect) ingestSelect.innerHTML = opts;
        if (timelineSelect) timelineSelect.innerHTML = opts;
      })
      .catch(function (err) {
        let list = document.getElementById('corpus-list');
        if (list) list.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9888;</span><span>Error loading corpora: ' + escHtml(err.message) + '</span></div>';
      });
  }

  /* ── Create Source ── */
  function createSource() {
    let name = document.getElementById('source-name').value.trim();
    let slug = document.getElementById('source-slug').value.trim();
    let kind = document.getElementById('source-kind').value;
    if (!name || !slug) {
      setStatus('source-status', 'Name and slug are required', false);
      return;
    }
    api('/v1/content/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slug, name: name, kind: kind }),
    })
      .then(function (data) {
        toastSuccess('Source "' + data.name + '" registered');
        document.getElementById('source-name').value = '';
        document.getElementById('source-slug').value = '';
        loadSources();
      })
      .catch(function (err) {
        setStatus('source-status', err.message, false);
      });
  }

  /* ── Load Sources ── */
  function loadSources() {
    api('/v1/content/sources')
      .then(function (data) {
        sourcesCache = {};
        let select = document.getElementById('ingest-source');
        if (!select) return;
        let opts = '<option value="">— select source —</option>';
        (data || []).forEach(function (s) {
          sourcesCache[s.id] = s;
          opts += '<option value="' + escHtml(s.slug) + '">' + escHtml(s.name) + ' (' + escHtml(s.slug) + ')</option>';
        });
        select.innerHTML = opts;
      })
      .catch(function () {});
  }

  /* ── Open Session ── */
  function openSession() {
    let corpusId = Number.parseInt(document.getElementById('ingest-corpus').value);
    let source = document.getElementById('ingest-source').value;
    if (!corpusId || !source) {
      toastError('Select both a corpus and a source');
      return;
    }
    api('/v1/content/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ corpus_id: corpusId, source: source }),
    })
      .then(function (data) {
        _currentSessionId = data.id;
        sessionsCache[data.id] = data;
        toastSuccess('Session #' + data.id + ' opened');
        renderSessionInfo(data);
        document.getElementById('stage-area').style.display = '';
        loadActiveSessions();
      })
      .catch(function (err) {
        toastError(err.message);
      });
  }

  function renderSessionInfo(s) {
    let el = document.getElementById('session-info');
    if (!el) return;
    el.innerHTML = '<div class="help-box" style="margin:0;">'
      + '<span class="help-title">Session #' + s.id + '</span> &mdash; '
      + 'status: <span class="badge badge-green">' + escHtml(s.status) + '</span> &middot; '
      + 'staged: ' + (s.staged_entry_count || 0) + ' entries'
      + '</div>';
  }

  /* ── Stage File ── */
  function stageFile() {
    let sessionId = _currentSessionId;
    if (!sessionId) { toastError('No active session'); return; }
    let path = document.getElementById('stage-path').value.trim();
    let fileInput = document.getElementById('stage-file');
    if (!path || !fileInput.files.length) {
      toastError('Provide a path and select a file');
      return;
    }
    let file = fileInput.files[0];
    let formData = new FormData();
    formData.append('file', file);

    let statusEl = document.getElementById('stage-status');
    if (statusEl) statusEl.textContent = 'Uploading...';

    window.apiFetch('/v1/content/sessions/' + sessionId + '/stage?path=' + encodeURIComponent(path), {
      method: 'POST',
      body: formData,
    })
      .then(function (resp) {
        return resp.json().then(function (body) {
          if (!resp.ok || body.error) throw new Error(body.detail || body.error || 'Upload failed');
          return body.data;
        });
      })
      .then(function (data) {
        toastSuccess('Staged: ' + data.path + ' (' + data.size_bytes + ' bytes)');
        if (statusEl) {
          statusEl.textContent = 'Staged ' + data.path + ' &middot; hash: ' + trunc(data.content_hash);
          statusEl.style.color = 'var(--accent-green)';
        }
        loadActiveSessions();
      })
      .catch(function (err) {
        if (statusEl) { statusEl.textContent = err.message; statusEl.style.color = 'var(--accent-orange)'; }
        toastError(err.message);
      });
  }

  /* ── Validate Session ── */
  function validateSession() {
    let sessionId = _currentSessionId;
    if (!sessionId) { toastError('No active session'); return; }
    let reportEl = document.getElementById('validation-report');
    if (reportEl) reportEl.innerHTML = '<span class="spinner"></span> Validating...';

    api('/v1/content/sessions/' + sessionId + '/validate', { method: 'POST' })
      .then(function (data) {
        if (!reportEl) return;
        if (data.ok) {
          reportEl.innerHTML = '<div class="help-box" style="margin:0;border-left:3px solid var(--accent-green);">'
            + '<span style="color:var(--accent-green);font-weight:600;">&#10003; Validation passed</span></div>';
          toastSuccess('Validation passed');
        } else {
          let problems = data.problems || [];
          let html = '<div class="help-box" style="margin:0;border-left:3px solid var(--accent-orange);">'
            + '<span style="color:var(--accent-orange);font-weight:600;">&#9888; ' + problems.length + ' problem(s)</span>';
          problems.forEach(function (p) {
            html += '<div style="margin-top:var(--space-1);font-size:var(--text-footnote);">'
              + '&bull; ' + escHtml(p.message || JSON.stringify(p)) + '</div>';
          });
          html += '</div>';
          reportEl.innerHTML = html;
          toastError(problems.length + ' validation problem(s)');
        }
        loadActiveSessions();
      })
      .catch(function (err) {
        if (reportEl) reportEl.innerHTML = '<div class="help-box" style="margin:0;border-left:3px solid var(--accent-red);">&#9888; ' + escHtml(err.message) + '</div>';
        toastError(err.message);
      });
  }

  /* ── Accept Session ── */
  function acceptSession() {
    let sessionId = _currentSessionId;
    if (!sessionId) { toastError('No active session'); return; }
    let resultEl = document.getElementById('accept-result');
    if (resultEl) resultEl.innerHTML = '<span class="spinner"></span> Accepting...';

    api('/v1/content/sessions/' + sessionId + '/accept', { method: 'POST' })
      .then(function (data) {
        if (resultEl) {
          resultEl.innerHTML = '<div class="help-box" style="margin:0;border-left:3px solid var(--accent-green);">'
            + '<span style="color:var(--accent-green);font-weight:600;">&#9874; Accepted!</span>'
            + '<div style="margin-top:var(--space-1);font-size:var(--text-footnote);">'
            + 'Version #' + data.version_number + ' &middot; '
            + data.entry_count + ' entries &middot; '
            + data.total_bytes + ' bytes &middot; '
            + 'digest: ' + trunc(data.manifest_digest, 20)
            + '</div></div>';
        }
        toastSuccess('Session accepted — version #' + data.version_number);
        _currentSessionId = null;
        document.getElementById('stage-area').style.display = 'none';
        document.getElementById('session-info').innerHTML = '';
        loadActiveSessions();
        loadCorpora();
      })
      .catch(function (err) {
        if (resultEl) resultEl.innerHTML = '<div class="help-box" style="margin:0;border-left:3px solid var(--accent-red);">&#9888; ' + escHtml(err.message) + '</div>';
        toastError(err.message);
      });
  }

  /* ── Abandon Session ── */
  function abandonSession() {
    let sessionId = _currentSessionId;
    if (!sessionId) { toastError('No active session'); return; }
    api('/v1/content/sessions/' + sessionId + '/abandon', { method: 'POST' })
      .then(function () {
        toastSuccess('Session abandoned');
        _currentSessionId = null;
        document.getElementById('stage-area').style.display = 'none';
        document.getElementById('session-info').innerHTML = '';
        loadActiveSessions();
      })
      .catch(function (err) {
        toastError(err.message);
      });
  }

  /* ── Load Active Sessions ── */
  function loadActiveSessions() {
    api('/v1/content/sessions')
      .then(function (data) {
        sessionsCache = {};
        let container = document.getElementById('injection-sessions');
        let badge = document.getElementById('injection-badge');
        if (!container) return;
        let sessions = data || [];
        if (badge) {
          let active = sessions.length;
          badge.textContent = active + ' active';
          badge.style.display = active ? '' : 'none';
        }
        if (!sessions.length) {
          container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9889;</span><span>No active ingestion sessions.</span></div>';
          return;
        }
        let html = '<div class="table-scroll"><table class="grouped-list">'
          + '<thead><tr><th>ID</th><th>Source</th><th>Status</th><th>Staged</th><th>Opened</th></tr></thead><tbody>';
        sessions.forEach(function (s) {
          let statusClass = 'badge-green';
          if (s.status === 'validating') statusClass = 'badge-yellow';
          else if (s.status === 'failed') statusClass = 'badge-red';
          html += '<tr>'
            + '<td class="cell-mono">#' + s.id + '</td>'
            + '<td>' + escHtml(s.source_id || '?') + '</td>'
            + '<td><span class="badge ' + statusClass + '">' + escHtml(s.status) + '</span></td>'
            + '<td class="cell-numeric">' + (s.staged_entry_count || 0) + '</td>'
            + '<td class="cell-meta">' + (s.opened_at ? new Date(s.opened_at).toLocaleString() : '—') + '</td>'
            + '</tr>';
        });
        html += '</tbody></table></div>';
        container.innerHTML = html;
      })
      .catch(function () {});
  }

  /* ── Show Versions (corpus) ── */
  function showVersions(corpusId) {
    let timelineSelect = document.getElementById('timeline-corpus');
    if (timelineSelect) timelineSelect.value = corpusId;
    loadTimeline();
  }

  /* ── Load Version Timeline ── */
  function loadTimeline() {
    let corpusId = Number.parseInt(document.getElementById('timeline-corpus').value);
    let container = document.getElementById('version-timeline');
    if (!container) return;
    if (!corpusId) {
      container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#128196;</span><span>Select a corpus to view versions.</span></div>';
      return;
    }

    api('/v1/content/corpora/' + corpusId + '/versions')
      .then(function (data) {
        if (!data || !data.length) {
          container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#128196;</span><span>No versions yet.</span></div>';
          return;
        }
        let html = '<div class="table-scroll"><table class="grouped-list">'
          + '<thead><tr><th>Version</th><th>Manifest Digest</th><th>Entries</th><th>Label/Tag</th><th>Created</th><th>Diff</th><th>Lineage</th></tr></thead><tbody>';

        data.forEach(function (v, i) {
          let prevDigest = i > 0 ? '(v' + data[i - 1].version_number + ')' : '—';
          html += '<tr>'
            + '<td class="cell-mono"><strong>v' + v.version_number + '</strong></td>'
            + '<td class="cell-mono cell-wrap" style="max-width:140px;"><code style="font-size:var(--text-caption-1);">' + trunc(v.manifest_digest, 20) + '</code></td>'
            + '<td class="cell-numeric">' + (v.entry_count || 0) + '</td>'
            + '<td>' + (v.label || v.tag || '—') + '</td>'
            + '<td class="cell-meta">' + (v.created_at ? new Date(v.created_at).toLocaleDateString() : '—') + '</td>'
            + '<td class="cell-meta">' + prevDigest + '</td>'
            + '<td><button class="btn btn-sm btn-secondary" onclick="content.loadLineage(' + v.id + ')">lineage</button></td>'
            + '</tr>';
        });
        html += '</tbody></table></div>';
        container.innerHTML = html;
      })
      .catch(function (err) {
        container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9888;</span>' + escHtml(err.message) + '</div>';
      });
  }

  /* ── Load Lineage ── */
  function loadLineage(versionId) {
    let container = document.getElementById('lineage-view');
    if (!container) return;
    container.innerHTML = '<span class="spinner"></span> Loading lineage...';

    api('/v1/content/versions/' + versionId + '/lineage')
      .then(function (data) {
        if (!data || !data.run_refs || !data.run_refs.length) {
          container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#128279;</span><span>No lineage data for this version.</span></div>';
          return;
        }
        let html = '<div class="help-box" style="margin:0;">'
          + '<div class="help-title">Version #' + versionId + ' — Lineage</div>';
        data.run_refs.forEach(function (ref) {
          html += '<div style="margin-top:var(--space-1);font-size:var(--text-footnote);">'
            + 'MLflow run: <code>' + trunc(ref.mlflow_run_id, 16) + '</code>'
            + (ref.corpus_ref ? ' &middot; corpus ref: ' + escHtml(ref.corpus_ref) : '')
            + '</div>';
        });
        html += '</div>';
        container.innerHTML = html;
      })
      .catch(function (err) {
        container.innerHTML = '<div class="empty-state-card"><span class="empty-state-card__icon">&#9888;</span>' + escHtml(err.message) + '</div>';
      });
  }

  /* ── Injection Monitor SSE ── */
  function startInjectionMonitor() {
    if (_injectionMonitor) {
      _injectionMonitor.destroy();
      _injectionMonitor = null;
    }
    let stateEl = document.getElementById('injection-state');
    let badge = document.getElementById('injection-badge');

    _injectionMonitor = {
      _es: null,
      _destroyed: false,
      _retryCount: 0,
      _maxRetries: 5,
      _backoff: [1000, 2000, 4000, 8000, 16000],

      connect: function () {
        if (this._destroyed) return;
        if (this._es) this._es.close();
        let self = this;
        this._es = new EventSource('/v1/content/stream/injection');
        if (stateEl) { stateEl.textContent = 'connecting'; stateEl.className = 'connection-state cs-connecting'; }

        this._es.addEventListener('open', function () {
          self._retryCount = 0;
          if (stateEl) { stateEl.textContent = 'connected'; stateEl.className = 'connection-state cs-streaming'; }
        });

        this._es.addEventListener('injection-status', function (e) {
          try {
            let d = JSON.parse(e.data);
            if (badge && d.active_sessions != null) {
              badge.textContent = d.active_sessions + ' active';
              badge.style.display = d.active_sessions ? '' : 'none';
            }
            loadActiveSessions();
          } catch (_) {}
        });

        this._es.addEventListener('heartbeat', function () {
          // keep-alive — no action needed
        });

        this._es.addEventListener('error', function () {
          if (self._destroyed) return;
          if (self._retryCount < self._maxRetries) {
            if (stateEl) { stateEl.textContent = 'reconnecting (' + (self._retryCount + 1) + ')'; stateEl.className = 'connection-state cs-reconnecting'; }
            let delay = self._backoff[self._retryCount];
            self._retryCount++;
            setTimeout(function () { self.connect(); }, delay);
          } else {
            if (stateEl) { stateEl.textContent = 'disconnected'; stateEl.className = 'connection-state cs-errored'; }
          }
        });
      },

      destroy: function () {
        this._destroyed = true;
        if (this._es) { this._es.close(); this._es = null; }
        if (stateEl) { stateEl.textContent = 'disconnected'; stateEl.className = 'connection-state cs-idle'; }
      },
    };

    _injectionMonitor.connect();
  }

  /* ── Init ── */
  function init() {
    loadCorpora();
    loadSources();
    loadActiveSessions();
    startInjectionMonitor();
  }

  /* ── Public API ── */
  window.content = {
    showCorpusForm: showCorpusForm,
    hideCorpusForm: hideCorpusForm,
    createCorpus: createCorpus,
    createSource: createSource,
    openSession: openSession,
    stageFile: stageFile,
    validateSession: validateSession,
    acceptSession: acceptSession,
    abandonSession: abandonSession,
    showVersions: showVersions,
    loadTimeline: loadTimeline,
    loadLineage: loadLineage,
    loadCorpora: loadCorpora,
    loadActiveSessions: loadActiveSessions,
    refresh: init,
  };

  /* ── Run on page load ── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
