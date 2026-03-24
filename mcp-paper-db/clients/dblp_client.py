"""DBLP API client — extracted from conf-papers/scripts/search_conf_papers.py."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

DBLP_API_URL = "https://dblp.org/search/publ/api"

# DBLP toc key mapping
DBLP_VENUES = {
    "CVPR": {"toc": "conf/cvpr", "toc_name": "cvpr{year}"},
    "ICCV": {"toc": "conf/iccv", "toc_name": "iccv{year}"},
    "ECCV": {"toc": "conf/eccv", "toc_name": None, "venue_query": "ECCV"},
    "ICLR": {"toc": "conf/iclr", "toc_name": "iclr{year}"},
    "AAAI": {"toc": "conf/aaai", "toc_name": "aaai{year}"},
    "NeurIPS": {"toc": "conf/nips", "toc_name": "neurips{year}"},
    "ICML": {"toc": "conf/icml", "toc_name": "icml{year}"},
}

# Conference → arXiv category mapping
VENUE_TO_CATEGORIES = {
    "CVPR": ["cs.CV"],
    "ICCV": ["cs.CV"],
    "ECCV": ["cs.CV"],
    "ICLR": ["cs.LG", "cs.AI"],
    "ICML": ["cs.LG"],
    "NeurIPS": ["cs.LG", "cs.AI", "cs.CL"],
    "AAAI": ["cs.AI"],
}


def search_dblp_conference(
    venue_key: str,
    year: int,
    max_results: int = 1000,
    max_retries: int = 3,
) -> list[dict]:
    """Search DBLP for papers from a specific conference and year.

    Args:
        venue_key: Conference name (e.g. "CVPR")
        year: Conference year
        max_results: Maximum papers to fetch
        max_retries: Retry count per request

    Returns:
        List of paper dicts with keys: title, authors, dblp_url, year,
        conference, doi, venue, source.
    """
    venue_info = DBLP_VENUES.get(venue_key)
    if not venue_info:
        logger.warning("[DBLP] Unknown venue: %s", venue_key)
        return []

    # Build query list: prefer toc format, fallback to venue+year
    queries = []
    toc_name = venue_info.get("toc_name")
    if toc_name:
        toc_path = venue_info["toc"]
        queries.append(f"toc:db/{toc_path}/{toc_name.format(year=year)}.bht:")
    venue_query = venue_info.get("venue_query", venue_key)
    queries.append(f"venue:{venue_query} year:{year}")

    for query_str in queries:
        papers: list[dict] = []
        hits_fetched = 0
        batch_size = min(max_results, 1000)
        query_failed = False

        while hits_fetched < max_results:
            params = {
                "q": query_str,
                "format": "json",
                "h": batch_size,
                "f": hits_fetched,
            }
            url = f"{DBLP_API_URL}?{urllib.parse.urlencode(params)}"
            logger.info("[DBLP] %s %d offset=%d query=%s", venue_key, year, hits_fetched, query_str[:60])

            for attempt in range(max_retries):
                try:
                    if HAS_REQUESTS:
                        resp = requests.get(url, headers={"User-Agent": "PaperDB-MCP/1.0"}, timeout=60)
                        resp.raise_for_status()
                        data = resp.json()
                    else:
                        req = urllib.request.Request(url, headers={"User-Agent": "PaperDB-MCP/1.0"})
                        with urllib.request.urlopen(req, timeout=60) as response:
                            data = json.loads(response.read().decode("utf-8"))

                    result = data.get("result", {})
                    hits = result.get("hits", {})
                    total = int(hits.get("@total", 0))
                    hit_list = hits.get("hit", [])

                    if not hit_list:
                        if papers:
                            return papers
                        query_failed = True
                        break

                    for hit in hit_list:
                        info = hit.get("info", {})
                        title = info.get("title", "").rstrip(".")
                        if not title:
                            continue

                        authors_info = info.get("authors", {}).get("author", [])
                        if isinstance(authors_info, dict):
                            authors_info = [authors_info]
                        authors = [a.get("text", "") for a in authors_info if a.get("text")]

                        papers.append({
                            "title": title,
                            "authors": authors,
                            "dblp_url": info.get("url", ""),
                            "year": int(info.get("year", year)),
                            "conference": venue_key,
                            "doi": info.get("doi", ""),
                            "venue": info.get("venue", venue_key),
                            "source": "dblp",
                        })

                    hits_fetched += len(hit_list)
                    if hits_fetched >= total or hits_fetched >= max_results:
                        break
                    time.sleep(1)
                    break  # success

                except Exception as e:
                    logger.warning("[DBLP] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
                    if attempt < max_retries - 1:
                        time.sleep((2 ** attempt) * 3)
                    else:
                        query_failed = True

            if query_failed:
                break
            if hits_fetched >= max_results:
                break

        if papers:
            logger.info("[DBLP] %s %d: %d papers", venue_key, year, len(papers))
            return papers

    logger.warning("[DBLP] %s %d: no papers found", venue_key, year)
    return []


def search_all_conferences(
    year: int,
    venues: Optional[list[str]] = None,
    max_per_venue: int = 1000,
) -> list[dict]:
    """Search papers across multiple conferences, deduplicated.

    Args:
        year: Conference year
        venues: Conference names (defaults to all known venues)
        max_per_venue: Max papers per venue

    Returns:
        Deduplicated list of paper dicts.
    """
    if venues is None:
        venues = list(DBLP_VENUES.keys())

    # Validate venue names
    name_map = {k.upper(): k for k in DBLP_VENUES}
    valid = [name_map[v.upper()] for v in venues if v.upper() in name_map]

    all_papers: list[dict] = []
    seen_titles: set[str] = set()

    for venue in valid:
        papers = search_dblp_conference(venue, year, max_results=max_per_venue)
        for p in papers:
            norm = re.sub(r"[^a-z0-9\s]", "", p["title"].lower()).strip()
            if norm not in seen_titles:
                seen_titles.add(norm)
                all_papers.append(p)
        time.sleep(1)

    logger.info("[DBLP] Total unique across %d venues: %d", len(valid), len(all_papers))
    return all_papers
