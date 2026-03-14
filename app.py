"""
Flask web application for Biblioteca — paper library.
"""

import os
import re
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from papers import (
    PAPERS_DIR,
    create_collection,
    create_paper_stub,
    create_topic,
    delete_collection,
    delete_paper,
    find_duplicates,
    find_topic_by_name,
    generate_id,
    get_all_tags,
    get_all_topics,
    get_api_key,
    list_collections,
    list_papers,
    list_topic_entities,
    load_collection,
    load_config,
    load_paper,
    load_topic,
    merge_papers,
    resolve_file_path,
    save_collection,
    save_config,
    save_paper,
    save_topic,
)

app = Flask(__name__)


# --- Pages ---

@app.route("/")
def index():
    return render_template("index.html")


# --- Paper CRUD ---

@app.route("/api/papers")
def api_list_papers():
    tag = request.args.get("tag")
    topic = request.args.get("topic")
    search = request.args.get("q")
    sort_by = request.args.get("sort", "added")
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 50))

    papers = list_papers(tag=tag, topic=topic, search=search, sort_by=sort_by)
    total = len(papers)
    paginated = papers[offset:offset + limit]

    return jsonify({
        "papers": paginated,
        "total": total,
        "offset": offset,
        "has_more": offset + limit < total,
    })


@app.route("/api/papers/<paper_id>")
def api_get_paper(paper_id):
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404
    return jsonify(paper)


@app.route("/api/papers", methods=["POST"])
def api_create_paper():
    data = request.json or {}
    title = data.get("title")
    authors = data.get("authors", [])
    year = data.get("year")

    paper_id = generate_id(title, authors, year, fallback="manual-entry")
    metadata = create_paper_stub(paper_id, pdf_filename=None, **{
        k: v for k, v in data.items() if k not in ("id", "added", "pdf_filename")
    }, import_source="manual")

    return jsonify({"success": True, "paper": metadata}), 201


@app.route("/api/papers/<paper_id>", methods=["PUT"])
def api_update_paper(paper_id):
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    data = request.json or {}
    # Update allowed fields
    updatable = ["title", "authors", "year", "source", "tags", "topics",
                 "summary", "notes", "private", "url", "arxiv_id", "doi"]
    for field in updatable:
        if field in data:
            paper[field] = data[field]

    # Auto-register any new topic entities when topics are assigned
    if "topics" in data:
        for topic_slug in data["topics"]:
            if topic_slug and not load_topic(topic_slug):
                # Create entity with slug as name (user can rename later)
                create_topic(topic_slug.replace("-", " ").title())

    save_paper(paper)
    return jsonify({"success": True, "paper": paper})


@app.route("/api/papers/<paper_id>", methods=["DELETE"])
def api_delete_paper(paper_id):
    if delete_paper(paper_id):
        return jsonify({"success": True})
    return jsonify({"error": "Paper not found"}), 404


@app.route("/api/papers/<paper_id>/toggle-private", methods=["POST"])
def api_toggle_private(paper_id):
    """Toggle a paper between public and private."""
    from papers import toggle_privacy
    metadata, warnings = toggle_privacy(paper_id)
    if metadata is None:
        return jsonify({"success": False, "error": "Paper not found"}), 404
    return jsonify({"success": True, "paper": metadata, "warnings": warnings})


# --- Search & Browse ---

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    if not q.strip():
        return jsonify({"papers": [], "total": 0})
    papers = list_papers(search=q)
    return jsonify({"papers": papers, "total": len(papers)})


@app.route("/api/tags")
def api_tags():
    return jsonify(get_all_tags())


@app.route("/api/topics")
def api_topics():
    return jsonify(get_all_topics())


@app.route("/api/topics/rename", methods=["POST"])
def api_rename_topic():
    data = request.json or {}
    old_topic = data.get("old_topic", "").strip()
    new_topic = data.get("new_topic", "").strip()
    if not old_topic or not new_topic:
        return jsonify({"success": False, "error": "Both old_topic and new_topic are required"}), 400

    from papers import rename_topic
    count = rename_topic(old_topic, new_topic)
    return jsonify({"success": True, "updated": count})


