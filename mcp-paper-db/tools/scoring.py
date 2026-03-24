"""MCP scoring tools — score_papers, get_recommendations."""

from __future__ import annotations

import logging
from typing import Optional

from ..db import PaperDatabase
from ..config import Config
from ..models import Paper
from ..scoring_engine import score_paper

logger = logging.getLogger(__name__)


def score_papers_impl(
    db: PaperDatabase,
    config: Config,
    domain: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """Re-score papers against current research interests config.

    Args:
        db: Database instance
        config: Current config with research domains
        domain: Optional domain filter — only rescore papers in this domain
        limit: Max papers to process

    Returns:
        Summary of how many papers were scored.
    """
    # Build domains dict from config
    domains = {
        name: dc for name, dc in config.research_domains.items()
    }
    excluded = config.excluded_keywords

    papers = db.search_papers(domain=domain, limit=limit)
    scored = 0

    for paper in papers:
        result = score_paper(
            title=paper.title,
            abstract=paper.abstract or "",
            categories=paper.categories,
            published_date=paper.published_date,
            citation_count=paper.citation_count,
            influential_citation_count=paper.influential_citation_count,
            is_hot=paper.is_hot_paper,
            domains=domains,
            excluded_keywords=excluded,
        )

        paper.relevance_score = result["relevance_score"]
        paper.recency_score = result["recency_score"]
        paper.popularity_score = result["popularity_score"]
        paper.quality_score = result["quality_score"]
        paper.recommendation_score = result["recommendation_score"]
        paper.domain = result["domain"]
        paper.matched_keywords = result["matched_keywords"]

        db.upsert_paper(paper)

        # Store matched keywords
        for kw in result["matched_keywords"]:
            kw_type = "category" if kw.startswith("cs.") else "matched"
            db.add_keyword(paper.id, kw, kw_type)

        scored += 1

    return {"scored": scored, "domain_filter": domain}


def get_recommendations_impl(
    db: PaperDatabase,
    domain: Optional[str] = None,
    min_score: float = 0.0,
    has_note: Optional[bool] = None,
    limit: int = 10,
) -> list[dict]:
    """Get top-N recommended papers from the database.

    Args:
        db: Database instance
        domain: Optional domain filter
        min_score: Minimum recommendation score
        has_note: Filter by whether paper has been analyzed
        limit: Number of papers to return

    Returns:
        List of paper summaries sorted by recommendation score.
    """
    # Default: exclude already-analyzed papers
    if has_note is None:
        has_note = False

    papers = db.search_papers(
        domain=domain,
        min_score=min_score,
        has_note=has_note,
        limit=limit,
    )

    results = []
    for p in papers:
        summary = p.to_summary()
        summary["scores"] = {
            "relevance": p.relevance_score,
            "recency": p.recency_score,
            "popularity": p.popularity_score,
            "quality": p.quality_score,
            "recommendation": p.recommendation_score,
        }
        results.append(summary)

    return results
