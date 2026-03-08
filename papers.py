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
TOPICS_DIR = DATA_DIR / "topics"
PRIVATE_DIR = DATA_DIR / "private"
DOCUMENTS_DIR = DATA_DIR / "documents"
CONFIG_FILE = DATA_DIR / "config.json"

# Content type detection
VERSIONABLE_EXTENSIONS = {".txt", ".md", ".tex", ".org", ".rst", ".bib", ".csv"}
ACCEPTED_EXTENSIONS = {".pdf"} | VERSIONABLE_EXTENSIONS


def detect_content_type(filename):
    """Detect content type and versionability from file extension.

    Returns (content_type, versionable) tuple.
    """
    ext = Path(filename).suffix.lower() if filename else ""
    type_map = {
        ".pdf": "pdf",
        ".txt": "text",
        ".md": "markdown",
        ".tex": "latex",
        ".org": "org",
        ".rst": "rst",
        ".bib": "bibtex",
        ".csv": "csv",
    }
    content_type = type_map.get(ext, "unknown")
    versionable = ext in VERSIONABLE_EXTENSIONS
    return content_type, versionable

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
    for d in [PAPERS_DIR, METADATA_DIR, COLLECTIONS_DIR, TOPICS_DIR, PRIVATE_DIR, DOCUMENTS_DIR]:
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
    """Generate a normalised filename like 'hinton-2006-deep-belief.pdf'.

    Preserves the original file extension. Falls back to sanitised original
    filename if no metadata available.
    """
    ext = Path(original).suffix.lower() if original else ".pdf"
    if not ext:
        ext = ".pdf"

    if title and (authors or year):
        base = generate_id(title, authors, year)
    elif original:
        stem = Path(original).stem
        base = _slugify(stem) or "paper"
    else:
        base = f"paper-{date.today().isoformat()}"

    # Versionable text files go to documents dir, others to papers dir
    target_dir = DOCUMENTS_DIR if ext in VERSIONABLE_EXTENSIONS else PAPERS_DIR

    filename = f"{base}{ext}"

    # Ensure uniqueness
    base_name = base
    counter = 2
    while (target_dir / filename).exists():
        filename = f"{base_name}-{counter}{ext}"
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
    # Detect content type from filename
    orig = kwargs.get("original_filename") or pdf_filename or ""
    auto_type, auto_versionable = detect_content_type(orig)
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
        "content_type": kwargs.get("content_type", auto_type),
        "versionable": kwargs.get("versionable", auto_versionable),
    }
    save_paper(metadata)
    return metadata


