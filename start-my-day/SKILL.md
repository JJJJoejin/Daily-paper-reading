---
name: start-my-day
description: Paper reading workflow starter - Generate daily paper recommendations
---

# Language Setting

This skill supports both Chinese and English reports. The language is determined by the `language` field in your config file:

- **English (default)**: Set `language: "en"` in config
- **Chinese**: Set `language: "zh"` in config

The config file should be located at: `$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml`

## Language Detection

At the start of execution, read the config file to detect the language setting:

```bash
# Read language from config
LANGUAGE=$(grep -E "^\s*language:" "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml" | awk '{print $2}' | tr -d '"')

# Default to English if not set
if [ -z "$LANGUAGE" ]; then
    LANGUAGE="en"
fi
```

Then use this language setting throughout the workflow:
- When generating notes, pass `--language $LANGUAGE` to scripts
- Use appropriate section headers in the generated notes

---

You are the Daily Paper Workflow Starter for OrbitOS.

# Goal
Help users start their research day by searching for highly popular, trending, and high-quality papers from the past month and past year, then generate recommendation notes.

# Workflow

## Workflow Overview

This skill uses Python scripts to call the arXiv API to search for papers, parse XML results, and filter and score them based on research interests.

## Step 1: Collect Context (Silent)

1. **Get today's date**
   - Determine the current date (YYYY-MM-DD format)

2. **Read research configuration**
   - Read `$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml` (note: the filename is interests, not interest) to get research areas
   - Extract: keywords, categories, and priorities

3. **Scan existing notes to build an index**
   - Scan all `.md` files under the `20_Research/Papers/` directory
   - Extract note titles (from filenames and frontmatter title fields)
   - Build a keyword-to-note-path mapping table for subsequent auto-linking
   - Prefer the title field from frontmatter, then fall back to filenames

## Step 2: Search Papers

### 2.1 Search Scope

Search for recent papers across all relevant categories:

1. **Search scope**
   - Use `scripts/search_arxiv.py` to search arXiv
   - Query: all research-related arXiv categories
   - Sort by submission date
   - Limit results: 200 papers

2. **Filtering strategy**
   - Filter papers based on the research interest config file
   - Calculate a composite recommendation score
   - Keep the top 10 high-scoring papers

### 2.2 Execute Search and Filtering

Use the `scripts/search_arxiv.py` script to complete search, parsing, and filtering:

```bash
# Use Python script to search, parse, and filter arXiv papers
# First switch to the skill directory, then execute the script
cd "$SKILL_DIR"
python scripts/search_arxiv.py \
  --config "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml" \
  --output arxiv_filtered.json \
  --max-results 200 \
  --top-n 10 \
  --categories "cs.AI,cs.LG,cs.CL,cs.CV,cs.MM,cs.MA,cs.RO"
```

**Script functionality**:
1. **Search arXiv**
   - Call the arXiv API to search for papers in specified categories
   - Retrieve up to 200 latest papers

2. **Parse XML results**
   - Parse the XML returned by the API
   - Extract: ID, title, authors, abstract, publication date, categories

3. **Apply filtering and scoring**
   - Filter papers based on the research interest config file
   - Calculate composite recommendation score (relevance 40%, recency 20%, popularity 30%, quality 10%)
   - Sort by score, keep the top 10

**Output**:
- `arxiv_filtered.json` - Filtered paper list (JSON format)
- Each paper includes:
  - Paper ID, title, authors, abstract
  - Publication date, categories
  - Relevance score, recency score, popularity score, quality score
  - Final recommendation score, matched domain

## Step 3: Read Filtered Results

### 3.1 Read JSON Results

Read the filtered and scored paper list from `arxiv_filtered.json`:

```bash
# Read filtered results
cat arxiv_filtered.json
```

**Results include**:
- `total_found`: Total number of papers found
- `total_filtered`: Number of papers after filtering
- `top_papers`: Top 10 high-scoring papers, each containing:
  - Paper ID, title, authors, abstract
  - Publication date, categories
  - Relevance score, recency score, quality score
  - Final recommendation score, matched domain, matched keywords

### 3.2 Scoring Explanation

Composite scoring across multiple dimensions:

```yaml
Recommendation score =
  Relevance score: 40%
  Recency score: 20%
  Popularity score: 30%
  Quality score: 10%
```

