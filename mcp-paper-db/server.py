"""MCP Paper Database Server — stdio transport entry point."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so we can import from mcp-paper-db
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Make mcp-paper-db importable as mcp_paper_db
import importlib
_pkg_dir = Path(__file__).parent
if "mcp_paper_db" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "mcp_paper_db", _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["mcp_paper_db"] = _mod

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .db import PaperDatabase
from .tools import search as search_tools
from .tools import scoring as scoring_tools
from .tools import management as mgmt_tools
from .tools import analytics as analytics_tools

# Load config and initialize database
config = load_config()
db = PaperDatabase(config.db_path)
db.migrate()

# Create the MCP server
mcp = FastMCP(
    "paper-db",
    instructions=(
        "Paper database server for searching, storing, and scoring academic papers. "
        "Provides structured queries over a SQLite database of paper metadata, "
        "reading history, and recommendation scores."
    ),
)


# ── Core tools ──


@mcp.tool()
def ping() -> str:
    """Health check — returns server status and paper count."""
    count = db.count_papers()
    return f"paper-db OK — {count} papers in database"


@mcp.tool()
def get_stats() -> dict:
    """Get paper database statistics: counts by domain, source, and recent activity."""
    return db.get_stats()


# ── Search tools ──


@mcp.tool()
def search_papers(
    query: str = "",
    domain: str = "",
    author: str = "",
    conference: str = "",
    has_note: bool | None = None,
    min_score: float | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search the local paper database with structured filters.

    All filters are optional and combined with AND logic.
    Returns papers sorted by recommendation score.
    """
    return search_tools.search_papers_impl(
        db,
        query=query or None,
        domain=domain or None,
        author=author or None,
        conference=conference or None,
        has_note=has_note,
        min_score=min_score,
        limit=limit,
    )


@mcp.tool()
def search_arxiv(
    query: str = "",
    categories: str = "",
    days: int = 30,
    max_results: int = 200,
) -> dict:
    """Search arXiv for papers and store results in the database.

    Args:
        query: Free-text search query. If empty, searches by date range.
        categories: Comma-separated arXiv categories (e.g. "cs.AI,cs.CL").
                   If empty, uses all categories from config.
        days: Number of days to look back (for date-range search).
        max_results: Maximum papers to fetch.

    Returns:
        Summary of fetched and stored paper counts.
    """
    cats = [c.strip() for c in categories.split(",") if c.strip()] or None
    return search_tools.search_arxiv_impl(
        db, config,
        categories=cats,
        query=query or None,
        days=days,
        max_results=max_results,
    )


@mcp.tool()
def search_semantic_scholar(
    query: str = "",
    days: int = 365,
    top_k: int = 20,
) -> dict:
    """Search Semantic Scholar for high-impact papers and store in the database.

    Args:
        query: Search query. If empty, searches using keywords from all research domains.
        days: Number of days to look back.
        top_k: Number of top papers to return per query.

    Returns:
        Summary of fetched and stored paper counts.
    """
    return search_tools.search_semantic_scholar_impl(
        db, config,
        query=query or None,
        days=days,
        top_k=top_k,
    )


@mcp.tool()
def search_conference_papers(
    venues: str = "",
    year: int = 0,
    max_per_venue: int = 1000,
    enrich: bool = True,
) -> dict:
    """Search DBLP for conference papers, optionally enrich with Semantic Scholar.

    Args:
        venues: Comma-separated conference names (e.g. "CVPR,ICLR").
               If empty, searches all known venues.
        year: Conference year (defaults to current year).
        max_per_venue: Max papers per venue from DBLP.
        enrich: Whether to enrich with S2 abstracts/citations.

    Returns:
        Summary of fetched and stored paper counts.
    """
    venue_list = [v.strip() for v in venues.split(",") if v.strip()] or None
    return search_tools.search_conference_papers_impl(
        db, config,
        venues=venue_list,
        year=year or None,
        max_per_venue=max_per_venue,
        enrich=enrich,
    )


@mcp.tool()
def enrich_papers(limit: int = 50) -> dict:
    """Backfill abstracts and citations from Semantic Scholar for papers missing them.

    Args:
        limit: Maximum papers to enrich in one call.

    Returns:
        Number of papers enriched.
    """
    return search_tools.enrich_papers_impl(db, config, limit=limit)


# ── Scoring tools ──


@mcp.tool()
def score_papers(domain: str = "", limit: int = 100) -> dict:
    """Re-score papers against current research interests configuration.

    Args:
        domain: Optional domain filter — only rescore papers in this domain.
        limit: Maximum papers to process.

    Returns:
        Number of papers scored.
    """
    return scoring_tools.score_papers_impl(
        db, config, domain=domain or None, limit=limit
    )


