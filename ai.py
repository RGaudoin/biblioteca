"""
AI features for Biblioteca — metadata extraction and summarisation using Claude API.
"""

import json
import re
from pathlib import Path

from papers import get_api_key, load_config, save_config


def _extract_text_from_pdf(pdf_path, max_pages=5):
    """Extract text from the first N pages of a PDF.

    Uses PyPDF2 for text extraction. Returns the extracted text string.
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return None

    try:
        reader = PdfReader(pdf_path)
        pages = reader.pages[:max_pages]
        text_parts = []
        for page in pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts) if text_parts else None
    except Exception:
        return None


def _get_pdf_metadata(pdf_path):
    """Extract basic metadata from PDF file properties."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return {}

    try:
        reader = PdfReader(pdf_path)
        info = reader.metadata
        if info is None:
            return {}
        result = {}
        if info.title:
            result["title"] = str(info.title)
        if info.author:
            result["authors"] = [a.strip() for a in str(info.author).split(",")]
        return result
    except Exception:
        return {}


def _track_usage(config, input_tokens, output_tokens, model=None):
    """Track API token usage in config, split by model."""
    usage = config.get("api_usage", {"input_tokens": 0, "output_tokens": 0})
    usage["input_tokens"] = usage.get("input_tokens", 0) + input_tokens
    usage["output_tokens"] = usage.get("output_tokens", 0) + output_tokens
    if model:
        by_model = usage.get("by_model", {})
        m = by_model.get(model, {"input_tokens": 0, "output_tokens": 0})
        m["input_tokens"] = m.get("input_tokens", 0) + input_tokens
        m["output_tokens"] = m.get("output_tokens", 0) + output_tokens
        by_model[model] = m
        usage["by_model"] = by_model
    config["api_usage"] = usage
    save_config(config)


def _extract_text_from_file(file_path):
    """Extract text from a file. For PDFs, uses PyPDF2. For text files, reads directly."""
    from papers import VERSIONABLE_EXTENSIONS
    ext = Path(file_path).suffix.lower()
    if ext in VERSIONABLE_EXTENSIONS:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
    return _extract_text_from_pdf(file_path)


def extract_metadata(pdf_path, config=None):
    """Extract title, authors, year, summary from a document using Claude API.

    Supports PDFs (via PyPDF2) and text files (read directly).
    Returns dict with extracted metadata fields, or empty dict if extraction fails.
    Falls back to PDF file metadata if no API key is configured.
    """
    if config is None:
        config = load_config()

    # Try PDF file metadata first (only works for PDFs)
    pdf_meta = _get_pdf_metadata(pdf_path)

    # Try Claude API extraction
    api_key = get_api_key(config)
    if not api_key:
        return pdf_meta

    text = _extract_text_from_file(pdf_path)
    if not text:
        return pdf_meta

    # Truncate to ~15k chars to keep costs down
    if len(text) > 15000:
        text = text[:15000] + "\n[... truncated ...]"

    try:
        import anthropic
    except ImportError:
        return pdf_meta

    model = config.get("extraction_model", "claude-haiku-4-5-20251001")

    prompt = f"""Extract metadata from this document. It may be an academic paper, a blog post, notes, or any other text. Return ONLY valid JSON with these fields:
{{
  "title": "document title",
  "authors": ["Author One", "Author Two"],
  "year": 2024,
  "source": "journal, conference, website, or publication name",
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "2-3 sentence summary of the document"
}}

If any field cannot be determined, use null. For tags, suggest 3-5 relevant lowercase tags. The summary should describe the document accurately — do not assume it is an academic paper unless it clearly is one.

Document text:
{text}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        # Track usage
        _track_usage(
            config,
            response.usage.input_tokens,
            response.usage.output_tokens,
            model=model,
        )

        # Parse response — extract JSON from the response text
        response_text = response.content[0].text
        # Try to find JSON in the response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            extracted = json.loads(json_match.group())
            # Normalise tags: lowercase, spaces to hyphens, deduplicate
            if extracted.get("tags"):
                seen = set()
                normalised = []
                for tag in extracted["tags"]:
                    t = re.sub(r"\s+", "-", tag.strip().lower())
                    if t and t not in seen:
                        seen.add(t)
                        normalised.append(t)
                extracted["tags"] = normalised
            # Merge with PDF metadata (Claude takes priority)
            result = {**pdf_meta, **{k: v for k, v in extracted.items() if v is not None}}
            if result.get("summary"):
                result["summary_model"] = model
            return result

    except Exception as e:
        import traceback
        traceback.print_exc()

    return pdf_meta


def summarise_paper(pdf_path, config=None, style="brief"):
    """Generate a summary of a paper using Claude API.

    Args:
        pdf_path: Path to the PDF file.
        config: Config dict (loaded if None).
        style: 'brief' (2-3 sentences) or 'detailed' (paragraph).

    Returns summary string, or None if summarisation fails.
    """
    if config is None:
        config = load_config()

    api_key = get_api_key(config)
    if not api_key:
        return None

    text = _extract_text_from_file(pdf_path)
    if not text:
        return None

    # Truncate to ~25k chars for summarisation
    if len(text) > 25000:
        text = text[:25000] + "\n[... truncated ...]"

    try:
        import anthropic
    except ImportError:
        return None

    model = config.get("summary_model", "claude-sonnet-4-20250514")

    if style == "brief":
        instruction = "Summarise this paper in 2-3 concise sentences."
    else:
        instruction = "Provide a detailed summary of this paper in one paragraph, covering the key contributions, methodology, and results."

    prompt = f"""{instruction}