**Scoring criteria**:

1. **Relevance score** (40%)
   - Degree of match with research interests
   - Title keyword match: +0.5 per match
   - Abstract keyword match: +0.3 per match
   - Category match: +1.0
   - Maximum score: ~3.0

2. **Recency score** (20%)
   - Within last 30 days: +3
   - 30-90 days: +2
   - 90-180 days: +1
   - Over 180 days: 0

3. **Popularity score** (30%)
   - (If data available) Citations > 100: +3
   - Citations 50-100: +2
   - Citations < 50: +1
   - No citation data: 0
   - Or inferred from time since publication (hot new papers within last 7 days): +2

4. **Quality score** (10%)
   - Inferred from abstract: Significant innovation: +3
   - Clear methodology: +2
   - General work: +1
   - Or read quality score from existing notes

**Final recommendation score** = Relevance(40%) + Recency(20%) + Popularity(30%) + Quality(10%)

## Step 4: Generate Daily Recommendation Notes

### 4.1 Read Filtered Results

Read the filtered paper list from `arxiv_filtered.json`:
- Contains the top 10 high-scoring papers
- Each paper includes complete information: ID, title, authors, abstract, scores, matched domain

### 4.2 Create Recommendation Note File

1. **Create recommendation note file**
   - Filename: `10_Daily/YYYY-MM-DD-paper-recommendations.md`
   - Must include properties:
     - `keywords`: Keywords from recommended papers (comma-separated, extracted from paper titles and abstracts)
     - `tags`: ["llm-generated", "daily-paper-recommend"]

2. **Check if paper is worth detailed coverage**
   - **Highly worth reading**: Recommendation score >= 7.5 or specially recommended papers
   - **General recommendation**: Other papers

3. **Check if paper already has notes**
   - Search the `20_Research/Papers/` directory
   - Check if detailed notes exist for the paper
   - If notes exist: Write briefly, reference existing notes
   - If no notes:
     - Highly worth reading: Write detailed section in recommendation notes
     - General recommendation: Write only basic information

### 4.2 Recommendation Note Structure

Note file structure:

```markdown
---
keywords: [keyword1, keyword2, ...]
tags: ["llm-generated", "daily-paper-recommend"]
---

[Paper recommendation list...]
```

#### 4.2.1 Today's Overview (placed before the paper list)

Before the paper list, add a "Today's Overview" section summarizing the overall situation of today's recommended papers:

```markdown
## Today's Overview

Today's {number of papers} recommended papers mainly focus on **{main research direction 1}**, **{main research direction 2}**, and **{main research direction 3}** and other frontier directions.

- **Overall trends**: {Summarize the overall research trends of today's papers, e.g., multimodal model reasoning capabilities, LLM efficient inference optimization, etc.}

- **Quality distribution**: Today's recommended papers score between {lowest score}-{highest score}, {overall quality assessment}.

- **Research hotspots**:
  - **{Hotspot 1}**: {Brief description}
  - **{Hotspot 2}**: {Brief description}
  - **{Hotspot 3}**: {Brief description}

- **Reading suggestions**: {Provide reading order suggestions, e.g., suggest reading a certain paper first to understand a direction, then focus on another paper's methods, etc.}
```

**Notes**:
- Summarize based on the titles, abstracts, and scores of the top 10 filtered papers
- Extract common research themes and trends
- Provide reasonable reading order suggestions

#### 4.2.2 Unified Format for All Papers

All papers listed in descending order by score, using a unified format

```markdown
### [[Paper Title]]
- **Authors**: [Author list]
- **Institution**: [Institution name]
- **Links**: [arXiv](link) | [PDF](link)
- **Source**: [arXiv]
- **Notes**: [[Existing note path]] or <<None>>

**One-line summary**: [One sentence summarizing the paper's core contribution]

**Core contributions/insights**:
- [Contribution 1]
- [Contribution 2]
- [Contribution 3]

**Key results**: [Most important results extracted from the abstract]

---
```

**Notes**:
- Paper titles use wikilink format: `[[Paper Title]]`
- For the top 3 papers, the paper title links to detailed reports
- For other papers, the paper title serves as a wikilink placeholder for future note creation

