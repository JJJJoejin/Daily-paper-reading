# evil-read-arxiv

> An automated paper reading workflow - search, recommend, analyze, and organize research papers

## Introduction

This is a collection of tools for automating the workflow of searching, recommending, analyzing, and organizing research papers. It includes a **Streamlit web UI**, **Claude Code Skills**, and an **MCP paper database** for persistent storage. By calling the arXiv, Semantic Scholar, and DBLP APIs, it recommends high-quality papers every day and generates detailed notes and knowledge graphs in your Obsidian vault.

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-25 | v2.0 | Added Streamlit UI (`app.py`), MCP paper database with SQLite, DeepSeek LLM-powered paper analysis, dual-mode operation (with/without MCP), date-based vault structure |
| 2026-03-13 | v1.1 | Added `conf-papers` skill: supports searching top conference papers from CVPR/ICCV/ECCV/ICLR/AAAI/NeurIPS/ICML |
| 2026-03-01 | v1.0 | Initial release: start-my-day, paper-analyze, extract-paper-images, paper-search |

## Features

### Streamlit Web UI (`app.py`)

A browser-based interface at `http://localhost:8502` with 8 pages:

| Page | Description |
|------|-------------|
| **Home** | Dashboard with research domains, vault stats, DB paper counts |
| **Start My Day** | Daily paper recommendations from arXiv + Semantic Scholar |
| **Analyze Paper** | Deep analysis with LLM-powered note generation (DeepSeek) |
| **Conference Papers** | Search CVPR/ICLR/NeurIPS etc. via DBLP |
| **Journal Search** | Search journal papers via OpenAlex |
| **Paper Database** | Browse/search the SQLite database (MCP mode only) |
| **Search** | Search paper notes in DB + vault markdown files |
| **Settings** | Configure vault path, DB maintenance, sync/rescore |

### MCP Paper Database (`mcp-paper-db/`)

SQLite-backed persistent storage with 16 MCP tools:

- **Search**: `search_papers`, `search_arxiv`, `search_semantic_scholar`, `search_conference_papers`, `enrich_papers`
- **Scoring**: `score_papers`, `get_recommendations`
- **Management**: `get_paper`, `upsert_paper`, `record_event`, `sync_vault_notes`, `add_citation`
- **Analytics**: `get_stats`, `get_reading_history`, `find_duplicates`, `ping`

### LLM-Powered Analysis

When `LLM_API_KEY` is set, the Analyze Paper page sends the paper's LaTeX source to DeepSeek and generates a fully filled analysis note (not just a template). Falls back to blank template if the key is not set.

### Claude Code Skills

All original skills still work via the CLI:

1. **start-my-day** — Daily paper recommendations
2. **paper-analyze** — Deep analysis of individual papers
3. **extract-paper-images** — Extract images from arXiv source packages
4. **paper-search** — Search existing paper notes
5. **conf-papers** — Top conference paper search

## Quick Start

### Prerequisites

- **Python 3.8+**
- **Obsidian** vault for storing notes

### Installation

```bash
git clone https://github.com/JJJJoejin/Daily-paper-reading.git
cd Daily-paper-reading

python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### Configuration

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your research interests
```

### Running the Streamlit UI

**Without MCP** (basic mode, no persistent DB):
```bash
OBSIDIAN_VAULT_PATH="/path/to/your/vault" \
DISABLE_MCP=1 \
streamlit run app.py --server.port 8501 --server.headless true
```

**With MCP** (persistent database):
```bash
OBSIDIAN_VAULT_PATH="/path/to/your/vault" \
streamlit run app.py --server.port 8502 --server.headless true
```

**With MCP + LLM Analysis** (full features):
```bash
OBSIDIAN_VAULT_PATH="/path/to/your/vault" \
LLM_API_KEY="your-deepseek-api-key" \
streamlit run app.py --server.port 8502 --server.headless true
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OBSIDIAN_VAULT_PATH` | Yes | Path to your Obsidian vault |
| `DISABLE_MCP` | No | Set to `1` to disable MCP database |
| `LLM_API_KEY` | No | DeepSeek API key for LLM-powered analysis |
| `S2_API_KEY` | No | Semantic Scholar API key (avoids rate limits) |

## Obsidian Vault Structure

