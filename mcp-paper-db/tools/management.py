"""MCP management tools — get_paper, upsert_paper, record_event,
sync_vault_notes, add_citation."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ..db import PaperDatabase
from ..config import Config
from ..models import Paper, Citation, ReadingEvent

logger = logging.getLogger(__name__)


def get_paper_impl(
    db: PaperDatabase,
    paper_id: Optional[int] = None,
    arxiv_id: Optional[str] = None,
) -> Optional[dict]:
    """Get full details for one paper."""
    paper = db.get_paper(paper_id=paper_id, arxiv_id=arxiv_id)
    if not paper:
        return None

    result = asdict(paper)
    result["keywords"] = db.get_keywords(paper.id)
    return result


def upsert_paper_impl(
    db: PaperDatabase,
    title: str,
    arxiv_id: Optional[str] = None,
    doi: Optional[str] = None,
    abstract: Optional[str] = None,
    authors: Optional[list[str]] = None,
    published_date: Optional[str] = None,
    categories: Optional[list[str]] = None,
    conference: Optional[str] = None,
    conference_year: Optional[int] = None,
    domain: Optional[str] = None,
    source: str = "manual",
    note_path: Optional[str] = None,
    has_note: bool = False,
) -> dict:
    """Add or update a paper in the database."""
    paper = Paper(
        title=title,
        arxiv_id=arxiv_id,
        doi=doi,
        abstract=abstract,
        authors=authors or [],
        published_date=published_date,
        categories=categories or [],
        conference=conference,
        conference_year=conference_year,
        domain=domain,
        source=source,
        note_path=note_path,
        has_note=has_note,
    )
    paper.normalize_title()
    paper = db.upsert_paper(paper)
    return {"id": paper.id, "title": paper.title, "action": "upserted"}


def record_event_impl(
    db: PaperDatabase,
    paper_id: int,
    event_type: str,
    context: Optional[str] = None,
    recommendation_rank: Optional[int] = None,
) -> dict:
    """Log a reading history event."""
    event = ReadingEvent(
        paper_id=paper_id,
        event_type=event_type,
        context=context,
        recommendation_rank=recommendation_rank,
    )
    event = db.record_event(event)
    return {"id": event.id, "event_type": event_type, "paper_id": paper_id}


def add_citation_impl(
    db: PaperDatabase,
    source_paper_id: int,
    target_paper_id: int,
    relationship_type: str = "related",
    weight: float = 0.5,
) -> dict:
    """Record a paper-to-paper relationship."""
    citation = Citation(
        source_paper_id=source_paper_id,
        target_paper_id=target_paper_id,
        relationship_type=relationship_type,
        weight=weight,
    )
    citation = db.add_citation(citation)
    return {
        "id": citation.id,
        "source": source_paper_id,
        "target": target_paper_id,
        "type": relationship_type,
    }


def _title_to_note_filename(title: str) -> str:
    """Convert paper title to Obsidian note filename (same as generate_note.py)."""
    return re.sub(r'[ /\\:*?"<>|]+', '_', title).strip('_')


def sync_vault_notes_impl(
    db: PaperDatabase,
    config: Config,
) -> dict:
    """Scan Obsidian vault for paper notes and match them to DB papers.

    Walks the papers directory, tries to match each .md file to a paper
    in the database by normalized title, and updates has_note/note_path.
    """
    papers_path = config.papers_path
    if not papers_path.exists():
        return {"error": f"Papers directory not found: {papers_path}", "matched": 0}

    matched = 0
    scanned = 0
    unmatched: list[str] = []

    for md_file in papers_path.rglob("*.md"):
        scanned += 1
        # Extract title from filename (reverse of _title_to_note_filename)
        stem = md_file.stem
        title_guess = stem.replace('_', ' ').strip()
        title_normalized = title_guess.lower()

        # Try to find in DB
        papers = db.search_papers(query=title_guess, limit=5)
        found = False

        for paper in papers:
            # Check fuzzy match on normalized title
            if paper.title_normalized == title_normalized or \
               _title_to_note_filename(paper.title) == stem:
                paper.has_note = True
                paper.note_path = str(md_file.relative_to(config.vault_path))
                paper.note_filename = stem
                db.upsert_paper(paper)
                matched += 1
                found = True
                break

        if not found:
            unmatched.append(stem)

    return {
        "scanned": scanned,
        "matched": matched,
        "unmatched_count": len(unmatched),
        "unmatched_sample": unmatched[:10],
    }