@app.route("/api/topics/merge", methods=["POST"])
def api_merge_topics():
    data = request.json or {}
    topics_to_merge = data.get("topics", [])
    target_topic = data.get("target", "").strip()
    if len(topics_to_merge) < 1 or not target_topic:
        return jsonify({"success": False, "error": "Provide topics list and target"}), 400

    from papers import merge_topics
    count = merge_topics(topics_to_merge, target_topic)
    return jsonify({"success": True, "updated": count})


@app.route("/api/topics/delete", methods=["POST"])
def api_delete_topic():
    data = request.json or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"success": False, "error": "Topic is required"}), 400

    from papers import delete_topic
    count = delete_topic(topic)
    return jsonify({"success": True, "updated": count})


@app.route("/api/topics/create", methods=["POST"])
def api_create_topic():
    """Create a new first-class topic entity."""
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Topic name is required"}), 400

    description = data.get("description", "").strip() or None
    topic = create_topic(name, description)
    return jsonify({"success": True, "topic": topic}), 201


@app.route("/api/topics/<topic_id>")
def api_get_topic(topic_id):
    """Get a single topic entity with its papers."""
    topic = load_topic(topic_id)
    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    papers = list_papers(topic=topic["name"])
    topic["papers"] = papers
    return jsonify(topic)


@app.route("/api/topics/<topic_id>", methods=["PUT"])
def api_update_topic(topic_id):
    """Update a topic entity (name, description)."""
    topic = load_topic(topic_id)
    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    data = request.json or {}

    new_name = data.get("name", "").strip()
    if new_name and new_name != topic["name"]:
        from papers import rename_topic
        rename_topic(topic["name"], new_name)
        # Reload since rename_topic creates a new entity
        topic = find_topic_by_name(new_name)

    if "description" in data:
        topic["description"] = data["description"]
        save_topic(topic)

    return jsonify({"success": True, "topic": topic})


@app.route("/api/topics/<topic_id>/add-papers", methods=["POST"])
def api_topic_add_papers(topic_id):
    """Add papers to a topic."""
    topic = load_topic(topic_id)
    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    data = request.json or {}
    paper_ids = data.get("paper_ids", [])
    added = []
    for pid in paper_ids:
        paper = load_paper(pid)
        if paper is None:
            continue
        topics = paper.get("topics", [])
        if not any(t.lower() == topic["name"].lower() for t in topics):
            topics.append(topic["name"])
            paper["topics"] = topics
            save_paper(paper)
            added.append(pid)
    return jsonify({"success": True, "added": added})


@app.route("/api/topics/<topic_id>/remove-papers", methods=["POST"])
def api_topic_remove_papers(topic_id):
    """Remove papers from a topic."""
    topic = load_topic(topic_id)
    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    data = request.json or {}
    paper_ids = data.get("paper_ids", [])
    removed = []
    for pid in paper_ids:
        paper = load_paper(pid)
        if paper is None:
            continue
        topics = paper.get("topics", [])
        new_topics = [t for t in topics if t.lower() != topic["name"].lower()]
        if len(new_topics) != len(topics):
            paper["topics"] = new_topics
            save_paper(paper)
            removed.append(pid)
    return jsonify({"success": True, "removed": removed})


@app.route("/api/papers/assign-topic", methods=["POST"])
def api_assign_topic_to_papers():
    """Assign a topic to multiple papers. Creates the topic entity if needed."""
    data = request.json or {}
    topic_name = data.get("topic", "").strip()
    paper_ids = data.get("paper_ids", [])
    if not topic_name or not paper_ids:
        return jsonify({"success": False, "error": "Topic name and paper_ids are required"}), 400

    entity = find_topic_by_name(topic_name)
    if not entity:
        entity = create_topic(topic_name)

    added = []
    for pid in paper_ids:
        paper = load_paper(pid)
        if paper is None:
            continue
        topics = paper.get("topics", [])
        if not any(t.lower() == topic_name.lower() for t in topics):
            topics.append(entity["name"])
            paper["topics"] = topics
            save_paper(paper)
            added.append(pid)
    return jsonify({"success": True, "added": added, "topic": entity})