#### 4.2.3 Insert Images and Call Detailed Analysis for Top 3 Papers

For the top 3 papers (3 highest-scoring):

**Step 0: Check if paper already has notes**
```bash
# Search for existing notes in the 20_Research/Papers/ directory
# Search methods:
# 1. Search by paper ID (e.g., 2602.23351)
# 2. Search by paper title (fuzzy match)
# 3. Search by paper title keywords
```

**Step 1: Decide processing approach based on check results**

If notes already exist:
- Do not generate new detailed reports
- Use existing note path as wikilink
- Reference existing notes in the "Detailed report" field of recommendation notes
- Check if images need to be extracted (if no images directory or images directory is empty)
  - If images needed: Call `extract-paper-images`
  - If images exist: Use existing images

If no notes exist:
- Call `extract-paper-images` to extract images
- Call `paper-analyze` to generate detailed reports
- Add images and detailed report links in recommendation notes

**Step 2: Insert images and links in recommendation notes**

**If notes already exist**:
```markdown
### [[Existing Paper Title]]
- **Authors**: [Author list]
- **Institution**: [Institution name]
- **Links**: [arXiv](link) | [PDF](link)
- **Source**: [arXiv]
- **Detailed report**: [[Existing note path]]
- **Notes**: Existing detailed analysis available

**One-line summary**: [One sentence summarizing the paper's core contribution]

![Existing image|600](existing image path)

**Core contributions/insights**:
...
```

**If no notes exist**:
```markdown
### [[Paper Title]]
- **Authors**: [Author list]
- **Institution**: [Institution name]
- **Links**: [arXiv](link) | [PDF](link)
- **Source**: [arXiv]
- **Detailed report**: [[Detailed report path]] (auto-generated)

**One-line summary**: [One sentence summarizing the paper's core contribution]

![Newly extracted image|600](new image path)

**Core contributions/insights**:
...
```

**Image notes**:
- Image path: `20_Research/Papers/[paper category]/images/[paper ID]_fig1.png`
- Width set to 600px
- Automatically extracted, no manual operation needed

**Detailed report notes**:
- Report path: `20_Research/Papers/[paper category]/[note_filename].md`
- **Important**: Use the `note_filename` field from the JSON (not the original title) to construct the wikilink, ensuring consistency with the filename created by `generate_note.py`
  - Correct: `[[20_Research/Papers/LLM/Hypothesis-Conditioned_Query_Rewriting_for_Decision-Useful_Retrieval]]`
  - Incorrect: `[[20_Research/Papers/LLM/Hypothesis-Conditioned Query Rewriting for Decision-Useful Retrieval]]`
- Display the wikilink in the "Detailed report" field: `- **Detailed report**: [[20_Research/Papers/[domain]/[note_filename]]]`
- Detailed reports are auto-generated by `paper-analyze`, containing complete paper analysis

## Step 5: Auto-link Keywords (Optional)

After generating recommendation notes, auto-link keywords to existing notes:

```bash
# Step 1: Scan existing notes
cd "$SKILL_DIR"
python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# Step 2: Generate recommendation notes (normal flow)
# ... use search_arxiv.py to search papers ...

# Step 3: Link keywords (new step)
python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input 10_Daily/YYYY-MM-DD-paper-recommendations.md \
  --output 10_Daily/YYYY-MM-DD-paper-recommendations_linked.md
```

**Note**:
- The keyword linking script automatically skips frontmatter, heading lines, and code blocks
- Filters out common words (and, for, model, learning, etc.)
- Preserves existing wikilinks without modification

# Important Rules

- **Expanded search scope**: Search papers from the past month + past year popular papers
- **Composite recommendation score**: Combines relevance, recency, popularity, and quality dimensions
- **Filename starts with date**: Maintain `10_Daily/YYYY-MM-DD-paper-recommendations.md` format
- **Add Today's Overview**: Add a "## Today's Overview" section at the beginning of recommendation notes, summarizing the main research directions, overall trends, quality distribution, research hotspots, and reading suggestions
- **Sort by score**: All papers sorted by recommendation score in descending order
- **Special handling for top 3**:
  - Paper titles in wikilink format: `[[Paper Title]]`
  - Automatically extract and insert the first image
  - Automatically call `paper-analyze` to generate detailed reports
  - Display wikilink association in the "Detailed report" field
