#!/usr/bin/env python3
"""
CLI entry points for Biblioteca — import, list, search, show papers.

Usage:
    python cli.py import local /path/to/paper.pdf [--ai]
    python cli.py import arxiv 2402.02160
    python cli.py import url https://example.com/paper.pdf
    python cli.py import batch ~/Documents/sciency/ML/DL/ [--ai]
    python cli.py import emails data/private/temp/email_samples_1.txt
    python cli.py list [--tag TAG] [--topic TOPIC]
    python cli.py search "query string"
    python cli.py show PAPER_ID
    python cli.py collections
"""

import argparse
import json
import sys

from papers import list_papers, load_paper, get_all_tags, get_all_topics, list_collections


def cmd_import_local(args):
    from importers import import_local
    result = import_local(args.path, use_ai=args.ai)
    if result["success"]:
        print(f"Imported: {result['paper_id']}")
        _print_metadata_summary(result["metadata"])
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)


def cmd_import_arxiv(args):
    from importers import import_arxiv
    print(f"Fetching from arxiv: {args.arxiv_id}...")
    result = import_arxiv(args.arxiv_id)
    if result["success"]:
        print(f"Imported: {result['paper_id']}")
        _print_metadata_summary(result["metadata"])
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        if result.get("existing_id"):
            print(f"  Existing paper: {result['existing_id']}")
        sys.exit(1)


def cmd_import_url(args):
    from importers import import_url
    print(f"Importing URL: {args.url}...")
    result = import_url(args.url)
    if result["success"]:
        print(f"Imported: {result['paper_id']}")
        if result.get("note"):
            print(f"  Note: {result['note']}")
        _print_metadata_summary(result["metadata"])
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)


def cmd_import_batch(args):
    from importers import import_batch
    print(f"Importing PDFs from: {args.folder}...")
    results = import_batch(args.folder, use_ai=args.ai)

    for item in results["imported"]:
        print(f"  Imported: {item['paper_id']} ({item['path']})")
    for item in results["skipped"]:
        print(f"  Skipped: {item['path']} — {item['reason']}")
    for item in results["failed"]:
        print(f"  Failed: {item['path']} — {item['error']}")

    print(f"\nSummary: {len(results['imported'])} imported, {len(results['skipped'])} skipped, {len(results['failed'])} failed")


def cmd_import_emails(args):
    from importers import import_emails
    print(f"Parsing emails: {args.path}...")
    results = import_emails(args.path)

    print(f"URLs found: {len(results['urls_found'])}")
    for url in results["urls_found"]:
        print(f"  {url}")

    print()
    for item in results["imported"]:
        note = f" — {item['note']}" if item.get("note") else ""
        print(f"  Imported: {item['paper_id']} ({item['url']}){note}")
    for item in results["failed"]:
        print(f"  Failed: {item['url']} — {item['error']}")


def cmd_list(args):
    papers = list_papers(tag=args.tag, topic=args.topic)
    if not papers:
        print("No papers found.")
        return

    for p in papers:
        title = p.get("title") or "(no title)"
        authors = ", ".join(p.get("authors", []))
        year = p.get("year") or "?"
        tags = ", ".join(p.get("tags", []))
        pdf = "PDF" if p.get("pdf_filename") else "ref"

        print(f"  {p['id']}")
        print(f"    {title}")
        if authors:
            print(f"    {authors} ({year})")
        if tags:
            print(f"    Tags: {tags}")
        print(f"    [{pdf}] Added: {p.get('added', '?')}")
        print()

    print(f"Total: {len(papers)} papers")


def cmd_search(args):
    papers = list_papers(search=args.query)
    if not papers:
        print(f"No papers matching '{args.query}'.")
        return

    for p in papers:
        title = p.get("title") or "(no title)"
        print(f"  {p['id']}: {title}")

    print(f"\n{len(papers)} results")


def cmd_show(args):
    paper = load_paper(args.paper_id)
    if paper is None:
        print(f"Paper not found: {args.paper_id}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(paper, indent=2, ensure_ascii=False))


def cmd_tags(args):
    tags = get_all_tags()
    if not tags:
        print("No tags found.")
        return
    for tag, count in tags.items():
        print(f"  {tag} ({count})")


def cmd_collections(args):
    colls = list_collections()
    if not colls:
        print("No collections found.")
        return
    for c in colls:
        n_papers = sum(len(s.get("papers", [])) for s in c.get("sections", []))
        print(f"  {c['id']}: {c['title']} ({n_papers} papers)")


def _print_metadata_summary(meta):
    """Print a brief summary of imported metadata."""
    if meta.get("title"):
        print(f"  Title: {meta['title']}")
    if meta.get("authors"):
        print(f"  Authors: {', '.join(meta['authors'])}")
    if meta.get("year"):
        print(f"  Year: {meta['year']}")
    if meta.get("tags"):
        print(f"  Tags: {', '.join(meta['tags'])}")
    if meta.get("pdf_filename"):
        print(f"  PDF: {meta['pdf_filename']}")


def main():
    parser = argparse.ArgumentParser(description="Biblioteca — paper library CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- import ---
    import_parser = subparsers.add_parser("import", help="Import papers")
    import_sub = import_parser.add_subparsers(dest="import_type", help="Import source type")

    # import local
    p = import_sub.add_parser("local", help="Import a local PDF file")
    p.add_argument("path", help="Path to PDF file")
    p.add_argument("--ai", action="store_true", help="Use AI for metadata extraction")
    p.set_defaults(func=cmd_import_local)

    # import arxiv
    p = import_sub.add_parser("arxiv", help="Import from arxiv")
    p.add_argument("arxiv_id", help="Arxiv ID or URL")
    p.set_defaults(func=cmd_import_arxiv)

    # import url
    p = import_sub.add_parser("url", help="Import from URL")
    p.add_argument("url", help="URL to import")
    p.set_defaults(func=cmd_import_url)

    # import batch
    p = import_sub.add_parser("batch", help="Import all PDFs from a folder")
    p.add_argument("folder", help="Path to folder")
    p.add_argument("--ai", action="store_true", help="Use AI for metadata extraction")
    p.set_defaults(func=cmd_import_batch)

    # import emails
    p = import_sub.add_parser("emails", help="Parse email text and import URLs")
    p.add_argument("path", help="Path to email text file or raw text")
    p.set_defaults(func=cmd_import_emails)

    # --- list ---
    p = subparsers.add_parser("list", help="List papers")
    p.add_argument("--tag", help="Filter by tag")
    p.add_argument("--topic", help="Filter by topic")
    p.set_defaults(func=cmd_list)

    # --- search ---
    p = subparsers.add_parser("search", help="Search papers")
    p.add_argument("query", help="Search query")
    p.set_defaults(func=cmd_search)

    # --- show ---
    p = subparsers.add_parser("show", help="Show paper details")
    p.add_argument("paper_id", help="Paper ID")
    p.set_defaults(func=cmd_show)

    # --- tags ---
    p = subparsers.add_parser("tags", help="List all tags")
    p.set_defaults(func=cmd_tags)

    # --- collections ---
    p = subparsers.add_parser("collections", help="List collections")
    p.set_defaults(func=cmd_collections)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "import" and not args.import_type:
        import_parser.print_help()
        sys.exit(1)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
