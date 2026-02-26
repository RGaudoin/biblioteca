/* Biblioteca — frontend logic */

let searchTimeout = null;
let currentPaperId = null;

// --- Navigation ---

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(sectionId).classList.add('active');
    event.target.classList.add('active');

    if (sectionId === 'library') refreshLibrary();
    if (sectionId === 'collections') refreshCollections();
    if (sectionId === 'settings') loadSettings();
}

function showTab(section, tabId) {
    const parent = document.getElementById(section);
    parent.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
}


// --- Library ---

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(refreshLibrary, 300);
}

async function refreshLibrary() {
    const search = document.getElementById('search-input').value;
    const tag = document.getElementById('tag-filter').value;
    const topic = document.getElementById('topic-filter').value;

    const params = new URLSearchParams();
    if (search) params.set('q', search);
    if (tag) params.set('tag', tag);
    if (topic) params.set('topic', topic);
    params.set('limit', '100');

    try {
        const resp = await fetch('/api/papers?' + params);
        const data = await resp.json();
        renderPaperList(data.papers, data.total);
    } catch (err) {
        console.error('Failed to load papers:', err);
    }

    // Refresh filters
    loadFilters();
}

function renderPaperList(papers, total) {
    const container = document.getElementById('paper-list');
    const countEl = document.getElementById('paper-count');
    countEl.textContent = `${total} paper${total !== 1 ? 's' : ''}`;

    if (papers.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No papers found</p><p>Import some papers to get started.</p></div>';
        return;
    }

    container.innerHTML = papers.map(p => {
        const title = p.title || '(no title)';
        const authors = (p.authors || []).join(', ');
        const year = p.year || '';
        const meta = [authors, year, p.source].filter(Boolean).join(' · ');
        const badge = p.pdf_filename ? '<span class="badge-pdf">PDF</span>' : '<span class="badge-ref">REF</span>';
        const tags = (p.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('');
        const topics = (p.topics || []).map(t => `<span class="tag topic">${esc(t)}</span>`).join('');

        return `<div class="paper-card" onclick="openPaper('${esc(p.id)}')">
            <div class="paper-title">${badge} ${esc(title)}</div>
            <div class="paper-meta">${esc(meta)}</div>
            ${(tags || topics) ? `<div class="paper-tags">${tags}${topics}</div>` : ''}
        </div>`;
    }).join('');
}

async function loadFilters() {
    try {
        const [tagsResp, topicsResp] = await Promise.all([
            fetch('/api/tags'),
            fetch('/api/topics')
        ]);
        const tags = await tagsResp.json();
        const topics = await topicsResp.json();

        const tagSelect = document.getElementById('tag-filter');
        const currentTag = tagSelect.value;
        tagSelect.innerHTML = '<option value="">All tags</option>' +
            Object.entries(tags).map(([t, c]) =>
                `<option value="${esc(t)}"${t === currentTag ? ' selected' : ''}>${esc(t)} (${c})</option>`
            ).join('');

        const topicSelect = document.getElementById('topic-filter');
        const currentTopic = topicSelect.value;
        topicSelect.innerHTML = '<option value="">All topics</option>' +
            Object.entries(topics).map(([t, c]) =>
                `<option value="${esc(t)}"${t === currentTopic ? ' selected' : ''}>${esc(t)} (${c})</option>`
            ).join('');
    } catch (err) {
        console.error('Failed to load filters:', err);
    }
}


// --- Paper Detail Modal ---

async function openPaper(paperId) {
    currentPaperId = paperId;
    try {
        const resp = await fetch(`/api/papers/${paperId}`);
        const paper = await resp.json();
        renderPaperModal(paper);
        document.getElementById('paper-modal').classList.add('active');
    } catch (err) {
        console.error('Failed to load paper:', err);
    }
}

function renderPaperModal(p) {
    document.getElementById('modal-title').textContent = p.title || '(no title)';

    const fields = [
        { label: 'Authors', value: (p.authors || []).join(', ') },
        { label: 'Year', value: p.year },
        { label: 'Source', value: p.source },
        { label: 'Tags', value: (p.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join(' '), html: true },
        { label: 'Topics', value: (p.topics || []).map(t => `<span class="tag topic">${esc(t)}</span>`).join(' '), html: true },
        { label: 'Summary', value: p.summary },
        { label: 'Notes', value: p.notes },
        { label: 'URL', value: p.url ? `<a href="${esc(p.url)}" target="_blank">${esc(p.url)}</a>` : null, html: true },
        { label: 'arXiv ID', value: p.arxiv_id },
        { label: 'DOI', value: p.doi },
        { label: 'PDF', value: p.pdf_filename },
        { label: 'Added', value: p.added },
        { label: 'Import source', value: p.import_source },
    ];

    const fieldsHtml = fields
        .filter(f => f.value)
        .map(f => `<div class="field">
            <div class="field-label">${f.label}</div>
            <div class="field-value">${f.html ? f.value : esc(String(f.value))}</div>
        </div>`)
        .join('');

    const pdfBtn = p.pdf_filename
        ? `<button onclick="window.open('/api/pdf/${encodeURIComponent(p.pdf_filename)}', '_blank')">View PDF</button>`
        : '';
    const aiBtn = p.pdf_filename
        ? `<button onclick="extractMetadata('${esc(p.id)}')">Extract Metadata (AI)</button>
           <button onclick="summarisePaper('${esc(p.id)}')">Summarise (AI)</button>`
        : '';

    document.getElementById('modal-body').innerHTML = `
        ${fieldsHtml}
        <div class="modal-actions">
            ${pdfBtn}
            ${aiBtn}
            <button onclick="editPaper('${esc(p.id)}')">Edit</button>
            <button onclick="deletePaper('${esc(p.id)}')" style="color:var(--error)">Delete</button>
        </div>
    `;
}

function closeModal() {
    document.getElementById('paper-modal').classList.remove('active');
    currentPaperId = null;
}

async function extractMetadata(paperId) {
    showModalLoading('Extracting metadata...');
    try {
        const resp = await fetch(`/api/ai/extract/${paperId}`, { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            renderPaperModal(data.paper);
            refreshLibrary();
        } else {
            alert('Extraction failed: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function summarisePaper(paperId) {
    showModalLoading('Generating summary...');
    try {
        const resp = await fetch(`/api/ai/summarise/${paperId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ style: 'brief' })
        });
        const data = await resp.json();
        if (data.success) {
            renderPaperModal(data.paper);
        } else {
            alert('Summarisation failed: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

function showModalLoading(msg) {
    const actions = document.querySelector('.modal-actions');
    if (actions) actions.innerHTML = `<div class="loading">${esc(msg)}</div>`;
}

async function editPaper(paperId) {
    const resp = await fetch(`/api/papers/${paperId}`);
    const paper = await resp.json();

    const body = document.getElementById('modal-body');
    body.innerHTML = `
        <div class="field">
            <label>Title<input type="text" id="edit-title" value="${esc(paper.title || '')}"></label>
        </div>
        <div class="field">
            <label>Authors (comma-separated)<input type="text" id="edit-authors" value="${esc((paper.authors || []).join(', '))}"></label>
        </div>
        <div class="field">
            <label>Year<input type="text" id="edit-year" value="${paper.year || ''}"></label>
        </div>
        <div class="field">
            <label>Source<input type="text" id="edit-source" value="${esc(paper.source || '')}"></label>
        </div>
        <div class="field">
            <label>Tags (comma-separated)<input type="text" id="edit-tags" value="${esc((paper.tags || []).join(', '))}"></label>
        </div>
        <div class="field">
            <label>Topics (comma-separated)<input type="text" id="edit-topics" value="${esc((paper.topics || []).join(', '))}"></label>
        </div>
        <div class="field">
            <label>Notes<textarea id="edit-notes" rows="3">${esc(paper.notes || '')}</textarea></label>
        </div>
        <div class="field">
            <label>URL<input type="text" id="edit-url" value="${esc(paper.url || '')}"></label>
        </div>
        <div class="modal-actions">
            <button type="submit" onclick="saveEdit('${esc(paperId)}')">Save</button>
            <button onclick="openPaper('${esc(paperId)}')">Cancel</button>
        </div>
    `;
}

async function saveEdit(paperId) {
    const splitCsv = v => v.split(',').map(s => s.trim()).filter(Boolean);
    const yearVal = document.getElementById('edit-year').value.trim();

    const data = {
        title: document.getElementById('edit-title').value.trim() || null,
        authors: splitCsv(document.getElementById('edit-authors').value),
        year: yearVal ? parseInt(yearVal) : null,
        source: document.getElementById('edit-source').value.trim() || null,
        tags: splitCsv(document.getElementById('edit-tags').value),
        topics: splitCsv(document.getElementById('edit-topics').value),
        notes: document.getElementById('edit-notes').value.trim() || null,
        url: document.getElementById('edit-url').value.trim() || null,
    };

    try {
        const resp = await fetch(`/api/papers/${paperId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await resp.json();
        if (result.success) {
            renderPaperModal(result.paper);
            refreshLibrary();
        } else {
            alert('Save failed: ' + (result.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function deletePaper(paperId) {
    if (!confirm('Delete this paper and its PDF? This cannot be undone.')) return;

    try {
        const resp = await fetch(`/api/papers/${paperId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            closeModal();
            refreshLibrary();
        } else {
            alert('Delete failed: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}


// --- Import handlers ---

async function handleUpload(e) {
    e.preventDefault();
    const file = document.getElementById('pdf-file').files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('ai', document.getElementById('upload-ai').checked);

    showResult('upload-result', 'info', 'Importing...');

    try {
        const resp = await fetch('/api/import/file', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.success) {
            showResult('upload-result', 'success', `Imported: ${data.paper_id}\n${formatMeta(data.paper)}`);
            refreshLibrary();
        } else {
            showResult('upload-result', 'error', `Error: ${data.error}`);
        }
    } catch (err) {
        showResult('upload-result', 'error', `Error: ${err.message}`);
    }
}

async function handleUrlImport(e) {
    e.preventDefault();
    const url = document.getElementById('import-url').value.trim();
    showResult('url-result', 'info', 'Importing...');

    try {
        const resp = await fetch('/api/import/url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await resp.json();
        if (data.success) {
            let msg = `Imported: ${data.paper_id}`;
            if (data.note) msg += `\n${data.note}`;
            msg += '\n' + formatMeta(data.paper);
            showResult('url-result', 'success', msg);
            refreshLibrary();
        } else {
            showResult('url-result', 'error', `Error: ${data.error}`);
        }
    } catch (err) {
        showResult('url-result', 'error', `Error: ${err.message}`);
    }
}

async function handleArxivImport(e) {
    e.preventDefault();
    const arxivId = document.getElementById('arxiv-id').value.trim();
    showResult('arxiv-result', 'info', 'Fetching from arXiv...');

    try {
        const resp = await fetch('/api/import/arxiv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ arxiv_id: arxivId })
        });
        const data = await resp.json();
        if (data.success) {
            showResult('arxiv-result', 'success', `Imported: ${data.paper_id}\n${formatMeta(data.paper)}`);
            refreshLibrary();
        } else {
            showResult('arxiv-result', 'error', `Error: ${data.error}`);
        }
    } catch (err) {
        showResult('arxiv-result', 'error', `Error: ${err.message}`);
    }
}

async function handleBatchImport(e) {
    e.preventDefault();
    const folder = document.getElementById('batch-folder').value.trim();
    const ai = document.getElementById('batch-ai').checked;
    showResult('batch-result', 'info', 'Importing folder...');

    try {
        const resp = await fetch('/api/import/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder, ai })
        });
        const data = await resp.json();
        let msg = '';
        if (data.imported) msg += `Imported (${data.imported.length}):\n` + data.imported.map(i => `  ${i.paper_id}`).join('\n') + '\n';
        if (data.skipped && data.skipped.length) msg += `\nSkipped (${data.skipped.length}):\n` + data.skipped.map(s => `  ${s.path}: ${s.reason}`).join('\n') + '\n';
        if (data.failed && data.failed.length) msg += `\nFailed (${data.failed.length}):\n` + data.failed.map(f => `  ${f.path}: ${f.error}`).join('\n');
        showResult('batch-result', data.failed && data.failed.length ? 'error' : 'success', msg || 'No PDFs found.');
        refreshLibrary();
    } catch (err) {
        showResult('batch-result', 'error', `Error: ${err.message}`);
    }
}

async function handleEmailImport(e) {
    e.preventDefault();
    const text = document.getElementById('email-text').value.trim();
    showResult('email-result', 'info', 'Parsing and importing...');

    try {
        const resp = await fetch('/api/import/emails', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await resp.json();
        let msg = `URLs found: ${data.urls_found.length}\n`;
        data.urls_found.forEach(u => msg += `  ${u}\n`);
        if (data.imported.length) msg += `\nImported (${data.imported.length}):\n` + data.imported.map(i => `  ${i.paper_id} (${i.url})`).join('\n') + '\n';
        if (data.failed.length) msg += `\nFailed (${data.failed.length}):\n` + data.failed.map(f => `  ${f.url}: ${f.error}`).join('\n');
        showResult('email-result', data.failed.length ? 'error' : 'success', msg);
        refreshLibrary();
    } catch (err) {
        showResult('email-result', 'error', `Error: ${err.message}`);
    }
}


// --- Collections ---

async function refreshCollections() {
    document.getElementById('collection-detail').style.display = 'none';
    try {
        const resp = await fetch('/api/collections');
        const colls = await resp.json();
        const container = document.getElementById('collections-list');

        if (colls.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No collections yet</p></div>';
            return;
        }

        container.innerHTML = colls.map(c => {
            const nPapers = (c.sections || []).reduce((sum, s) => sum + (s.papers || []).length, 0);
            return `<div class="collection-card" onclick="openCollection('${esc(c.id)}')">
                <div class="paper-title">${esc(c.title)}</div>
                <div class="paper-meta">${nPapers} papers · Updated ${c.updated || '?'}</div>
                ${c.description ? `<div class="paper-meta">${esc(c.description)}</div>` : ''}
            </div>`;
        }).join('');
    } catch (err) {
        console.error('Failed to load collections:', err);
    }
}

async function openCollection(collId) {
    try {
        const resp = await fetch(`/api/collections/${collId}`);
        const coll = await resp.json();
        const detail = document.getElementById('collection-detail');

        let html = `<h2>${esc(coll.title)}</h2>`;
        if (coll.description) html += `<p>${esc(coll.description)}</p>`;

        for (const section of (coll.sections || [])) {
            html += `<h3>${esc(section.title)}</h3>`;
            if (section.notes) html += `<p class="paper-meta">${esc(section.notes)}</p>`;
            html += '<div class="section-papers">';
            for (const ref of (section.papers || [])) {
                html += `<div class="paper-card" onclick="openPaper('${esc(ref.paper_id)}')">
                    <div class="paper-title">${esc(ref.paper_id)}</div>
                    ${ref.notes ? `<div class="paper-meta">${esc(ref.notes)}</div>` : ''}
                </div>`;
            }
            html += '</div>';
        }

        if (coll.external_links && coll.external_links.length) {
            html += '<h3>External Links</h3>';
            for (const link of coll.external_links) {
                html += `<div class="paper-card">
                    <div class="paper-title"><a href="${esc(link.url)}" target="_blank">${esc(link.title || link.url)}</a></div>
                    ${link.notes ? `<div class="paper-meta">${esc(link.notes)}</div>` : ''}
                </div>`;
            }
        }

        html += `<div class="modal-actions">
            <button onclick="refreshCollections()">Back to list</button>
            <button onclick="deleteCollection('${esc(collId)}')" style="color:var(--error)">Delete</button>
        </div>`;

        detail.innerHTML = html;
        detail.style.display = 'block';
        document.getElementById('collections-list').style.display = 'none';
    } catch (err) {
        console.error('Failed to load collection:', err);
    }
}

function showCreateCollection() {
    const title = prompt('Collection title:');
    if (!title) return;
    const description = prompt('Description (optional):') || '';

    fetch('/api/collections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) refreshCollections();
        else alert('Error: ' + (data.error || 'Unknown error'));
    })
    .catch(err => alert('Error: ' + err.message));
}

async function deleteCollection(collId) {
    if (!confirm('Delete this collection?')) return;
    try {
        const resp = await fetch(`/api/collections/${collId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('collections-list').style.display = 'flex';
            refreshCollections();
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}


// --- Settings ---

async function loadSettings() {
    try {
        const resp = await fetch('/api/config');
        const config = await resp.json();

        const statusEl = document.getElementById('api-key-status');
        if (config.hasApiKey) {
            statusEl.innerHTML = `<span style="color:var(--success)">API key configured (${config.apiKeySource})</span>`;
        } else {
            statusEl.innerHTML = '<span style="color:var(--text-secondary)">No API key set</span>';
        }

        document.getElementById('extraction-model').value = config.extraction_model || '';
        document.getElementById('summary-model').value = config.summary_model || '';

        const usage = config.api_usage || {};
        document.getElementById('usage-stats').textContent =
            `Input tokens: ${(usage.input_tokens || 0).toLocaleString()} · Output tokens: ${(usage.output_tokens || 0).toLocaleString()}`;
    } catch (err) {
        console.error('Failed to load settings:', err);
    }
}

async function saveApiKey() {
    const key = document.getElementById('api-key-input').value.trim();
    if (!key) return alert('Please enter an API key.');

    try {
        const resp = await fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claude_api_key: key })
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('api-key-input').value = '';
            loadSettings();
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function testApiKey() {
    try {
        const resp = await fetch('/api/config/test-api-key', { method: 'POST' });
        const data = await resp.json();
        alert(data.success ? 'API key is valid!' : 'Test failed: ' + data.error);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function clearApiKey() {
    if (!confirm('Remove API key from config?')) return;
    try {
        await fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claude_api_key: '' })
        });
        loadSettings();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function saveModels() {
    const data = {
        extraction_model: document.getElementById('extraction-model').value.trim(),
        summary_model: document.getElementById('summary-model').value.trim(),
    };
    try {
        await fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        alert('Models saved.');
    } catch (err) {
        alert('Error: ' + err.message);
    }
}


// --- Utility ---

function esc(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function showResult(elementId, type, message) {
    const el = document.getElementById(elementId);
    el.className = `result-box visible ${type}`;
    el.textContent = message;
}

function formatMeta(paper) {
    const parts = [];
    if (paper.title) parts.push(`Title: ${paper.title}`);
    if (paper.authors && paper.authors.length) parts.push(`Authors: ${paper.authors.join(', ')}`);
    if (paper.year) parts.push(`Year: ${paper.year}`);
    if (paper.pdf_filename) parts.push(`PDF: ${paper.pdf_filename}`);
    return parts.join('\n');
}


// --- Init ---

document.addEventListener('DOMContentLoaded', () => {
    refreshLibrary();
});