Paper text:
{text}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        _track_usage(
            config,
            response.usage.input_tokens,
            response.usage.output_tokens,
            model=model,
        )

        return {"summary": response.content[0].text.strip(), "model": model}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None


def parse_reading_list(text, paper_list, config=None):
    """Parse a reading list / notes file into a structured collection using Claude.

    Args:
        text: The file content as a string.
        paper_list: List of dicts with 'id' and 'title' for existing papers.
        config: Config dict (loaded if None).

    Returns dict with collection structure, or None on failure.
    """
    if config is None:
        config = load_config()

    api_key = get_api_key(config)
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    model = config.get("extraction_model", "claude-haiku-4-5-20251001")

    # Build the paper list for the prompt
    papers_str = "\n".join(
        f"  {p['id']}: {p.get('title') or '(untitled)'}"
        for p in paper_list
    )

    # Truncate text if very long
    if len(text) > 30000:
        text = text[:30000] + "\n[... truncated ...]"

    prompt = f"""Parse this reading list / notes file into a structured collection.

Existing papers in the library:
{papers_str}

Return ONLY valid JSON with this structure:
{{
  "title": "suggested collection title",
  "description": "brief description of the collection",
  "sections": [
    {{
      "title": "Section Name",
      "notes": "section-level notes if any, null if none",
      "papers": [
        {{
          "ref": "original reference text from the file",
          "matched_id": "existing-paper-id or null if no match",
          "suggested_title": "descriptive title for unmatched references",
          "url": "url if available, null otherwise",
          "notes": "all notes/comments about this reference from the file"
        }}
      ],
      "external_links": [
        {{
          "url": "https://...",
          "title": "link title or description",
          "notes": "notes about this link from the file"
        }}
      ]
    }}
  ]
}}

Rules:
- Match references to existing paper IDs where possible. The file may use original filenames (e.g. MCTS_loops), abbreviations, or partial titles. Be flexible with matching.
- If a reference cannot be matched, set matched_id to null and provide a suggested_title.
- Group into sections based on the document's own structure (headings, topic groupings, clear divisions).
- Preserve ALL notes, comments, and annotations from the original text. Include indented sub-points as part of the notes.
- External URLs (blogs, forums, documentation, Stack Exchange, etc.) go in external_links with their surrounding notes.
- Paper references (local files, academic papers) go in the papers list.
- If the document has general comments not tied to a specific reference, include them in the section notes.

File content:
{text}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        _track_usage(
            config,
            response.usage.input_tokens,
            response.usage.output_tokens,
            model=model,
        )

        response_text = response.content[0].text
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            return json.loads(json_match.group())

    except Exception as e:
        import traceback
        traceback.print_exc()

    return None


def suggest_tag_merges(tags_with_counts, config=None):
    """Use Claude to suggest tag consolidations based on near-duplicates and synonyms.

    Args:
        tags_with_counts: dict mapping tag name to paper count.
        config: Config dict (loaded if None).

    Returns list of dicts: [{"tags": ["tag1", "tag2"], "suggested": "target", "reason": "..."}]
    """
    if config is None:
        config = load_config()

    api_key = get_api_key(config)
    if not api_key:
        return []

    try:
        import anthropic
    except ImportError:
        return []

    model = config.get("extraction_model", "claude-haiku-4-5-20251001")

    tags_str = "\n".join(f"  {tag} ({count} papers)" for tag, count in tags_with_counts.items())

    prompt = f"""Analyse these tags from an academic paper library and suggest merges for near-duplicates, synonyms, or tags that should be consolidated.

Tags:
{tags_str}

Return ONLY valid JSON — a list of merge suggestions:
[
  {{
    "tags": ["tag1", "tag2"],
    "suggested": "preferred-tag-name",
    "reason": "brief explanation"
  }}
]