@app.route("/api/tags/rename", methods=["POST"])
def api_rename_tag():
    """Rename a tag across all papers."""
    data = request.json or {}
    old_tag = data.get("old_tag", "").strip()
    new_tag = data.get("new_tag", "").strip()
    if not old_tag or not new_tag:
        return jsonify({"success": False, "error": "Both old_tag and new_tag are required"}), 400

    from papers import rename_tag
    count = rename_tag(old_tag, new_tag)
    return jsonify({"success": True, "updated": count})


@app.route("/api/tags/merge", methods=["POST"])
def api_merge_tags():
    """Merge multiple tags into one."""
    data = request.json or {}
    tags_to_merge = data.get("tags", [])
    target_tag = data.get("target", "").strip()
    if len(tags_to_merge) < 1 or not target_tag:
        return jsonify({"success": False, "error": "Provide tags list and target"}), 400

    from papers import merge_tags
    count = merge_tags(tags_to_merge, target_tag)
    return jsonify({"success": True, "updated": count})


@app.route("/api/tags/delete", methods=["POST"])
def api_delete_tag():
    """Remove a tag from all papers."""
    data = request.json or {}
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"success": False, "error": "Tag is required"}), 400

    from papers import delete_tag
    count = delete_tag(tag)
    return jsonify({"success": True, "updated": count})


# --- Import ---

