# MCP Paper Database Server — Design Document

## Architecture Overview

```
Claude Code (user session)
    │
    ├── MCP Tools (paper-db server)     ← NEW: structured queries, persistence
    │       ├── SQLite database          ← paper metadata, reading history, scores
    │       ├── arXiv API client         ← extracted from search_arxiv.py
    │       ├── Semantic Scholar client  ← extracted from search_arxiv.py
    │       └── DBLP client              ← extracted from search_conf_papers.py
    │
    └── Existing Skills (SKILL.md)       ← UNCHANGED: still write markdown to vault
            └── Obsidian Vault (filesystem)
```

The MCP server handles **data operations** (search, store, query, score). Skills continue to handle **content generation** (writing markdown, extracting images).

---

## Database Schema (SQLite)

### Core tables

**`papers`** — central table, every discovered paper gets a row:

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `arxiv_id` | TEXT UNIQUE | e.g. "2603.22213" |
| `s2_id`, `doi`, `dblp_url` | TEXT | Cross-references |
| `title`, `title_normalized` | TEXT | Display + dedup |
| `abstract` | TEXT | Full abstract |
| `authors_json` | TEXT | JSON array |
| `published_date` | TEXT | ISO format |
| `categories_json` | TEXT | arXiv categories |
| `conference`, `conference_year` | TEXT/INT | e.g. "ICLR", 2025 |
| `domain` | TEXT | Matched domain from config |
| `relevance_score`, `recency_score`, `popularity_score`, `quality_score`, `recommendation_score` | REAL | Scoring |
| `matched_keywords_json` | TEXT | Which keywords matched |
| `note_path` | TEXT | Path in vault if analyzed |
| `has_note`, `has_images` | BOOLEAN | Vault status |
| `source` | TEXT | "arxiv", "s2", "dblp", "manual" |
| `first_seen_at`, `last_updated_at` | TEXT | Timestamps |

**`authors`** — deduplicated author list
**`paper_authors`** — junction table with author position
**`citations`** — paper-to-paper relationships (cites, extends, compares)
**`reading_history`** — events: recommended, analyzed, searched, bookmarked
**`keywords`** — matched/category/user tags per paper
**`search_runs`** — tracks API calls to avoid redundant searches

### Full SQL

```sql
CREATE TABLE papers (
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

CREATE INDEX idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX idx_papers_title_normalized ON papers(title_normalized);
CREATE INDEX idx_papers_domain ON papers(domain);
CREATE INDEX idx_papers_recommendation_score ON papers(recommendation_score DESC);
CREATE INDEX idx_papers_published_date ON papers(published_date DESC);
CREATE INDEX idx_papers_conference ON papers(conference, conference_year);
CREATE INDEX idx_papers_has_note ON papers(has_note);

CREATE TABLE authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    institution TEXT,
    s2_author_id TEXT,
    UNIQUE(name_normalized)
);

CREATE INDEX idx_authors_name ON authors(name_normalized);

CREATE TABLE paper_authors (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    position INTEGER,
    PRIMARY KEY (paper_id, author_id)
);

CREATE TABLE citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    target_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'related',
    weight REAL DEFAULT 0.5,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_paper_id, target_paper_id, relationship_type)
);

CREATE INDEX idx_citations_source ON citations(source_paper_id);
CREATE INDEX idx_citations_target ON citations(target_paper_id);

CREATE TABLE reading_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL DEFAULT (date('now')),
    context TEXT,
    recommendation_rank INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_reading_history_paper ON reading_history(paper_id);
CREATE INDEX idx_reading_history_date ON reading_history(event_date);
CREATE INDEX idx_reading_history_type ON reading_history(event_type);

CREATE TABLE search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_type TEXT NOT NULL,
    query_params_json TEXT NOT NULL,
    result_count INTEGER,
    run_date TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT DEFAULT 'completed'
);

CREATE TABLE keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    keyword_type TEXT NOT NULL,
    UNIQUE(paper_id, keyword, keyword_type)
);

CREATE INDEX idx_keywords_keyword ON keywords(keyword);
CREATE INDEX idx_keywords_paper ON keywords(paper_id);
```

---

## MCP Tools

### Search & Discovery

| Tool | Replaces | Purpose |
|------|----------|---------|
| `search_papers` | grep in paper-search skill | Structured DB query by author, domain, date, score, conference |
| `search_arxiv` | `search_arxiv.py` | Call arXiv API, store results in DB |
| `search_semantic_scholar` | S2 calls in scripts | Search S2 for hot papers, store in DB |
| `search_conference_papers` | `search_conf_papers.py` | Search DBLP, store in DB |
| `enrich_papers` | inline S2 enrichment | Backfill abstracts/citations from S2 |

### Scoring & Recommendations

