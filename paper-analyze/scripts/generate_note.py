#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian note generation script - correctly handles frontmatter format
Supports English and Chinese report generation
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_vault_path(cli_vault=None):
    """Get vault path from CLI argument or environment variable"""
    if cli_vault:
        return cli_vault
    env_path = os.environ.get('OBSIDIAN_VAULT_PATH')
    if env_path:
        return env_path
    logger.error("Vault path not specified. Please set it via --vault argument or OBSIDIAN_VAULT_PATH environment variable.")
    sys.exit(1)


def generate_note_content(paper_id, title, authors, domain, date, language="en"):
    """Generate Markdown content for the note"""

    # Domain tags mapping
    domain_tags_map = {
            "LLM": ["LLM", "Large Language Model"],
            "Multimodal": ["Multimodal", "Vision-Language"],
            "Agent": ["Agent", "Multi-Agent"],
            "Other": ["Paper Notes"],
    }
    tags = ["paper-notes"] + domain_tags_map.get(domain, [domain])
    tags_yaml = "\n".join(f'  - {tag}' for tag in tags)

    return f'''---
date: "{date}"
paper_id: "{paper_id}"
title: "{title}"
authors: "{authors}"
domain: "{domain}"
tags:
{tags_yaml}
quality_score: "[SCORE]/10"
related_papers: []
created: "{date}"
updated: "{date}"
status: analyzed
---

# {title}

## Core Information
- **Paper ID**: {paper_id}
- **Authors**: {authors}
- **Institution**: [Infer from authors or check paper]
- **Publication Date**: {date}
- **Conference/Journal**: [Infer from categories]
- **Links**: [arXiv](https://arxiv.org/abs/{paper_id}) | [PDF](https://arxiv.org/pdf/{paper_id})
- **Citations**: [If available]

## Research Problem
[Problem description and explanation]

## Method Overview

### Core Method

1. [Method 1]
   - [Detailed description]
   - [Key steps]
   - [Innovation points]

### Mathematical Formula (Markdown LaTeX)
- Use `$...$` for inline formulas
- Use `$$...$$` on a separate line for block formulas
- Inline example: The objective is $L(\\theta)$.
- Block example:
    $$\\theta^* = \\arg\\min_\\theta L(\\theta)$$

### Method Architecture
[Architecture description and image references]

### Key Innovations

1. [Innovation 1] - [Why important]
2. [Innovation 2] - [Why important]
3. [Innovation 3] - [Why important]

## Experimental Results

### Datasets
- [Dataset 1]: [Scale, characteristics]
- [Dataset 2]: [Scale, characteristics]

### Experimental Settings
- **Baseline Methods**: [List comparison methods]
- **Evaluation Metrics**: [List metrics]
- **Experimental Environment**: [Hardware, hyperparameters]

### Main Results
[Experimental results table and key findings]

## Deep Analysis

### Research Value
- **Theoretical Contribution**: [Theoretical contribution]
- **Practical Applications**: [Practical application value]
- **Field Impact**: [Potential impact on research field]

### Advantages
- [Advantage 1]
- [Advantage 2]
- [Advantage 3]

### Limitations
- [Limitation 1]
- [Limitation 2]
- [Limitation 3]

### Applicable Scenarios
- [Scenario 1]
- [Scenario 2]

## Comparison with Related Papers

### [[Related Paper 1]] - [Relationship]
- **Difference**: [How this method differs]
- **Improvement**: [Improvements compared to others]
- **Performance Comparison**: [If available]

### [[Related Paper 2]] - [Relationship]
[Similar format]

### [[Related Paper 3]] - [Relationship]
[Similar format]

## Technical Track Positioning

This paper belongs to [technical track], focusing on [specific sub-direction].

## Future Work Suggestions

1. [Author's suggestion 1]
2. [Author's suggestion 2]
3. [Extension suggestions based on analysis]

## My Comprehensive Evaluation

### Value Scoring
- **Overall Score**: [X.X/10]
- **Breakdown**:
  - Innovation: [X/10]
  - Technical Quality: [X/10]
  - Experiment Thoroughness: [X/10]
  - Writing Quality: [X/10]
  - Practicality: [X/10]

### Highlights
- [Highlight 1]
- [Highlight 2]
- [Highlight 3]

### Key Points to Focus On
- [Aspects that need special attention]

### Learnings
- [Techniques to learn from]
- [Methods to apply]
- [Inspiring ideas]

### Critical Thinking
- [Potential issues]
- [Areas for improvement]
- [Points of contention]

## My Notes

[Content to be added manually after reading]

## Related Papers
- [[Related Paper 1]] - [Relationship]
- [[Related Paper 2]] - [Relationship]
- [[Related Paper 3]] - [Relationship]

## External Resources
- [Paper links]
- [Code links (if available)]
- [Project homepage (if available)]
- [Related resources]
'''


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description='Generate paper analysis notes')
    parser.add_argument('--paper-id', type=str, default='[PAPER_ID]', help='Paper arXiv ID')
    parser.add_argument('--title', type=str, default='[Paper Title]', help='Paper title')
    parser.add_argument('--authors', type=str, default='[Authors]', help='Paper authors')
    parser.add_argument('--domain', type=str, default='Other', help='Paper domain')
    parser.add_argument('--vault', type=str, default=None, help='Obsidian vault path')
    parser.add_argument('--language', type=str, default='en', choices=['zh', 'en'], help='Language: zh (Chinese) or en (English)')
    args = parser.parse_args()

    vault_root = get_vault_path(args.vault)
    papers_dir = os.path.join(vault_root, "20_Research", "Papers")
    date = datetime.now().strftime("%Y-%m-%d")

    # Clean invalid characters from filename
    import re
    paper_title_safe = re.sub(r'[ /\\:*?"<>|]+', '_', args.title).strip('_')

    # Validate domain name, prevent path traversal
    domain = args.domain.strip('/\\').replace('..', '')
    if not domain:
        domain = 'Other'

    note_dir = os.path.join(papers_dir, domain)
    os.makedirs(note_dir, exist_ok=True)

    note_path = os.path.join(note_dir, f"{paper_title_safe}.md")
    content = generate_note_content(args.paper_id, args.title, args.authors, domain, date, args.language)

    try:
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except IOError as e:
        logger.error("Failed to write note: %s", e)
        sys.exit(1)

    print(f"Note generated: {note_path}")
    print("Please manually edit the note content, replacing placeholders with actual analysis results")


if __name__ == '__main__':
    main()