@app.route("/api/import/file", methods=["POST"])
def api_import_file():
    """Import an uploaded PDF file."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    from papers import ACCEPTED_EXTENSIONS
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if not file.filename or ext not in ACCEPTED_EXTENSIONS:
        accepted = ", ".join(sorted(ACCEPTED_EXTENSIONS))
        return jsonify({"success": False, "error": f"Unsupported file type. Accepted: {accepted}"}), 400

    # Save to temp, then import
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=ext or ".pdf", delete=False) as tmp:
        file.save(tmp)
        tmp_path = tmp.name

    from importers import import_local
    use_ai = request.form.get("ai", "false").lower() == "true"
    private = request.form.get("private", "false").lower() == "true"
    result = import_local(tmp_path, use_ai=use_ai,
                          metadata_overrides={"original_filename": file.filename, "private": private})

    # Clean up
    Path(tmp_path).unlink(missing_ok=True)

    if result["success"]:
        return jsonify({"success": True, "paper_id": result["paper_id"], "paper": result["metadata"]})
    return jsonify(result), 400


@app.route("/api/import/url", methods=["POST"])
def api_import_url():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "URL is required"}), 400

    from importers import import_url
    private = data.get("private", False)
    use_ai = data.get("ai", False)
    result = import_url(url, private=private, use_ai=use_ai)

    if result["success"]:
        return jsonify({"success": True, "paper_id": result["paper_id"],
                        "paper": result["metadata"], "note": result.get("note")})
    return jsonify(result), 400


@app.route("/api/import/arxiv", methods=["POST"])
def api_import_arxiv():
    data = request.json or {}
    arxiv_id = data.get("arxiv_id", "").strip()
    if not arxiv_id:
        return jsonify({"success": False, "error": "Arxiv ID is required"}), 400

    from importers import import_arxiv
    private = data.get("private", False)
    result = import_arxiv(arxiv_id, private=private)

    if result["success"]:
        return jsonify({"success": True, "paper_id": result["paper_id"], "paper": result["metadata"]})
    return jsonify(result), 400


@app.route("/api/import/batch/scan", methods=["POST"])
def api_scan_batch():
    """Scan a folder for PDFs and check for duplicates (does NOT import)."""
    data = request.json or {}
    folder = data.get("folder", "").strip()
    if not folder:
        return jsonify({"success": False, "error": "Folder path is required"}), 400

    resolved = os.path.realpath(folder)
    home = os.path.realpath(os.path.expanduser("~"))
    if not resolved.startswith(home + os.sep) and resolved != home:
        return jsonify({"success": False, "error": "Folder must be within home directory"}), 403

    recursive = data.get("recursive", False)

    from importers import scan_batch
    results = scan_batch(resolved, recursive=recursive)

    return jsonify({"success": True, "files": results})


@app.route("/api/import/batch", methods=["POST"])
def api_import_batch():
    data = request.json or {}
    folder = data.get("folder", "").strip()
    if not folder:
        return jsonify({"success": False, "error": "Folder path is required"}), 400

    resolved = os.path.realpath(folder)
    home = os.path.realpath(os.path.expanduser("~"))
    if not resolved.startswith(home + os.sep) and resolved != home:
        return jsonify({"success": False, "error": "Folder must be within home directory"}), 403

    from importers import import_batch
    use_ai = data.get("ai", False)
    recursive = data.get("recursive", False)
    paths = data.get("paths")  # Optional: only import specific files
    private = data.get("private", False)
    results = import_batch(resolved, use_ai=use_ai, recursive=recursive, paths=paths, private=private)

    return jsonify({
        "success": True,
        "imported": results["imported"],
        "skipped": results["skipped"],
        "failed": results["failed"],
    })


@app.route("/api/import/links", methods=["POST"])
@app.route("/api/import/emails", methods=["POST"])
def api_import_text():
    """Import from a text block containing URLs, arxiv IDs, or email content."""
    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400

    from importers import import_from_text
    private = data.get("private", False)
    use_ai = data.get("ai", False)
    results = import_from_text(text, private=private, use_ai=use_ai)

    return jsonify({
        "success": True,
        "urls_found": results.get("urls_found", []),
        "imported": results["imported"],
        "failed": results["failed"],
        "skipped": results.get("skipped", []),
    })


@app.route("/api/import/reading-list", methods=["POST"])
def api_import_reading_list():
    """Parse a reading list / notes file into a collection using AI."""
    data = request.json or {}
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"success": False, "error": "File path is required"}), 400

    resolved = os.path.realpath(path)
    home = os.path.realpath(os.path.expanduser("~"))
    if not resolved.startswith(home + os.sep) and resolved != home:
        return jsonify({"success": False, "error": "File must be within home directory"}), 403

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured (needed for AI parsing)"}), 400

    from importers import import_reading_list
    result = import_reading_list(resolved)

    if result["success"]:
        return jsonify({
            "success": True,
            "collection_id": result["collection_id"],
            "matched": result["matched"],
            "stubs_created": result["stubs_created"],
            "external_links": result["external_links"],
        })
    return jsonify(result), 400


# --- Collections ---

@app.route("/api/collections")
def api_list_collections():
    return jsonify(list_collections())


@app.route("/api/collections/<collection_id>")
def api_get_collection(collection_id):
    coll = load_collection(collection_id)
    if coll is None:
        return jsonify({"error": "Collection not found"}), 404
    return jsonify(coll)


@app.route("/api/collections", methods=["POST"])
def api_create_collection():
    data = request.json or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"success": False, "error": "Title is required"}), 400

    from papers import _slugify
    coll_id = _slugify(title)
    description = data.get("description")
    coll = create_collection(coll_id, title, description)

    return jsonify({"success": True, "collection": coll}), 201


@app.route("/api/collections/<collection_id>", methods=["PUT"])
def api_update_collection(collection_id):
    coll = load_collection(collection_id)
    if coll is None:
        return jsonify({"error": "Collection not found"}), 404

    data = request.json or {}
    for field in ["title", "description", "sections", "external_links"]:
        if field in data:
            coll[field] = data[field]

    save_collection(coll)
    return jsonify({"success": True, "collection": coll})


@app.route("/api/collections/<collection_id>", methods=["DELETE"])
def api_delete_collection(collection_id):
    if delete_collection(collection_id):
        return jsonify({"success": True})
    return jsonify({"error": "Collection not found"}), 404


@app.route("/api/collections/<collection_id>/apply-topics", methods=["POST"])
def api_apply_collection_topics(collection_id):
    """Retroactively assign section titles as topics to papers in a collection."""
    coll = load_collection(collection_id)
    if coll is None:
        return jsonify({"error": "Collection not found"}), 404

    from importers import _apply_reading_list_metadata
    updated = []
    for section in coll.get("sections", []):
        for ref in section.get("papers", []):
            _apply_reading_list_metadata(
                ref["paper_id"],
                section.get("title", ""),
                ref.get("notes"),
                coll.get("title", ""),
            )
            updated.append(ref["paper_id"])

    return jsonify({"success": True, "updated": list(set(updated))})


# --- AI ---

@app.route("/api/ai/bulk-extract", methods=["POST"])
def api_ai_bulk_extract():
    """Extract metadata for multiple papers that are missing titles."""
    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    data = request.json or {}
    paper_ids = data.get("paper_ids")  # Optional: specific paper IDs

    if paper_ids:
        papers = [load_paper(pid) for pid in paper_ids]
        papers = [p for p in papers if p is not None]
    else:
        # Default: all papers missing a title
        papers = [p for p in list_papers() if not p.get("title")]

    if not papers:
        return jsonify({"success": True, "processed": 0, "results": [],
                        "message": "No papers need extraction"})

    from ai import extract_metadata
    results = []
    for paper in papers:
        if not paper.get("pdf_filename"):
            results.append({"paper_id": paper["id"], "status": "skipped",
                            "reason": "No PDF file"})
            continue

        pdf_path = resolve_file_path(paper)
        if not pdf_path:
            results.append({"paper_id": paper["id"], "status": "skipped",
                            "reason": "File not found on disk"})
            continue

        extracted = extract_metadata(str(pdf_path), config)
        if not extracted:
            # Fallback: derive title from original filename
            orig = paper.get("original_filename", "")
            if orig:
                fallback_title = re.sub(r"\.[^.]+$", "", orig).strip()
                if fallback_title:
                    paper["title"] = fallback_title
                    save_paper(paper)
                    results.append({"paper_id": paper["id"], "status": "updated",
                                    "title": fallback_title,
                                    "reason": "Title from filename (PDF text not extractable)"})
                    continue
            results.append({"paper_id": paper["id"], "status": "failed",
                            "reason": "Could not extract text from PDF"})
            continue

        updated = False
        for field in ["title", "authors", "year", "source", "summary", "tags"]:
            if extracted.get(field) and not paper.get(field):
                paper[field] = extracted[field]
                updated = True

        # Record models used
        for model_field in ["summary_model", "extraction_model"]:
            if extracted.get(model_field) and not paper.get(model_field):
                paper[model_field] = extracted[model_field]
                updated = True

        if updated:
            save_paper(paper)
            results.append({"paper_id": paper["id"], "status": "updated",
                            "title": paper.get("title")})
        else:
            results.append({"paper_id": paper["id"], "status": "unchanged"})

    return jsonify({
        "success": True,
        "processed": len(results),
        "results": results,
    })


def extract_metadata_from_url(url, config):
    """Fetch a URL's content and extract metadata from it."""
    import tempfile
    from importers import _fetch_page_metadata, _html_to_markdown
    from ai import extract_metadata

    page = _fetch_page_metadata(url)
    if not page.get("html"):
        return {}

    md = _html_to_markdown(page["html"])
    if len(md) < 50:
        return {}

    # Write markdown to a temp file for extract_metadata
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(md)
        tmp_path = tmp.name

    try:
        extracted = extract_metadata(tmp_path, config)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return extracted


