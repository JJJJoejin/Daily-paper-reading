---
name: paper-analyze
description: Deep analyze a single paper, generate detailed notes with evaluation and images
allowed-tools: Read, Write, Bash, WebFetch
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
- Generate content in the appropriate language

---

You are the Paper Analyzer for OrbitOS.

# Goal
Perform deep analysis on a specific paper, generate comprehensive notes, evaluate quality and value, and update the knowledge base.

# Workflow

## Implementation Scripts

### Step 0: Initialize Environment

```bash
# Create working directory
mkdir -p /tmp/paper_analysis
cd /tmp/paper_analysis

# Set variables (read from environment variable OBSIDIAN_VAULT_PATH, or let user specify)
PAPER_ID="[PAPER_ID]"
VAULT_ROOT="${OBSIDIAN_VAULT_PATH}"
PAPERS_DIR="${VAULT_ROOT}/20_Research/Papers"
```

### Step 1: Identify Paper

### 1.1 Parse Paper Identifier

Accepted input formats:
- arXiv ID: "2402.12345"
- Full ID: "arXiv:2402.12345"
- Paper title: "Paper Title"
- File path: Direct path to existing note

### 1.2 Check Existing Notes

1. **Search for existing notes**
   - Search by arXiv ID in the `20_Research/Papers/` directory
   - Match by title
   - If found, read that note

2. **Read paper note**
   - If found, return full content

## Step 2: Get Paper Content

### 2.1 Download PDF and Extract Source

```bash
# Download PDF
curl -L "https://arxiv.org/pdf/[PAPER_ID]" -o /tmp/paper_analysis/[PAPER_ID].pdf

# Download source package (contains TeX and images)
curl -L "https://arxiv.org/e-print/[PAPER_ID]" -o /tmp/paper_analysis/[PAPER_ID].tar.gz
tar -xzf /tmp/paper_analysis/[PAPER_ID].tar.gz -C /tmp/paper_analysis/
```

### 2.2 Extract Paper Metadata

```bash
# Use curl to get arXiv page
curl -s "https://arxiv.org/abs/[PAPER_ID]" > /tmp/paper_analysis/arxiv_page.html

# Extract key information (using generic regex, applicable to any paper)
TITLE=$(grep -oP '<title>\K[^<]*' /tmp/paper_analysis/arxiv_page.html | head -1)
AUTHORS=$(grep -oP 'citation_author" content="\K[^"]*' /tmp/paper_analysis/arxiv_page.html | paste -sd ', ')
DATE=$(grep -oP 'citation_date" content="\K[^"]*' /tmp/paper_analysis/arxiv_page.html | head -1)
```

### 2.3 Read TeX Source Content

```bash
# Read each section's content
cat /tmp/paper_analysis/1-introduction.tex > /tmp/paper_analysis/intro.txt
cat /tmp/paper_analysis/2-joint-optimization.tex > /tmp/paper_analysis/methods.txt
cat /tmp/paper_analysis/3-agent-swarm.tex > /tmp/paper_analysis/agent_swarm.txt
cat /tmp/paper_analysis/5-eval.tex > /tmp/paper_analysis/eval.txt
```

## Step 2.1 Fetch from arXiv

1. **Get paper metadata**
   - Use WebFetch to access arXiv API
   - Query parameter: `id_list=[arXiv ID]`
   - Extract: title, authors, abstract, publication date, categories, links, PDF link

2. **Get PDF content and images**
   - Use WebFetch to get PDF
   - **Important**: Extract all images from the paper
   - Save images to `20_Research/Papers/[domain]/[paper title]/images/`
   - Generate image index: `images/index.md`

### 2.2 Fetch from Hugging Face (if applicable)

1. **Get paper details**
   - Use WebFetch to access Hugging Face
   - Extract: title, authors, abstract, tags, likes, downloads

## Step 3: Perform Deep Analysis

### 3.1 Analyze Abstract

1. **Extract key concepts**
   - Identify main research questions
   - List key terms and concepts
   - Note technical domain

2. **Summarize research objectives**
   - What problem is being solved?
   - What is the proposed solution approach?
   - What are the main contributions?