def resolve_file_path(metadata):
    """Resolve the full path to a paper's content file.

    Checks both data/documents/ (versionable text) and data/papers/ (binary).
    Returns Path if found, None if file doesn't exist or no filename set.
    """
    fn = metadata.get("pdf_filename")
    if not fn:
        return None
    # Check documents dir first for versionable types, then papers dir
    for d in [DOCUMENTS_DIR, PAPERS_DIR]:
        path = d / fn
        if path.exists():
            return path
    return None


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

    # Delete content file if requested
    if delete_pdf and metadata.get("pdf_filename"):
        file_path = resolve_file_path(metadata)
        if file_path and file_path.exists():
            file_path.unlink()

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
    """Get all topics with paper counts and entity metadata.

    Returns dict mapping topic name to info dict:
    {name: {"count": N, "description": "...", "id": "slug", "registered": bool}}
    """
    papers = list_papers()
    topic_counts = {}
    for p in papers:
        for topic in p.get("topics", []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    entities_by_name = {}
    for t in list_topic_entities():
        entities_by_name[t["name"].lower()] = t

    result = {}
    for name, count in sorted(topic_counts.items()):
        entity = entities_by_name.pop(name.lower(), None)
        result[name] = {
            "count": count,
            "description": entity["description"] if entity else None,
            "id": entity["id"] if entity else None,
            "registered": entity is not None,
        }
    # Topic entities with no papers assigned yet
    for name_lower, entity in entities_by_name.items():
        result[entity["name"]] = {
            "count": 0,
            "description": entity["description"],
            "id": entity["id"],
            "registered": True,
        }

    return dict(sorted(result.items(), key=lambda x: x[0].lower()))


def rename_tag(old_tag, new_tag):
    """Rename a tag across all papers. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    for p in papers:
        tags = p.get("tags", [])
        if old_tag in tags:
            tags = [new_tag if t == old_tag else t for t in tags]
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
    """Rename a topic across all papers and its entity file. Returns count of papers updated."""
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
    # Also rename topic entity
    entity = find_topic_by_name(old_topic)
    if entity:
        desc = entity.get("description")
        delete_topic_entity(entity["id"])
        create_topic(new_topic, description=desc)
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
    # Merge topic entities: keep target, delete sources
    target_entity = find_topic_by_name(target_topic)
    for source in source_topics:
        source_entity = find_topic_by_name(source)
        if source_entity:
            if not target_entity and source_entity.get("description"):
                target_entity = create_topic(target_topic, description=source_entity["description"])
            delete_topic_entity(source_entity["id"])
    if not target_entity:
        create_topic(target_topic)
    return count


def delete_topic(topic):
    """Remove a topic from all papers and delete its entity file. Returns count of papers updated."""
    papers = list_papers()
    count = 0
    for p in papers:
        topics = p.get("topics", [])
        if any(t.lower() == topic.lower() for t in topics):
            p["topics"] = [t for t in topics if t.lower() != topic.lower()]
            save_paper(p)
            count += 1
    entity = find_topic_by_name(topic)
    if entity:
        delete_topic_entity(entity["id"])
    return count


# --- Topic entities ---

def _topic_path(topic_id):
    """Get path to topic JSON file."""
    return TOPICS_DIR / f"{topic_id}.json"


def load_topic(topic_id):
    """Load a topic entity by ID. Returns None if not found."""
    path = _topic_path(topic_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_topic(topic):
    """Save a topic entity."""
    _ensure_dirs()
    topic["updated"] = date.today().isoformat()
    path = _topic_path(topic["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(topic, f, ensure_ascii=False, indent=2)


def create_topic(name, description=None):
    """Create a new topic entity. Returns existing if name matches (case-insensitive)."""
    _ensure_dirs()
    existing = find_topic_by_name(name)
    if existing:
        return existing

    topic_id = _slugify(name)
    base_id = topic_id
    counter = 2
    while _topic_path(topic_id).exists():
        topic_id = f"{base_id}-{counter}"
        counter += 1

    topic = {
        "id": topic_id,
        "name": name.strip(),
        "description": description,
        "created": date.today().isoformat(),
        "updated": date.today().isoformat(),
    }
    save_topic(topic)
    return topic


def delete_topic_entity(topic_id):
    """Delete a topic JSON file. Returns True if deleted."""
    path = _topic_path(topic_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def list_topic_entities():
    """List all topic entities from data/topics/. Returns list of topic dicts."""
    _ensure_dirs()
    topics = []
    for path in TOPICS_DIR.glob("*.json"):
        if path.name == ".gitkeep":
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                topics.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue
    topics.sort(key=lambda t: t.get("name", "").lower())
    return topics


def find_topic_by_name(name):
    """Find a topic entity by display name (case-insensitive). Returns dict or None."""
    name_lower = name.strip().lower()
    for t in list_topic_entities():
        if t["name"].lower() == name_lower:
            return t
    return None


def bootstrap_topic_entities():
    """Create topic entity files for all existing topics found on papers.

    Idempotent: skips topics that already have entity files.
    Returns list of created topic names.
    """
    all_topics = get_all_topics()
    created = []
    for name, info in all_topics.items():
        if not info.get("registered"):
            create_topic(name)
            created.append(name)
    return created


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


def _normalise_title(title):
    """Normalise a title for duplicate comparison: lowercase, strip non-alphanumeric."""
    if not title:
        return ""
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("ascii")
    title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return re.sub(r"\s+", " ", title)


def find_duplicates():
    """Find duplicate papers and orphan stubs across the library.

    Returns dict with:
        groups: list of {reason, papers: [metadata...]}
        orphans: list of metadata dicts (pdf_filename set but file missing)
    """
    papers = list_papers()

    # Build indexes
    by_hash = {}
    by_arxiv = {}
    by_doi = {}
    by_title = {}
    orphans = []

    for p in papers:
        # Check for orphan: metadata references a PDF that doesn't exist
        pdf_fn = p.get("pdf_filename")
        if pdf_fn and not resolve_file_path(p):
            orphans.append(p)

        h = p.get("pdf_hash")
        if h:
            by_hash.setdefault(h, []).append(p)

        arxiv = p.get("arxiv_id")
        if arxiv:
            by_arxiv.setdefault(arxiv, []).append(p)

        doi = p.get("doi")
        if doi:
            by_doi.setdefault(doi.lower(), []).append(p)

        norm = _normalise_title(p.get("title"))
        if norm and len(norm) > 5:  # skip very short/empty titles
            by_title.setdefault(norm, []).append(p)

    # Collect duplicate groups, deduplicating across detection methods
    groups = []
    seen_pairs = set()  # track paper ID pairs already reported

    def _add_group(reason, group_papers):
        ids = frozenset(p["id"] for p in group_papers)
        if ids in seen_pairs or len(ids) < 2:
            return
        seen_pairs.add(ids)
        groups.append({"reason": reason, "papers": group_papers})

    # Hash matches (strongest signal)
    for h, ps in by_hash.items():
        if len(ps) > 1:
            _add_group("hash", ps)

    # arXiv ID matches
    for aid, ps in by_arxiv.items():
        if len(ps) > 1:
            _add_group("arxiv_id", ps)

    # DOI matches
    for doi, ps in by_doi.items():
        if len(ps) > 1:
            _add_group("doi", ps)

    # Title matches (weakest signal)
    for norm, ps in by_title.items():
        if len(ps) > 1:
            _add_group("title", ps)

    return {"groups": groups, "orphans": orphans}


def merge_papers(keep_id, remove_ids):
    """Merge duplicate papers: keep one, absorb metadata from others, delete others.

    Merges tags, topics, and notes from removed papers into the keeper.
    Fills in any fields that are null on the keeper but set on a removed paper.

    Returns updated keeper metadata, or None if keep_id not found.
    """
    keeper = load_paper(keep_id)
    if keeper is None:
        return None

    for rid in remove_ids:
        if rid == keep_id:
            continue
        other = load_paper(rid)
        if other is None:
            continue

        # Merge tags (union, case-insensitive dedup)
        existing_tags_lower = {t.lower() for t in keeper.get("tags", [])}
        for tag in other.get("tags", []):
            if tag.lower() not in existing_tags_lower:
                keeper.setdefault("tags", []).append(tag)
                existing_tags_lower.add(tag.lower())

        # Merge topics (union, case-insensitive dedup)
        existing_topics_lower = {t.lower() for t in keeper.get("topics", [])}
        for topic in other.get("topics", []):
            if topic.lower() not in existing_topics_lower:
                keeper.setdefault("topics", []).append(topic)
                existing_topics_lower.add(topic.lower())

        # Append notes
        other_notes = (other.get("notes") or "").strip()
        if other_notes:
            keeper_notes = (keeper.get("notes") or "").strip()
            if keeper_notes:
                keeper["notes"] = keeper_notes + "\n\n" + other_notes
            else:
                keeper["notes"] = other_notes

        # Fill in missing fields from the other paper
        fill_fields = ["title", "authors", "year", "source", "doi", "arxiv_id",
                        "url", "summary", "pdf_hash", "import_source"]
        for field in fill_fields:
            if not keeper.get(field) and other.get(field):
                keeper[field] = other[field]

        # If keeper has no PDF but other does, take it
        if not keeper.get("pdf_filename") and other.get("pdf_filename"):
            if resolve_file_path(other):
                keeper["pdf_filename"] = other["pdf_filename"]
                # Don't delete the PDF when removing the other paper
                delete_paper(rid, delete_pdf=False)
                continue

        delete_paper(rid)

    save_paper(keeper)
    return keeper


def check_consistency():
    """Check library consistency: orphan files, missing files, type mismatches.

    Returns dict with lists of issues found.
    """
    papers = list_papers()
    issues = []

    # Collect all filenames referenced by metadata
    referenced_files = set()

    for p in papers:
        fn = p.get("pdf_filename")
        if not fn:
            continue
        referenced_files.add(fn)

        # Check file exists
        resolved = resolve_file_path(p)
        if not resolved:
            issues.append({
                "type": "missing_file",
                "paper_id": p["id"],
                "filename": fn,
                "message": f"File '{fn}' referenced by metadata but not found on disk",
            })
            continue

        # Check file is in the correct directory for its type
        ext = Path(fn).suffix.lower()
        expected_dir = DOCUMENTS_DIR if ext in VERSIONABLE_EXTENSIONS else PAPERS_DIR
        if resolved.parent != expected_dir:
            issues.append({
                "type": "wrong_directory",
                "paper_id": p["id"],
                "filename": fn,
                "message": f"File '{fn}' is in {resolved.parent.name}/ but should be in {expected_dir.name}/",
            })

        # Check content_type field matches actual extension
        detected_type, detected_ver = detect_content_type(fn)
        if p.get("content_type") and p["content_type"] != detected_type:
            issues.append({
                "type": "type_mismatch",
                "paper_id": p["id"],
                "filename": fn,
                "message": f"Metadata says '{p['content_type']}' but file extension suggests '{detected_type}'",
            })

    # Check for orphan files (files with no metadata)
    for directory, dir_name in [(PAPERS_DIR, "papers"), (DOCUMENTS_DIR, "documents")]:
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.name.startswith("."):
                continue
            if f.name not in referenced_files:
                issues.append({
                    "type": "orphan_file",
                    "filename": f.name,
                    "directory": dir_name,
                    "message": f"File '{f.name}' in {dir_name}/ has no matching metadata",
                })

    return {"issues": issues, "total_papers": len(papers)}


def backfill_content_types():
    """Add content_type and versionable fields to papers that lack them.

    Returns count of papers updated.
    """
    updated = 0
    for p in list_papers():
        if "content_type" in p and "versionable" in p:
            continue
        fn = p.get("pdf_filename") or p.get("original_filename") or ""
        ct, ver = detect_content_type(fn)
        p["content_type"] = p.get("content_type", ct)
        p["versionable"] = p.get("versionable", ver)
        save_paper(p)
        updated += 1
    return updated