- **Other papers**: Write only basic information, no images
- **Stay fast**: Let users quickly understand daily recommendations
- **Avoid duplicates**: Check already recommended papers
- **Auto keyword linking**:
  - After generating recommendation notes, automatically scan existing notes
  - Replace keywords in text (e.g., BLIP, CLIP) with wikilinks
  - Example: `BLIP` -> `[[BLIP]]`
  - Preserve existing wikilinks without modification
  - Do not replace content in code blocks
  - Do not replace content that already has wikilinks (avoid duplication)

# Differences from Other Skills

## start-my-day (this skill)
- **Purpose**: Filter recommended papers from a broad search, generate daily recommendation notes
- **Search scope**: Past month + past year popular/quality papers
- **Content**: Recommendation list
  - Begins with "Today's Overview": Summarizes main research directions, overall trends, quality distribution, research hotspots, and reading suggestions
  - All papers in unified format
  - Special handling for top 3:
    - Paper titles in wikilink format: `[[Paper Title]]`
    - Automatically extract and insert the first image
    - Automatically call `paper-analyze` to generate detailed reports
    - Display wikilink association in the "Detailed report" field
- **Image handling**: Auto-extract and insert first image for top 3; no images for all papers
- **Detailed reports**: Auto-generated for top 3, not generated for other papers
- **Usage**: User triggers manually each day
- **Note references**: If paper already has notes, write briefly and reference; if analysis needs to reference historical notes, reference directly

## paper-analyze (deep analysis skill)
- **Purpose**: User actively views a single paper for in-depth research
- **Use case**: Papers the user wants to read but AI hasn't organized
- **Content**: Detailed paper deep analysis notes
  - Contains all core information: research questions, method overview, method architecture, key innovations, experimental results, deep analysis, related paper comparisons, etc.
  - **Richly illustrated**: All images from the paper should be used (core architecture diagrams, method diagrams, experimental result charts, etc.)
- **Usage**: User manually calls `/paper-analyze [paper ID]` or paper title
- **Important requirement**: Whether organized by start-my-day or actively viewed by user, should be richly illustrated

# Usage Instructions

When users type "start my day", execute the following steps:

**Date parameter support**:
- No parameter: Generate paper recommendation notes for today
- With parameter (YYYY-MM-DD): Generate paper recommendation notes for the specified date
  - Example: `/start-my-day 2026-02-27`

## Auto Execution Flow

1. **Get target date**
   - No parameter: Use current date (YYYY-MM-DD format)
   - With parameter: Use specified date

2. **Scan existing notes to build index**
   ```bash
   # Scan existing paper notes in the vault
   cd "$SKILL_DIR"
   python scripts/scan_existing_notes.py \
     --vault "$OBSIDIAN_VAULT_PATH" \
     --output existing_notes_index.json
   ```
   - Scan the `20_Research/Papers/` directory
   - Extract note titles and tags
   - Build keyword-to-note-path mapping table

3. **Search and filter arXiv papers**
   ```bash
   # Use Python script to search, parse, and filter arXiv papers
   # First switch to the skill directory, then execute the script
   # If there is a target date parameter (e.g., 2026-02-21), pass it to --target-date
   cd "$SKILL_DIR"
   python scripts/search_arxiv.py \
     --config "$OBSIDIAN_VAULT_PATH/99_System/Config/research_interests.yaml" \
     --output arxiv_filtered.json \
     --max-results 200 \
     --top-n 10 \
     --categories "cs.AI,cs.LG,cs.CL,cs.CV,cs.MM,cs.MA,cs.RO" \
     --target-date "{target date}"  # If user specified a date, replace with actual date
   ```

4. **Read filtered results**
   - Read filtered results from `arxiv_filtered.json`
   - Get top 10 high-scoring papers
   - Each paper includes: ID, title, authors, abstract, scores, matched domain