3. **Generate translation**
   - Translate the abstract into the target language fluently
   - Use appropriate technical terminology

### 3.2 Analyze Methodology

1. **Identify core methods**
   - Main algorithms or methods
   - Technical innovation points
   - Differences from existing methods

2. **Analyze method structure**
   - Method components and their relationships
   - Data flow or processing pipeline
   - Key parameters or configurations

3. **Evaluate method novelty**
   - What makes this method unique?
   - How does it compare to existing methods?
   - What are the key innovations?

### 3.3 Analyze Experiments

1. **Extract experimental setup**
   - Datasets used
   - Comparison baselines
   - Evaluation metrics
   - Experimental environment

2. **Extract results**
   - Key performance numbers
   - Comparison with baselines
   - Ablation studies (if any)

3. **Evaluate experimental rigor**
   - Are experiments comprehensive?
   - Are evaluations fair?
   - Are baselines appropriate?

### 3.4 Generate Insights

1. **Research value**
   - Theoretical contributions
   - Practical applications
   - Domain impact

2. **Limitations**
   - Limitations mentioned in the paper
   - Potential weaknesses
   - What assumptions may not hold?

3. **Future work**
   - Follow-up research suggested by authors
   - What are natural extensions?
   - What improvements are possible?

4. **Comparison with related work**
   - Search for related historical papers
   - How does it compare with similar papers?
   - What gap does it fill?
   - Which research lineage does it belong to?

### 3.5 Formula Output Standards (Markdown LaTeX)

1. **Unified format**
   - Inline formulas use `$...$`
   - Block-level formulas use `$$...$$` on separate lines

2. **Avoid non-renderable syntax**
   - Do not wrap formulas that need rendering in triple-backtick code blocks
   - Do not use plain-text pseudo-formulas instead of LaTeX

3. **Recommended syntax**
   - Inline example: The model objective is to minimize `$L(\theta)$`
   - Block-level example:
     `$$\theta^* = \arg\min_\theta L(\theta)$$`

4. **Complex formulas**
   - Multi-line or derivation formulas uniformly use block-level `$$...$$`
   - Keep symbols consistent with the original paper, avoid rewriting symbol semantics

## Step 3: Copy Images and Generate Index

```bash
# Copy figures directory to target location
cp /tmp/paper_analysis/*.{pdf,png,jpg,jpeg} "PAPERS_DIR/[DOMAIN]/[PAPER_TITLE]/images/" 2>/dev/null

# List copied content
ls "PAPERS_DIR/[DOMAIN]/[PAPER_TITLE]/images/"
```

## Step 4: Generate Comprehensive Paper Notes

### 4.1 Determine Note Path and Domain

```bash
# Determine domain based on paper content (Agent/LLM/Multimodal/Reinforcement_Learning_LLM_Agent, etc.)
# Inference rules:
# - If mentions "agent/swarm/multi-agent/orchestration" -> Agent
# - If mentions "vision/visual/image/video" -> Multimodal
# - If mentions "reinforcement learning/RL" -> Reinforcement_Learning_LLM_Agent
# - If mentions "language model/LLM/MoE" -> LLM
# - Otherwise -> Other

PAPERS_DIR="${VAULT_ROOT}/20_Research/Papers"
DOMAIN="[inferred domain]"
PAPER_TITLE="[paper title, spaces replaced with underscores]"
NOTE_PATH="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}.md"
IMAGES_DIR="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}/images"
INDEX_PATH="${IMAGES_DIR}/index.md"
```

### 4.2 Use Python to Generate Notes (Correctly Handle Obsidian Format)

```bash
# Call external script to generate notes
python "scripts/generate_note.py" --paper-id "[PAPER_ID]" --title "[paper title]" --authors "[authors]" --domain "[domain]" --language "$LANGUAGE"
```

### 4.3 Use obsidian-markdown Skill to Generate Final Notes

After analysis is complete, call the obsidian-markdown skill to ensure correct formatting, then manually supplement detailed content.

## Step 5: Update Knowledge Graph

### 5.1 Read Existing Graph

