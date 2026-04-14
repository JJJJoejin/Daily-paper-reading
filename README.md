# DailyPapers

> Your AI research assistant — papers ready before coffee ☕️

DailyPapers automatically searches, scores, analyzes, and organizes newly published research papers every day. It pulls from multiple academic sources, ranks papers by relevance to your interests, generates detailed analysis notes with an LLM, and stores everything in an Obsidian vault and a local SQLite database.

## What's Inside

### Streamlit Web UI

A browser-based interface with 8 pages:

| Page | What it does |
|------|-------------|
| **Home** | Dashboard with research domain stats, vault overview, and paper counts |
| **Start My Day** | One-click daily recommendations — searches, scores, and auto-analyzes top papers |
| **Analyze Paper** | Deep analysis of a single paper with LLM-generated notes from LaTeX source |
| **Conference Papers** | Search top conferences (CVPR, ICLR, NeurIPS, ICML, AAAI, etc.) via DBLP |
| **Journal Search** | Search journal papers via OpenAlex |
| **Paper Database** | Browse and search the SQLite paper collection |
| **Search** | Full-text search across database records and vault markdown notes |
| **Settings** | Configure vault path, run DB maintenance, sync and rescore |

### MCP Paper Database

A custom MCP server backed by SQLite, exposing 16 tools:

- **Search** (5 tools): `search_papers`, `search_arxiv`, `search_semantic_scholar`, `search_conference_papers`, `enrich_papers`
- **Scoring** (2 tools): `score_papers`, `get_recommendations`
- **Management** (5 tools): `get_paper`, `upsert_paper`, `record_event`, `add_citation`, `sync_vault_notes`
- **Analytics** (4 tools): `get_stats`, `get_reading_history`, `find_duplicates`, `ping`

### Paper Scoring

Papers are ranked on a 0–10 scale using four dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Relevance | 40% | Keyword match in title/abstract, arXiv category alignment |
| Popularity | 30% | Citation count, influential citations, hot paper detection |
| Recency | 20% | Publication date (papers within 30 days score highest) |
| Quality | 10% | Innovation signals, methodology rigor, quantitative results |

### LLM-Powered Analysis

When an API key is configured, the Analyze Paper page sends the paper's LaTeX source to DeepSeek and generates a complete analysis note — methodology breakdown, experiment summary, insights, limitations, and comparison with related work. Without the key, it generates a blank template.

### Claude Code Skills

Five skills available via the CLI:

1. `/start-my-day` — Daily paper recommendations
2. `/paper-analyze` — Deep analysis of individual papers
3. `/extract-paper-images` — Extract figures from arXiv source packages
4. `/paper-search` — Search existing paper notes
5. `/conf-papers` — Top conference paper search

## Getting Started

### Prerequisites

- **Python 3.8+**
- **Obsidian** vault for storing notes

### 1. Clone and install

```bash
git clone https://github.com/JJJJoejin/Daily-paper-reading.git
cd Daily-paper-reading

python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 2. Configure your research interests

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to define your research domains, keywords, and arXiv categories:

```yaml
vault_path: "/path/to/your/obsidian/vault"

research_domains:
  "LLM":
    keywords:
      - "large language model"
      - "LLM"
      - "transformer"
    arxiv_categories:
      - "cs.CL"
      - "cs.AI"
    priority: 5

  "Your_Domain":
    keywords:
      - "your keyword 1"
      - "your keyword 2"
    arxiv_categories:
      - "cs.XX"
    priority: 4

excluded_keywords:
  - "3D"
  - "robotics"
```

### 3. Set up your Obsidian vault

Create this directory structure in your vault:

```
YourVault/
├── 10_Daily/
├── 20_Research/
│   ├── Papers/
│   └── PaperGraph/
└── 99_System/
    └── Config/
```

Copy the config into your vault:

```bash
cp config.yaml "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml"
```

### 4. Run the app

**Basic mode** (no persistent database):

```bash
OBSIDIAN_VAULT_PATH="/path/to/your/vault" \
DISABLE_MCP=1 \
streamlit run app.py --server.port 8501 --server.headless true
```

**With MCP database** (recommended):

```bash
OBSIDIAN_VAULT_PATH="/path/to/your/vault" \
streamlit run app.py --server.port 8502 --server.headless true
```

**Full features** (MCP + LLM analysis):

```bash
OBSIDIAN_VAULT_PATH="/path/to/your/vault" \
LLM_API_KEY="your-deepseek-api-key" \
streamlit run app.py --server.port 8502 --server.headless true
```

Then open `http://localhost:8502` in your browser.