5. **Generate recommendation notes (with keyword linking)**
   - Create `10_Daily/YYYY-MM-DD-paper-recommendations.md` (using target date)
   - **Sort by score**: All papers sorted by recommendation score in descending order
   - **Special handling for top 3**:
     - Paper titles in wikilink format: `[[Paper Title]]`
     - Insert the actually extracted first image after "One-line summary"
     - Display wikilink association in the "Detailed report" field
   - **Other papers**: Write only basic information, no images
   - **Auto keyword linking** (Important!):
     - After generating notes, scan keywords in the text
     - Use `existing_notes_index.json` for matching
     - Replace keywords with wikilinks, e.g., `BLIP` -> `[[BLIP]]`
     - Preserve existing wikilinks without modification
     - Do not replace content in code blocks

6. **Execute deep analysis for top 3 papers**
   ```bash
   # For each of the top 3 papers, execute the following

   # Step 1: Check if paper already has notes
   # Search in the 20_Research/Papers/ directory
   # - Search by paper ID (e.g., 2602.23351)
   # - Search by paper title (fuzzy match)
   # - Search by paper title keywords (e.g., "Pragmatics", "Reporting Bias")

   # Step 2: Decide processing approach based on check results
   if notes_exist:
       # Do not generate new detailed reports
       # Use existing note path
       # Only extract images (if none exist)
   else:
       # Extract first image
       /extract-paper-images [paper ID]

       # Generate detailed analysis report
       /paper-analyze [paper ID]
   ```
   - **If notes already exist**:
     - Do not duplicate detailed report generation
     - Use existing note path as wikilink
     - Check if images need to be extracted (if no images directory or images directory is empty)
     - Reference existing notes in the "Detailed report" field of recommendation notes
   - **If no notes exist**:
     - Extract first image and save to vault
     - Generate detailed paper analysis report
     - Add images and detailed report links in recommendation notes

## Temporary File Cleanup

- Temporary XML and JSON files generated during search can be cleaned up
- After recommendation notes are saved to the vault, temporary files are no longer needed

## MCP Integration (Optional Enhancement)

If the `paper-db` MCP server is available, the workflow can use MCP tools for persistent storage and smarter recommendations:

**Enhanced workflow with MCP**:
1. `sync_vault_notes` — Scan vault and match notes to DB entries
2. `search_arxiv(days=30, max_results=200)` — Search arXiv and store in DB
3. `search_semantic_scholar(days=365, top_k=20)` — Search S2 hot papers and store in DB
4. `score_papers()` — Re-score all papers against current research interests
5. `get_recommendations(limit=10)` — Get top 10 unanalyzed papers
6. Generate recommendation notes (same format as above)
7. `record_event(paper_id=X, event_type="recommended", recommendation_rank=N)` — Log recommendations

**Benefits of MCP integration**:
- Papers persist across sessions (no re-searching)
- Deduplication across arXiv and S2 sources
- History tracking (what was recommended when)
- Structured queries for follow-up searches

The MCP tools complement but do not replace the existing Python scripts — the scripts handle direct API calls, while MCP tools handle storage and retrieval.

## Dependencies

- Python 3.x (for running search and filtering scripts)
- PyYAML (for reading the research interest config file)
- Network connection (accessing arXiv API)
- `20_Research/Papers/` directory (for scanning existing notes and saving detailed reports)
- `extract-paper-images` skill (for extracting paper images)
- `paper-analyze` skill (for generating detailed reports)
- `paper-db` MCP server (optional, for persistent paper database)

## Script Documentation

### search_arxiv.py

Located at `scripts/search_arxiv.py`, features include:

1. **Search arXiv**: Call arXiv API to retrieve papers
2. **Parse XML**: Extract paper information (ID, title, authors, abstract, etc.)
3. **Filter papers**: Filter based on the research interest config file
4. **Calculate scores**: Composite scoring across relevance, recency, quality, and other dimensions
5. **Output JSON**: Save filtered results to `arxiv_filtered.json`

### scan_existing_notes.py

Located at `scripts/scan_existing_notes.py`, features include:

1. **Scan notes directory**: Scan all `.md` files under `20_Research/Papers/`
2. **Extract note information**:
   - File path
   - Filename
   - Title field from frontmatter
   - Tags field
3. **Build index**: Create keyword-to-note-path mapping table
4. **Output JSON**: Save index to `existing_notes_index.json`

**Usage**:
```bash
cd "$SKILL_DIR"
python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json
```