```
YourVault/
├── 10_Daily/                          # Daily recommendation notes
│   └── YYYY-MM-DD-paper-recommendations.md
├── 20_Research/
│   ├── Papers/                        # Paper analysis notes
│   │   └── YYYY-MM-DD/               # Date-based organization
│   │       └── LLM/
│   │           ├── Paper_Title.md     # Analysis note
│   │           └── Paper_Title/
│   │               └── images/        # Extracted figures
│   └── PaperGraph/
│       └── graph_data.json            # Knowledge graph
└── 99_System/
    └── Config/
        └── research_interests.yaml    # Research interests config
```

## Project Structure

```
evil-read-arxiv/
├── app.py                    # Streamlit web UI
├── config.example.yaml       # Config template
├── requirements.txt          # Python dependencies
├── mcp-paper-db/             # MCP paper database server
│   ├── server.py             # MCP entry point (stdio transport)
│   ├── db.py                 # SQLite schema, migrations, CRUD
│   ├── models.py             # Paper, Author, Citation dataclasses
│   ├── config.py             # Config loading
│   ├── scoring_engine.py     # Paper scoring (relevance, recency, etc.)
│   ├── tools/                # MCP tool implementations
│   │   ├── search.py         # search_papers, search_arxiv, etc.
│   │   ├── scoring.py        # score_papers, get_recommendations
│   │   ├── management.py     # upsert_paper, sync_vault_notes, etc.
│   │   └── analytics.py      # get_stats, get_reading_history
│   ├── clients/              # External API clients
│   │   ├── arxiv_client.py   # arXiv API
│   │   ├── s2_client.py      # Semantic Scholar API
│   │   └── dblp_client.py    # DBLP API
│   └── migrations/
│       └── 001_initial.sql
├── start-my-day/             # Daily recommendation skill
│   ├── SKILL.md
│   └── scripts/
├── paper-analyze/            # Paper analysis skill
│   ├── SKILL.md
│   └── scripts/
├── extract-paper-images/     # Image extraction skill
│   ├── SKILL.md
│   └── scripts/
├── paper-search/             # Paper search skill
│   └── SKILL.md
├── conf-papers/              # Conference paper search skill
│   ├── SKILL.md
│   └── scripts/
└── journal-search/           # Journal search
    └── scripts/
```

## Scoring Mechanism

Paper recommendation scoring is based on four dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Relevance | 40% | Match with research interests (keywords, categories) |
| Recency | 20% | Publication date |
| Popularity | 30% | Citation count / impact |
| Quality | 10% | Method quality inferred from abstract |

## Dual-Mode Operation

You can run two instances simultaneously:

| Port | Mode | Features |
|------|------|----------|
| 8501 | No MCP | Script-based search, results not persisted, vault-only search |
| 8502 | MCP | DB-backed search, persistent storage, recommendations accumulate over time |

Both modes write the same Obsidian notes. The MCP version additionally stores everything in a SQLite database (`mcp-paper-db/papers.db`).

## FAQ

### Q: No search results?
A: Check network connection, verify keywords in config, try expanding arXiv categories.

### Q: Semantic Scholar 429 rate limit?
A: Get a free API key at https://www.semanticscholar.org/product/api and set `S2_API_KEY`, or check "Skip Semantic Scholar hot papers" in the UI.

### Q: Image extraction failed?
A: Make sure PyMuPDF is installed (`pip install PyMuPDF`) and the arXiv ID format is correct.

### Q: LLM analysis not working?
A: Set `LLM_API_KEY` environment variable with your DeepSeek API key. Without it, you get a blank template note instead.

### Q: Port already in use?
A: Run `pkill -f "streamlit run app.py"` then start again.

## License

MIT License

## Acknowledgments

- [arXiv](https://arxiv.org/) — Open-access academic preprint platform
- [Semantic Scholar](https://www.semanticscholar.org/) — AI-powered academic research platform
- [DBLP](https://dblp.org/) — Computer science bibliography
- [DeepSeek](https://deepseek.com/) — LLM API for paper analysis
- [Claude Code](https://claude.ai/claude-code) — AI-assisted development
- [Obsidian](https://obsidian.md/) — Knowledge management tool
- [Streamlit](https://streamlit.io/) — Web UI framework
