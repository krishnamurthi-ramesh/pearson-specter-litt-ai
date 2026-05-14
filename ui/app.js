/**
 * app.js
 * ======
 * Frontend logic for the Pearson Specter Litt Document Intelligence UI.
 */

const API = '/api';

// ── Navigation ────────────────────────────────────────────────
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('panel-' + btn.dataset.panel).classList.add('active');

        // Load data when switching panels
        if (btn.dataset.panel === 'draft') loadDocList();
        if (btn.dataset.panel === 'feedback') loadFeedback();
    });
});

// ── Helpers ───────────────────────────────────────────────────
function show(id) { document.getElementById(id)?.classList.remove('hidden'); }
function hide(id) { document.getElementById(id)?.classList.add('hidden'); }
function setStatus(msg, type = 'processing') {
    const el = document.getElementById('upload-status');
    el.textContent = msg;
    el.className = 'status-bar ' + type;
    show('upload-status');
}

async function api(path, opts = {}) {
    const resp = await fetch(API + path, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || 'API error');
    }
    return resp.json();
}

// ── Panel 1: Document Upload ──────────────────────────────────
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

const hfBtn = document.getElementById('import-hf-btn');
if (hfBtn) {
    hfBtn.addEventListener('click', async () => {
        setStatus('⏳ Streaming & parsing real-world Congressional legislation from Hugging Face Hub…', 'processing');
        hide('doc-results');
        hfBtn.disabled = true;

        try {
            // Generates a random bill index 0-20 for rich variation
            const randIdx = Math.floor(Math.random() * 15);
            const data = await api(`/huggingface/import?item_index=${randIdx}`, { method: 'POST' });
            setStatus(` Successfully imported "${data.doc_id}" from Hugging Face 'billsum'! Indexed ${data.num_chunks} context chunks.`, 'success');
            renderDocResults(data);
        } catch (err) {
            setStatus(`Dataset Import Failed: ${err.message}. Ensure backend server has active internet access to download from Hugging Face.`, 'error');
        } finally {
            hfBtn.disabled = false;
        }
    });
}

async function handleFiles(files) {
    for (const file of files) {
        await uploadFile(file);
    }
}

async function uploadFile(file) {
    setStatus(`⏳ Processing "${file.name}"…`, 'processing');
    hide('doc-results');

    const form = new FormData();
    form.append('file', file);

    try {
        const data = await api('/documents/upload', { method: 'POST', body: form });
        setStatus(`✅ "${file.name}" processed successfully — ${data.num_chunks} chunks indexed`, 'success');
        renderDocResults(data);
    } catch (err) {
        setStatus(`❌ Error: ${err.message}`, 'error');
    }
}

function renderDocResults(data) {
    // Extracted text
    document.getElementById('extracted-text').textContent = data.cleaned_text;

    // Structured data
    const sd = data.structured_data;
    let html = '';
    for (const [key, val] of Object.entries(sd)) {
        if (Array.isArray(val) && val.length > 0) {
            const tagClass = key === 'dates' ? 'gold' : key === 'amounts' ? 'green' : '';
            html += `<div class="tag-group">
                <div class="label">${key}</div>
                <div class="tag-list">${val.map(v => `<span class="tag ${tagClass}">${v}</span>`).join('')}</div>
            </div>`;
        } else if (!Array.isArray(val)) {
            html += `<div class="tag-group">
                <div class="label">${key}</div>
                <div class="tag-list"><span class="tag">${val}</span></div>
            </div>`;
        }
    }
    document.getElementById('structured-data').innerHTML = html;

    // Metadata
    const meta = [
        { label: 'Document ID', value: data.doc_id },
        { label: 'File Type', value: data.file_type.toUpperCase() },
        { label: 'OCR Used', value: data.ocr_used ? 'Yes' : 'No' },
        { label: 'Confidence', value: (data.confidence * 100).toFixed(0) + '%' },
        { label: 'Quality Score', value: (data.quality_score * 100).toFixed(0) + '%' },
        { label: 'Text Length', value: data.text_length.toLocaleString() + ' chars' },
        { label: 'Pages', value: data.num_pages },
        { label: 'Chunks', value: data.num_chunks },
    ];
    document.getElementById('doc-metadata').innerHTML = meta.map(m =>
        `<div class="meta-item"><div class="label">${m.label}</div><div class="value">${m.value}</div></div>`
    ).join('');

    show('doc-results');
}

// ── Panel 2: Retrieval ────────────────────────────────────────
document.getElementById('search-btn').addEventListener('click', doSearch);
document.getElementById('search-query').addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
});

