# Biblioteca — Paper Library Tool

## Environment

TBD — likely Flask + Python, similar to wu-laoshi. No virtualenv set up yet.

## Project Structure (Planned)

```
biblioteca/
├── app.py                 # Flask web application (future)
├── templates/             # Jinja2 templates (future)
├── static/                # CSS/JS (future)
├── data/
│   ├── papers/            # PDF files (gitignored)
│   ├── metadata/          # Per-paper JSON metadata (versioned)
│   ├── private/           # Private annotations/metadata (gitignored)
│   └── config.json        # User settings (gitignored)
├── README.md
├── CLAUDE.md
└── .gitignore
```

## Key Design Decisions

- **Paper storage:** PDFs live in `data/papers/`, never version-controlled
- **Metadata:** one JSON file per paper in `data/metadata/`, version-controlled
- **Private content:** papers or annotations flagged as private go to `data/private/`, gitignored
- **No database initially** — flat JSON files, can add SQLite/search index later if needed
- **AI features** (summarisation, extraction) are optional and require an API key

## Conventions

- All development on `dev` branch; `main` is for stable releases
- British spelling in all user-facing text and comments
- Keep it simple — no premature abstraction, no over-engineering
- Metadata format should be human-readable and hand-editable

## Metadata Schema (Draft)

Each paper gets a JSON file in `data/metadata/` named by a slug or ID:

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
  "url": "https://doi.org/..."
}
```

## Common Commands

```bash
# Run web app (future)
python app.py

# Open http://localhost:5001
```
