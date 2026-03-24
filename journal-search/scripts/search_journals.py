#!/usr/bin/env python3
"""
Journal paper search script using OpenAlex API.
Searches for papers by topic, filters by journal rank and citations,
and reports open access status.

OpenAlex API: https://docs.openalex.org/
Free, no API key required (polite pool with email in User-Agent).
"""

import json
import os
import re
import sys
import time
import logging
import argparse
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# OpenAlex API base
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_SOURCES_URL = "https://api.openalex.org/sources"

# Polite pool email (gets higher rate limits)
USER_EMAIL = "evil-read-arxiv@example.com"


def search_openalex(
    query: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    min_citations: int = 0,
    journal_only: bool = True,
    open_access_only: bool = False,
    max_results: int = 50,
) -> List[Dict]:
    """
    Search OpenAlex for journal papers.

    Args:
        query: Search query (topic, keywords)
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        min_citations: Minimum citation count filter
        journal_only: Only return journal articles (not conference papers)
        open_access_only: Only return open access papers
        max_results: Maximum results to return

    Returns:
        List of paper dicts
    """
    params = {
        "search": query,
        "per_page": min(max_results, 200),
        "sort": "cited_by_count:desc",
        "mailto": USER_EMAIL,
    }

    # Build filter string
    filters = []
    if from_date:
        filters.append(f"from_publication_date:{from_date}")
    if to_date:
        filters.append(f"to_publication_date:{to_date}")
    if min_citations > 0:
        filters.append(f"cited_by_count:>{min_citations}")
    if journal_only:
        filters.append("type:article")
    if open_access_only:
        filters.append("is_oa:true")

    if filters:
        params["filter"] = ",".join(filters)

    url = f"{OPENALEX_WORKS_URL}?{urllib.parse.urlencode(params)}"
    logger.info("[OpenAlex] Searching: %s", query)
    logger.info("[OpenAlex] URL: %s", url[:200])

    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"EvilReadArxiv/1.0 (mailto:{USER_EMAIL})"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("[OpenAlex] Search failed: %s", e)
        return []

    results = data.get("results", [])
    logger.info("[OpenAlex] Found %d results (total: %s)", len(results), data.get("meta", {}).get("count", "?"))

    papers = []
    for work in results:
        paper = parse_openalex_work(work)
        if paper:
            papers.append(paper)

    return papers


def parse_openalex_work(work: Dict) -> Optional[Dict]:
    """Parse an OpenAlex work into our paper format."""
    title = work.get("title", "")
    if not title:
        return None

    # Authors
    authors = []
    for authorship in work.get("authorships", []):
        author = authorship.get("author", {})
        name = author.get("display_name", "")
        if name:
            authors.append(name)

    # Source (journal) info
    source_info = {}
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    if source:
        source_info = {
            "journal_name": source.get("display_name", ""),
            "journal_issn": source.get("issn_l", ""),
            "journal_type": source.get("type", ""),
            "journal_id": source.get("id", ""),
        }

    # Open access info
    oa_info = work.get("open_access", {})
    is_oa = oa_info.get("is_oa", False)
    oa_status = oa_info.get("oa_status", "closed")
    oa_url = oa_info.get("oa_url", "")

    # Best open access URL
    best_oa_location = work.get("best_oa_location") or {}
    pdf_url = best_oa_location.get("pdf_url", "")
    landing_url = best_oa_location.get("landing_page_url", "")

    # IDs
    doi = work.get("doi", "")
    openalex_id = work.get("id", "")

    # Extract arXiv ID if available
    arxiv_id = ""
    for location in work.get("locations", []):
        loc_source = location.get("source") or {}
        if loc_source.get("display_name") == "arXiv":
            landing = location.get("landing_page_url", "")
            m = re.search(r"(\d{4}\.\d+)", landing)
            if m:
                arxiv_id = m.group(1)
                break

    # Abstract
    abstract = ""
    abstract_index = work.get("abstract_inverted_index")
    if abstract_index:
        # Reconstruct abstract from inverted index
        word_positions = []
        for word, positions in abstract_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        abstract = " ".join(w for _, w in word_positions)

    # Citation info
    cited_by_count = work.get("cited_by_count", 0)

    # Publication date
    pub_date = work.get("publication_date", "")

    # Concepts/topics
    concepts = []
    for concept in work.get("concepts", []):
        if concept.get("score", 0) > 0.3:
            concepts.append(concept.get("display_name", ""))

    # Determine access status
    if is_oa and pdf_url:
        access_status = "open_access_pdf"
        access_message = "Full PDF available (Open Access)"
    elif is_oa and oa_url:
        access_status = "open_access_html"
        access_message = "Open Access (HTML/landing page)"
    elif arxiv_id:
        access_status = "arxiv_preprint"
        access_message = f"arXiv preprint available: {arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    elif doi:
        access_status = "paywalled"
        access_message = f"Paywalled - you may need institutional access. DOI: {doi}"
    else:
        access_status = "unknown"
        access_message = "Access status unknown"

    paper = {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "publication_date": pub_date,
        "cited_by_count": cited_by_count,
        "doi": doi,
        "openalex_id": openalex_id,
        "arxiv_id": arxiv_id,
        "concepts": concepts[:5],
        # Source/journal
        **source_info,
        # Access
        "is_open_access": is_oa,
        "oa_status": oa_status,
        "access_status": access_status,
        "access_message": access_message,
        "pdf_url": pdf_url,
        "oa_url": oa_url or landing_url,
        "landing_url": landing_url or (f"https://doi.org/{doi}" if doi else ""),
    }

    return paper


