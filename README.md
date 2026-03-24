# evil-read-arxiv

> An automated paper reading workflow - search, recommend, analyze, and organize research papers

## Introduction

This is a collection of Claude Code Skills for automating the workflow of searching, recommending, analyzing, and organizing research papers. By calling the arXiv and Semantic Scholar APIs, it recommends high-quality papers for you every day and automatically generates detailed notes and knowledge graphs.

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-13 | v1.1 | Added `conf-papers` skill: supports searching top conference papers from CVPR/ICCV/ECCV/ICLR/AAAI/NeurIPS/ICML, powered by DBLP + Semantic Scholar dual data sources, independent config file, three-dimensional scoring |
| 2026-03-01 | v1.0 | Initial release: start-my-day daily recommendations, paper-analyze paper analysis, extract-paper-images image extraction, paper-search paper search |

## Features

### 1. start-my-day - Daily Paper Recommendations
- Searches arXiv for papers from the last month
- Searches Semantic Scholar for high-impact papers from the past year
- Comprehensive scoring based on four dimensions: relevance, recency, popularity, and quality
- Automatically generates a daily overview and recommendation list
- Top 3 papers automatically get detailed analysis and image extraction
- Automatically links keywords to existing notes

### 2. paper-analyze - In-Depth Paper Analysis
- Deep analysis of individual papers
- Generates structured notes including:
  - Abstract translation and key point extraction
  - Research background and motivation
  - Method overview and architecture
  - Experimental results analysis
  - Research value assessment
  - Strengths and limitations analysis
  - Comparison with related papers
- Automatically extracts paper images and inserts them into notes
- Updates knowledge graph

### 3. extract-paper-images - Paper Image Extraction
- Prioritizes extracting high-quality images from arXiv source packages
- Supports extracting images from PDF as a fallback
- Automatically generates an image index
- Saves to the images subdirectory of the notes directory

### 4. paper-search - Paper Note Search
- Searches existing notes for papers
- Supports search by title, author, keywords, and domain
- Results sorted by relevance score

### 5. conf-papers - Top Conference Paper Search & Recommendations
- Searches top conference papers from CVPR/ICCV/ECCV/ICLR/AAAI/NeurIPS/ICML
- Uses DBLP API to get paper lists + Semantic Scholar to supplement citations and abstracts
- Independent config file `conf-papers.yaml` (keywords, exclusions, default year/conference)
- Two-stage filtering: title keyword lightweight screening -> S2 supplementation -> three-dimensional scoring (relevance 40% + popularity 40% + quality 20%)
- Top 3 papers automatically get detailed analysis (requires arXiv ID)

## Installation

### Prerequisites

1. **Claude Code CLI** - Must be installed and configured
2. **Python 3.8+** - Required for running search and analysis scripts
3. **Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Installation Steps

1. Clone or copy this repository to your Claude Code skills directory:
   ```bash
   # Windows PowerShell
   Copy-Item -Recurse evil-read-arxiv\start-my-day $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\paper-analyze $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\extract-paper-images $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\paper-search $env:USERPROFILE\.claude\skills\

   # macOS/Linux
   cp -r evil-read-arxiv/start-my-day ~/.claude/skills/
   cp -r evil-read-arxiv/paper-analyze ~/.claude/skills/
   cp -r evil-read-arxiv/extract-paper-images ~/.claude/skills/
   cp -r evil-read-arxiv/paper-search ~/.claude/skills/
   ```

2. Configure environment variables and paths (see the "Configuration" section below)

3. Restart Claude Code CLI

## Configuration

> **Strongly recommended**: Read [QUICKSTART.md](QUICKSTART.md) first for a quick setup.

### Step 1: Set Environment Variables (Recommended)

All scripts read the Obsidian Vault path from the `OBSIDIAN_VAULT_PATH` environment variable. This is the simplest configuration method:

```bash
# Windows PowerShell (temporary)
$env:OBSIDIAN_VAULT_PATH = "C:/Users/YourName/Documents/Obsidian Vault"

# Windows PowerShell (permanent)
[System.Environment]::SetEnvironmentVariable("OBSIDIAN_VAULT_PATH", "C:/Users/YourName/Documents/Obsidian Vault", "User")

# macOS/Linux (add to ~/.bashrc or ~/.zshrc)
export OBSIDIAN_VAULT_PATH="/Users/yourname/Documents/Obsidian Vault"
```

