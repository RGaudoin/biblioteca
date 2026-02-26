# Biblioteca

A personal research paper library — for collecting, annotating, summarising, and searching academic papers gathered from emails, conference folders, and ad-hoc reading.

Built as a bespoke tool for one researcher's workflow, in the same spirit as [Wu Laoshi](https://github.com/RGaudoin/wu-laoshi): customised exactly for how I actually work, not how a product thinks I should.

## Why

Papers accumulate everywhere — email attachments, conference proceedings, colleague recommendations, rabbit-hole discoveries. They end up scattered across folders with no consistent way to search, annotate, or recall why a paper mattered. Biblioteca is meant to fix that.

## Planned Features

- **Paper ingestion** — import PDFs from local folders; extract title, authors, abstract automatically where possible
- **Summaries** — AI-assisted summarisation with the option to write or edit your own
- **Annotations & comments** — personal notes, key takeaways, relevance to current work
- **Search** — full-text and metadata search across the whole collection
- **Tags & topics** — flexible categorisation (topics, tags, project links)
- **Privacy controls** — flag papers/notes as private (stored in a separate, non-versioned metadata directory)
- **Web interface** — lightweight Flask app for browsing and managing the library
- **Public-friendly design** — the tool and metadata are version-controlled and shareable; actual PDF files and private annotations are not

## Design Principles

- **Personal first** — optimised for one user's workflow; not trying to be Zotero or Mendeley
- **Simple storage** — JSON metadata files alongside a folder of PDFs; no database required to start
- **Incremental** — start with basic import and search; add AI features as needed
- **Transparent** — all metadata is human-readable; no opaque databases or binary formats

## Project Status

Early planning stage. No code yet.

## Licence

MIT