```bash
GRAPH_PATH="${PAPERS_DIR}/../PaperGraph/graph_data.json"
cat "$GRAPH_PATH" 2>/dev/null || echo "{}"
```

### 5.2 Generate Graph Nodes and Edges

```bash
# Call external script to update knowledge graph
python "scripts/update_graph.py" --paper-id "[PAPER_ID]" --title "[paper title]" --domain "[domain]" --score [score] --language "$LANGUAGE"
```

## Step 4: Generate Comprehensive Paper Notes

### 4.1 Note Structure

```markdown
---
date: "YYYY-MM-DD"
paper_id: "arXiv:XXXX.XXXXX"
title: "Paper Title"
authors: "Author List"
domain: "[Domain Name]"
tags:
  - paper-notes
  - [domain tag]
  - [method-tag-no-spaces]  # Tag names cannot have spaces, replace spaces with -

# Tag name format rules
# Obsidian tag names cannot contain spaces; use hyphens (-) to connect words
# Examples:
#   "Agent Swarm" -> "Agent-Swarm"
#   "Visual Agentic" -> "Visual-Agentic"
#   "MoonViT-3D" -> "MoonViT-Three-D"
#
# Python script (scripts/generate_note.py) automatically handles spaces in tag names
# Applies tag.replace(' ', '-') to remove spaces
  - [related paper 1]    <- Add related papers in tags
  - [related paper 2]    <- Add related papers in tags
quality_score: "[X.X]/10"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
status: analyzed
---

# [Paper Title]

## Core Information
- **Paper ID**: arXiv:XXXX.XXXXX
- **Authors**: [Author1, Author2, Author3]
- **Institution**: [Inferred from authors or from paper]
- **Publication date**: YYYY-MM-DD
- **Conference/Journal**: [Inferred from categories]
- **Links**: [arXiv](link) | [PDF](link)
- **Citations**: [If available]

## Abstract

### English Abstract
[Original English abstract of the paper]

### Translated Abstract
[Translate the abstract fluently into the target language, maintaining accuracy of academic terminology]

### Key Points
- **Research background**: [Current state and existing problems in this research area]
- **Research motivation**: [Why this research was conducted]
- **Core method**: [One sentence summarizing the main method]
- **Main results**: [Most important experimental results]
- **Research significance**: [Contribution of this research to the field]

## Research Background and Motivation

### Current State of the Field
[Detailed description of the current development status of this research area]

### Limitations of Existing Methods
[In-depth analysis of problems with existing methods:]

### Research Motivation
[Explain why this research is needed:]

## Research Questions

### Core Research Questions
[Clearly and accurately describe the core problems the paper aims to solve]

## Method Overview

### Core Idea
[Explain the core idea of the method in accessible language, understandable to non-experts]

### Method Framework

#### Overall Architecture
[Describe the overall architecture of the method, including main components and their relationships]

**Architecture diagram selection principles**:
1. **Prefer existing figures from the paper** - If the paper PDF has architecture/flow/method diagrams, insert directly
2. **Create Canvas only when no figures exist** - Only use JSON Canvas to draw when the paper lacks suitable architecture diagrams

**Method 1: Insert figure from the paper (preferred)**
```
![Architecture diagram|800](images/pageX_figY.pdf)

> Figure 1: [Architecture description, including the meaning of each part and their relationships]
```
**Note**: Image filenames must match actual filenames (images extracted from arXiv are usually in `.pdf` format)

**Method 2: Create Canvas architecture diagram (when paper has no figures)**
Call the `json-canvas` skill to create a `.canvas` file, then embed:
```
![[Paper_Title_Architecture.canvas|1200|400]]
```

Canvas creation steps:
1. Call `json-canvas` skill
2. Use `--create --file "path/architecture.canvas"` parameters
3. Create nodes and connections, using different colors for hierarchy
4. Save and embed reference in markdown

**Text diagram example** (last resort when images or Canvas cannot be used):
```
Input -> [Module 1] -> [Module 2] -> [Module 3] -> Output
          |             |             |
        [Sub-module]  [Sub-module]  [Sub-module]