@mcp.tool()
def get_recommendations(
    domain: str = "",
    min_score: float = 0.0,
    exclude_analyzed: bool = True,
    limit: int = 10,
) -> list[dict]:
    """Get top recommended papers, sorted by recommendation score.

    Args:
        domain: Optional domain filter.
        min_score: Minimum recommendation score threshold.
        exclude_analyzed: If true, exclude papers that already have notes.
        limit: Number of papers to return.

    Returns:
        List of paper summaries with scores.
    """
    has_note = False if exclude_analyzed else None
    return scoring_tools.get_recommendations_impl(
        db,
        domain=domain or None,
        min_score=min_score,
        has_note=has_note,
        limit=limit,
    )


# ── Management tools ──


@mcp.tool()
def get_paper(paper_id: int = 0, arxiv_id: str = "") -> dict:
    """Get full details for one paper by DB id or arXiv ID.

    Args:
        paper_id: Database paper ID.
        arxiv_id: arXiv paper ID (e.g. "2603.12345").

    Returns:
        Full paper details including keywords, or error if not found.
    """
    result = mgmt_tools.get_paper_impl(
        db, paper_id=paper_id or None, arxiv_id=arxiv_id or None
    )
    return result or {"error": "Paper not found"}


@mcp.tool()
def upsert_paper(
    title: str,
    arxiv_id: str = "",
    doi: str = "",
    abstract: str = "",
    authors: str = "",
    published_date: str = "",
    categories: str = "",
    conference: str = "",
    conference_year: int = 0,
    domain: str = "",
    source: str = "manual",
    note_path: str = "",
    has_note: bool = False,
) -> dict:
    """Add or update a paper in the database.

    Args:
        title: Paper title (required).
        arxiv_id: arXiv ID.
        doi: DOI.
        abstract: Paper abstract.
        authors: Comma-separated author names.
        published_date: ISO date string.
        categories: Comma-separated arXiv categories.
        conference: Conference name.
        conference_year: Conference year.
        domain: Research domain.
        source: Source ("arxiv", "s2", "dblp", "manual").
        note_path: Path to note in vault.
        has_note: Whether this paper has been analyzed.

    Returns:
        Paper ID and action taken.
    """
    author_list = [a.strip() for a in authors.split(",") if a.strip()] if authors else []
    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    return mgmt_tools.upsert_paper_impl(
        db,
        title=title,
        arxiv_id=arxiv_id or None,
        doi=doi or None,
        abstract=abstract or None,
        authors=author_list,
        published_date=published_date or None,
        categories=cat_list,
        conference=conference or None,
        conference_year=conference_year or None,
        domain=domain or None,
        source=source,
        note_path=note_path or None,
        has_note=has_note,
    )


@mcp.tool()
def record_event(
    paper_id: int,
    event_type: str,
    context: str = "",
    recommendation_rank: int = 0,
) -> dict:
    """Log a reading history event for a paper.

    Args:
        paper_id: Database paper ID.
        event_type: Event type ("recommended", "analyzed", "searched", "bookmarked").
        context: Optional context string.
        recommendation_rank: Optional rank in recommendation list.

    Returns:
        Event ID and details.
    """
    return mgmt_tools.record_event_impl(
        db,
        paper_id=paper_id,
        event_type=event_type,
        context=context or None,
        recommendation_rank=recommendation_rank or None,
    )


@mcp.tool()
def add_citation(
    source_paper_id: int,
    target_paper_id: int,
    relationship_type: str = "related",
    weight: float = 0.5,
) -> dict:
    """Record a paper-to-paper relationship (citation, extension, comparison).

    Args:
        source_paper_id: The citing/referencing paper ID.
        target_paper_id: The cited/referenced paper ID.
        relationship_type: "cites", "extends", "compares", or "related".
        weight: Relationship strength (0-1).

    Returns:
        Citation ID and details.
    """
    return mgmt_tools.add_citation_impl(
        db,
        source_paper_id=source_paper_id,
        target_paper_id=target_paper_id,
        relationship_type=relationship_type,
        weight=weight,
    )


@mcp.tool()
def sync_vault_notes() -> dict:
    """Scan Obsidian vault and match paper notes to database entries.

    Walks the papers directory, matches .md files to papers by title,
    and updates has_note/note_path fields.

    Returns:
        Summary of scanned, matched, and unmatched notes.
    """
    return mgmt_tools.sync_vault_notes_impl(db, config)


# ── Analytics tools ──


@mcp.tool()
def get_reading_history(
    event_type: str = "",
    days: int = 30,
    limit: int = 50,
) -> list[dict]:
    """Get reading history events with paper details.

    Args:
        event_type: Filter by event type ("recommended", "analyzed", etc.). Empty = all.
        days: Number of days to look back.
        limit: Maximum events to return.

    Returns:
        List of events with paper title and arXiv ID.
    """
    return analytics_tools.get_reading_history_impl(
        db, event_type=event_type or None, days=days, limit=limit
    )


@mcp.tool()
def find_duplicates() -> list[dict]:
    """Find papers with duplicate normalized titles in the database.

    Returns:
        List of duplicate groups with paper IDs.
    """
    return analytics_tools.find_duplicates_impl(db)


def main():
    """Run the MCP server on stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
