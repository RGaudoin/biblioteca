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
    if (sectionId === 'topics') refreshTopicManagement();
    if (sectionId === 'tags') refreshTagManagement();
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

function filterByTag(tag) {
    closeModal();
    document.getElementById('tag-filter').value = tag;
    document.getElementById('topic-filter').value = '';
    document.getElementById('search-input').value = '';
    // Switch to library section
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('library').classList.add('active');
    document.querySelector('.nav-btn').classList.add('active');
    refreshLibrary();
}

function filterByTopic(topic) {
    closeModal();
    document.getElementById('topic-filter').value = topic;
    document.getElementById('tag-filter').value = '';
    document.getElementById('search-input').value = '';
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('library').classList.add('active');
    document.querySelector('.nav-btn').classList.add('active');
    refreshLibrary();
}

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

        // Show bulk extract button if any papers lack titles
        const untitled = data.papers.filter(p => !p.title);
        const bulkBtn = document.getElementById('bulk-extract-btn');
        if (untitled.length > 0) {
            bulkBtn.style.display = '';
            bulkBtn.textContent = `Extract Missing Metadata (${untitled.length} papers)`;
        } else {
            bulkBtn.style.display = 'none';
        }
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
        const title = paperDisplayTitle(p);
        const titleClass = p.title ? '' : ' unprocessed';
        const authors = (p.authors || []).join(', ');
        const year = p.year || '';
        const meta = [authors, year, p.source].filter(Boolean).join(' · ');
        const badge = !p.pdf_filename ? '<span class="badge-ref">REF</span>'
            : !p.title ? '<span class="badge-new">NEW</span>'
            : '<span class="badge-pdf">PDF</span>';
        const tags = (p.tags || []).map(t => `<span class="tag clickable" onclick="event.stopPropagation(); filterByTag('${esc(t)}')">${esc(t)}</span>`).join('');
        const topics = (p.topics || []).map(t => `<span class="tag topic clickable" onclick="event.stopPropagation(); filterByTopic('${esc(t)}')">${esc(t)}</span>`).join('');

        return `<div class="paper-card" onclick="openPaper('${esc(p.id)}')">
            <div class="paper-title${titleClass}">${badge} ${esc(title)}</div>
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


async function bulkExtract() {
    const btn = document.getElementById('bulk-extract-btn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Extracting... (this may take a while)';

    try {
        const resp = await fetch('/api/ai/bulk-extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await resp.json();
        if (data.success) {
            const updated = data.results.filter(r => r.status === 'updated').length;
            const failed = data.results.filter(r => r.status === 'failed').length;
            alert(`Bulk extraction complete: ${updated} updated, ${failed} failed out of ${data.processed} processed.`);
            refreshLibrary();
        } else {
            alert('Bulk extraction failed: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
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
    const modalTitle = document.getElementById('modal-title');
    modalTitle.textContent = paperDisplayTitle(p);
    modalTitle.className = p.title ? '' : 'unprocessed';

    const fields = [
        { label: 'Authors', value: (p.authors || []).join(', ') },
        { label: 'Year', value: p.year },
        { label: 'Source', value: p.source },
        { label: 'Tags', value: (p.tags || []).map(t => `<span class="tag clickable" onclick="filterByTag('${esc(t)}')">${esc(t)}</span>`).join(' '), html: true },
        { label: 'Topics', value: (p.topics || []).map(t => `<span class="tag topic clickable" onclick="filterByTopic('${esc(t)}')">${esc(t)}</span>`).join(' '), html: true },
        { label: 'Summary', value: p.summary ? (p.summary + (p.summary_model ? ` <span style="opacity:0.5;font-size:0.85em">[${esc(p.summary_model)}]</span>` : '')) : null, html: true },
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

let batchScanData = null;  // Store scan results for import step

async function handleBatchScan(e) {
    e.preventDefault();
    const folder = document.getElementById('batch-folder').value.trim();
    const recursive = document.getElementById('batch-recursive').checked;
    showResult('batch-result', 'info', 'Scanning folder...');
    document.getElementById('batch-scan-results').innerHTML = '';

    try {
        const resp = await fetch('/api/import/batch/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder, recursive })
        });
        const data = await resp.json();
        batchScanData = data.files || [];

        if (batchScanData.length === 0) {
            showResult('batch-result', 'info', 'No PDFs found.');
            return;
        }

        const newFiles = batchScanData.filter(f => f.status === 'new');
        const dupes = batchScanData.filter(f => f.status === 'duplicate');
        const empty = batchScanData.filter(f => f.status === 'empty');

        let html = `<p style="margin:0.75rem 0"><strong>${batchScanData.length}</strong> PDFs found: <strong>${newFiles.length}</strong> new, <strong>${dupes.length}</strong> duplicates, <strong>${empty.length}</strong> empty</p>`;
        if (newFiles.length > 0) {
            html += `<p style="margin:0 0 0.5rem"><label><input type="checkbox" checked onchange="toggleBatchAll(this.checked)"> Select all new</label></p>`;
        }
        html += '<div class="paper-list" style="max-height:300px;overflow-y:auto">';
        for (let i = 0; i < batchScanData.length; i++) {
            const f = batchScanData[i];
            const sizeKb = Math.round(f.size / 1024);
            if (f.status === 'new') {
                html += `<div class="paper-card" style="padding:0.4rem 0.75rem"><label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer"><input type="checkbox" class="batch-file-cb" data-idx="${i}" checked><span class="badge-pdf">NEW</span> ${esc(f.filename)} (${sizeKb} KB)</label></div>`;
            } else if (f.status === 'duplicate') {
                html += `<div class="paper-card" style="padding:0.4rem 0.75rem;opacity:0.6"><span class="badge-ref">DUP</span> ${esc(f.filename)} — duplicate of ${esc(f.existing_id)}</div>`;
            } else {
                html += `<div class="paper-card" style="padding:0.4rem 0.75rem;opacity:0.4">${esc(f.filename)} — empty</div>`;
            }
        }
        html += '</div>';
        document.getElementById('batch-scan-results').innerHTML = html;
        if (newFiles.length > 0) {
            showResult('batch-result', 'info', `Scan complete. ${newFiles.length} new papers selected. Untick any you want to skip, then click "Import All New".`);
        } else if (dupes.length > 0) {
            showResult('batch-result', 'info', `All ${dupes.length} PDFs already in library. To update metadata, use "Extract Missing Metadata (AI)" in the Library tab.`);
        } else {
            showResult('batch-result', 'info', 'Scan complete. No importable PDFs found.');
        }
    } catch (err) {
        showResult('batch-result', 'error', `Error: ${err.message}`);
    }
}

