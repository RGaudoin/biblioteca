"""
AI features for Biblioteca — metadata extraction and summarisation using Claude API.
"""

import json
import re

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


def _track_usage(config, input_tokens, output_tokens):
    """Track API token usage in config."""
    usage = config.get("api_usage", {"input_tokens": 0, "output_tokens": 0})
    usage["input_tokens"] = usage.get("input_tokens", 0) + input_tokens
    usage["output_tokens"] = usage.get("output_tokens", 0) + output_tokens
    config["api_usage"] = usage
    save_config(config)


def extract_metadata(pdf_path, config=None):
    """Extract title, authors, year, summary from PDF using Claude API.

    Sends first ~5 pages of text to Claude with a structured prompt.
    Returns dict with extracted metadata fields, or empty dict if extraction fails.
    Falls back to PDF file metadata if no API key is configured.
    """
    if config is None:
        config = load_config()

    # Always try PDF file metadata first
    pdf_meta = _get_pdf_metadata(pdf_path)

    # Try Claude API extraction
    api_key = get_api_key(config)
    if not api_key:
        return pdf_meta

    text = _extract_text_from_pdf(pdf_path)
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

    prompt = f"""Extract metadata from this academic paper text. Return ONLY valid JSON with these fields:
{{
  "title": "full paper title",
  "authors": ["Author One", "Author Two"],
  "year": 2024,
  "source": "journal or conference name",
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "2-3 sentence summary of the paper"
}}

If any field cannot be determined, use null. For tags, suggest 3-5 relevant lowercase tags.

Paper text:
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
        )

        # Parse response — extract JSON from the response text
        response_text = response.content[0].text
        # Try to find JSON in the response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            extracted = json.loads(json_match.group())
            # Merge with PDF metadata (Claude takes priority)
            result = {**pdf_meta, **{k: v for k, v in extracted.items() if v is not None}}
            return result

    except Exception:
        pass

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

    text = _extract_text_from_pdf(pdf_path, max_pages=10)
    if not text:
        return None

    # Truncate to ~25k chars for summarisation
    if len(text) > 25000:
        text = text[:25000] + "\n[... truncated ...]"

    try:
        import anthropic
    except ImportError:
        return None

    model = config.get("summary_model", "claude-sonnet-4-6-20250514")

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
        )

        return response.content[0].text.strip()

    except Exception:
        return None