```

#### Detailed Module Descriptions

**Module 1: [Module Name]**
- **Function**: [Main function of this module]
- **Input**: [Input data/information]
- **Output**: [Output data/information]
- **Processing flow**:
  1. [Step 1 detailed description]
  2. [Step 2 detailed description]
  3. [Step 3 detailed description]
- **Key technology**: [Key technology or algorithm used]
- **Mathematical formula**: [If there are important formulas]
   Inline example: The loss function is $L(\theta)$.
   Block-level example:
   $$\theta^* = \arg\min_\theta L(\theta)$$

**Module 2: [Module Name]**
- **Function**: [Main function of this module]
- **Input**: [Input data/information]
- **Output**: [Output data/information]
- **Processing flow**:
  1. [Step 1 detailed description]
  2. [Step 2 detailed description]
  3. [Step 3 detailed description]
- **Key technology**: [Key technology or algorithm used]

**Module 3: [Module Name]**
[Similar format]

### Method Architecture Diagram
[Choose the most suitable way to present the architecture]

**Selection principles**:
1. **Prefer architecture diagrams from the paper** - If the paper has suitable method architecture, flow, or system diagrams, insert directly
2. **Create Canvas only when no figures exist** - Only use JSON Canvas to draw when the paper lacks related architecture diagrams

**Method 1: Insert figure from the paper (preferred)**
```
![Architecture diagram|800](images/pageX_figY.pdf)

