"""
Import pipeline for Biblioteca — local PDFs, arxiv, URLs, batch, email parsing.
"""

import hashlib
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

from papers import (
    PAPERS_DIR,
    create_paper_stub,
    find_by_arxiv_id,
    find_by_hash,
    generate_id,
    list_papers,
    load_config,
    load_paper,
    normalise_filename,
    save_collection,
)


def compute_hash(file_path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# --- Local PDF import ---

def import_local(pdf_path, metadata_overrides=None, use_ai=False):
    """Import a local PDF file into the library.

    Copies the PDF to data/papers/ and creates a metadata stub.

    Args:
        pdf_path: Path to the PDF file.
        metadata_overrides: Optional dict of metadata fields to set.
        use_ai: If True, attempt AI metadata extraction.

    Returns:
        dict with 'success', 'paper_id', 'metadata', and optionally 'error'.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        return {"success": False, "error": f"File not found: {pdf_path}"}

    if not pdf_path.suffix.lower() == ".pdf":
        return {"success": False, "error": f"Not a PDF file: {pdf_path}"}

    # Check for 0-byte files
    if pdf_path.stat().st_size == 0:
        return {"success": False, "error": f"Empty file (0 bytes): {pdf_path}"}

    # Check for duplicates by hash
    file_hash = compute_hash(str(pdf_path))
    existing = find_by_hash(file_hash)
    if existing:
        return {"success": False, "error": f"Duplicate of existing paper: {existing['id']}",
                "duplicate": True, "existing_id": existing["id"]}

    overrides = metadata_overrides or {}

    # Try AI extraction if requested
    ai_metadata = {}
    if use_ai:
        try:
            from ai import extract_metadata
            ai_metadata = extract_metadata(str(pdf_path))
        except Exception:
            pass

    # Merge: overrides > AI > defaults
    title = overrides.get("title") or ai_metadata.get("title")
    authors = overrides.get("authors") or ai_metadata.get("authors", [])
    year = overrides.get("year") or ai_metadata.get("year")

    # Generate ID and filename
    paper_id = generate_id(title, authors, year, fallback=pdf_path.stem)
    pdf_filename = normalise_filename(title, authors, year, original=pdf_path.name)

    # Copy PDF to papers directory
    dest = PAPERS_DIR / pdf_filename
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(pdf_path), str(dest))

    # Build metadata
    meta_fields = {
        "title": title,
        "authors": authors,
        "year": year,
        "source": overrides.get("source") or ai_metadata.get("source"),
        "tags": overrides.get("tags") or ai_metadata.get("tags", []),
        "topics": overrides.get("topics", []),
        "summary": overrides.get("summary") or ai_metadata.get("summary"),
        "notes": overrides.get("notes"),
        "private": overrides.get("private", False),
        "url": overrides.get("url"),
        "arxiv_id": overrides.get("arxiv_id"),
        "doi": overrides.get("doi"),
        "import_source": overrides.get("import_source", "local"),
        "original_filename": pdf_path.name,
        "pdf_hash": compute_hash(str(dest)),
    }

    metadata = create_paper_stub(paper_id, pdf_filename, **meta_fields)

    return {"success": True, "paper_id": paper_id, "metadata": metadata}


# --- Arxiv import ---

ARXIV_ID_PATTERN = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
ARXIV_API_URL = "http://export.arxiv.org/api/query"


def _extract_arxiv_id(input_str):
    """Extract arxiv ID from a URL or raw ID string."""
    # Handle URLs like https://arxiv.org/abs/2402.02160
    match = ARXIV_ID_PATTERN.search(input_str)
    if match:
        return match.group(1)
    return None


def _parse_arxiv_response(xml_text):
    """Parse arxiv API Atom XML response. Returns metadata dict or None."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    entry = root.find("atom:entry", ns)
    if entry is None:
        return None

    # Check for error (no results)
    id_elem = entry.find("atom:id", ns)
    if id_elem is None:
        return None

    title = entry.findtext("atom:title", default="", namespaces=ns).strip()
    title = re.sub(r"\s+", " ", title)  # Collapse whitespace

    authors = []
    for author in entry.findall("atom:author", ns):
        name = author.findtext("atom:name", default="", namespaces=ns).strip()
        if name:
            authors.append(name)

    summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
    summary = re.sub(r"\s+", " ", summary)

    published = entry.findtext("atom:published", default="", namespaces=ns)
    year = int(published[:4]) if published and len(published) >= 4 else None

    # Get journal ref if available
    journal_ref = entry.findtext("arxiv:journal_ref", default=None, namespaces=ns)

    # Get DOI if available
    doi = entry.findtext("arxiv:doi", default=None, namespaces=ns)

    # Get primary category
    primary_cat = entry.find("arxiv:primary_category", ns)
    category = primary_cat.get("term") if primary_cat is not None else None

    # PDF link
    pdf_link = None
    for link in entry.findall("atom:link", ns):
        if link.get("title") == "pdf":
            pdf_link = link.get("href")
            break

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "summary": summary,
        "source": journal_ref,
        "doi": doi,
        "category": category,
        "pdf_url": pdf_link,
    }