@app.route("/api/ai/extract/<paper_id>", methods=["POST"])
def api_ai_extract(paper_id):
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    # Try local file first, then fall back to fetching URL content
    pdf_path = resolve_file_path(paper) if paper.get("pdf_filename") else None

    from ai import extract_metadata
    if pdf_path:
        extracted = extract_metadata(str(pdf_path), config)
    elif paper.get("url"):
        # No local file — fetch the URL and extract from the page content
        extracted = extract_metadata_from_url(paper["url"], config)
    else:
        return jsonify({"success": False, "error": "Paper has no file or URL to extract from"}), 400

    if not extracted:
        return jsonify({"success": False, "error": "Could not extract metadata"}), 400

    # Update paper with extracted fields (only fill in missing fields)
    updated = False
    for field in ["title", "authors", "year", "source", "summary", "tags"]:
        if extracted.get(field) and not paper.get(field):
            paper[field] = extracted[field]
            updated = True

    # Record models used
    if extracted.get("summary_model") and not paper.get("summary_model"):
        paper["summary_model"] = extracted["summary_model"]
        updated = True
    if extracted.get("extraction_model") and not paper.get("extraction_model"):
        paper["extraction_model"] = extracted["extraction_model"]
        updated = True

    if updated:
        save_paper(paper)

    return jsonify({"success": True, "paper": paper, "extracted": extracted})


