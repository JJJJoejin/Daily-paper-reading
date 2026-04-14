"""SQLite database management for the paper database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import Paper, Author, Citation, ReadingEvent, SearchRun

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class PaperDatabase:
    """SQLite database for paper metadata, reading history, and scores."""

    def __init__(self, db_path: str | Path = "mcp-paper-db/papers.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Migrations --

    def get_current_version(self) -> int:
        try:
            row = self.conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
            return row[0] or 0
        except sqlite3.OperationalError:
            return 0

    def migrate(self):
        """Apply all pending migrations."""
        current = self.get_current_version()
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for mf in migration_files:
            version = int(mf.stem.split("_")[0])
            if version > current:
                sql = mf.read_text()
                self.conn.executescript(sql)
                print(f"Applied migration {mf.name}")
        return self.get_current_version()

    # -- Paper CRUD --

    def upsert_paper(self, paper: Paper) -> Paper:
        """Insert or update a paper. Returns the paper with its DB id."""
        if not paper.title_normalized:
            paper.normalize_title()

        row = paper.to_db_row()

        # Try to find existing paper by arxiv_id or normalized title
        existing = None
        if paper.arxiv_id:
            existing = self.conn.execute(
                "SELECT id FROM papers WHERE arxiv_id = ?", (paper.arxiv_id,)
            ).fetchone()
        if not existing and paper.title_normalized:
            existing = self.conn.execute(
                "SELECT id FROM papers WHERE title_normalized = ?",
                (paper.title_normalized,),
            ).fetchone()

        if existing:
            paper_id = existing["id"]
            # Update non-null fields
            update_cols = []
            update_vals = []
            for col, val in row.items():
                if val is not None and col not in ("source",):
                    update_cols.append(f"{col} = ?")
                    update_vals.append(val)
            update_cols.append("last_updated_at = datetime('now')")
            update_vals.append(paper_id)
            self.conn.execute(
                f"UPDATE papers SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            self.conn.commit()
            paper.id = paper_id
        else:
            cols = list(row.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            self.conn.execute(
                f"INSERT INTO papers ({col_names}) VALUES ({placeholders})",
                [row[c] for c in cols],
            )
            self.conn.commit()
            paper.id = self.conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

        return paper

    def get_paper(self, paper_id: Optional[int] = None, arxiv_id: Optional[str] = None) -> Optional[Paper]:
        """Get a paper by DB id or arxiv_id."""
        if paper_id:
            row = self.conn.execute(
                "SELECT * FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
        elif arxiv_id:
            row = self.conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
            ).fetchone()
        else:
            return None
        return Paper.from_db_row(dict(row)) if row else None

    def search_papers(
        self,
        query: Optional[str] = None,
        domain: Optional[str] = None,
        author: Optional[str] = None,
        conference: Optional[str] = None,
        has_note: Optional[bool] = None,
        min_score: Optional[float] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Paper]:
        """Search papers with structured filters."""
        conditions = []
        params = []

        if query:
            conditions.append(
                "(title LIKE ? OR abstract LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q])
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        if author:
            conditions.append("authors_json LIKE ?")
            params.append(f"%{author}%")
        if conference:
            conditions.append("conference = ?")
            params.append(conference)
        if has_note is not None:
            conditions.append("has_note = ?")
            params.append(int(has_note))
        if min_score is not None:
            conditions.append("recommendation_score >= ?")
            params.append(min_score)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        rows = self.conn.execute(
            f"SELECT * FROM papers WHERE {where} "
            f"ORDER BY recommendation_score DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [Paper.from_db_row(dict(r)) for r in rows]

    def count_papers(self, domain: Optional[str] = None) -> int:
        if domain:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM papers WHERE domain = ?", (domain,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM papers").fetchone()
        return row[0]

    # -- Author CRUD --

    def upsert_author(self, author: Author) -> Author:
        if not author.name_normalized:
            author.normalize_name()
        existing = self.conn.execute(
            "SELECT id FROM authors WHERE name_normalized = ?",
            (author.name_normalized,),
        ).fetchone()
        if existing:
            author.id = existing["id"]
        else:
            self.conn.execute(
                "INSERT INTO authors (name, name_normalized, institution, s2_author_id) "
                "VALUES (?, ?, ?, ?)",
                (author.name, author.name_normalized, author.institution, author.s2_author_id),
            )
            self.conn.commit()
            author.id = self.conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]
        return author

    def link_paper_author(self, paper_id: int, author_id: int, position: int):
        self.conn.execute(
            "INSERT OR IGNORE INTO paper_authors (paper_id, author_id, position) "
            "VALUES (?, ?, ?)",
            (paper_id, author_id, position),
        )
        self.conn.commit()

    # -- Citation CRUD --

    def add_citation(self, citation: Citation) -> Citation:
        self.conn.execute(
            "INSERT OR IGNORE INTO citations "
            "(source_paper_id, target_paper_id, relationship_type, weight) "
            "VALUES (?, ?, ?, ?)",
            (citation.source_paper_id, citation.target_paper_id,
             citation.relationship_type, citation.weight),
        )
        self.conn.commit()
        citation.id = self.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        return citation

    # -- Reading History --

    def record_event(self, event: ReadingEvent) -> ReadingEvent:
        self.conn.execute(
            "INSERT INTO reading_history "
            "(paper_id, event_type, event_date, context, recommendation_rank) "
            "VALUES (?, ?, COALESCE(?, date('now')), ?, ?)",
            (event.paper_id, event.event_type, event.event_date,
             event.context, event.recommendation_rank),
        )
        self.conn.commit()
        event.id = self.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        return event

    def get_reading_history(
        self, event_type: Optional[str] = None, days: int = 30, limit: int = 50
    ) -> list[dict]:
        conditions = ["rh.event_date >= date('now', ?)"]
        params: list = [f"-{days} days"]
        if event_type:
            conditions.append("rh.event_type = ?")
            params.append(event_type)
        where = " AND ".join(conditions)
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT rh.*, p.title, p.arxiv_id FROM reading_history rh "
            f"JOIN papers p ON p.id = rh.paper_id "
            f"WHERE {where} ORDER BY rh.created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Search Runs --

    def record_search_run(self, run: SearchRun) -> SearchRun:
        self.conn.execute(
            "INSERT INTO search_runs (search_type, query_params_json, result_count, status) "
            "VALUES (?, ?, ?, ?)",
            (run.search_type, json.dumps(run.query_params),
             run.result_count, run.status),
        )
        self.conn.commit()
        run.id = self.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        return run

    def get_recent_search_run(
        self, search_type: str, max_age_hours: int = 6
    ) -> Optional[dict]:
        """Check if a search of this type ran recently (within max_age_hours).

        Returns the most recent matching run or None.
        """
        row = self.conn.execute(
            "SELECT id, search_type, query_params_json, result_count, status, run_date "
            "FROM search_runs "
            "WHERE search_type = ? AND run_date >= datetime('now', ?) AND status = 'completed' "
            "ORDER BY run_date DESC LIMIT 1",
            (search_type, f"-{max_age_hours} hours"),
        ).fetchone()
        return dict(row) if row else None

    # -- Keywords --

    def add_keyword(self, paper_id: int, keyword: str, keyword_type: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO keywords (paper_id, keyword, keyword_type) "
            "VALUES (?, ?, ?)",
            (paper_id, keyword, keyword_type),
        )
        self.conn.commit()

    def get_keywords(self, paper_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT keyword, keyword_type FROM keywords WHERE paper_id = ?",
            (paper_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Stats --

    def get_stats(self) -> dict:
        total = self.count_papers()
        with_notes = self.conn.execute(
            "SELECT COUNT(*) FROM papers WHERE has_note = 1"
        ).fetchone()[0]
        domains = self.conn.execute(
            "SELECT domain, COUNT(*) as cnt FROM papers "
            "WHERE domain IS NOT NULL GROUP BY domain ORDER BY cnt DESC"
        ).fetchall()
        sources = self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM papers "
            "GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        recent_events = self.conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM reading_history "
            "WHERE event_date >= date('now', '-7 days') "
            "GROUP BY event_type"
        ).fetchall()
        return {
            "total_papers": total,
            "papers_with_notes": with_notes,
            "by_domain": {r["domain"]: r["cnt"] for r in domains},
            "by_source": {r["source"]: r["cnt"] for r in sources},
            "recent_events_7d": {r["event_type"]: r["cnt"] for r in recent_events},
        }

    # -- Duplicates --

    def find_duplicates(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT title_normalized, GROUP_CONCAT(id) as ids, COUNT(*) as cnt "
            "FROM papers GROUP BY title_normalized HAVING cnt > 1"
        ).fetchall()
        return [dict(r) for r in rows]