def import_arxiv(arxiv_input):
    """Import a paper from arxiv by ID or URL.

    Args:
        arxiv_input: An arxiv ID (e.g. '2402.02160') or URL.

    Returns:
        dict with 'success', 'paper_id', 'metadata', and optionally 'error'.
    """
    arxiv_id = _extract_arxiv_id(arxiv_input)
    if not arxiv_id:
        return {"success": False, "error": f"Could not extract arxiv ID from: {arxiv_input}"}

    # Check for duplicates
    existing = find_by_arxiv_id(arxiv_id)
    if existing:
        return {"success": False, "error": f"Paper already imported: {existing['id']}", "existing_id": existing["id"]}

    # Fetch metadata from arxiv API
    try:
        resp = requests.get(ARXIV_API_URL, params={"id_list": arxiv_id}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"success": False, "error": f"Failed to fetch arxiv metadata: {e}"}

    meta = _parse_arxiv_response(resp.text)
    if not meta or not meta.get("title"):
        return {"success": False, "error": f"No results found for arxiv ID: {arxiv_id}"}

    # Download PDF
    pdf_url = meta.get("pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        pdf_resp = requests.get(pdf_url, timeout=60)
        pdf_resp.raise_for_status()
    except requests.RequestException as e:
        return {"success": False, "error": f"Failed to download PDF: {e}"}

    if len(pdf_resp.content) < 1000:
        return {"success": False, "error": "Downloaded PDF appears too small / invalid"}

    # Generate ID and filename
    paper_id = generate_id(meta["title"], meta["authors"], meta["year"])
    pdf_filename = normalise_filename(meta["title"], meta["authors"], meta["year"])

    # Save PDF
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PAPERS_DIR / pdf_filename
    with open(dest, "wb") as f:
        f.write(pdf_resp.content)

    # Suggest tags from category
    tags = []
    if meta.get("category"):
        tags.append(meta["category"])

    # Create metadata
    metadata = create_paper_stub(
        paper_id,
        pdf_filename,
        title=meta["title"],
        authors=meta["authors"],
        year=meta["year"],
        source=meta["source"],
        summary=meta["summary"],
        tags=tags,
        url=f"https://arxiv.org/abs/{arxiv_id}",
        arxiv_id=arxiv_id,
        doi=meta.get("doi"),
        import_source="arxiv",
        original_filename=f"{arxiv_id}.pdf",
        pdf_hash=compute_hash(str(dest)),
    )

    return {"success": True, "paper_id": paper_id, "metadata": metadata}


# --- URL import ---

def import_url(url):
    """Import a paper from a URL. Routes to specific handlers based on URL pattern.

    Returns:
        dict with 'success', 'paper_id', 'metadata', and optionally 'error'.
    """
    url = url.strip()

    # Arxiv
    if "arxiv.org" in url:
        return import_arxiv(url)

    # Direct PDF link
    if url.lower().endswith(".pdf"):
        return _import_pdf_url(url)

    # DOI
    doi_match = re.search(r"(10\.\d{4,}/[^\s]+)", url)
    if doi_match or "doi.org" in url:
        return _import_doi(url)

    # GitHub — store as reference, no PDF
    if "github.com" in url:
        return _import_github_ref(url)

    # Generic URL — try to download as PDF or store as reference
    return _import_generic_url(url)


def _import_pdf_url(url):
    """Download a PDF from a direct URL and import it."""
    try:
        resp = requests.get(url, timeout=60, headers={"User-Agent": "Biblioteca/1.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"success": False, "error": f"Failed to download: {e}"}

    if len(resp.content) < 1000:
        return {"success": False, "error": "Downloaded file appears too small / invalid"}

    # Save to temp, then import locally
    filename = url.split("/")[-1].split("?")[0]
    if not filename.endswith(".pdf"):
        filename = "download.pdf"

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    result = import_local(tmp_path, metadata_overrides={"url": url, "import_source": "url", "original_filename": filename})

    # Clean up temp file
    Path(tmp_path).unlink(missing_ok=True)

    return result


def _import_doi(url):
    """Resolve a DOI and import the paper."""
    # Extract DOI
    doi_match = re.search(r"(10\.\d{4,}/[^\s]+)", url)
    if doi_match:
        doi = doi_match.group(1)
    else:
        return {"success": False, "error": f"Could not extract DOI from: {url}"}

    # Try CrossRef API for metadata
    try:
        resp = requests.get(
            f"https://api.crossref.org/works/{doi}",
            timeout=30,
            headers={"User-Agent": "Biblioteca/1.0 (personal research library)"},
        )
        resp.raise_for_status()
        data = resp.json()["message"]
    except Exception as e:
        return {"success": False, "error": f"Failed to resolve DOI: {e}"}

    title = ""
    if data.get("title"):
        title = data["title"][0]

    authors = []
    for author in data.get("author", []):
        name_parts = []
        if author.get("given"):
            name_parts.append(author["given"])
        if author.get("family"):
            name_parts.append(author["family"])
        if name_parts:
            authors.append(" ".join(name_parts))

    year = None
    for date_field in ["published-print", "published-online", "created"]:
        if data.get(date_field, {}).get("date-parts"):
            parts = data[date_field]["date-parts"][0]
            if parts and parts[0]:
                year = parts[0]
                break

    source = None
    if data.get("container-title"):
        source = data["container-title"][0]

    # Store as reference (DOI papers often behind paywall)
    paper_id = generate_id(title, authors, year, fallback=doi.replace("/", "-"))
    metadata = create_paper_stub(
        paper_id,
        pdf_filename=None,
        title=title,
        authors=authors,
        year=year,
        source=source,
        url=f"https://doi.org/{doi}",
        doi=doi,
        import_source="url",
    )

    return {"success": True, "paper_id": paper_id, "metadata": metadata, "note": "No PDF downloaded (may be behind paywall). Add PDF manually if available."}


def _import_github_ref(url):
    """Store a GitHub repository as a reference (no PDF)."""
    # Extract repo info from URL
    match = re.match(r"https?://github\.com/([^/]+)/([^/\s?#]+)", url)
    repo_name = match.group(2) if match else url.split("/")[-1]

    paper_id = generate_id(fallback=f"github-{repo_name}")
    metadata = create_paper_stub(
        paper_id,
        pdf_filename=None,
        title=f"GitHub: {repo_name}",
        url=url,
        import_source="url",
        tags=["github", "code"],
    )

    return {"success": True, "paper_id": paper_id, "metadata": metadata, "note": "Stored as reference (no PDF)."}


def _import_generic_url(url):
    """Store a generic URL as a reference."""
    paper_id = generate_id(fallback=url.split("/")[-1] or "web-reference")
    metadata = create_paper_stub(
        paper_id,
        pdf_filename=None,
        title=url,
        url=url,
        import_source="url",
    )

    return {"success": True, "paper_id": paper_id, "metadata": metadata, "note": "Stored as reference. Use AI extraction to populate metadata."}


# --- Batch import ---

def scan_batch(folder_path, recursive=False):
    """Scan a folder for PDFs and check for duplicates. Does NOT import.

    Returns list of dicts with 'path', 'filename', 'size', 'status', 'existing_id'.
    Status is one of: 'new', 'duplicate', 'empty'.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return []

    pattern = "**/*.pdf" if recursive else "*.pdf"
    results = []

    for pdf_path in sorted(folder.glob(pattern)):
        size = pdf_path.stat().st_size
        if size == 0:
            results.append({"path": str(pdf_path), "filename": pdf_path.name,
                            "size": 0, "status": "empty", "existing_id": None})
            continue

        file_hash = compute_hash(str(pdf_path))
        existing = find_by_hash(file_hash)
        if existing:
            results.append({"path": str(pdf_path), "filename": pdf_path.name,
                            "size": size, "status": "duplicate", "existing_id": existing["id"]})
        else:
            results.append({"path": str(pdf_path), "filename": pdf_path.name,
                            "size": size, "status": "new", "existing_id": None})

    return results


def import_batch(folder_path, use_ai=False, recursive=False, paths=None):
    """Import PDFs from a folder.

    Args:
        folder_path: Path to folder containing PDFs.
        use_ai: If True, attempt AI metadata extraction for each.
        recursive: If True, scan subdirectories too.
        paths: If provided, only import these specific file paths (from scan_batch).

    Returns:
        dict with 'imported', 'skipped', 'failed' lists.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return {"imported": [], "skipped": [], "failed": [{"path": str(folder_path), "error": "Not a directory"}]}

    results = {"imported": [], "skipped": [], "failed": []}

    if paths is not None:
        pdf_files = [Path(p) for p in paths]
    else:
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = sorted(folder.glob(pattern))

    for pdf_path in pdf_files:
        # Skip 0-byte files
        if pdf_path.stat().st_size == 0:
            results["skipped"].append({"path": str(pdf_path), "reason": "Empty file (0 bytes)"})
            continue

        result = import_local(pdf_path, use_ai=use_ai)
        if result["success"]:
            results["imported"].append({"path": str(pdf_path), "paper_id": result["paper_id"]})
        elif result.get("duplicate"):
            results["skipped"].append({"path": str(pdf_path), "reason": f"Duplicate of {result['existing_id']}"})
        else:
            results["failed"].append({"path": str(pdf_path), "error": result["error"]})

    return results


# --- Email parsing ---

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def extract_urls_from_text(text):
    """Extract all URLs from a text string."""
    urls = URL_PATTERN.findall(text)
    # Clean trailing punctuation
    cleaned = []
    for url in urls:
        url = url.rstrip(".,;:!?)")
        if url not in cleaned:
            cleaned.append(url)
    return cleaned


def import_emails(text_or_path):
    """Parse email text (or file path) to extract URLs and import each.

    Args:
        text_or_path: Either raw email text or path to a text file.

    Returns:
        dict with 'urls_found', 'imported', 'failed' lists.
    """
    # If it looks like a file path, read it
    path = Path(text_or_path)
    if path.exists() and path.is_file():
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = text_or_path

    urls = extract_urls_from_text(text)

    results = {"urls_found": urls, "imported": [], "failed": []}

    for url in urls:
        # Skip Yahoo Mail boilerplate URLs
        if "yahoo.com" in url and "mail" in url.lower():
            continue

        result = import_url(url)
        if result["success"]:
            results["imported"].append({"url": url, "paper_id": result["paper_id"], "note": result.get("note")})
        else:
            results["failed"].append({"url": url, "error": result["error"]})

    return results


# --- Link file import ---

def import_links_file(file_path):
    """Import papers from a text file containing URLs or arxiv IDs, one per line.

    Lines starting with # are treated as comments. Blank lines are skipped.

    Args:
        file_path: Path to text file.

    Returns:
        dict with 'imported', 'failed', 'skipped' lists.
    """
    path = Path(file_path)
    if not path.exists():
        return {"imported": [], "failed": [{"line": file_path, "error": "File not found"}], "skipped": []}

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    results = {"imported": [], "failed": [], "skipped": []}

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Detect arxiv ID (bare, no URL)
        arxiv_match = ARXIV_ID_PATTERN.match(line)
        if arxiv_match and "://" not in line:
            result = import_arxiv(line)
        elif "://" in line:
            result = import_url(line)
        else:
            results["skipped"].append({"line": line, "reason": "Not a recognised URL or arxiv ID"})
            continue

        if result["success"]:
            results["imported"].append({"line": line, "paper_id": result["paper_id"], "note": result.get("note")})
        else:
            results["failed"].append({"line": line, "error": result["error"]})

    return results


# --- Reading list import ---

def _apply_reading_list_metadata(paper_id, section_title, ref_notes, collection_title):
    """Apply topics and notes from a reading list to a paper's metadata.

    Adds section title as a topic and appends per-paper notes with a source marker.
    """
    from papers import save_paper

    paper = load_paper(paper_id)
    if paper is None:
        return

    changed = False

    # Add section title as topic (case-insensitive dedup)
    topic = section_title.strip()
    if topic:
        existing_topics = paper.get("topics", [])
        if not any(t.lower() == topic.lower() for t in existing_topics):
            existing_topics.append(topic)
            paper["topics"] = existing_topics
            changed = True

    # Merge notes with source marker
    if ref_notes:
        existing_notes = paper.get("notes") or ""
        marker = f"--- From {collection_title} ---"
        if marker not in existing_notes:
            if existing_notes:
                new_notes = f"{existing_notes}\n\n{marker}\n{ref_notes}"
            else:
                new_notes = f"{marker}\n{ref_notes}"
            paper["notes"] = new_notes
            changed = True

    if changed:
        save_paper(paper)


def import_reading_list(file_path):
    """Import a reading list / notes file as a structured collection using AI.

    Supports .md, .txt, and .pdf files. Uses Claude to parse the content,
    match references to existing papers, and create stubs for unmatched ones.

    Args:
        file_path: Path to the reading list file.

    Returns:
        dict with 'success', 'collection_id', 'matched', 'stubs_created',
        'external_links', 'error'.
    """
    from ai import parse_reading_list, _extract_text_from_pdf

    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    # Read file content
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_text_from_pdf(str(path), max_pages=20)
        if not text:
            return {"success": False, "error": "Could not extract text from PDF"}
    elif suffix in (".md", ".txt", ".text", ".markdown"):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        # Try reading as text
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            return {"success": False, "error": f"Cannot read file format: {suffix}"}

    if not text or not text.strip():
        return {"success": False, "error": "File is empty"}

    # Get existing papers for matching
    paper_list = [{"id": p["id"], "title": p.get("title")}
                  for p in list_papers()]

    config = load_config()

    # Parse with AI
    parsed = parse_reading_list(text, paper_list, config)
    if not parsed:
        return {"success": False, "error": "AI parsing failed"}

    # Build the collection
    from papers import _slugify, _collection_path
    coll_title = parsed.get("title", path.stem)
    coll_description = parsed.get("description")
    coll_id = _slugify(coll_title) if coll_title else _slugify(path.stem)

    # Ensure unique collection ID
    base_id = coll_id
    counter = 2
    while _collection_path(coll_id).exists():
        coll_id = f"{base_id}-{counter}"
        counter += 1

    matched = []
    stubs_created = []
    link_count = 0

    sections = []
    for section_data in parsed.get("sections", []):
        section = {
            "title": section_data.get("title", "Untitled"),
            "notes": section_data.get("notes"),
            "papers": [],
            "external_links": section_data.get("external_links", []),
        }
        link_count += len(section["external_links"])

        for paper_ref in section_data.get("papers", []):
            matched_id = paper_ref.get("matched_id")
            notes = paper_ref.get("notes")

            if matched_id:
                # Verify the paper actually exists
                existing = load_paper(matched_id)
                if existing:
                    section["papers"].append({
                        "paper_id": matched_id,
                        "notes": notes,
                    })
                    matched.append(matched_id)
                    _apply_reading_list_metadata(matched_id, section["title"], notes, coll_title)
                    continue

            # Unmatched — create a stub paper
            stub_title = paper_ref.get("suggested_title") or paper_ref.get("ref", "Unknown")
            stub_url = paper_ref.get("url")
            stub_id = generate_id(title=stub_title, fallback=paper_ref.get("ref", "stub"))

            create_paper_stub(
                stub_id,
                pdf_filename=None,
                title=stub_title,
                url=stub_url,
                import_source="reading-list",
            )

            section["papers"].append({
                "paper_id": stub_id,
                "notes": notes,
            })
            stubs_created.append(stub_id)
            _apply_reading_list_metadata(stub_id, section["title"], notes, coll_title)

        sections.append(section)

    # Create the collection
    collection = {
        "id": coll_id,
        "title": coll_title,
        "description": coll_description,
        "created": date.today().isoformat(),
        "updated": date.today().isoformat(),
        "sections": sections,
        "external_links": [],
    }
    save_collection(collection)

    return {
        "success": True,
        "collection_id": coll_id,
        "collection": collection,
        "matched": matched,
        "stubs_created": stubs_created,
        "external_links": link_count,
    }