@app.route("/api/ai/summarise/<paper_id>", methods=["POST"])
def api_ai_summarise(paper_id):
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    if not paper.get("pdf_filename"):
        return jsonify({"success": False, "error": "Paper has no file"}), 400

    pdf_path = resolve_file_path(paper)
    if not pdf_path:
        return jsonify({"success": False, "error": "File not found on disk"}), 400

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    data = request.json or {}
    style = data.get("style", "brief")

    from ai import summarise_paper
    result = summarise_paper(str(pdf_path), config, style=style)

    if not result:
        return jsonify({"success": False, "error": "Could not generate summary"}), 400

    # Save summary and model to paper
    paper["summary"] = result["summary"]
    paper["summary_model"] = result["model"]
    save_paper(paper)

    return jsonify({"success": True, "paper": paper, "summary": result["summary"]})


@app.route("/api/ai/suggest-tags/<paper_id>", methods=["POST"])
def api_ai_suggest_tags(paper_id):
    """Generate new tag suggestions for a paper."""
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    # Find content to analyse
    pdf_path = resolve_file_path(paper) if paper.get("pdf_filename") else None
    if not pdf_path:
        return jsonify({"success": False, "error": "Paper has no file to analyse"}), 400

    from ai import suggest_tags
    result = suggest_tags(str(pdf_path), existing_tags=paper.get("tags", []), config=config)

    if not result or not result.get("tags"):
        return jsonify({"success": False, "error": "Could not generate tag suggestions"}), 400

    # Replace tags and record model
    paper["tags"] = result["tags"]
    paper["extraction_model"] = result["model"]
    save_paper(paper)

    return jsonify({"success": True, "paper": paper, "tags": result["tags"]})


@app.route("/api/ai/suggest-tag-merges", methods=["POST"])
def api_suggest_tag_merges():
    """Use AI to suggest tag consolidations."""
    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    from ai import suggest_tag_merges
    tags = get_all_tags()
    suggestions = suggest_tag_merges(tags, config)
    return jsonify({"success": True, "suggestions": suggestions})


@app.route("/api/ai/suggest-topics/<paper_id>", methods=["POST"])
def api_suggest_topics(paper_id):
    """Suggest existing topics for a paper using AI."""
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    if not paper.get("pdf_filename"):
        return jsonify({"success": False, "error": "Paper has no file"}), 400

    pdf_path = resolve_file_path(paper)
    if not pdf_path:
        return jsonify({"success": False, "error": "File not found on disk"}), 400

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    all_existing = [{"name": t["name"], "description": t.get("description")}
                    for t in list_topic_entities()]
    current = paper.get("topics", [])

    from ai import suggest_topics
    suggestions = suggest_topics(str(pdf_path), all_existing, current, config)
    return jsonify({"success": True, "suggestions": suggestions})


