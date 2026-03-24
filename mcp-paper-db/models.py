"""Dataclasses for the paper database."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Paper:
    """A paper record in the database."""

    id: Optional[int] = None
    arxiv_id: Optional[str] = None
    s2_id: Optional[str] = None
    doi: Optional[str] = None
    dblp_url: Optional[str] = None
    title: str = ""
    title_normalized: str = ""
    abstract: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    published_date: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    conference: Optional[str] = None
    conference_year: Optional[int] = None
    domain: Optional[str] = None
    pdf_url: Optional[str] = None
    arxiv_url: Optional[str] = None
    source: str = "manual"
    citation_count: int = 0
    influential_citation_count: int = 0
    relevance_score: float = 0.0
    recency_score: float = 0.0
    popularity_score: float = 0.0
    quality_score: float = 0.0
    recommendation_score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)
    is_hot_paper: bool = False
    note_path: Optional[str] = None
    note_filename: Optional[str] = None
    has_note: bool = False
    has_images: bool = False
    quality_assessment_score: Optional[float] = None
    first_seen_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    last_scored_at: Optional[str] = None

    def normalize_title(self) -> str:
        """Generate a normalized title for deduplication."""
        self.title_normalized = self.title.lower().strip()
        return self.title_normalized

    def to_db_row(self) -> dict:
        """Convert to a dict suitable for DB insertion."""
        row = asdict(self)
        row["authors_json"] = json.dumps(row.pop("authors"))
        row["categories_json"] = json.dumps(row.pop("categories"))
        row["matched_keywords_json"] = json.dumps(row.pop("matched_keywords"))
        row.pop("id", None)
        row.pop("first_seen_at", None)
        row.pop("last_updated_at", None)
        return row

    @classmethod
    def from_db_row(cls, row: dict) -> Paper:
        """Create a Paper from a database row dict."""
        data = dict(row)
        data["authors"] = json.loads(data.pop("authors_json", "[]") or "[]")
        data["categories"] = json.loads(data.pop("categories_json", "[]") or "[]")
        data["matched_keywords"] = json.loads(
            data.pop("matched_keywords_json", "[]") or "[]"
        )
        data["is_hot_paper"] = bool(data.get("is_hot_paper", 0))
        data["has_note"] = bool(data.get("has_note", 0))
        data["has_images"] = bool(data.get("has_images", 0))
        return cls(**data)

    def to_summary(self) -> dict:
        """Return a compact summary for MCP tool responses."""
        return {
            "id": self.id,
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors[:5],
            "published_date": self.published_date,
            "domain": self.domain,
            "recommendation_score": self.recommendation_score,
            "has_note": self.has_note,
            "source": self.source,
        }


@dataclass
class Author:
    """A deduplicated author record."""

    id: Optional[int] = None
    name: str = ""
    name_normalized: str = ""
    institution: Optional[str] = None
    s2_author_id: Optional[str] = None

    def normalize_name(self) -> str:
        self.name_normalized = self.name.lower().strip()
        return self.name_normalized


@dataclass
class Citation:
    """A paper-to-paper relationship."""

    id: Optional[int] = None
    source_paper_id: int = 0
    target_paper_id: int = 0
    relationship_type: str = "related"
    weight: float = 0.5
    created_at: Optional[str] = None


@dataclass
class ReadingEvent:
    """A reading history event."""

    id: Optional[int] = None
    paper_id: int = 0
    event_type: str = ""
    event_date: Optional[str] = None
    context: Optional[str] = None
    recommendation_rank: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class SearchRun:
    """Tracks an API search call."""

    id: Optional[int] = None
    search_type: str = ""
    query_params: dict = field(default_factory=dict)
    result_count: Optional[int] = None
    run_date: Optional[str] = None
    status: str = "completed"