> Figure 1: [Architecture description, including the meaning of each part and their relationships]
```
**Note**: Image filenames must match actual filenames (images extracted from arXiv are usually in `.pdf` format)

**Method 2: Create Canvas architecture diagram (when paper has no figures)**
```
![[Paper_Title_Architecture.canvas|1200|400]]
```
Call `json-canvas` skill to create, supports:
- Colored nodes (colors 1-6 or custom hex)
- Labeled arrow connections
- Node grouping and hierarchy
- Markdown text rendering

**Note**: Canvas is only supplementary; do not replace the paper's original architecture diagrams. Paper figures are usually more accurate and authoritative.

## Experimental Results

### Experimental Objectives
[What this experiment aims to verify]

### Datasets

#### Dataset Statistics

| Dataset | Samples | Feature Dimensions | Classes | Data Type |
|---------|---------|-------------------|---------|-----------|
| Dataset 1 | X0,000 | Y-dim | Z classes | [Type] |
| Dataset 2 | X0,000 | Y-dim | Z classes | [Type] |

### Experimental Setup

#### Baselines
[List all comparison baselines and briefly explain each]


#### Evaluation Metrics
[List all evaluation metrics and explain the meaning of each]


#### Experimental Environment

#### Hyperparameter Settings


### Main Results

#### Main Experimental Results

| Method | Dataset1-Metric1 | Dataset1-Metric2 | Dataset2-Metric1 | Dataset2-Metric2 | Avg Rank |
|--------|-------------------|-------------------|-------------------|-------------------|----------|
| Baseline 1 | X.X+/-Y.Y | X.X+/-Y.Y | X.X+/-Y.Y | X.X+/-Y.Y | N |
| Baseline 2 | X.X+/-Y.Y | X.X+/-Y.Y | X.X+/-Y.Y | X.X+/-Y.Y | N |
| Baseline 3 | X.X+/-Y.Y | X.X+/-Y.Y | X.X+/-Y.Y | X.X+/-Y.Y | N |
| **Proposed Method** | **X.X+/-Y.Y** | **X.X+/-Y.Y** | **X.X+/-Y.Y** | **X.X+/-Y.Y** | **N** |

> Note: Numbers after +/- indicate standard deviation, **bold** indicates best results

#### Results Analysis
[Detailed analysis of main experimental results]

### Ablation Studies

#### Experimental Design
[Design rationale for ablation studies]

#### Ablation Results and Analysis

### Experimental Result Figures
[Insert experimental result figures from the paper]

![Experimental results|800](images/experimental_results.pdf)

> Figure 2: [Figure description]
**Note**: Image filenames must match actual filenames (images extracted from arXiv are usually in `.pdf` format)

## Deep Analysis

### Research Value Assessment

#### Theoretical Contributions
- **Contribution 1**: [Detailed description of theoretical contribution]
  - Innovation: [New theory/new method/new perspective]
  - Academic value: [Value to academia]
  - Impact scope: [Research fields impacted]

- **Contribution 2**: [Detailed description of theoretical contribution]
  [Similar format]

#### Practical Application Value
- **Application scenario 1**: [Application scenario description]
  - Applicability: [Applicability of this method in this scenario]
  - Advantages: [Advantages over existing solutions]
  - Potential impact: [Possible impact]

- **Application scenario 2**: [Application scenario description]
  [Similar format]

#### Domain Impact
- **Short-term impact**: [Near-term possible impact]
- **Medium-term impact**: [Medium-term possible impact]
- **Long-term impact**: [Long-term possible impact]
- **Potential transformation**: [Possible paradigm shifts]

### Method Advantages Detailed

#### Advantage 1: [Advantage Name]
- **Description**: [Detailed description of this advantage]
- **Technical basis**: [Technical foundation of this advantage]
- **Experimental validation**: [How experiments validate this advantage]
- **Comparative analysis**: [Degree of advantage over existing methods]

#### Advantage 2: [Advantage Name]
[Similar format]

#### Advantage 3: [Advantage Name]
[Similar format]

### Limitations Analysis

#### Limitation 1: [Limitation Name]
- **Description**: [Detailed description of this limitation]
- **Manifestation**: [How it manifests in practice]
- **Root cause**: [Root cause of this limitation]
- **Impact**: [Impact on practical applications]
- **Possible solutions**: [How to mitigate or resolve]

#### Limitation 2: [Limitation Name]
[Similar format]

#### Limitation 3: [Limitation Name]
[Similar format]

### Scenario Analysis

#### Applicable Scenarios
- **Scenario 1**: [Scenario description]
  - Reason for applicability: [Why it's applicable]
  - Expected effect: [Expected achievable results]
  - Notes: [What to pay attention to when using]

- **Scenario 2**: [Scenario description]
  [Similar format]

#### Non-applicable Scenarios
- **Scenario 1**: [Scenario description]
  - Reason for non-applicability: [Why it's not applicable]
  - Alternative: [Suggested alternative approach]

- **Scenario 2**: [Scenario description]
  [Similar format]

## Comparison with Related Papers

### Basis for Selecting Comparison Papers
[Why these papers were selected for comparison]

### [[Related Paper 1]] - [Paper Title]

#### Basic Information
- **Authors**: [Authors]
- **Publication date**: [Date]
- **Conference/Journal**: [Venue]
- **Core method**: [One sentence summary]

#### Method Comparison
| Comparison Dimension | Related Paper 1 | Proposed Method |
|---------------------|-----------------|-----------------|
| Core idea | [Description] | [Description] |
| Technical approach | [Description] | [Description] |
| Key components | [Description] | [Description] |
| Innovation degree | [Description] | [Description] |

#### Performance Comparison
| Dataset | Metric | Related Paper 1 | Proposed Method | Improvement |
|---------|--------|-----------------|-----------------|-------------|
| Dataset 1 | Metric 1 | X.X | Y.Y | +Z.Z% |
| Dataset 2 | Metric 2 | X.X | Y.Y | +Z.Z% |

#### Relationship Analysis
- **Relationship type**: [Improvement/Extension/Comparison/Follow-up]
- **Improvements in this paper**: [Improvements over that paper]
- **Advantages**: [Advantages of the proposed method]
- **Disadvantages**: [Disadvantages of the proposed method]
- **Complementarity**: [Whether the two methods are complementary]

### [[Related Paper 2]] - [Paper Title]
[Similar format]

### [[Related Paper 3]] - [Paper Title]
[Similar format]

### Comparison Summary
[Summary of all comparison papers]

## Technical Lineage Positioning

### Technical Lineage
This paper belongs to [technical lineage name], whose core characteristics are:
- Characteristic 1: [Description]
- Characteristic 2: [Description]
- Characteristic 3: [Description]

### Technical Lineage Development History
```
[Milestone 1] -> [Milestone 2] -> [Milestone 3] -> [This work] -> [Future direction]
   ^               ^               ^               ^
 [Paper A]       [Paper B]       [Paper C]      [This paper]