function toggleBatchAll(checked) {
    document.querySelectorAll('.batch-file-cb').forEach(cb => cb.checked = checked);
}

async function handleBatchImportAll() {
    const folder = document.getElementById('batch-folder').value.trim();
    if (!folder) return alert('Enter a folder path and scan first.');

    const ai = document.getElementById('batch-ai').checked;
    const recursive = document.getElementById('batch-recursive').checked;

    // Use checked files from scan results
    let paths = null;
    if (batchScanData) {
        const checkboxes = document.querySelectorAll('.batch-file-cb:checked');
        if (checkboxes.length > 0) {
            paths = Array.from(checkboxes).map(cb => batchScanData[parseInt(cb.dataset.idx)].path);
        } else {
            // No checkboxes at all means no scan was done, or nothing new
            const newFiles = batchScanData.filter(f => f.status === 'new');
            if (newFiles.length === 0) {
                showResult('batch-result', 'info', 'All papers already imported. To update metadata, use "Extract Missing Metadata (AI)" in the Library tab.');
                return;
            }
            showResult('batch-result', 'info', 'No papers selected. Tick the ones you want to import.');
            return;
        }
    }

    showResult('batch-result', 'info', 'Importing...');

    try {
        const resp = await fetch('/api/import/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder, ai, recursive, paths })
        });
        const data = await resp.json();
        let msg = '';
        if (data.imported) msg += `Imported (${data.imported.length}):\n` + data.imported.map(i => `  ${i.paper_id}`).join('\n') + '\n';
        if (data.skipped && data.skipped.length) msg += `\nSkipped (${data.skipped.length}):\n` + data.skipped.map(s => `  ${s.path}: ${s.reason}`).join('\n') + '\n';
        if (data.failed && data.failed.length) msg += `\nFailed (${data.failed.length}):\n` + data.failed.map(f => `  ${f.path}: ${f.error}`).join('\n');
        showResult('batch-result', data.failed && data.failed.length ? 'error' : 'success', msg || 'No PDFs found.');
        batchScanData = null;
        refreshLibrary();
    } catch (err) {
        showResult('batch-result', 'error', `Error: ${err.message}`);
    }
}

