# Biblioteca — Paper Library Tool

## Environment

Flask + Python. Install dependencies: `pip install -r requirements.txt`

## Project Structure

```
biblioteca/
├── app.py                 # Flask web application + API routes
├── papers.py              # Core data model: CRUD, search, config, paths
├── importers.py           # Import pipeline: local, URL, arxiv, batch, email
├── ai.py                  # Claude API: metadata extraction, summarisation
├── cli.py                 # CLI entry points (import, list, search)
├── templates/
│   └── index.html         # Single-page app (Jinja2)
├── static/
│   ├── app.js             # Frontend logic (vanilla JS)
│   └── style.css          # Styles
├── data/
│   ├── papers/            # PDF files (gitignored)
│   ├── metadata/          # Per-paper JSON metadata (versioned)
│   ├── collections/       # Collection JSON files (versioned)
│   ├── private/           # Private annotations/metadata (gitignored)
│   └── config.json        # User settings incl. API key (gitignored)
├── requirements.txt
├── README.md
├── CLAUDE.md
└── .gitignore
```

## Key Design Decisions

- **Paper storage:** PDFs copied into `data/papers/`, never version-controlled
- **Metadata:** one JSON file per paper in `data/metadata/`, version-controlled
- **Collections:** one JSON file per collection in `data/collections/`, versioned
- **Private content:** papers or annotations flagged as private go to `data/private/`, gitignored
- **No database** — flat JSON files
- **AI features** (summarisation, extraction) use Claude API, require key in config
- **API key security:** stored only in `data/config.json` (gitignored), never in responses

## Conventions

- All development on `dev` branch; `main` is for stable releases
- British spelling in all user-facing text and comments
- Keep it simple — no premature abstraction, no over-engineering
- Metadata format should be human-readable and hand-editable

## Metadata Schema

Each paper gets a JSON file in `data/metadata/` named by ID slug:

```json
{
  "id": "hinton-2006-deep-belief",
  "title": "A Fast Learning Algorithm for Deep Belief Nets",
  "authors": ["Geoffrey Hinton", "Simon Osindero", "Yee-Whye Teh"],
  "year": 2006,
  "source": "Neural Computation",
  "tags": ["deep-learning", "unsupervised", "RBM"],
  "topics": ["neural-networks"],
  "summary": "...",
  "notes": "...",
  "private": false,
  "added": "2026-02-26",
  "pdf_filename": "hinton-2006-deep-belief.pdf",
  "url": "https://doi.org/...",
  "arxiv_id": "2402.02160",
  "doi": "10.1162/neco.2006.18.7.1527",
  "import_source": "arxiv",
  "original_filename": "hinton_2006.pdf"
}
```

## Collection Schema

Each collection gets a JSON file in `data/collections/`:

```json
{
  "id": "mcts-reading-list",
  "title": "MCTS++ Reading List",
  "description": "...",
  "created": "2026-02-26",
  "updated": "2026-02-26",
  "sections": [
    {
      "title": "MCTS",
      "notes": "...",
      "papers": [
        { "paper_id": "mcts-loops", "notes": "..." }
      ]
    }
  ],
  "external_links": [
    { "url": "https://...", "title": "...", "notes": "..." }
  ]
}
```

## Common Commands

```bash
# Run web app
python app.py
# Open http://localhost:5001

# CLI import
python cli.py import local /path/to/paper.pdf [--ai]
python cli.py import arxiv 2402.02160
python cli.py import url https://arxiv.org/abs/2402.02160
python cli.py import batch ~/Documents/sciency/ML/DL/
python cli.py import emails data/private/temp/email_samples_1.txt

# CLI browse
python cli.py list [--tag TAG] [--topic TOPIC]
python cli.py search "query"
python cli.py show PAPER_ID
python cli.py tags
python cli.py collections
```