```

### Position of This Paper in the Technical Lineage
- **Builds upon**: [What prior work it inherits]
- **Enables**: [What foundation it provides for future work]
- **Key node**: [Why it is a key node in the technical lineage]

### Specific Sub-direction
This paper mainly focuses on [specific sub-direction], whose research focus is:
- Focus 1: [Description]
- Focus 2: [Description]

### Related Work Map
[Represent relationships with related work using text or diagrams]

## Future Work Suggestions

### Future Work Suggested by Authors
1. **Suggestion 1**: [Author's suggestion]
   - Feasibility: [Whether feasible]
   - Value: [Potential value]
   - Difficulty: [Implementation difficulty]

2. **Suggestion 2**: [Author's suggestion]
   [Similar format]

### Future Directions Based on Analysis
1. **Direction 1**: [Direction description]
   - Motivation: [Why this direction is worth researching]
   - Possible methods: [Possible research methods]
   - Expected outcomes: [Possible achievements]
   - Challenges: [Challenges faced]

2. **Direction 2**: [Direction description]
   [Similar format]

3. **Direction 3**: [Direction description]
   [Similar format]

### Improvement Suggestions
[Specific improvement suggestions for the proposed method]
1. **Improvement 1**: [Improvement description]
   - Current problem: [Existing problem]
   - Improvement plan: [How to improve]
   - Expected effect: [Expected achievable results]

2. **Improvement 2**: [Improvement description]
   [Similar format]

## My Overall Assessment

### Value Score

#### Overall Score
**[X.X]/10** - [Brief scoring rationale]

#### Dimension Scores

| Scoring Dimension | Score | Rationale |
|-------------------|-------|-----------|
| Innovation | [X]/10 | [Detailed rationale] |
| Technical quality | [X]/10 | [Detailed rationale] |
| Experimental sufficiency | [X]/10 | [Detailed rationale] |
| Writing quality | [X]/10 | [Detailed rationale] |
| Practicality | [X]/10 | [Detailed rationale] |

### Key Focus Areas

#### Technical points worth noting

#### Sections requiring deeper understanding

## My Notes

%% Users can add personal reading notes here %%

## Related Papers

### Directly Related
- [[Related Paper 1]] - [Relationship description: improvement/extension/comparison, etc.]
- [[Related Paper 2]] - [Relationship description]

### Background Related
- [[Background Paper 1]] - [Relationship description]
- [[Background Paper 2]] - [Relationship description]

### Follow-up Work
- [[Follow-up Paper 1]] - [Relationship description]
- [[Follow-up Paper 2]] - [Relationship description]

## External Resources
[List relevant videos, blogs, projects, and other links]

> [!tip] Key Insight
> [The most important insight from the paper, summarize the core idea in one sentence]

> [!warning] Notes
> - [Note 1]
> - [Note 2]
> - [Note 3]

> [!success] Recommendation Index
> [Recommendation index and brief rationale, e.g., Highly recommended! This is a milestone paper in the XX field]
```

## Step 5: Update Knowledge Graph

### 5.1 Add or Update Node

1. **Read graph data**
   - File path: `$OBSIDIAN_VAULT_PATH/20_Research/PaperGraph/graph_data.json`

2. **Add or update this paper's node**
   - Include analysis metadata:
     - quality_score
     - tags
     - domain
     - analyzed: true

3. **Create edges to related papers**
   - For each related paper, create an edge
   - Edge types:
     - `improves`: Improvement relationship
     - `related`: General relationship
   - Weight: Based on similarity (0.3-0.8)

4. **Update timestamp**
   - Set `last_updated` to current date

5. **Save graph**
   - Write updated graph_data.json

## Step 6: Display Analysis Summary

### 6.1 Output Format