async function handleLinksImport(e) {
    e.preventDefault();
    const text = document.getElementById('links-text').value.trim();
    showResult('links-result', 'info', 'Importing links...');

    try {
        const resp = await fetch('/api/import/links', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await resp.json();
        let msg = '';
        if (data.imported && data.imported.length) msg += `Imported (${data.imported.length}):\n` + data.imported.map(i => `  ${i.paper_id} (${i.line})`).join('\n') + '\n';
        if (data.skipped && data.skipped.length) msg += `\nSkipped (${data.skipped.length}):\n` + data.skipped.map(s => `  ${s.line}: ${s.reason}`).join('\n') + '\n';
        if (data.failed && data.failed.length) msg += `\nFailed (${data.failed.length}):\n` + data.failed.map(f => `  ${f.line}: ${f.error}`).join('\n');
        showResult('links-result', data.failed && data.failed.length ? 'error' : 'success', msg || 'No links found.');
        refreshLibrary();
    } catch (err) {
        showResult('links-result', 'error', `Error: ${err.message}`);
    }
}

async function handleReadingListImport(e) {
    e.preventDefault();
    const path = document.getElementById('reading-list-path').value.trim();
    showResult('reading-list-result', 'info', 'Parsing reading list with AI... (this may take a moment)');

    try {
        const resp = await fetch('/api/import/reading-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        const data = await resp.json();
        if (data.success) {
            let msg = `Collection created: ${data.collection_id}\n`;
            msg += `Matched papers: ${data.matched.length}\n`;
            data.matched.forEach(id => msg += `  ${id}\n`);
            msg += `Stubs created: ${data.stubs_created.length}\n`;
            data.stubs_created.forEach(id => msg += `  ${id}\n`);
            msg += `External links: ${data.external_links}`;
            showResult('reading-list-result', 'success', msg);
            refreshLibrary();
        } else {
            showResult('reading-list-result', 'error', `Error: ${data.error}`);
        }
    } catch (err) {
        showResult('reading-list-result', 'error', `Error: ${err.message}`);
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
    document.getElementById('collections-list').style.display = '';
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

        // Fetch paper data for display
        const paperIds = new Set();
        for (const section of (coll.sections || [])) {
            for (const ref of (section.papers || [])) paperIds.add(ref.paper_id);
        }
        const paperData = {};
        await Promise.all(Array.from(paperIds).map(async id => {
            try {
                const r = await fetch(`/api/papers/${id}`);
                if (r.ok) { paperData[id] = await r.json(); }
            } catch (e) { /* ignore */ }
        }));

        for (const section of (coll.sections || [])) {
            html += `<h3>${esc(section.title)}</h3>`;
            if (section.notes) html += `<p class="paper-meta">${esc(section.notes)}</p>`;
            html += '<div class="section-papers">';
            for (const ref of (section.papers || [])) {
                const p = paperData[ref.paper_id];
                const title = p ? paperDisplayTitle(p) : ref.paper_id;
                const badge = !p ? ''
                    : !p.pdf_filename ? '<span class="badge-ref">REF</span> '
                    : !p.title ? '<span class="badge-new">NEW</span> '
                    : '<span class="badge-pdf">PDF</span> ';
                const titleClass = (p && !p.title) ? ' unprocessed' : '';
                html += `<div class="paper-card" onclick="openPaper('${esc(ref.paper_id)}')">
                    <div class="paper-title${titleClass}">${badge}${esc(title)}</div>
                    ${ref.notes ? `<div class="paper-meta" style="white-space:pre-line">${esc(ref.notes)}</div>` : ''}
                </div>`;
            }
            // Per-section external links
            for (const link of (section.external_links || [])) {
                html += `<div class="paper-card">
                    <div class="paper-title"><a href="${esc(link.url)}" target="_blank">${esc(link.title || link.url)}</a></div>
                    ${link.notes ? `<div class="paper-meta" style="white-space:pre-line">${esc(link.notes)}</div>` : ''}
                </div>`;
            }
            html += '</div>';
        }

        // Top-level external links (legacy)
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
            <button onclick="applyCollectionTopics('${esc(collId)}')">Apply Topics to Papers</button>
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

async function applyCollectionTopics(collId) {
    if (!confirm('Assign section titles as topics to all papers in this collection, and merge per-paper notes?')) return;
    try {
        const resp = await fetch(`/api/collections/${collId}/apply-topics`, { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            alert(`Topics and notes applied to ${data.updated.length} papers.`);
            openCollection(collId);
        } else {
            alert('Error: ' + (data.error || 'Unknown'));
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
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


// --- Topic Management ---

async function refreshTopicManagement() {
    try {
        const resp = await fetch('/api/topics');
        const topics = await resp.json();
        const container = document.getElementById('topics-list');

        if (Object.keys(topics).length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No topics yet. Import a reading list or add topics manually.</p></div>';
            return;
        }

        let html = '<div style="margin-bottom:0.75rem">';
        html += '<button onclick="mergeSelectedTopics()">Merge Selected</button> ';
        html += '<button onclick="deleteSelectedTopics()" style="color:var(--error)">Delete Selected</button>';
        html += '</div>';

        for (const [topic, count] of Object.entries(topics)) {
            html += `<div class="paper-card" style="padding:0.4rem 0.75rem">
                <label style="display:flex;align-items:center;gap:0.75rem;cursor:pointer;font-weight:normal">
                    <input type="checkbox" class="topic-select-cb" data-topic="${esc(topic)}">
                    <span class="tag clickable" onclick="event.preventDefault(); filterByTopic('${esc(topic)}')">${esc(topic)}</span>
                    <span class="paper-meta">${count} paper${count !== 1 ? 's' : ''}</span>
                    <span style="margin-left:auto">
                        <button onclick="event.preventDefault(); renameTopic('${esc(topic)}')" style="padding:0.2rem 0.5rem;font-size:0.8rem">Rename</button>
                        <button onclick="event.preventDefault(); deleteSingleTopic('${esc(topic)}')" style="padding:0.2rem 0.5rem;font-size:0.8rem;color:var(--error)">Delete</button>
                    </span>
                </label>
            </div>`;
        }
        container.innerHTML = html;
    } catch (err) {
        console.error('Failed to load topics:', err);
    }
}

async function renameTopic(oldTopic) {
    const newTopic = prompt(`Rename "${oldTopic}" to:`, oldTopic);
    if (!newTopic || newTopic === oldTopic) return;

    try {
        const resp = await fetch('/api/topics/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_topic: oldTopic, new_topic: newTopic })
        });
        const data = await resp.json();
        if (data.success) {
            alert(`Renamed: ${data.updated} papers updated.`);
            refreshTopicManagement();
        }
    } catch (err) { alert('Error: ' + err.message); }
}

async function mergeSelectedTopics() {
    const checked = Array.from(document.querySelectorAll('.topic-select-cb:checked'));
    if (checked.length < 2) return alert('Select at least 2 topics to merge.');

    const topics = checked.map(cb => cb.dataset.topic);
    const target = prompt(`Merge these topics into one:\n${topics.join(', ')}\n\nTarget topic name:`, topics[0]);
    if (!target) return;

    try {
        const resp = await fetch('/api/topics/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topics, target })
        });
        const data = await resp.json();
        if (data.success) {
            alert(`Merged: ${data.updated} papers updated.`);
            refreshTopicManagement();
        }
    } catch (err) { alert('Error: ' + err.message); }
}

async function deleteSelectedTopics() {
    const checked = Array.from(document.querySelectorAll('.topic-select-cb:checked'));
    if (checked.length === 0) return alert('Select topics to delete.');

    const topics = checked.map(cb => cb.dataset.topic);
    if (!confirm(`Delete these topics from all papers?\n${topics.join(', ')}`)) return;

    for (const topic of topics) {
        await fetch('/api/topics/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });
    }
    alert('Topics deleted.');
    refreshTopicManagement();
}

async function deleteSingleTopic(topic) {
    if (!confirm(`Delete topic "${topic}" from all papers?`)) return;
    try {
        await fetch('/api/topics/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });
        refreshTopicManagement();
    } catch (err) { alert('Error: ' + err.message); }
}

function addTopicManual() {
    const name = prompt('Topic name:');
    if (!name) return;
    // Adding a topic manually means we just note it — it only exists on papers.
    // So prompt user to go to library and assign it to papers.
    alert(`Topic "${name}" noted. Assign it to papers from the paper detail view, or use "Add to topic" from the library.`);
}


// --- Tag Management ---

async function refreshTagManagement() {
    try {
        const resp = await fetch('/api/tags');
        const tags = await resp.json();
        const container = document.getElementById('tags-list');

        if (Object.keys(tags).length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No tags yet</p></div>';
            return;
        }

        let html = '<div style="margin-bottom:0.75rem">';
        html += '<button onclick="mergeSelectedTags()">Merge Selected</button> ';
        html += '<button onclick="deleteSelectedTags()" style="color:var(--error)">Delete Selected</button>';
        html += '</div>';

        for (const [tag, count] of Object.entries(tags)) {
            html += `<div class="paper-card" style="padding:0.4rem 0.75rem">
                <label style="display:flex;align-items:center;gap:0.75rem;cursor:pointer;font-weight:normal">
                    <input type="checkbox" class="tag-select-cb" data-tag="${esc(tag)}">
                    <span class="tag clickable" onclick="event.preventDefault(); filterByTag('${esc(tag)}')">${esc(tag)}</span>
                    <span class="paper-meta">${count} paper${count !== 1 ? 's' : ''}</span>
                    <span style="margin-left:auto">
                        <button onclick="event.preventDefault(); renameTag('${esc(tag)}')" style="padding:0.2rem 0.5rem;font-size:0.8rem">Rename</button>
                        <button onclick="event.preventDefault(); deleteSingleTag('${esc(tag)}')" style="padding:0.2rem 0.5rem;font-size:0.8rem;color:var(--error)">Delete</button>
                    </span>
                </label>
            </div>`;
        }
        container.innerHTML = html;
    } catch (err) {
        console.error('Failed to load tags:', err);
    }
}

async function renameTag(oldTag) {
    const newTag = prompt(`Rename "${oldTag}" to:`, oldTag);
    if (!newTag || newTag === oldTag) return;

    try {
        const resp = await fetch('/api/tags/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_tag: oldTag, new_tag: newTag })
        });
        const data = await resp.json();
        if (data.success) {
            alert(`Renamed: ${data.updated} papers updated.`);
            refreshTagManagement();
        }
    } catch (err) { alert('Error: ' + err.message); }
}

async function mergeSelectedTags() {
    const checked = Array.from(document.querySelectorAll('.tag-select-cb:checked'));
    if (checked.length < 2) return alert('Select at least 2 tags to merge.');

    const tags = checked.map(cb => cb.dataset.tag);
    const target = prompt(`Merge these tags into one:\n${tags.join(', ')}\n\nTarget tag name:`, tags[0]);
    if (!target) return;

    try {
        const resp = await fetch('/api/tags/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags, target })
        });
        const data = await resp.json();
        if (data.success) {
            alert(`Merged: ${data.updated} papers updated.`);
            refreshTagManagement();
        }
    } catch (err) { alert('Error: ' + err.message); }
}

async function deleteSelectedTags() {
    const checked = Array.from(document.querySelectorAll('.tag-select-cb:checked'));
    if (checked.length === 0) return alert('Select tags to delete.');

    const tags = checked.map(cb => cb.dataset.tag);
    if (!confirm(`Delete these tags from all papers?\n${tags.join(', ')}`)) return;

    for (const tag of tags) {
        await fetch('/api/tags/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag })
        });
    }
    alert('Tags deleted.');
    refreshTagManagement();
}

async function deleteSingleTag(tag) {
    if (!confirm(`Delete tag "${tag}" from all papers?`)) return;
    try {
        await fetch('/api/tags/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag })
        });
        refreshTagManagement();
    } catch (err) { alert('Error: ' + err.message); }
}

async function suggestTagMerges() {
    const el = document.getElementById('tag-suggestions');
    el.className = 'result-box visible info';
    el.textContent = 'Analysing tags with AI...';

    try {
        const resp = await fetch('/api/ai/suggest-tag-merges', { method: 'POST' });
        const data = await resp.json();

        if (!data.success) {
            el.className = 'result-box visible error';
            el.textContent = 'Error: ' + (data.error || 'Unknown');
            return;
        }

        if (data.suggestions.length === 0) {
            el.className = 'result-box visible success';
            el.textContent = 'No merge suggestions — tags look clean.';
            return;
        }

        let html = '<strong>Suggested merges:</strong> <button onclick="applySelectedSuggestions()">Apply Selected</button> ';
        html += '<button onclick="toggleAllSuggestions()" style="padding:0.15rem 0.5rem;font-size:0.8rem">Select All / None</button><br>';
        for (let i = 0; i < data.suggestions.length; i++) {
            const s = data.suggestions[i];
            html += `<div style="margin:0.5rem 0;padding:0.5rem;background:var(--bg);border-radius:var(--radius)">`;
            html += `<label style="display:flex;align-items:baseline;gap:0.5rem;cursor:pointer;font-weight:normal">`;
            html += `<input type="checkbox" class="suggestion-cb" data-index="${i}" checked>`;
            html += `<span>${s.tags.map(t => `<span class="tag">${esc(t)}</span>`).join(' + ')} → <span class="tag" style="font-weight:600">${esc(s.suggested)}</span>`;
            html += `<br><small>${esc(s.reason)}</small></span>`;
            html += `</label></div>`;
        }

        el.className = 'result-box visible success';
        el.innerHTML = html;
        // stash suggestions for apply
        el._suggestions = data.suggestions;
    } catch (err) {
        el.className = 'result-box visible error';
        el.textContent = 'Error: ' + err.message;
    }
}

function toggleAllSuggestions() {
    const cbs = document.querySelectorAll('.suggestion-cb');
    const allChecked = Array.from(cbs).every(cb => cb.checked);
    cbs.forEach(cb => cb.checked = !allChecked);
}

async function applySelectedSuggestions() {
    const el = document.getElementById('tag-suggestions');
    const suggestions = el._suggestions || [];
    const checked = el.querySelectorAll('.suggestion-cb:checked');
    if (checked.length === 0) return alert('No suggestions selected.');

    let total = 0;
    for (const cb of checked) {
        const s = suggestions[parseInt(cb.dataset.index)];
        try {
            const resp = await fetch('/api/tags/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags: s.tags, target: s.suggested })
            });
            const data = await resp.json();
            if (data.success) total += data.updated;
        } catch (err) { /* continue with remaining */ }
    }
    alert(`Applied ${checked.length} merge(s): ${total} papers updated.`);
    el.innerHTML = '';
    el.className = 'result-box';
    refreshTagManagement();
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
        let usageHtml = `<p><strong>Total:</strong> ${(usage.input_tokens || 0).toLocaleString()} input · ${(usage.output_tokens || 0).toLocaleString()} output</p>`;
        const byModel = usage.by_model || {};
        const models = Object.keys(byModel);
        if (models.length > 0) {
            usageHtml += '<table class="usage-table"><tr><th>Model</th><th>Input</th><th>Output</th></tr>';
            for (const m of models.sort()) {
                const mu = byModel[m];
                usageHtml += `<tr><td>${m}</td><td>${(mu.input_tokens || 0).toLocaleString()}</td><td>${(mu.output_tokens || 0).toLocaleString()}</td></tr>`;
            }
            usageHtml += '</table>';
        }
        if (usage.reset_date) {
            usageHtml += `<p style="color:var(--text-secondary); font-size:0.85rem">Since reset on ${usage.reset_date}</p>`;
        }
        document.getElementById('usage-stats').innerHTML = usageHtml;
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

async function resetUsage() {
    if (!confirm('Reset API usage counters?')) return;
    try {
        await fetch('/api/config/reset-usage', { method: 'POST' });
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

function paperDisplayTitle(p) {
    if (p.title) return p.title;
    // Fallback: show original filename (sans extension) or pdf_filename
    if (p.original_filename) {
        return p.original_filename.replace(/\.pdf$/i, '');
    }
    if (p.pdf_filename) {
        return p.pdf_filename.replace(/\.pdf$/i, '');
    }
    return p.id;
}

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