def get_journal_info(journal_id: str) -> Optional[Dict]:
    """Get journal details from OpenAlex."""
    if not journal_id:
        return None

    url = f"{journal_id}?mailto={USER_EMAIL}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"EvilReadArxiv/1.0 (mailto:{USER_EMAIL})"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("[OpenAlex] Failed to get journal info: %s", e)
        return None

    return {
        "name": data.get("display_name", ""),
        "issn": data.get("issn_l", ""),
        "type": data.get("type", ""),
        "works_count": data.get("works_count", 0),
        "cited_by_count": data.get("cited_by_count", 0),
        "h_index": data.get("summary_stats", {}).get("h_index", 0),
        "i10_index": data.get("summary_stats", {}).get("i10_index", 0),
        "2yr_mean_citedness": data.get("summary_stats", {}).get("2yr_mean_citedness", 0),
        "is_oa": data.get("is_oa", False),
    }


def search_by_cited_papers(
    paper_openalex_id: str,
    direction: str = "references",
    max_results: int = 20,
) -> List[Dict]:
    """
    Search papers that cite or are cited by a given paper.

    Args:
        paper_openalex_id: OpenAlex ID of the paper
        direction: "references" (papers this one cites) or "cited_by" (papers citing this one)
        max_results: Maximum results

    Returns:
        List of papers
    """
    # Extract the short ID
    short_id = paper_openalex_id.replace("https://openalex.org/", "")

    if direction == "cited_by":
        filter_str = f"cites:{short_id}"
    else:
        filter_str = f"cited_by:{short_id}"

    params = {
        "filter": filter_str,
        "per_page": min(max_results, 200),
        "sort": "cited_by_count:desc",
        "mailto": USER_EMAIL,
    }

    url = f"{OPENALEX_WORKS_URL}?{urllib.parse.urlencode(params)}"
    logger.info("[OpenAlex] Searching %s for %s", direction, short_id)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"EvilReadArxiv/1.0 (mailto:{USER_EMAIL})"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("[OpenAlex] Citation search failed: %s", e)
        return []

    papers = []
    for work in data.get("results", []):
        paper = parse_openalex_work(work)
        if paper:
            papers.append(paper)

    return papers


def score_journal_paper(paper: Dict, query_keywords: List[str]) -> float:
    """
    Score a journal paper based on citations, journal quality, and relevance.

    Returns:
        Score 0-10
    """
    score = 0.0

    # Citation score (0-4 points)
    citations = paper.get("cited_by_count", 0)
    if citations >= 100:
        score += 4.0
    elif citations >= 50:
        score += 3.0
    elif citations >= 20:
        score += 2.5
    elif citations >= 10:
        score += 2.0
    elif citations >= 5:
        score += 1.5
    elif citations > 0:
        score += 1.0

    # Journal quality proxy - using h_index from 2yr_mean_citedness (0-3 points)
    mean_citedness = paper.get("2yr_mean_citedness", 0)
    if mean_citedness >= 5:
        score += 3.0
    elif mean_citedness >= 3:
        score += 2.0
    elif mean_citedness >= 1:
        score += 1.0

    # Relevance - keyword matching in title and abstract (0-3 points)
    title_lower = paper.get("title", "").lower()
    abstract_lower = paper.get("abstract", "").lower()
    matched = 0
    for kw in query_keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            matched += 2
        elif kw_lower in abstract_lower:
            matched += 1
    score += min(matched * 0.5, 3.0)

    return round(min(score, 10.0), 2)


def main():
    parser = argparse.ArgumentParser(description="Search journal papers via OpenAlex")
    parser.add_argument("--query", type=str, required=True, help="Search query")
    parser.add_argument("--from-date", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--min-citations", type=int, default=0, help="Minimum citation count")
    parser.add_argument("--include-conferences", action="store_true", help="Include conference papers")
    parser.add_argument("--open-access-only", action="store_true", help="Only open access papers")
    parser.add_argument("--max-results", type=int, default=50, help="Max results")
    parser.add_argument("--output", type=str, default="journal_papers.json", help="Output JSON file")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    papers = search_openalex(
        query=args.query,
        from_date=args.from_date,
        to_date=args.to_date,
        min_citations=args.min_citations,
        journal_only=not args.include_conferences,
        open_access_only=args.open_access_only,
        max_results=args.max_results,
    )

    # Score papers
    query_keywords = args.query.split()
    for p in papers:
        p["score"] = score_journal_paper(p, query_keywords)

    papers.sort(key=lambda x: x["score"], reverse=True)

    # Summary stats
    oa_count = sum(1 for p in papers if p["is_open_access"])
    arxiv_count = sum(1 for p in papers if p["arxiv_id"])
    paywalled_count = sum(1 for p in papers if p["access_status"] == "paywalled")

    output = {
        "query": args.query,
        "total_results": len(papers),
        "open_access": oa_count,
        "arxiv_preprint": arxiv_count,
        "paywalled": paywalled_count,
        "papers": papers,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("Results saved to: %s", args.output)
    logger.info("Total: %d | Open Access: %d | arXiv: %d | Paywalled: %d",
                len(papers), oa_count, arxiv_count, paywalled_count)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