```markdown
## Paper Analysis Complete!

**Paper**: [[Paper Title]] (arXiv:XXXX.XXXXX)

**Analysis status**: Detailed notes generated
**Note location**: [[20_Research/Papers/domain/YYYY-MM-DD-arXiv-ID.md]]

---

**Overall score**: [X.X/10]

**Dimension scores**:
- Innovation: [X/10]
- Technical quality: [X/10]
- Experimental sufficiency: [X/10]
- Writing quality: [X/10]
- Practicality: [X/10]

**Highlights**:
- [Highlight 1]
- [Highlight 2]
- [Highlight 3]

**Main advantages**:
- [Advantage 1]
- [Advantage 2]

**Main limitations**:
- [Limitation 1]
- [Limitation 2]

**Related papers** (N papers):
- [[Related Paper 1]] - [Relationship]
- [[Related Paper 2]] - [Relationship]
- [[Related Paper 3]] - [Relationship]

**Technical lineage**:
This paper belongs to [technical lineage], mainly focusing on [sub-direction].

---

**Quick actions**:
- Click the note link to view detailed analysis
- Use `/paper-search` to search for more related papers
- Open Graph View to see paper relationships
- Decide whether to dive deeper or skip based on the analysis

**Suggestions**:
- [Specific suggestion based on analysis 1]
- [Specific suggestion based on analysis 2]
```

## Important Rules

- **Preserve user's existing notes** - Do not overwrite manual notes
- **Use comprehensive analysis** - Cover methodology, experiments, value assessment
- **Provide content in the configured language** - Translations and explanations in the configured language
- **Reference related work** - Establish connections to existing knowledge base
- **Objective scoring** - Use consistent scoring criteria
- **Update knowledge graph** - Maintain relationships between papers
- **Richly illustrated** - Use all images from the paper (core architecture diagrams, method diagrams, experimental result charts, etc.)
- **Handle errors gracefully** - If one source fails, continue
- **Manage token usage** - Comprehensive but within token limits

## Scoring Criteria

### Scoring Scale (0-10)

**Innovation**:
- 9-10: Novel breakthrough, new paradigm
- 7-8: Significant improvement or combination
- 5-6: Minor contribution, known or established
- 3-4: Incremental improvement
- 1-2: Known or established

**Technical quality**:
- 9-10: Rigorous methodology, sound approach
- 7-8: Good methodology, minor issues
- 5-6: Acceptable methodology, some issues
- 3-4: Problematic methodology, poor approach
- 1-2: Poor methodology

**Experimental sufficiency**:
- 9-10: Comprehensive experiments, strong baselines
- 7-8: Good experiments, adequate baselines
- 5-6: Acceptable experiments, partial baselines
- 3-4: Limited experiments, poor baselines
- 1-2: Poor experiments or no baselines

**Writing quality**:
- 9-10: Clear, well-organized
- 7-8: Generally clear, minor issues
- 5-6: Understandable, partially unclear
- 3-4: Difficult to understand, confusing
- 1-2: Poor writing

**Practicality**:
- 9-10: High practical impact, directly applicable
- 7-8: Good practical potential
- 5-6: Moderate practical value
- 3-4: Limited practicality, theoretical only
- 1-2: Low practicality, theoretical only

### Relationship Type Definitions

- `improves`: Clear improvement over related work
- `extends`: Extends or builds on related work
- `compares`: Direct comparison, may be better/worse in certain aspects
- `follows`: Follow-up work in the same research lineage
- `cites`: Citation (if citation data available)
- `related`: General conceptual relationship
```

## Error Handling

- **Paper not found**: Check ID format, suggest searching
- **arXiv down**: Use cache or retry later, note limitations in output
- **PDF parsing failed**: Fall back to abstract, note limitations
- **Related papers not found**: Note lack of context
- **Graph update failed**: Continue without updating graph

## Usage Instructions

When users call `/paper-analyze [paper ID]`:

### Quick Execution (Recommended)

Use the following bash script for one-click full workflow execution:

```bash
#!/bin/bash

# Variable setup
PAPER_ID="$1"
TITLE="${2:-Pending Title}"
AUTHORS="${3:-Kimi Team}"
DOMAIN="${4:-Other}"

