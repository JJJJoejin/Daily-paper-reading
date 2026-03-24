"""arXiv API client — extracted from start-my-day/scripts/search_arxiv.py."""

from __future__ import annotations

import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def parse_arxiv_xml(xml_content: str) -> list[dict]:
    """Parse arXiv Atom XML into a list of paper dicts."""
    papers = []
    try:
        root = ET.fromstring(xml_content)
        for entry in root.findall("atom:entry", ARXIV_NS):
            paper: dict = {}

            id_elem = entry.find("atom:id", ARXIV_NS)
            if id_elem is not None:
                paper["id"] = id_elem.text
                match = re.search(r"arXiv:(\d+\.\d+)", paper["id"])
                if match:
                    paper["arxiv_id"] = match.group(1)
                else:
                    match = re.search(r"/(\d+\.\d+)", paper["id"])
                    if match:
                        paper["arxiv_id"] = match.group(1)

            title_elem = entry.find("atom:title", ARXIV_NS)
            if title_elem is not None:
                paper["title"] = title_elem.text.strip()

            summary_elem = entry.find("atom:summary", ARXIV_NS)
            if summary_elem is not None:
                paper["abstract"] = summary_elem.text.strip()

            authors = []
            for author in entry.findall("atom:author", ARXIV_NS):
                name_elem = author.find("atom:name", ARXIV_NS)
                if name_elem is not None:
                    authors.append(name_elem.text)
            paper["authors"] = authors

            published_elem = entry.find("atom:published", ARXIV_NS)
            if published_elem is not None:
                paper["published"] = published_elem.text
                try:
                    paper["published_date"] = datetime.fromisoformat(
                        published_elem.text.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    paper["published_date"] = None

            categories = []
            for category in entry.findall("atom:category", ARXIV_NS):
                term = category.get("term")
                if term:
                    categories.append(term)
            paper["categories"] = categories

            for link in entry.findall("atom:link", ARXIV_NS):
                if link.get("title") == "pdf":
                    paper["pdf_url"] = link.get("href")
                    break

            if "id" in paper:
                paper["arxiv_url"] = paper["id"]

            paper["source"] = "arxiv"
            papers.append(paper)

    except ET.ParseError as e:
        logger.error("Error parsing arXiv XML: %s", e)
        raise

    return papers


def search_arxiv(
    categories: list[str],
    start_date: datetime,
    end_date: datetime,
    max_results: int = 200,
    max_retries: int = 3,
) -> list[dict]:
    """Search arXiv API for papers in a date range.

    Args:
        categories: arXiv categories (e.g. ["cs.AI", "cs.LG"])
        start_date: Start of date window
        end_date: End of date window
        max_results: Max papers to return
        max_retries: Retry count on failure

    Returns:
        List of paper dicts with keys: arxiv_id, title, abstract, authors,
        published_date, categories, pdf_url, arxiv_url, source.
    """
    category_query = "+OR+".join([f"cat:{cat}" for cat in categories])
    date_query = (
        f"submittedDate:[{start_date.strftime('%Y%m%d')}0000"
        f"+TO+{end_date.strftime('%Y%m%d')}2359]"
    )
    full_query = f"({category_query})+AND+{date_query}"

    url = (
        f"https://export.arxiv.org/api/query?"
        f"search_query={full_query}&"
        f"max_results={max_results}&"
        f"sortBy=submittedDate&"
        f"sortOrder=descending"
    )

    logger.info("[arXiv] Searching %s to %s", start_date.date(), end_date.date())

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                xml_content = response.read().decode("utf-8")
                papers = parse_arxiv_xml(xml_content)
                logger.info("[arXiv] Found %d papers", len(papers))
                return papers
        except Exception as e:
            logger.warning("[arXiv] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
            else:
                logger.error("[arXiv] Failed after %d attempts", max_retries)
                return []

    return []


def search_arxiv_by_query(
    query: str,
    categories: Optional[list[str]] = None,
    max_results: int = 50,
    max_retries: int = 3,
) -> list[dict]:
    """Search arXiv by free-text query, optionally filtered by categories.

    Args:
        query: Free-text search query
        categories: Optional category filter
        max_results: Max papers to return
        max_retries: Retry count on failure

    Returns:
        List of paper dicts.
    """
    search_query = f"all:{urllib.parse.quote(query)}"
    if categories:
        cat_query = "+OR+".join([f"cat:{cat}" for cat in categories])
        search_query = f"({search_query})+AND+({cat_query})"

    url = (
        f"https://export.arxiv.org/api/query?"
        f"search_query={search_query}&"
        f"max_results={max_results}&"
        f"sortBy=relevance&"
        f"sortOrder=descending"
    )

    logger.info("[arXiv] Query search: %s", query)

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                xml_content = response.read().decode("utf-8")
                papers = parse_arxiv_xml(xml_content)
                logger.info("[arXiv] Found %d papers", len(papers))
                return papers
        except Exception as e:
            logger.warning("[arXiv] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
            else:
                return []

    return []


# Need urllib.parse for search_arxiv_by_query
import urllib.parse  # noqa: E402
