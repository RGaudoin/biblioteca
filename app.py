"""
Flask web application for Biblioteca — paper library.
"""

import os

from flask import Flask, jsonify, render_template, request, send_from_directory

from papers import (
    PAPERS_DIR,
    create_collection,
    create_paper_stub,
    delete_collection,
    delete_paper,
    generate_id,
    get_all_tags,
    get_all_topics,
    get_api_key,
    list_collections,
    list_papers,
    load_collection,
    load_config,
    load_paper,
    save_collection,
    save_config,
    save_paper,
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

    save_paper(paper)
    return jsonify({"success": True, "paper": paper})


@app.route("/api/papers/<paper_id>", methods=["DELETE"])
def api_delete_paper(paper_id):
    if delete_paper(paper_id):
        return jsonify({"success": True})
    return jsonify({"error": "Paper not found"}), 404


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


# --- Import ---

@app.route("/api/import/file", methods=["POST"])
def api_import_file():
    """Import an uploaded PDF file."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"success": False, "error": "Only PDF files are accepted"}), 400

    # Save to temp, then import
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        file.save(tmp)
        tmp_path = tmp.name

    from importers import import_local
    use_ai = request.form.get("ai", "false").lower() == "true"
    result = import_local(tmp_path, use_ai=use_ai,
                          metadata_overrides={"original_filename": file.filename})

    # Clean up
    from pathlib import Path
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
    result = import_url(url)

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
    result = import_arxiv(arxiv_id)

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

    recursive = data.get("recursive", False)

    from importers import scan_batch
    results = scan_batch(folder, recursive=recursive)

    return jsonify({"success": True, "files": results})


@app.route("/api/import/batch", methods=["POST"])
def api_import_batch():
    data = request.json or {}
    folder = data.get("folder", "").strip()
    if not folder:
        return jsonify({"success": False, "error": "Folder path is required"}), 400

    from importers import import_batch
    use_ai = data.get("ai", False)
    recursive = data.get("recursive", False)
    paths = data.get("paths")  # Optional: only import specific files
    results = import_batch(folder, use_ai=use_ai, recursive=recursive, paths=paths)

    return jsonify({
        "success": True,
        "imported": results["imported"],
        "skipped": results["skipped"],
        "failed": results["failed"],
    })


@app.route("/api/import/links", methods=["POST"])
def api_import_links():
    """Import from a text block of URLs/arxiv IDs, one per line."""
    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400

    # Write to temp file and use the links importer
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    from importers import import_links_file
    results = import_links_file(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    return jsonify({
        "success": True,
        "imported": results["imported"],
        "failed": results["failed"],
        "skipped": results.get("skipped", []),
    })


@app.route("/api/import/emails", methods=["POST"])
def api_import_emails():
    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "Email text is required"}), 400

    from importers import import_emails
    results = import_emails(text)

    return jsonify({
        "success": True,
        "urls_found": results["urls_found"],
        "imported": results["imported"],
        "failed": results["failed"],
    })


@app.route("/api/import/reading-list", methods=["POST"])
def api_import_reading_list():
    """Parse a reading list / notes file into a collection using AI."""
    data = request.json or {}
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"success": False, "error": "File path is required"}), 400

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured (needed for AI parsing)"}), 400

    from importers import import_reading_list
    result = import_reading_list(path)

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

        pdf_path = PAPERS_DIR / paper["pdf_filename"]
        if not pdf_path.exists():
            results.append({"paper_id": paper["id"], "status": "skipped",
                            "reason": "PDF not found on disk"})
            continue

        extracted = extract_metadata(str(pdf_path), config)
        if not extracted:
            results.append({"paper_id": paper["id"], "status": "failed",
                            "reason": "Could not extract metadata"})
            continue

        updated = False
        for field in ["title", "authors", "year", "source", "summary", "tags"]:
            if extracted.get(field) and not paper.get(field):
                paper[field] = extracted[field]
                updated = True
        if extracted.get("summary_model") and extracted.get("summary") == paper.get("summary"):
            paper["summary_model"] = extracted["summary_model"]

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


@app.route("/api/ai/extract/<paper_id>", methods=["POST"])
def api_ai_extract(paper_id):
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    if not paper.get("pdf_filename"):
        return jsonify({"success": False, "error": "Paper has no PDF file"}), 400

    pdf_path = PAPERS_DIR / paper["pdf_filename"]
    if not pdf_path.exists():
        return jsonify({"success": False, "error": "PDF file not found on disk"}), 400

    config = load_config()
    if not get_api_key(config):
        return jsonify({"success": False, "error": "No API key configured"}), 400

    from ai import extract_metadata
    extracted = extract_metadata(str(pdf_path), config)

    if not extracted:
        return jsonify({"success": False, "error": "Could not extract metadata"}), 400

    # Update paper with extracted fields (only fill in missing fields)
    updated = False
    for field in ["title", "authors", "year", "source", "summary", "tags"]:
        if extracted.get(field) and not paper.get(field):
            paper[field] = extracted[field]
            updated = True
    # Track which model produced the summary
    if extracted.get("summary_model") and extracted.get("summary") == paper.get("summary"):
        paper["summary_model"] = extracted["summary_model"]

    if updated:
        save_paper(paper)

    return jsonify({"success": True, "paper": paper, "extracted": extracted})


@app.route("/api/ai/summarise/<paper_id>", methods=["POST"])
def api_ai_summarise(paper_id):
    paper = load_paper(paper_id)
    if paper is None:
        return jsonify({"error": "Paper not found"}), 404

    if not paper.get("pdf_filename"):
        return jsonify({"success": False, "error": "Paper has no PDF file"}), 400

    pdf_path = PAPERS_DIR / paper["pdf_filename"]
    if not pdf_path.exists():
        return jsonify({"success": False, "error": "PDF file not found on disk"}), 400

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
def api_serve_pdf(filename):
    return send_from_directory(PAPERS_DIR, filename)


# --- Main ---

if __name__ == "__main__":
    app.run(debug=True, port=5001)