# Execute full workflow
python "scripts/generate_note.py" --paper-id "$PAPER_ID" --title "$TITLE" --authors "$AUTHORS" --domain "$DOMAIN" --language "$LANGUAGE" --language "$LANGUAGE" || \
    echo "Note generation script execution failed"

# Extract images
# Call extract-paper-images skill
# /extract-paper-images "$PAPER_ID" "$DOMAIN" "$TITLE" || \
#     echo "Image extraction failed"
```

### Manual Step-by-step Execution (For Debugging)

#### Step 0: Initialize environment
```bash
# Create working directory
mkdir -p /tmp/paper_analysis
cd /tmp/paper_analysis
```

#### Step 1: Identify paper
```bash
# Search for existing notes
find "${VAULT_ROOT}/20_Research/Papers" -name "*${PAPER_ID}*" -type f
```

#### Step 2: Get paper content
```bash
# Download PDF and source (see steps 2.1, 2.2, 2.3)

# Or read from existing data
cat /tmp/paper_analysis/{1-introduction,2-joint-optimization,3-agent-swarm,5-eval}.tex
```

#### Step 3: Copy images
```bash
# Use extract-paper-images skill
/extract-paper-images "$PAPER_ID" "$DOMAIN" "$TITLE"
```

#### Step 4: Generate notes
```bash
# Use external script to generate notes
python "scripts/generate_note.py" --paper-id "$PAPER_ID" --title "$TITLE" --authors "$AUTHORS" --domain "$DOMAIN" --language "$LANGUAGE"
```

#### Step 5: Update graph
```bash
# Use external script to update knowledge graph
python "scripts/update_graph.py" --paper-id "$PAPER_ID" --title "$TITLE" --domain "$DOMAIN" --score 8.8 --language "$LANGUAGE"
```

#### Step 6: Use obsidian-markdown skill to fix formatting

After analysis is complete, call `/obsidian-markdown` to ensure frontmatter format is correct, then manually supplement detailed content.

### Complete Workflow Examples

**Scenario 1: Analyze arXiv paper (with network access)**
```bash
# One-click execution
bash run_full_analysis.sh 2602.02276 "Kimi K2.5: Visual Agentic Intelligence" "Kimi Team" "Agent"
```

**Scenario 2: Analyze local PDF (without network access)**
```bash
# Manually upload PDF
cp /path/to/local.pdf /tmp/paper_analysis/[ID].pdf

# Execute analysis (skip step 2 download)
python3 run_paper_analysis.py [ID] [TITLE] [AUTHORS] [DOMAIN] --local-pdf /tmp/paper_analysis/[ID].pdf
```

### Notes

1. **Frontmatter format (important)**: All string values must be wrapped in double quotes
   ```yaml
   ---
   date: "YYYY-MM-DD"
   paper_id: "arXiv:XXXX.XXXXX"
   title: "Paper Title"
   authors: "Author List"
   domain: "[Domain Name]"
   quality_score: "[X.X]/10"
   created: "YYYY-MM-DD"
   updated: "YYYY-MM-DD"
   status: analyzed
   ---
   ```
   **Obsidian has strict YAML format requirements; missing quotes will cause frontmatter display issues!**

2. **Image paths**: Use relative paths `images/xxx` (do not specify extension, Obsidian auto-detects)
   - **Important**: Images extracted from arXiv are usually in `.pdf` format; Obsidian can display PDF images directly
   - Image paths should use actual filenames, e.g., `images/loss_curve.pdf` or `images/figure1.png`
3. **Wikilinks**: Use `[[Paper Name]]` format
4. **Domain inference**: Automatically inferred based on paper content
5. **Related papers**: Reference `[[Related Paper]]` in notes; the graph will automatically create edges

## Important Rules

## Key Features

**Richly illustrated**: Use all images from the paper
- **Save to correct location**: `20_Research/Papers/[domain]/[paper title]/images/`
- **Image index**: Generate `images/index.md` indexing all images
- **Difference from start-my-day**: paper-analyze is for deep analysis of a single paper
- **Comprehensive analysis**: Include all sections, richly illustrated
