# Biblioteca

A personal paper library tool — for collecting, annotating, summarising, and organising papers and articles gathered from everywhere: emails, conference folders, social media links, Google Drive, random browser tabs.

Built as a bespoke tool for my workflow, in the same spirit as [Wu Laoshi](https://github.com/RGaudoin/wu-laoshi): customised exactly for how I actually work, not how a product thinks I should.

## Why

Papers and articles accumulate everywhere. An interesting link spotted on social media while on a bus in London. Email attachments from colleagues. Conference proceedings downloaded in bulk. Rabbit-hole discoveries at 2am. They end up scattered across folders, cloud drives, browser bookmarks, and email threads — with no consistent way to search, annotate, or recall why something mattered.

This isn't limited to academic papers. Current affairs pieces, technical blog posts, long-form analyses — anything worth reading carefully and returning to later. Biblioteca is meant to bring all of that into one searchable, annotated, organised place.

## Features

- **Multi-source import** — upload PDFs, paste arXiv IDs or URLs, batch-import from folders, parse email text for links, import reading lists
- **AI metadata extraction** — automatic title, authors, year, tags, and summary extraction using Claude
- **AI summarisation** — generate concise summaries on demand, with model attribution
- **Topics** — first-class organisational units with descriptions, paper management, and AI-suggested assignments
- **Tags** — granular labels with AI-suggested merges, bulk rename, and cleanup tools
- **Collections** — curated reading lists with sections and notes
- **Duplicate detection** — find duplicate papers by hash, arXiv ID, DOI, or title similarity, with merge/cleanup tools
- **Search** — full-text and metadata search across the whole library
- **Privacy controls** — flag papers or notes as private (stored separately, never version-controlled)
- **Web interface** — lightweight single-page Flask app for browsing and managing everything

## Design Principles

- **Personal first** — optimised for my workflow, not trying to be Zotero or Mendeley, but something I can modify, extend, evolve and customise exactly to my needs
- **Simple storage** — JSON metadata files alongside a folder of PDFs; no database
- **Transparent** — all metadata is human-readable and hand-editable
- **Public-friendly** — the tool and metadata are version-controlled and shareable; PDFs and private annotations are not

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web app
python app.py
# Open http://localhost:5001
```

You'll need a Claude API key for AI features (summarisation, metadata extraction, topic suggestions). Add it in Settings once the app is running.

## CLI

```bash
# Import a single paper
python cli.py import local /path/to/paper.pdf [--ai]
python cli.py import arxiv 2402.02160
python cli.py import url https://arxiv.org/abs/2402.02160

# Batch import from a folder
python cli.py import batch ~/Documents/papers/

# Browse
python cli.py list [--tag TAG] [--topic TOPIC]
python cli.py search "query"
python cli.py show PAPER_ID
python cli.py tags
python cli.py collections
```

## Project Structure

```
biblioteca/
├── app.py              # Flask web application + API routes
├── papers.py           # Core data model: CRUD, search, config, paths
├── importers.py        # Import pipeline: local, URL, arXiv, batch, email
├── ai.py               # Claude API: metadata extraction, summarisation
├── cli.py              # CLI entry points
├── templates/
│   └── index.html      # Single-page app (Jinja2)
├── static/
│   ├── app.js          # Frontend logic (vanilla JS)
│   └── style.css       # Styles
└── data/
    ├── papers/         # PDF files (gitignored)
    ├── metadata/       # Per-paper JSON metadata (versioned)
    ├── collections/    # Collection JSON files (versioned)
    ├── topics/         # Topic entity files (versioned)
    ├── private/        # Private annotations (gitignored)
    └── config.json     # User settings (gitignored)
```

## TODO

- **Private annotations** — marking a paper as private should move all related metadata (not just the annotation) into `data/private/`, with logic to handle the split and avoid duplication between public and private stores
- **Paper finder** — given partial information (e.g. a title or topic), search for and fetch the PDF from arXiv or other open-access sources, especially useful when the original is behind a paywall
- **Paper linking** — link related papers together (e.g. multi-part series, papers that build on each other), optionally ordered, with navigation between linked papers

## How It Was Built

Biblioteca was built entirely through conversation with [Claude Code](https://claude.ai/claude-code) — Anthropic's agentic coding tool. The design, architecture, and every line of code emerged from an iterative dialogue: describing what I needed, reviewing what was built, testing, and refining. No code was written by hand.

## Licence

MIT