After setting the environment variable, **there is no need to modify any paths in the scripts**.

### Step 2: Create Configuration File

Copy `config.example.yaml` and modify it:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and modify the keywords according to your research interests:

```yaml
vault_path: "/path/to/your/obsidian/vault"

research_domains:
  "YourResearchDomain1":
    keywords:
      - "keyword1"
      - "keyword2"
    arxiv_categories:
      - "cs.AI"
      - "cs.LG"
```

Then copy the modified `config.yaml` into your Vault:
```bash
cp config.yaml "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml"
```

### Step 3 (Optional): Override Paths via CLI Arguments

If you prefer not to set environment variables, you can specify paths via arguments each time you call a script:

```bash
python scripts/search_arxiv.py --config "/your/path/research_interests.yaml"
python scripts/scan_existing_notes.py --vault "/your/obsidian/vault"
python scripts/generate_note.py --vault "/your/obsidian/vault" --paper-id "2402.12345" --title "Paper Title" --authors "Author" --domain "LLM"
python scripts/update_graph.py --vault "/your/obsidian/vault" --paper-id "2402.12345" --title "Paper Title" --domain "LLM"
```

### Path Format Notes

- **Windows**: You can use forward slashes `/` or double backslashes `\\`
  - Correct: `C:/Users/Name/Documents/Vault`
  - Correct: `C:\\Users\\Name\\Documents\\Vault`
  - Wrong: `C:\Users\Name\Documents\Vault` (single backslashes need escaping in Python strings)

- **macOS/Linux**: Use forward slashes `/`
  - Correct: `/Users/name/Documents/Vault`

### Obsidian Directory Structure Requirements

Your Obsidian Vault should contain the following directory structure:

```
YourVault/
├── 10_Daily/                    # Daily recommendation notes (auto-created)
│   └── YYYY-MM-DD-paper-recommendations.md
├── 20_Research/
│   └── Papers/                  # Detailed paper notes directory
│       ├── LLM/
│       │   └── PaperTitle.md
│       │       └── images/      # Paper images
│       ├── Multimodal/
│       └── Agent/
└── 99_System/
    └── Config/
        └── research_interests.yaml  # Research interests config (copy config.yaml here)
```

## Usage

### Start Daily Paper Recommendations

Open a terminal in your Obsidian Vault directory and type:

```bash
start my day
```

This will:
1. Search for high-quality papers from the last month and past year
2. Filter and score based on your research interests
3. Generate a daily recommendation note (saved to `10_Daily/`)
4. Automatically generate detailed analysis for the top 3 papers
5. Extract paper images and insert them into notes
6. Automatically link keywords to existing notes

### Analyze a Single Paper

If you want to read a paper in depth:

```bash
paper-analyze 2602.12345
# Or use the paper title
paper-analyze "Paper Title"
```

This will:
1. Download the paper PDF
2. Extract images
3. Generate a detailed analysis note
4. Update the knowledge graph

### Extract Paper Images

```bash
extract-paper-images 2602.12345
```

### Search Existing Papers

```bash
paper-search "keywords"
```

## Directory Structure

```
evil-read-arxiv/
├── README.md                 # This file
├── QUICKSTART.md             # Quick start guide
├── config.example.yaml       # Config template (copy and modify)
├── requirements.txt          # Python dependencies
├── start-my-day/             # Daily recommendation skill
│   ├── SKILL.md              # Skill definition file
│   └── scripts/
│       ├── search_arxiv.py   # arXiv/Semantic Scholar search script
│       ├── scan_existing_notes.py  # Scan existing notes
│       └── link_keywords.py  # Keyword auto-linking script
├── paper-analyze/            # Paper analysis skill
│   ├── SKILL.md
│   └── scripts/
│       ├── generate_note.py  # Generate note template
│       └── update_graph.py   # Update knowledge graph
├── extract-paper-images/     # Image extraction skill
│   ├── SKILL.md
│   └── scripts/
│       └── extract_images.py # Image extraction script
├── paper-search/             # Paper search skill
│   └── SKILL.md
└── conf-papers/              # Top conference paper search skill
    ├── SKILL.md              # Skill definition file
    ├── conf-papers.yaml      # Independent config (keywords, conferences, years)
    └── scripts/
        └── search_conf_papers.py  # DBLP search + S2 supplement + scoring
```