Rules:
- Only suggest merges where tags genuinely overlap in meaning
- Prefer the tag with the higher paper count as the target
- Use lowercase, hyphenated form for suggested names
- If no merges are needed, return an empty list []"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        _track_usage(
            config,
            response.usage.input_tokens,
            response.usage.output_tokens,
            model=model,
        )

        response_text = response.content[0].text
        json_match = re.search(r"\[[\s\S]*\]", response_text)
        if json_match:
            return json.loads(json_match.group())

    except Exception:
        import traceback
        traceback.print_exc()

    return []


def suggest_topics(pdf_path, all_existing_topics, current_topics=None, config=None):
    """Suggest topics for a paper — existing or new.

    Args:
        pdf_path: Path to the PDF file.
        all_existing_topics: List of dicts with 'name' and optionally 'description'.
        current_topics: List of topic names already assigned to this paper.
        config: Config dict (loaded if None).

    Returns list of topic name strings. Existing topics use their canonical name.
    New suggestions are returned as-is.
    """
    if config is None:
        config = load_config()

    api_key = get_api_key(config)
    if not api_key:
        return []

    text = _extract_text_from_file(pdf_path)
    if not text:
        return []

    if len(text) > 15000:
        text = text[:15000] + "\n[... truncated ...]"

    try:
        import anthropic
    except ImportError:
        return []

    model = config.get("extraction_model", "claude-haiku-4-5-20251001")

    if all_existing_topics:
        topics_str = "\n".join(
            f"  - {t['name']}" + (f": {t['description']}" if t.get("description") else "")
            for t in all_existing_topics
        )
        existing_block = f"""Existing topics (use the EXACT name if one fits):
{topics_str}"""
    else:
        existing_block = "No existing topics yet."

    prompt = f"""Given this document, suggest which topics it belongs to.
Use existing topics from the list below ONLY if they are a genuinely good fit — use their EXACT names.
Do NOT force a match to a generic or catch-all topic (e.g. "Other") when a more specific topic would be better.
Suggest new, specific topic names whenever the existing ones are too broad or irrelevant.
Aim for 2-4 topics. Return ONLY a JSON list of topic name strings.

{existing_block}

Document text:
{text}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        _track_usage(
            config,
            response.usage.input_tokens,
            response.usage.output_tokens,
            model=model,
        )

        response_text = response.content[0].text
        json_match = re.search(r"\[[\s\S]*\]", response_text)
        if json_match:
            suggested = json.loads(json_match.group())
            existing_by_name = {t["name"].lower(): t["name"] for t in all_existing_topics}
            current_lower = {t.lower() for t in (current_topics or [])}

            results = []
            for s in suggested:
                sl = s.lower()
                # Map to existing topic name (exact or fuzzy substring match)
                canonical = None
                if sl in existing_by_name:
                    canonical = existing_by_name[sl]
                else:
                    for el, en in existing_by_name.items():
                        if sl in el or el in sl:
                            canonical = en
                            break

                name = canonical or s
                # Skip if already assigned to this paper
                if name.lower() in current_lower:
                    continue
                if name not in results:
                    results.append(name)
            return results

    except Exception:
        import traceback
        traceback.print_exc()

    return []


def suggest_unifying_topics(paper_summaries, existing_topics, config=None):
    """Suggest topics for a group of papers.

    Args:
        paper_summaries: List of dicts with 'title', 'summary', 'tags' for each paper.
        existing_topics: List of dicts with 'name' and optionally 'description'.
        config: Config dict (loaded if None).

    Returns list of dicts: [{"name": "...", "description": "...", "existing": bool}]
    """
    if config is None:
        config = load_config()

    api_key = get_api_key(config)
    if not api_key:
        return []

    try:
        import anthropic
    except ImportError:
        return []

    model = config.get("extraction_model", "claude-haiku-4-5-20251001")

    papers_str = "\n".join(
        f"  - {p.get('title', 'Untitled')}"
        + (f" — {p['summary'][:200]}" if p.get("summary") else "")
        + (f" [tags: {', '.join(p['tags'])}]" if p.get("tags") else "")
        for p in paper_summaries
    )

    existing_str = "\n".join(
        f"  - {t['name']}" + (f": {t['description']}" if t.get("description") else "")
        for t in existing_topics
    ) if existing_topics else "  (none)"

    prompt = f"""Given these papers, suggest one or more topics they belong to.
Prefer existing topics from the list below where relevant — use their EXACT names.
You may also suggest new topic names if none of the existing ones fit.
Only suggest topics that are genuinely relevant.

Papers:
{papers_str}

Existing topics:
{existing_str}

Return ONLY a JSON list:
[{{"name": "Topic Name", "description": "One sentence description", "existing": true/false}}]"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        _track_usage(
            config,
            response.usage.input_tokens,
            response.usage.output_tokens,
            model=model,
        )

        response_text = response.content[0].text
        json_match = re.search(r"\[[\s\S]*\]", response_text)
        if json_match:
            return json.loads(json_match.group())

    except Exception:
        import traceback
        traceback.print_exc()

    return []
