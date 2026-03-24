"""MCP analytics tools — get_reading_history, find_duplicates."""

from __future__ import annotations

import logging
from typing import Optional

from ..db import PaperDatabase

logger = logging.getLogger(__name__)


def get_reading_history_impl(
    db: PaperDatabase,
    event_type: Optional[str] = None,
    days: int = 30,
    limit: int = 50,
) -> list[dict]:
    """Get reading history events with paper details."""
    return db.get_reading_history(event_type=event_type, days=days, limit=limit)


def find_duplicates_impl(db: PaperDatabase) -> list[dict]:
    """Find papers with duplicate normalized titles."""
    return db.find_duplicates()
