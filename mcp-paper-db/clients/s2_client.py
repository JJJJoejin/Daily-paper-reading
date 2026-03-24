"""Semantic Scholar API client — extracted from search_arxiv.py + search_conf_papers.py."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = "title,abstract,publicationDate,citationCount,influentialCitationCount,url,authors,externalIds"
S2_RATE_LIMIT_WAIT = 30
S2_CATEGORY_REQUEST_INTERVAL = 3

# Default arXiv category → keyword mapping for S2 queries
ARXIV_CATEGORY_KEYWORDS = {
    "cs.AI": "artificial intelligence",
    "cs.LG": "machine learning",
    "cs.CL": "computational linguistics natural language processing",
    "cs.CV": "computer vision",
    "cs.MM": "multimedia",
    "cs.MA": "multi-agent systems",
    "cs.RO": "robotics",
}


def _make_headers(api_key: Optional[str] = None) -> dict:
    headers = {"User-Agent": "PaperDB-MCP/1.0"}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _get_json(url: str, params: dict, headers: dict, timeout: int = 15) -> dict:
    """HTTP GET with requests or urllib fallback."""
    if HAS_REQUESTS:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    else:
        qs = urllib.parse.urlencode(params)
        full_url = f"{url}?{qs}"
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def title_similarity(a: str, b: str) -> float:
    """Jaccard word-level similarity between two titles."""
    def normalize(s: str) -> str:
        return re.sub(r"[^a-z0-9\s]", "", s.lower()).strip()

    words_a = set(normalize(a).split())
    words_b = set(normalize(b).split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


# ── Hot paper search (from search_arxiv.py) ──


def search_hot_papers(
    query: str,
    start_date: datetime,
    end_date: datetime,
    top_k: int = 20,
    api_key: Optional[str] = None,
    max_retries: int = 3,
) -> list[dict]:
    """Search S2 for high-impact papers in a date range.

    Returns papers sorted by influential citation count.
    """
    date_range = f"{start_date.strftime('%Y-%m-%d')}:{end_date.strftime('%Y-%m-%d')}"
    params = {
        "query": query,
        "publicationDateOrYear": date_range,
        "limit": 100,
        "fields": S2_FIELDS,
    }
    headers = _make_headers(api_key)

    logger.info("[S2] Searching hot papers: '%s' (%s to %s)", query, start_date.date(), end_date.date())

    for attempt in range(max_retries):
        try:
            data = _get_json(S2_API_URL, params, headers)
            papers = data.get("data", [])
            if not papers:
                return []

            valid = []
            for p in papers:
                if not p.get("title") or not p.get("abstract"):
                    continue
                p["influentialCitationCount"] = p.get("influentialCitationCount") or 0
                p["citationCount"] = p.get("citationCount") or 0
                p["source"] = "s2"
                # Extract arXiv ID
                ext_ids = p.get("externalIds") or {}
                p["arxiv_id"] = ext_ids.get("ArXiv")
                p["doi"] = ext_ids.get("DOI")
                # Flatten authors
                p["authors"] = [a.get("name", "") for a in (p.get("authors") or []) if a.get("name")]
                # Rename publicationDate
                p["published_date"] = p.get("publicationDate")
                valid.append(p)

            valid.sort(key=lambda x: x["influentialCitationCount"], reverse=True)
            logger.info("[S2] %d valid, returning top %d", len(valid), top_k)
            return valid[:top_k]

        except Exception as e:
            logger.warning("[S2] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            is_rate_limit = "429" in str(e) or "Too Many Requests" in str(e)
            if attempt < max_retries - 1:
                wait = S2_RATE_LIMIT_WAIT if is_rate_limit else (2 ** attempt) * 2
                time.sleep(wait)
            else:
                return []

    return []


def search_hot_papers_multi(
    categories: list[str],
    start_date: datetime,
    end_date: datetime,
    top_k_per_query: int = 5,
    api_key: Optional[str] = None,
    domain_keywords: Optional[dict[str, list[str]]] = None,
) -> list[dict]:
    """Search hot papers across multiple categories/domains.

    Args:
        categories: arXiv categories
        start_date: Window start
        end_date: Window end
        top_k_per_query: Papers per query
        api_key: Optional S2 API key
        domain_keywords: {domain_name: [keywords]} — if given, uses first 3 keywords per domain
    """
    queries: list[str] = []
    if domain_keywords:
        for kws in domain_keywords.values():
            if kws:
                queries.append(" ".join(kws[:3]))
    if not queries:
        queries = [ARXIV_CATEGORY_KEYWORDS.get(cat, cat) for cat in categories]

    # Deduplicate
    seen = set()
    unique_queries = []
    for q in queries:
        ql = q.lower()
        if ql not in seen:
            seen.add(ql)
            unique_queries.append(q)

    all_papers: list[dict] = []
    seen_ids: set[str] = set()

    for query in unique_queries:
        papers = search_hot_papers(query, start_date, end_date, top_k_per_query, api_key)
        for p in papers:
            aid = p.get("arxiv_id")
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                all_papers.append(p)
            elif not aid:
                all_papers.append(p)
        time.sleep(S2_CATEGORY_REQUEST_INTERVAL)

    all_papers.sort(key=lambda x: x.get("influentialCitationCount", 0), reverse=True)
    return all_papers


# ── Enrichment (from search_conf_papers.py) ──


def enrich_papers(
    papers: list[dict],
    api_key: Optional[str] = None,
    max_retries: int = 3,
) -> list[dict]:
    """Enrich papers with abstracts/citations from S2 by title matching.

    Modifies papers in-place and returns the list.
    """
    if not HAS_REQUESTS:
        logger.warning("[S2] requests library not available, skipping enrichment")
        for p in papers:
            p.setdefault("abstract", None)
            p.setdefault("citationCount", 0)
            p.setdefault("influentialCitationCount", 0)
        return papers

    headers = _make_headers(api_key)
    enriched = 0

    for i, paper in enumerate(papers):
        title = paper.get("title", "")
        if not title:
            continue

        if (i + 1) % 10 == 0:
            logger.info("[S2] Enrichment progress: %d/%d (enriched: %d)", i + 1, len(papers), enriched)

        params = {"query": title, "limit": 3, "fields": S2_FIELDS}
        matched = False

        for attempt in range(max_retries):
            try:
                if HAS_REQUESTS:
                    resp = requests.get(S2_API_URL, params=params, headers=headers, timeout=15)
                    if resp.status_code == 429:
                        logger.warning("[S2] Rate limit, waiting %ds", S2_RATE_LIMIT_WAIT)
                        time.sleep(S2_RATE_LIMIT_WAIT)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                else:
                    data = _get_json(S2_API_URL, params, headers)

                results = data.get("data", [])
                if not results:
                    break

                best, best_sim = None, 0.0
                for r in results:
                    sim = title_similarity(title, r.get("title", ""))
                    if sim > best_sim:
                        best_sim = sim
                        best = r

                if best and best_sim >= 0.6:
                    paper["abstract"] = best.get("abstract")
                    paper["citationCount"] = best.get("citationCount") or 0
                    paper["influentialCitationCount"] = best.get("influentialCitationCount") or 0
                    paper["s2_url"] = best.get("url", "")
                    ext_ids = best.get("externalIds") or {}
                    paper["arxiv_id"] = ext_ids.get("ArXiv")
                    paper["doi"] = paper.get("doi") or ext_ids.get("DOI", "")
                    if not paper.get("authors") and best.get("authors"):
                        paper["authors"] = [a["name"] for a in best["authors"] if a.get("name")]
                    paper["published_date"] = best.get("publicationDate")
                    enriched += 1
                    matched = True
                break

            except Exception as e:
                is_rate_limit = "429" in str(e)
                if attempt < max_retries - 1:
                    time.sleep(S2_RATE_LIMIT_WAIT if is_rate_limit else 2 ** attempt)
                else:
                    logger.debug("[S2] Failed to enrich: %s", title[:50])

        if not matched:
            paper.setdefault("abstract", None)
            paper.setdefault("citationCount", 0)
            paper.setdefault("influentialCitationCount", 0)

        time.sleep(1.0)  # S2 free tier ~1 req/sec

    logger.info("[S2] Enrichment done: %d/%d", enriched, len(papers))
    return papers