async function doSearch() {
    const query = document.getElementById('search-query').value.trim();
    if (!query) return;

    const container = document.getElementById('search-results');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching…</p></div>';

    try {
        const data = await api(`/retrieve?query=${encodeURIComponent(query)}&n=8`);
        if (data.results.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem;">No results found. Upload a document first.</p>';
            return;
        }
        container.innerHTML = data.results.map(r => `
            <div class="result-item">
                <div class="result-meta">
                    <span>📄 ${r.doc_id}</span>
                    <span>📃 Page ${r.page}</span>
                    <span>🎯 ${(r.similarity * 100).toFixed(1)}%
                        <span class="similarity-bar" style="width:${r.similarity * 60}px"></span>
                    </span>
                </div>
                <div class="result-text">${r.text}</div>
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = `<p style="color:var(--danger);">Error: ${err.message}</p>`;
    }
}

// ── Panel 3: Draft Generation ─────────────────────────────────
async function loadDocList() {
    try {
        const data = await api('/documents');
        const sel = document.getElementById('draft-doc-id');
        sel.innerHTML = data.documents.map(d => `<option value="${d}">${d}</option>`).join('');
    } catch (e) { }
}

document.getElementById('generate-btn').addEventListener('click', generateDraft);

async function generateDraft() {
    const docId = document.getElementById('draft-doc-id').value;
    const draftType = document.getElementById('draft-type').value;
    if (!docId) return alert('Upload a document first');

    hide('draft-output');
    show('draft-loading');
    document.getElementById('generate-btn').disabled = true;

    try {
        const data = await api('/drafts/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doc_id: docId, draft_type: draftType }),
        });

        document.getElementById('draft-text').value = data.draft_text;
        document.getElementById('edited-text').value = data.draft_text;

        // Grounding badge
        const score = data.grounding_report?.grounding_score || 0;
        const badge = document.getElementById('grounding-badge');
        badge.textContent = `Grounding: ${(score * 100).toFixed(0)}%`;
        badge.className = 'badge ' + (score > 0.7 ? 'high' : score > 0.4 ? '' : 'low');

        // --- Agentic Self-Correction Badge Display ---
        const agenticAlert = document.getElementById('agentic-heal-alert');
        if (data.agentic_self_correction_applied) {
            document.getElementById('agentic-heal-log').innerHTML = (data.agentic_remediation_logs || []).join(' &middot; ');
            agenticAlert?.classList.remove('hidden');
        } else {
            agenticAlert?.classList.add('hidden');
        }

        // Evidence
        const evList = document.getElementById('evidence-list');
        evList.innerHTML = (data.evidence_used || []).map(e =>
            `<div class="evidence-item">
                <div class="ev-meta">📄 ${e.doc_id} · Page ${e.page} · Relevance: ${(e.similarity * 100).toFixed(0)}%</div>
            </div>`
        ).join('');

        hide('draft-loading');
        show('draft-output');
    } catch (err) {
        hide('draft-loading');
        alert('Error: ' + err.message);
    }
    document.getElementById('generate-btn').disabled = false;
}

document.getElementById('submit-edit-btn').addEventListener('click', submitEdit);

async function submitEdit() {
    const docId = document.getElementById('draft-doc-id').value;
    const draftType = document.getElementById('draft-type').value;
    const original = document.getElementById('draft-text').value;
    const edited = document.getElementById('edited-text').value;

    if (original === edited) return alert('No changes detected');

    try {
        const data = await api('/drafts/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id: docId,
                draft_type: draftType,
                original_text: original,
                edited_text: edited,
            }),
        });
        alert(`✅ Edit saved! ${data.patterns_extracted} patterns extracted.\nChange ratio: ${data.diff.change_ratio}%`);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// ── Panel 4: Feedback Dashboard ───────────────────────────────
async function loadFeedback() {
    try {
        const data = await api('/feedback/patterns');

        // Metrics
        const m = data.metrics;
        document.getElementById('metric-edits').textContent = m.total_edits;
        document.getElementById('metric-patterns').textContent = m.patterns_learned;
        document.getElementById('metric-change').textContent = m.avg_change_ratio + '%';
        document.getElementById('metric-improvement').textContent =
            m.improvement_detected ? '📈 Improving' : m.total_edits > 0 ? '➡️ Stable' : '—';

        // Patterns
        const pc = document.getElementById('patterns-container');
        if (data.patterns.length === 0) {
            pc.innerHTML = '<p style="color:var(--text-muted);padding:1rem;">No patterns learned yet. Edit a draft to start the learning loop.</p>';
        } else {
            pc.innerHTML = data.patterns.map(p => `
                <div class="pattern-item">
                    <span class="pattern-type-badge ${p.pattern_type}">${p.pattern_type}</span>
                    <span class="pattern-desc">${p.description}</span>
                    <span class="pattern-freq">${p.frequency}×</span>
                </div>
            `).join('');
        }

        // Edits
        const edits = await api('/feedback/edits?limit=10');
        const ec = document.getElementById('edits-container');
        if (edits.edits.length === 0) {
            ec.innerHTML = '<p style="color:var(--text-muted);padding:1rem;">No edits recorded yet.</p>';
        } else {
            ec.innerHTML = edits.edits.map(e => {
                const stats = JSON.parse(e.edit_stats);
                return `<div class="edit-item">
                    <div class="edit-meta">📄 ${e.doc_id} · ${e.draft_type} · ${e.created_at} · Change: ${stats.change_ratio}%</div>
                    <div style="color:var(--text-secondary);font-size:0.8rem;">${e.edited_text}</div>
                </div>`;
            }).join('');
        }
    } catch (err) {
        console.error('Failed to load feedback:', err);
    }
}

// ── Init ──────────────────────────────────────────────────────
console.log('🏛️ Pearson Specter Litt — Document Intelligence System loaded');
