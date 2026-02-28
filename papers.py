"""
Core data model for Biblioteca — paper CRUD, search, config, path constants.
"""

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path


# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
PAPERS_DIR = DATA_DIR / "papers"
METADATA_DIR = DATA_DIR / "metadata"
COLLECTIONS_DIR = DATA_DIR / "collections"
PRIVATE_DIR = DATA_DIR / "private"
CONFIG_FILE = DATA_DIR / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "claude_api_key": None,
    "extraction_model": "claude-haiku-4-5-20251001",
    "summary_model": "claude-sonnet-4-20250514",
    "api_usage": {"input_tokens": 0, "output_tokens": 0},
    "default_tags": [],
    "default_private": False,
}


def _ensure_dirs():
    """Create data directories if they don't exist."""
    for d in [PAPERS_DIR, METADATA_DIR, COLLECTIONS_DIR, PRIVATE_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# --- Config ---

def load_config():
    """Load configuration. Creates default config if missing."""
    _ensure_dirs()
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return dict(DEFAULT_CONFIG)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Merge with defaults (in case new settings are added)
    merged = dict(DEFAULT_CONFIG)
    for key, value in config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def save_config(config):
    """Save configuration."""
    _ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_api_key(config=None):
    """Get Claude API key from config or environment variable."""
    if config is None:
        config = load_config()
    if config.get("claude_api_key"):
        return config["claude_api_key"]
    return os.environ.get("CLAUDE_API_KEY")


# --- ID and filename generation ---

def _slugify(text):
    """Convert text to a URL-safe slug."""
    # Normalise unicode, strip accents
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanum with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    # Strip leading/trailing hyphens, collapse multiples
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def generate_id(title=None, authors=None, year=None, fallback=None):
    """Generate a paper ID slug like 'hinton-2006-deep-belief'.

    Uses first author surname, year, and first few words of title.
    Falls back to sanitised fallback string if no metadata available.
    """
    parts = []

    if authors and len(authors) > 0:
        # Extract surname from first author (last word)
        first_author = authors[0].strip()
        surname = first_author.split()[-1] if first_author else ""
        if surname:
            parts.append(_slugify(surname))

    if year:
        parts.append(str(year))

    if title:
        # Take first few meaningful words from title
        stop_words = {"a", "an", "the", "of", "for", "in", "on", "to", "and", "with", "by", "from", "is", "are"}
        words = [w for w in _slugify(title).split("-") if w and w not in stop_words]
        parts.extend(words[:4])

    if not parts and fallback:
        parts = [_slugify(fallback)]

    if not parts:
        parts = [f"paper-{date.today().isoformat()}"]

    slug = "-".join(parts)

    # Ensure uniqueness — append -2, -3 etc. if needed
    base_slug = slug
    counter = 2
    while (METADATA_DIR / f"{slug}.json").exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def normalise_filename(title=None, authors=None, year=None, original=None):
    """Generate a normalised PDF filename like 'hinton-2006-deep-belief.pdf'.

    Falls back to sanitised original filename if no metadata available.
    """
    if title and (authors or year):
        base = generate_id(title, authors, year)
    elif original:
        # Strip extension, slugify, re-add .pdf
        stem = Path(original).stem
        base = _slugify(stem) or "paper"
    else:
        base = f"paper-{date.today().isoformat()}"

    filename = f"{base}.pdf"

    # Ensure uniqueness
    base_name = base
    counter = 2
    while (PAPERS_DIR / filename).exists():
        filename = f"{base_name}-{counter}.pdf"
        counter += 1

    return filename


# --- Paper CRUD ---

def _metadata_path(paper_id):
    """Get path to metadata JSON file for a paper."""
    return METADATA_DIR / f"{paper_id}.json"


def create_paper_stub(paper_id, pdf_filename, **kwargs):
    """Create a minimal metadata stub for a newly imported paper.

    Returns the metadata dict.
    """
    _ensure_dirs()
    metadata = {
        "id": paper_id,
        "title": kwargs.get("title"),
        "authors": kwargs.get("authors", []),
        "year": kwargs.get("year"),
        "source": kwargs.get("source"),
        "tags": kwargs.get("tags", []),
        "topics": kwargs.get("topics", []),
        "summary": kwargs.get("summary"),
        "notes": kwargs.get("notes"),
        "private": kwargs.get("private", False),
        "added": date.today().isoformat(),
        "pdf_filename": pdf_filename,
        "url": kwargs.get("url"),
        "arxiv_id": kwargs.get("arxiv_id"),
        "doi": kwargs.get("doi"),
        "import_source": kwargs.get("import_source", "manual"),
        "original_filename": kwargs.get("original_filename"),
        "pdf_hash": kwargs.get("pdf_hash"),
    }
    save_paper(metadata)
    return metadata


def load_paper(paper_id):
    """Load a paper's metadata by ID. Returns None if not found."""
    path = _metadata_path(paper_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_paper(metadata):
    """Save a paper's metadata."""
    _ensure_dirs()
    paper_id = metadata["id"]
    path = _metadata_path(paper_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def delete_paper(paper_id, delete_pdf=True):
    """Delete a paper's metadata and optionally its PDF.

    Returns True if deleted, False if not found.
    """
    metadata = load_paper(paper_id)
    if metadata is None:
        return False

    # Delete metadata
    _metadata_path(paper_id).unlink()

    # Delete PDF if requested
    if delete_pdf and metadata.get("pdf_filename"):
        pdf_path = PAPERS_DIR / metadata["pdf_filename"]
        if pdf_path.exists():
            pdf_path.unlink()

    return True


def list_papers(tag=None, topic=None, search=None, sort_by="added", reverse=True):
    """List all papers, optionally filtered.

    Args:
        tag: Filter by tag (case-insensitive).
        topic: Filter by topic (case-insensitive).
        search: Search across title, authors, notes, summary.
        sort_by: Field to sort by (default: 'added').
        reverse: Sort descending (default: True, newest first).

    Returns list of metadata dicts.
    """
    _ensure_dirs()
    papers = []
    for path in METADATA_DIR.glob("*.json"):
        if path.name == ".gitkeep":
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                papers.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue

    # Filter by tag
    if tag:
        tag_lower = tag.lower()
        papers = [p for p in papers if any(t.lower() == tag_lower for t in p.get("tags", []))]

    # Filter by topic
    if topic:
        topic_lower = topic.lower()
        papers = [p for p in papers if any(t.lower() == topic_lower for t in p.get("topics", []))]

    # Search across text fields
    if search:
        search_lower = search.lower()
        def matches(p):
            fields = [
                p.get("title") or "",
                " ".join(p.get("authors", [])),
                p.get("summary") or "",
                p.get("notes") or "",
                p.get("source") or "",
                " ".join(p.get("tags", [])),
                " ".join(p.get("topics", [])),
            ]
            text = " ".join(fields).lower()
            return search_lower in text
        papers = [p for p in papers if matches(p)]

    # Sort
    def sort_key(p):
        val = p.get(sort_by)
        if val is None:
            return ""
        if isinstance(val, list):
            return " ".join(val)
        return str(val)

    papers.sort(key=sort_key, reverse=reverse)
    return papers


def get_all_tags():
    """Get all tags with paper counts."""
    papers = list_papers()
    tag_counts = {}
    for p in papers:
        for tag in p.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return dict(sorted(tag_counts.items()))


def get_all_topics():
    """Get all topics with paper counts."""
    papers = list_papers()
    topic_counts = {}
    for p in papers:
        for topic in p.get("topics", []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    return dict(sorted(topic_counts.items()))


def rename_tag(old_tag, new_tag):
    """Rename a tag across all papers. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    for p in papers:
        tags = p.get("tags", [])
        if old_tag in tags:
            tags = [new_tag if t == old_tag else t for t in tags]
            # Deduplicate (in case new_tag already existed)
            seen = set()
            deduped = []
            for t in tags:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    deduped.append(t)
            p["tags"] = deduped
            save_paper(p)
            count += 1
    return count


def merge_tags(source_tags, target_tag):
    """Merge multiple tags into target_tag. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    source_set = {t.lower() for t in source_tags}
    for p in papers:
        tags = p.get("tags", [])
        if any(t.lower() in source_set for t in tags):
            new_tags = [t for t in tags if t.lower() not in source_set]
            if not any(t.lower() == target_tag.lower() for t in new_tags):
                new_tags.append(target_tag)
            p["tags"] = new_tags
            save_paper(p)
            count += 1
    return count


def delete_tag(tag):
    """Remove a tag from all papers. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    for p in papers:
        tags = p.get("tags", [])
        if tag in tags:
            p["tags"] = [t for t in tags if t != tag]
            save_paper(p)
            count += 1
    return count


def rename_topic(old_topic, new_topic):
    """Rename a topic across all papers. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    for p in papers:
        topics = p.get("topics", [])
        if any(t.lower() == old_topic.lower() for t in topics):
            topics = [new_topic if t.lower() == old_topic.lower() else t for t in topics]
            seen = set()
            deduped = []
            for t in topics:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    deduped.append(t)
            p["topics"] = deduped
            save_paper(p)
            count += 1
    return count


def merge_topics(source_topics, target_topic):
    """Merge multiple topics into target_topic. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    source_set = {t.lower() for t in source_topics}
    for p in papers:
        topics = p.get("topics", [])
        if any(t.lower() in source_set for t in topics):
            new_topics = [t for t in topics if t.lower() not in source_set]
            if not any(t.lower() == target_topic.lower() for t in new_topics):
                new_topics.append(target_topic)
            p["topics"] = new_topics
            save_paper(p)
            count += 1
    return count


def delete_topic(topic):
    """Remove a topic from all papers. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    for p in papers:
        topics = p.get("topics", [])
        if any(t.lower() == topic.lower() for t in topics):
            p["topics"] = [t for t in topics if t.lower() != topic.lower()]
            save_paper(p)
            count += 1
    return count


# --- Collections ---

def _collection_path(collection_id):
    """Get path to collection JSON file."""
    return COLLECTIONS_DIR / f"{collection_id}.json"


def load_collection(collection_id):
    """Load a collection by ID. Returns None if not found."""
    path = _collection_path(collection_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_collection(collection):
    """Save a collection."""
    _ensure_dirs()
    collection_id = collection["id"]
    collection["updated"] = date.today().isoformat()
    path = _collection_path(collection_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2)


def create_collection(collection_id, title, description=None):
    """Create a new empty collection. Returns the collection dict."""
    collection = {
        "id": collection_id,
        "title": title,
        "description": description,
        "created": date.today().isoformat(),
        "updated": date.today().isoformat(),
        "sections": [],
        "external_links": [],
    }
    save_collection(collection)
    return collection


def delete_collection(collection_id):
    """Delete a collection. Returns True if deleted, False if not found."""
    path = _collection_path(collection_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def list_collections():
    """List all collections. Returns list of collection dicts."""
    _ensure_dirs()
    collections = []
    for path in COLLECTIONS_DIR.glob("*.json"):
        if path.name == ".gitkeep":
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                collections.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue
    collections.sort(key=lambda c: c.get("updated", ""), reverse=True)
    return collections


# --- Deduplication helpers ---

def find_by_arxiv_id(arxiv_id):
    """Find a paper by arxiv ID. Returns metadata dict or None."""
    for p in list_papers():
        if p.get("arxiv_id") == arxiv_id:
            return p
    return None


def find_by_hash(file_hash):
    """Find a paper by PDF hash. Checks original_hash field in metadata."""
    for p in list_papers():
        if p.get("pdf_hash") == file_hash:
            return p
    return None