## Scoring Mechanism

Paper recommendation scoring is based on four dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Relevance | 40% | Degree of match with research interests |
| Recency | 20% | Paper publication date |
| Popularity | 30% | Citation count / impact |
| Quality | 10% | Method quality inferred from abstract |

**Scoring Details**:
- **Relevance**: Title keyword match (+0.5 each), abstract keyword match (+0.3 each), category match (+1.0)
- **Recency**: Within 30 days (+3), 30-90 days (+2), 90-180 days (+1), over 180 days (0)
- **Popularity**: High-impact citations > 100 (+3), 50-100 (+2), < 50 (+1)
- **Quality**: Multi-dimensional metrics (strong innovation terms > weak innovation terms > method metrics > quantitative results > experimental metrics)

## Common arXiv Categories

| Category Code | Name | Description |
|---------------|------|-------------|
| cs.AI | Artificial Intelligence | AI |
| cs.LG | Learning | Machine Learning |
| cs.CL | Computation and Language | Computational Linguistics / NLP |
| cs.CV | Computer Vision | Computer Vision |
| cs.MM | Multimedia | Multimedia |
| cs.MA | Multiagent Systems | Multi-Agent Systems |
| cs.RO | Robotics | Robotics |

## FAQ

### Q: No search results?
A: Check the following:
1. Verify your network connection is working
2. Check that the keywords in your config file are correct
3. Try expanding the arXiv category scope

### Q: Image extraction failed?
A:
1. Make sure PyMuPDF is installed: `pip install PyMuPDF`
2. Check that the arXiv ID format is correct (e.g., 2602.12345)

### Q: Keyword auto-linking is inaccurate?
A: You can edit the `COMMON_WORDS` set in `start-my-day/scripts/link_keywords.py` to add words you don't want to be auto-linked.

### Q: "Papers directory not found" error?
A:
1. Check that the `OBSIDIAN_VAULT_PATH` environment variable is set correctly
2. Verify that the directory structure in your Obsidian Vault has been created correctly (20_Research/Papers/)

### Q: "Vault path not specified" error?
A: Set the `OBSIDIAN_VAULT_PATH` environment variable, or specify the path via `--vault` / `--config` arguments when calling scripts.

## Advanced Configuration

### Modify arXiv Search Categories

Specify categories via the `--categories` argument when calling `search_arxiv.py`:

```bash
python scripts/search_arxiv.py --categories "cs.AI,cs.LG,cs.CL,cs.CV"
```

### Modify Daily Recommendation Count

Specify the count via the `--top-n` argument when calling `search_arxiv.py`:

```bash
python scripts/search_arxiv.py --top-n 15
```

### Modify Scoring Weights

Adjust the weights in the `calculate_recommendation_score` function in `start-my-day/scripts/search_arxiv.py`.

## How It Works

```
User types "start my day"
         |
    1. Load research config
    2. Scan existing notes to build index
         |
    3. Search arXiv (last 30 days)
    4. Search Semantic Scholar (past year, high impact)
         |
    5. Merge results and deduplicate
    6. Comprehensive scoring and sorting
    7. Take top N papers
         |
    8. Generate daily recommendation note
    9. Generate detailed analysis for top 3
    10. Auto-link keywords
```

## Contributing

Issues and Pull Requests are welcome!

If you find this project helpful, please give it a Star to show your support!

[![Star History Chart](https://api.star-history.com/svg?repos=juliye2025/evil-read-arxiv&type=Date)](https://star-history.com/#juliye2025/evil-read-arxiv&Date)

## License

MIT License

## Acknowledgments

- [arXiv](https://arxiv.org/) - Open-access academic preprint platform
- [Semantic Scholar](https://www.semanticscholar.org/) - AI-powered academic research platform
- [Claude Code](https://claude.ai/claude-code) - AI-assisted code and writing tool
- [Obsidian](https://obsidian.md/) - Powerful knowledge management tool
