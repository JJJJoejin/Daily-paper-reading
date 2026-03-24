-- Migration 001: Initial schema
-- Creates all core tables for the paper database

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id TEXT UNIQUE,
    s2_id TEXT,
    doi TEXT,
    dblp_url TEXT,
    title TEXT NOT NULL,
    title_normalized TEXT NOT NULL,
    abstract TEXT,
    authors_json TEXT,
    published_date TEXT,
    categories_json TEXT,
    conference TEXT,
    conference_year INTEGER,
    domain TEXT,
    pdf_url TEXT,
    arxiv_url TEXT,
    source TEXT NOT NULL,
    citation_count INTEGER DEFAULT 0,
    influential_citation_count INTEGER DEFAULT 0,
    relevance_score REAL DEFAULT 0,
    recency_score REAL DEFAULT 0,
    popularity_score REAL DEFAULT 0,
    quality_score REAL DEFAULT 0,
    recommendation_score REAL DEFAULT 0,
    matched_keywords_json TEXT,
    is_hot_paper BOOLEAN DEFAULT 0,
    note_path TEXT,
    note_filename TEXT,
    has_note BOOLEAN DEFAULT 0,
    has_images BOOLEAN DEFAULT 0,
    quality_assessment_score REAL,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_scored_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_papers_title_normalized ON papers(title_normalized);
CREATE INDEX IF NOT EXISTS idx_papers_domain ON papers(domain);
CREATE INDEX IF NOT EXISTS idx_papers_recommendation_score ON papers(recommendation_score DESC);
CREATE INDEX IF NOT EXISTS idx_papers_published_date ON papers(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_papers_conference ON papers(conference, conference_year);
CREATE INDEX IF NOT EXISTS idx_papers_has_note ON papers(has_note);

CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    institution TEXT,
    s2_author_id TEXT,
    UNIQUE(name_normalized)
);

CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name_normalized);

CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    position INTEGER,
    PRIMARY KEY (paper_id, author_id)
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    target_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'related',
    weight REAL DEFAULT 0.5,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_paper_id, target_paper_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_paper_id);
CREATE INDEX IF NOT EXISTS idx_citations_target ON citations(target_paper_id);

CREATE TABLE IF NOT EXISTS reading_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL DEFAULT (date('now')),
    context TEXT,
    recommendation_rank INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reading_history_paper ON reading_history(paper_id);
CREATE INDEX IF NOT EXISTS idx_reading_history_date ON reading_history(event_date);
CREATE INDEX IF NOT EXISTS idx_reading_history_type ON reading_history(event_type);

CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_type TEXT NOT NULL,
    query_params_json TEXT NOT NULL,
    result_count INTEGER,
    run_date TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    keyword_type TEXT NOT NULL,
    UNIQUE(paper_id, keyword, keyword_type)
);

CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_keywords_paper ON keywords(paper_id);

-- Migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO schema_migrations (version) VALUES (1);