@app.route("/api/ai/suggest-unifying-topic", methods=["POST"])
def api_suggest_unifying_topic():
    """Suggest a topic for a group of papers."""
    data = request.json or {}
    paper_ids = data.get("paper_ids", [])
    if len(paper_ids) < 1:
        return jsonify({"success": False, "error": "Select at least one paper"}), 400

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    paper_summaries = []
    for pid in paper_ids:
        p = load_paper(pid)
        if p:
            paper_summaries.append({
                "title": p.get("title") or pid,
                "summary": p.get("summary"),
                "tags": p.get("tags", []),
            })

    existing = [{"name": t["name"], "description": t.get("description")}
                for t in list_topic_entities()]

    from ai import suggest_unifying_topics
    suggestions = suggest_unifying_topics(paper_summaries, existing, config)
    if suggestions:
        return jsonify({"success": True, "suggestions": suggestions})
    return jsonify({"success": False, "error": "Could not generate suggestions"})


# --- Duplicates ---

@app.route("/api/duplicates")
def api_find_duplicates():
    """Scan library for duplicate papers and orphan stubs."""
    result = find_duplicates()
    return jsonify(result)


@app.route("/api/duplicates/merge", methods=["POST"])
def api_merge_duplicates():
    """Merge duplicate papers: keep one, absorb metadata from others, delete others."""
    data = request.json or {}
    keep_id = data.get("keep_id", "").strip()
    remove_ids = data.get("remove_ids", [])
    if not keep_id or not remove_ids:
        return jsonify({"success": False, "error": "keep_id and remove_ids are required"}), 400

    keeper = merge_papers(keep_id, remove_ids)
    if keeper is None:
        return jsonify({"success": False, "error": "Paper to keep not found"}), 404
    return jsonify({"success": True, "paper": keeper})


@app.route("/api/consistency")
def api_check_consistency():
    """Check library consistency: orphan files, missing files, type mismatches."""
    from papers import check_consistency
    result = check_consistency()
    return jsonify(result)


# --- Config ---

@app.route("/api/config")
def api_get_config():
    config = load_config()
    # Never return the API key itself
    response_config = {k: v for k, v in config.items() if k != "claude_api_key"}
    response_config["hasApiKey"] = bool(get_api_key(config))
    response_config["apiKeySource"] = (
        "config" if config.get("claude_api_key") else
        ("env" if os.environ.get("CLAUDE_API_KEY") else None)
    )
    return jsonify(response_config)


@app.route("/api/config", methods=["PUT"])
def api_update_config():
    config = load_config()
    data = request.json or {}

    if "claude_api_key" in data:
        key = data["claude_api_key"].strip()
        if key:
            config["claude_api_key"] = key
        else:
            config.pop("claude_api_key", None)

    for field in ["extraction_model", "summary_model", "default_tags", "default_private"]:
        if field in data:
            config[field] = data[field]

    save_config(config)

    # Return config without API key
    response_config = {k: v for k, v in config.items() if k != "claude_api_key"}
    response_config["hasApiKey"] = bool(get_api_key(config))
    return jsonify({"success": True, "config": response_config})


@app.route("/api/config/reset-usage", methods=["POST"])
def api_reset_usage():
    config = load_config()
    config["api_usage"] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "by_model": {},
        "reset_date": date.today().isoformat(),
    }
    save_config(config)
    return jsonify({"success": True, "api_usage": config["api_usage"]})


@app.route("/api/config/test-api-key", methods=["POST"])
def api_test_api_key():
    config = load_config()
    api_key = get_api_key(config)
    if not api_key:
        return jsonify({"success": False, "error": "No API key configured"}), 400

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'OK'"}],
        )
        return jsonify({"success": True, "message": "API key is valid"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# --- PDF serving ---

@app.route("/api/pdf/<filename>")
def api_serve_file(filename):
    from papers import DOCUMENTS_DIR, PRIVATE_DOCUMENTS_DIR
    # Check private docs, public docs, then papers dir
    for d in [PRIVATE_DOCUMENTS_DIR, DOCUMENTS_DIR, PAPERS_DIR]:
        if (d / filename).exists():
            return send_from_directory(d, filename)
    return send_from_directory(PAPERS_DIR, filename)


# --- Main ---

if __name__ == "__main__":
    app.run(debug=False, port=5001)