**Output format**:
```json
{
  "notes": [
    {
      "path": "20_Research/Papers/Multimodal/BLIP_Bootstrapping-Language-Image-Pre-training.md",
      "filename": "BLIP_Bootstrapping-Language-Image-Pre-training.md",
      "title": "BLIP: Bootstrapping Language-Image Pre-training for Unified Vision-Language Understanding and Generation",
      "title_keywords": ["BLIP", "Bootstrapping", "Language-Image", "Pre-training", "Unified", "Vision-Language", "Understanding", "Generation"],
      "tags": ["Vision-Language-Pre-training", "Multimodal-Encoder-Decoder", "Bootstrapping", "Image-Captioning", "Image-Text-Retrieval", "VQA"]
    }
  ],
  "keyword_to_notes": {
    "blip": ["20_Research/Papers/Multimodal/BLIP_Bootstrapping-Language-Image-Pre-training.md"],
    "bootstrapping": ["20_Research/Papers/Multimodal/BLIP_Bootstrapping-Language-Image-Pre-training.md"],
    "vision-language": ["20_Research/Papers/Multimodal/BLIP_Bootstrapping-Language-Image-Pre-training.md"]
  }
}
```

### link_keywords.py

Located at `scripts/link_keywords.py`, features include:

1. **Read text**: Read the text content to be processed
2. **Read note index**: Load note mapping from `existing_notes_index.json`
3. **Replace keywords**: Find keywords in text and replace with wikilinks
   - Do not replace existing wikilinks (e.g., `[[BLIP]]`)
   - Do not replace content in code blocks
   - Matching rules:
     - Prefer matching complete title keywords
     - Then match keywords from tags
     - Case-insensitive matching
     - Filter common words (and, for, model, learning, etc.)
     - Skip frontmatter and heading lines
4. **Output result**: Output the processed text

**Usage**:
```bash
# First switch to the skill directory, then execute the script
cd "$SKILL_DIR"
python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input "input.txt" \
  --output "output.txt"
```

**Matching example**:
```
Original text:
"This paper uses BLIP and CLIP as baseline methods."

After processing:
"This paper uses [[BLIP]] and [[CLIP]] as baseline methods."
```

**Usage**:
```bash
# Step 1: Scan existing notes
cd "$SKILL_DIR"
python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# Step 2: Generate recommendation notes (normal flow)
# ... use search_arxiv.py to search papers ...

# Step 3: Link keywords (new step)
python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input 10_Daily/YYYY-MM-DD-paper-recommendations.md \
  --output 10_Daily/YYYY-MM-DD-paper-recommendations_linked.md
```

**Key features**:
- **Smart matching**: Case-insensitive matching
- **Protect existing links**: Do not replace existing wikilinks
- **Avoid code pollution**: Do not replace content in code blocks or inline code
- **Path encoding**: Use UTF-8 encoding to ensure correct paths
- **Skip sensitive areas**: Do not process frontmatter, heading lines, or code blocks

### Keyword Linking Implementation (New!)

**Feature overview**:
After generating daily recommendation notes, automatically scan existing notes and replace keywords in the text (e.g., BLIP, CLIP) with wikilinks (e.g., [[BLIP]]).

**Implementation flow**:
1. **Scan existing notes**: Scan the `20_Research/Papers/` directory
   - Extract note frontmatter (title, tags)
   - Extract keywords from titles (by separators and common affixes)
   - Extract keywords from tags (split by hyphens)
   - Build keyword-to-note-path mapping table

2. **Generate recommendation notes**: Generate recommendation note content normally

3. **Link keywords**: Process the generated notes
   - Find keywords in the text
   - Replace found keywords with wikilinks
   - Preserve existing wikilinks
   - Do not replace content in code blocks or inline code

**Usage**:
```bash
# Step 1: Scan existing notes
cd "$SKILL_DIR"
python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# Step 2: Generate recommendation notes (normal flow)
# ... use search_arxiv.py to search papers ...

# Step 3: Link keywords (new step)
python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input 10_Daily/YYYY-MM-DD-paper-recommendations.md \
  --output 10_Daily/YYYY-MM-DD-paper-recommendations_linked.md
```

**Key features**:
- **Smart matching**: Case-insensitive matching
- **Protect existing links**: Do not replace existing wikilinks
- **Avoid code pollution**: Do not replace content in code blocks or inline code
- **Path encoding**: Use UTF-8 encoding to ensure correct paths