| Tool | Purpose |
|------|---------|
| `score_papers` | Re-score papers against current research_interests.yaml |
| `get_recommendations` | Top N papers, filtered by domain/score/analyzed status |

### Paper Management

| Tool | Purpose |
|------|---------|
| `get_paper` | Full details for one paper |
| `upsert_paper` | Add or update paper metadata |
| `record_event` | Log reading history (recommended, analyzed, etc.) |
| `sync_vault_notes` | Scan vault, match notes to DB papers |
| `add_citation` | Record paper-to-paper relationship |

### Analytics

| Tool | Purpose |
|------|---------|
| `get_stats` | Paper counts by domain, source, reading activity |
| `get_reading_history` | What was recommended/read and when |
| `find_duplicates` | Detect near-duplicate papers |

---

## How Existing Skills Change

### `start-my-day` (before → after)
- Before: `scan_existing_notes.py` → JSON → `search_arxiv.py` → JSON → Claude writes markdown
- After: `sync_vault_notes` → `search_arxiv` → `score_papers` → `get_recommendations` → Claude writes markdown → `record_event`

### `paper-search` (biggest improvement)
- Before: grep through hundreds of markdown files
- After: `search_papers(query="diffusion", author="Ho", domain="LLM")` — instant structured results

### `paper-analyze` (after analysis)
- Calls `upsert_paper` to mark `has_note=true` + `add_citation` for related papers

### `extract-paper-images` — no change needed

---

## File Structure

```
evil-read-arxiv/
├── mcp-paper-db/
│   ├── __init__.py
│   ├── server.py              # MCP entry point (stdio transport)
│   ├── db.py                  # SQLite schema, migrations, CRUD
│   ├── models.py              # Paper, Author, Citation dataclasses
│   ├── config.py              # Vault path, research interests loading
│   ├── scoring_engine.py      # Extracted from search_arxiv.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py          # search_papers, search_arxiv, etc.
│   │   ├── scoring.py         # score_papers, get_recommendations
│   │   ├── management.py      # upsert_paper, record_event, sync_vault_notes
│   │   └── analytics.py       # get_stats, get_reading_history
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── arxiv_client.py    # Extracted from search_arxiv.py
│   │   ├── s2_client.py       # Extracted from search_arxiv.py + search_conf_papers.py
│   │   └── dblp_client.py     # Extracted from search_conf_papers.py
│   ├── migrations/
│   │   └── 001_initial.sql
│   └── papers.db              # SQLite file (gitignored)
```

## Tech Stack

- **Python** — all existing code is Python, scoring functions can be extracted directly
- **`mcp` SDK** — official Python MCP SDK, stdio transport
- **SQLite** with WAL mode — simple, no external dependencies, sufficient for single-user
- No new runtime — runs in the existing `.venv`

## Configuration

In `.claude/settings.json`:

```json
{
  "mcpServers": {
    "paper-db": {
      "command": ".venv/bin/python",
      "args": ["-m", "mcp_paper_db.server"],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/path/to/vault",
        "PAPER_DB_PATH": "mcp-paper-db/papers.db"
      }
    }
  }
}
```

---

## Implementation Phases

### Phase 1: Core — DB schema, server skeleton, config loading
- Create directory structure and `__init__.py` files
- Implement `db.py` with schema creation and migrations
- Implement `models.py` with Paper, Author, Citation dataclasses
- Implement `config.py` for vault path and research interests
- Implement `server.py` with MCP server init (stdio transport)
- Add `mcp` to `requirements.txt`
- Write `migrations/001_initial.sql`

### Phase 2: Search tools — Extract API clients, implement search
- Extract `arxiv_client.py` from `start-my-day/scripts/search_arxiv.py`
- Extract `s2_client.py` from `search_arxiv.py` + `search_conf_papers.py`
- Extract `dblp_client.py` from `conf-papers/scripts/search_conf_papers.py`
- Implement `tools/search.py`: `search_papers`, `search_arxiv`, `search_semantic_scholar`, `search_conference_papers`, `enrich_papers`

### Phase 3: Scoring — Extract scoring engine, implement scoring tools
- Extract `scoring_engine.py` from `search_arxiv.py`
- Implement `tools/scoring.py`: `score_papers`, `get_recommendations`

### Phase 4: Management — Paper CRUD and vault sync
- Implement `tools/management.py`: `get_paper`, `upsert_paper`, `record_event`, `sync_vault_notes`, `add_citation`

### Phase 5: Analytics — Stats and history
- Implement `tools/analytics.py`: `get_stats`, `get_reading_history`, `find_duplicates`

### Phase 6: Skill migration — Update SKILL.md files
- Update `paper-search/SKILL.md` to use `search_papers` MCP tool
- Update `start-my-day/SKILL.md` to use MCP tools
- Update `conf-papers/SKILL.md` to use MCP tools
- Update `paper-analyze/SKILL.md` to call `upsert_paper` and `add_citation`