### 5. (Optional) Install Claude Code Skills

```bash
# macOS/Linux
cp -r start-my-day ~/.claude/skills/
cp -r paper-analyze ~/.claude/skills/
cp -r extract-paper-images ~/.claude/skills/
cp -r paper-search ~/.claude/skills/
cp -r conf-papers ~/.claude/skills/

# Windows PowerShell
Copy-Item -Recurse start-my-day $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse paper-analyze $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse extract-paper-images $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse paper-search $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse conf-papers $env:USERPROFILE\.claude\skills\
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OBSIDIAN_VAULT_PATH` | Yes | Path to your Obsidian vault |
| `DISABLE_MCP` | No | Set to `1` to run without the MCP database |
| `LLM_API_KEY` | No | DeepSeek API key for LLM-powered paper analysis |
| `S2_API_KEY` | No | Semantic Scholar API key (avoids rate limits) |

## Project Structure

```
DailyPapers/
├── app.py                    # Streamlit web UI
├── config.example.yaml       # Config template
├── requirements.txt          # Python dependencies
├── mcp-paper-db/             # MCP paper database server
│   ├── server.py             # MCP entry point (stdio transport)
│   ├── db.py                 # SQLite schema, migrations, CRUD
│   ├── models.py             # Paper, Author, Citation dataclasses
│   ├── config.py             # Config loading
│   ├── scoring_engine.py     # Paper scoring engine
│   ├── tools/                # MCP tool implementations
│   │   ├── search.py         # search_papers, search_arxiv, etc.
│   │   ├── scoring.py        # score_papers, get_recommendations
│   │   ├── management.py     # upsert_paper, sync_vault_notes, etc.
│   │   └── analytics.py      # get_stats, get_reading_history
│   └── clients/              # External API clients
│       ├── arxiv_client.py   # arXiv API
│       ├── s2_client.py      # Semantic Scholar API
│       └── dblp_client.py    # DBLP API
├── start-my-day/             # Daily recommendation skill
├── paper-analyze/            # Paper analysis skill
├── extract-paper-images/     # Image extraction skill
├── paper-search/             # Paper search skill
├── conf-papers/              # Conference paper search skill
└── journal-search/           # Journal search
```

## Obsidian Vault Output

```
YourVault/
├── 10_Daily/
│   └── 2026-03-26-paper-recommendations.md    # Daily top papers
├── 20_Research/
│   ├── Papers/
│   │   └── LLM/                               # Grouped by domain
│   │       └── 2026-03-25_Paper_Title/         # Self-contained folder
│   │           ├── 2026-03-25_Paper_Title.md   # Full analysis note
│   │           └── images/                     # Extracted figures
│   └── PaperGraph/
│       └── graph_data.json                     # Knowledge graph
└── 99_System/
    └── Config/
        └── research_interests.yaml
```

## FAQ

**No search results?**
Check your network connection, verify keywords in `config.yaml`, and try expanding your arXiv categories.

**Semantic Scholar 429 rate limit?**
Get a free API key at https://www.semanticscholar.org/product/api and set `S2_API_KEY`.

**Image extraction failed?**
Make sure PyMuPDF is installed (`pip install PyMuPDF`) and the arXiv ID format is correct (e.g., `2602.12345`).

**LLM analysis not working?**
Set the `LLM_API_KEY` environment variable with your DeepSeek API key.

**Port already in use?**
Run `pkill -f "streamlit run app.py"` and try again.

## License

MIT License

## Acknowledgments

- [arXiv](https://arxiv.org/) — Open-access preprint platform
- [Semantic Scholar](https://www.semanticscholar.org/) — AI-powered research platform
- [DBLP](https://dblp.org/) — Computer science bibliography
- [OpenAlex](https://openalex.org/) — Open catalog of scholarly works
- [DeepSeek](https://deepseek.com/) — LLM API for paper analysis
- [Claude Code](https://claude.ai/claude-code) — AI-assisted development
- [Obsidian](https://obsidian.md/) — Knowledge management
- [Streamlit](https://streamlit.io/) — Web UI framework
