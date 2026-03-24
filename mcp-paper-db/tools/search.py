"""MCP search tools — search_papers, search_arxiv, search_semantic_scholar,
search_conference_papers, enrich_papers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..db import PaperDatabase
from ..config import Config
from ..models import Paper, SearchRun
from ..clients import arxiv_client, s2_client, dblp_client

logger = logging.getLogger(__name__)


def _raw_to_paper(raw: dict, source: str) -> Paper:
    """Convert a raw API result dict to a Paper model."""
    pub_date = raw.get("published_date")
    if isinstance(pub_date, datetime):
        pub_date = pub_date.strftime("%Y-%m-%d")

    p = Paper(
        arxiv_id=raw.get("arxiv_id"),
        s2_id=raw.get("s2_id"),
        doi=raw.get("doi"),
        dblp_url=raw.get("dblp_url"),
        title=raw.get("title", ""),
        abstract=raw.get("abstract") or raw.get("summary"),
        authors=raw.get("authors", []),
        published_date=pub_date,
        categories=raw.get("categories", []),
        conference=raw.get("conference"),
        conference_year=raw.get("year"),
        pdf_url=raw.get("pdf_url"),
        arxiv_url=raw.get("arxiv_url") or raw.get("url"),
        source=source,
        citation_count=raw.get("citationCount", 0) or 0,
        influential_citation_count=raw.get("influentialCitationCount", 0) or 0,
    )
    p.normalize_title()
    return p


# ── MCP tool implementations ──


def search_papers_impl(
    db: PaperDatabase,
    query: Optional[str] = None,
    domain: Optional[str] = None,
    author: Optional[str] = None,
    conference: Optional[str] = None,
    has_note: Optional[bool] = None,
    min_score: Optional[float] = None,
    limit: int = 20,
) -> list[dict]:
    """Search the local paper database with structured filters."""
    papers = db.search_papers(
        query=query,
        domain=domain,
        author=author,
        conference=conference,
        has_note=has_note,
        min_score=min_score,
        limit=limit,
    )
    return [p.to_summary() for p in papers]


def search_arxiv_impl(
    db: PaperDatabase,
    config: Config,
    categories: Optional[list[str]] = None,
    query: Optional[str] = None,
    days: int = 30,
    max_results: int = 200,
) -> dict:
    """Search arXiv and store results in the database.

    Either searches by date range (using categories from config) or by query.
    """
    if categories is None:
        categories = config.all_categories

    if query:
        raw_papers = arxiv_client.search_arxiv_by_query(
            query=query, categories=categories, max_results=max_results
        )
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        raw_papers = arxiv_client.search_arxiv(
            categories=categories,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
        )

    # Store in DB
    stored = 0
    for raw in raw_papers:
        paper = _raw_to_paper(raw, source="arxiv")
        if paper.title:
            db.upsert_paper(paper)
            stored += 1

    # Record search run
    db.record_search_run(SearchRun(
        search_type="arxiv",
        query_params={"categories": categories, "query": query, "days": days},
        result_count=stored,
    ))

    return {
        "fetched": len(raw_papers),
        "stored": stored,
        "source": "arxiv",
    }


def search_semantic_scholar_impl(
    db: PaperDatabase,
    config: Config,
    query: Optional[str] = None,
    days: int = 365,
    top_k: int = 20,
) -> dict:
    """Search Semantic Scholar for hot papers and store in DB."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    if query:
        raw_papers = s2_client.search_hot_papers(
            query=query,
            start_date=start_date,
            end_date=end_date,
            top_k=top_k,
            api_key=config.semantic_scholar_api_key,
        )
    else:
        domain_kws = {
            name: d.keywords for name, d in config.research_domains.items()
        }
        raw_papers = s2_client.search_hot_papers_multi(
            categories=config.all_categories,
            start_date=start_date,
            end_date=end_date,
            top_k_per_query=top_k,
            api_key=config.semantic_scholar_api_key,
            domain_keywords=domain_kws,
        )

    stored = 0
    for raw in raw_papers:
        paper = _raw_to_paper(raw, source="s2")
        if paper.title:
            db.upsert_paper(paper)
            stored += 1

    db.record_search_run(SearchRun(
        search_type="semantic_scholar",
        query_params={"query": query, "days": days, "top_k": top_k},
        result_count=stored,
    ))

    return {
        "fetched": len(raw_papers),
        "stored": stored,
        "source": "semantic_scholar",
    }


def search_conference_papers_impl(
    db: PaperDatabase,
    config: Config,
    venues: Optional[list[str]] = None,
    year: Optional[int] = None,
    max_per_venue: int = 1000,
    enrich: bool = True,
) -> dict:
    """Search DBLP for conference papers, optionally enrich with S2, store in DB."""
    if year is None:
        year = datetime.now().year
    if venues is None:
        venues = list(dblp_client.DBLP_VENUES.keys())

    raw_papers = dblp_client.search_all_conferences(year, venues, max_per_venue)

    if enrich and raw_papers:
        raw_papers = s2_client.enrich_papers(
            raw_papers, api_key=config.semantic_scholar_api_key
        )

    stored = 0
    for raw in raw_papers:
        paper = _raw_to_paper(raw, source="dblp")
        if paper.title:
            db.upsert_paper(paper)
            stored += 1

    db.record_search_run(SearchRun(
        search_type="conference",
        query_params={"venues": venues, "year": year, "enrich": enrich},
        result_count=stored,
    ))

    return {
        "fetched": len(raw_papers),
        "stored": stored,
        "source": "dblp",
        "year": year,
        "venues": venues,
    }


def enrich_papers_impl(
    db: PaperDatabase,
    config: Config,
    limit: int = 50,
) -> dict:
    """Enrich papers that are missing abstracts/citations from Semantic Scholar."""
    # Find papers without abstracts
    papers = db.search_papers(limit=limit)
    to_enrich = [p for p in papers if not p.abstract]

    if not to_enrich:
        return {"enriched": 0, "message": "No papers need enrichment"}

    raw_list = [{"title": p.title, "arxiv_id": p.arxiv_id} for p in to_enrich]
    enriched = s2_client.enrich_papers(raw_list, api_key=config.semantic_scholar_api_key)

    updated = 0
    for raw, original in zip(enriched, to_enrich):
        if raw.get("abstract"):
            original.abstract = raw["abstract"]
            original.citation_count = raw.get("citationCount", 0)
            original.influential_citation_count = raw.get("influentialCitationCount", 0)
            if raw.get("doi"):
                original.doi = raw["doi"]
            db.upsert_paper(original)
            updated += 1

    return {"enriched": updated, "total_checked": len(to_enrich)}
