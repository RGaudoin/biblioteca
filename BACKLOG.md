# Biblioteca — Backlog

## Short-term / Easy fixes

- [ ] **Force re-extraction option** — extraction endpoint and CLI skip fields that already have values; add a `--force` flag to overwrite bogus data (e.g. titles like "Untitled" or raw patent numbers)
- [ ] **Detect bogus titles in CLI extract** — treat titles matching the paper ID, "Untitled", or bare numbers as missing, so they get picked up by default extraction
- [ ] **Paper rename/re-ID** — function to change a paper's ID, updating metadata JSON, PDF filename, and all collection references in one operation
- [ ] **CLI parity: tag management** — expose rename, merge, delete tags via CLI (already in web API)
- [ ] **CLI parity: duplicate detection** — expose find/merge duplicates via CLI (already in web API)
- [ ] **CLI parity: consistency checker** — expose via CLI (already in web API)
- [ ] **CLI parity: privacy toggle** — expose via CLI (already in web API)
- [x] **Private flag at import time** — allow setting `private=true` during import (single, batch, URL, arXiv), so papers go directly to `data/private/` without needing a separate toggle step afterwards. Especially useful for batch imports where all files should be private.
- [x] **Merge import_links_file and import_emails** — consolidated into `import_from_text`, single "Links / Email" UI tab
- [ ] **Clean up README TODOs** — content type awareness, consistency checker, and private content separation are now implemented

## Long-term / Nice to haves

- [ ] **OCR fallback for image PDFs** — integrate an OCR library (e.g. pytesseract, or the Claude vision API) as fallback when PyPDF2 text extraction yields nothing
- [ ] **Paper finder** — given partial information (title, topic), search for and fetch PDFs from arXiv or other open-access sources
- [ ] **Paper linking** — link related papers (multi-part series, continuations, patent families) with navigation between them
- [ ] **Version text content** — git-track versionable text documents alongside metadata; binary files stay gitignored
- [ ] **Batch import improvements** — better handling of duplicate filenames, scanned PDFs, and non-English documents during import
- [ ] **CLI parity: full topic and collection management** — CRUD, merge, rename via CLI
- [ ] **Render-to-PDF for web articles** — optional headless browser (playwright) to render web pages as PDF for full visual fidelity; offer as "Download as PDF" button alongside the default lightweight markdown extraction
- [ ] **Separate tagging model setting** — add `tagging_model` to config so tag generation can use a different model from metadata extraction
- [ ] **Authentication** — all endpoints are unauthenticated; critical before any network/Lambda deployment (API key exfiltration, data access). Needs Flask-Login or equivalent
- [ ] **Encrypted private backup** — optional encrypted mirror of private content in `data/private-encrypted/` (git-tracked)
- [ ] **Long list handling** — paper pickers, tag lists, and topic lists will need search/filter and possibly pagination as the library grows; currently all are simple flat lists
