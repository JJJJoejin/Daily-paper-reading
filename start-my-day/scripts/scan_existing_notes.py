#!/usr/bin/env python3
"""
Scan existing notes and build index
Used by the start-my-day skill to scan existing notes in the vault and build a keyword-to-note-path mapping
"""

import os
import re
import json
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple
import yaml

from common_words import COMMON_WORDS

logger = logging.getLogger(__name__)


def parse_frontmatter(content: str) -> Dict:
    """
    Parse frontmatter (YAML format)

    Args:
        content: markdown file content

    Returns:
        frontmatter dictionary
    """
    # Find frontmatter start and end markers
    frontmatch = re.match(r'^---\s*\n(.*?)^---\s*\n', content, re.MULTILINE | re.DOTALL)

    if not frontmatch:
        return {}

    try:
        frontmatter_str = frontmatch.group(1)
        frontmatter_data = yaml.safe_load(frontmatter_str)
        return frontmatter_data or {}
    except Exception as e:
        logger.warning("Error parsing frontmatter: %s", e)
        return {}


def extract_keywords_from_title(title: str) -> List[str]:
    """
    Extract keywords from title

    Args:
        title: Paper title

    Returns:
        List of keywords
    """
    if not title:
        return []

    keywords = []

    # Primary strategy: extract paper abbreviations or proper nouns (capitalized words)
    # e.g.: extract "BLIP" from "BLIP: Bootstrapping..."
    main_keyword = re.match(r'^([A-Z]{2,})(?:\s*:|\s+)', title)
    if main_keyword:
        keywords.append(main_keyword.group(1))

    # Strategy 2: extract the full title before colon (if in abbreviation+colon format)
    colon_match = title.split(':')
    if len(colon_match) >= 2 and len(colon_match[0].strip()) > 2:
        before_colon = colon_match[0].strip()
        # Only add if length is between 3-20
        if 3 <= len(before_colon) <= 20:
            keywords.append(before_colon)

    # Strategy 3: extract hyphenated terms (e.g. Vision-Language, Fine-Tuning, In-Context)
    # Only match clear technical terms, avoid over-splitting
    tech_terms = re.findall(r'\b[A-Z][a-z]*(?:-[A-Z][a-z]*)+\b', title)
    for term in tech_terms:
        term_clean = term.strip()
        # Only add technical terms with length between 3-20
        if 3 <= len(term_clean) <= 20:
            # Filter out common words
            if term_clean.lower() not in COMMON_WORDS:
                keywords.append(term_clean)

    # Deduplicate
    keywords = list(dict.fromkeys(keywords))

    return keywords


def scan_notes_directory(papers_dir: Path) -> List[Dict]:
    """
    Scan all notes in the Papers directory

    Args:
        papers_dir: Path to the Papers directory

    Returns:
        List of notes
    """
    notes = []

    # Recursively find all .md files
    for md_file in papers_dir.rglob('*.md'):
        try:
            with open(md_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Parse frontmatter
            frontmatter = parse_frontmatter(content)

            # Extract information
            # Calculate path relative to vault (using forward slashes)
            rel_path = md_file.relative_to(papers_dir.parent.parent)
            note_info = {
                'path': str(rel_path).replace('\\', '/'),  # Use forward slashes
                'filename': md_file.name,
                'short_name': md_file.stem,  # Filename (without .md extension), used for short links
                'path_str': str(rel_path),  # String representation of path, used for correct encoding
                'title': frontmatter.get('title', md_file.stem),
                'tags': frontmatter.get('tags', []),
            }

            # Extract keywords from title
            title_keywords = extract_keywords_from_title(note_info['title'])
            note_info['title_keywords'] = title_keywords

            # Extract keywords from tags (keep meaningful tags)
            tag_keywords = []
            for tag in note_info['tags']:
                if isinstance(tag, list):
                    for sub_tag in tag:
                        if isinstance(sub_tag, str):
                            # Only add tags with length 3-20, filter common words
                            if 3 <= len(sub_tag) <= 20 and sub_tag.lower() not in COMMON_WORDS:
                                tag_keywords.append(sub_tag)
                elif isinstance(tag, str):
                    if 3 <= len(tag) <= 20 and tag.lower() not in COMMON_WORDS:
                        tag_keywords.append(tag)

            note_info['tag_keywords'] = tag_keywords

            notes.append(note_info)

        except Exception as e:
            logger.warning("Error reading %s: %s", md_file, e)
            continue

    return notes


def build_keyword_index(notes: List[Dict]) -> Dict[str, List[str]]:
    """
    Build a keyword-to-note-path mapping

    Args:
        notes: List of notes

    Returns:
        Keyword mapping dictionary
    """
    # Use set for deduplication, avoiding O(n) list-in operations
    keyword_sets: Dict[str, set] = {}

    def _add_keyword(keyword_lower: str, path: str):
        if 3 <= len(keyword_lower) <= 30 and keyword_lower not in COMMON_WORDS:
            if keyword_lower not in keyword_sets:
                keyword_sets[keyword_lower] = set()
            keyword_sets[keyword_lower].add(path)

    for note in notes:
        # Prioritize keywords extracted from title
        for keyword in note['title_keywords']:
            _add_keyword(keyword.lower(), note['path'])

        # Add keywords extracted from tags
        for keyword in note['tag_keywords']:
            _add_keyword(keyword.lower(), note['path'])

        # Use short name (filename) as keyword, but only add the main part
        if 'short_name' in note:
            short_name = note['short_name']
            # Remove version numbers and common suffixes
            clean_short = re.sub(r'(-\d{4}\.\d{4,5}|-v\d+)$', '', short_name)

            # If the cleaned short name has suitable length, add to index
            if 3 <= len(clean_short) <= 40 and clean_short.lower() not in COMMON_WORDS:
                _add_keyword(clean_short.lower(), note['path'])

    # Convert sets to lists for output
    keyword_index = {k: list(v) for k, v in keyword_sets.items()}
    return keyword_index


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Scan existing notes and build keyword index')
    parser.add_argument('--vault', type=str,
                        default=os.environ.get('OBSIDIAN_VAULT_PATH', ''),
                        help='Path to Obsidian vault (or set OBSIDIAN_VAULT_PATH env var)')
    parser.add_argument('--output', type=str, default='existing_notes_index.json',
                        help='Output JSON file path')
    parser.add_argument('--papers-dir', type=str,
                        default='20_Research/Papers',
                        help='Relative path to Papers directory')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    if not args.vault:
        logger.error("Vault path not specified. Please set it via --vault argument or OBSIDIAN_VAULT_PATH environment variable.")
        sys.exit(1)

    vault_path = Path(args.vault)
    papers_dir = vault_path / args.papers_dir

    if not papers_dir.exists():
        logger.error("Papers directory not found: %s", papers_dir)
        logger.error("Using vault path: %s", vault_path)
        sys.exit(1)

    logger.info("Scanning notes in: %s", papers_dir)

    notes = scan_notes_directory(papers_dir)
    logger.info("Found %d notes", len(notes))

    keyword_index = build_keyword_index(notes)
    logger.info("Built index with %d keywords", len(keyword_index))

    # Prepare output
    output = {
        'notes': notes,
        'keyword_to_notes': keyword_index
    }

    # Save results
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Index saved to: %s", args.output)

    logger.info("=== Keyword Index Statistics ===")
    logger.info("Total notes: %d", len(notes))
    logger.info("Total keywords: %d", len(keyword_index))

    if len(keyword_index) > 0:
        logger.info("=== Sample Keywords ===")
        sample_keywords = sorted(keyword_index.items())[:10]
        for keyword, paths in sample_keywords:
            logger.info("  %s: %d notes", keyword, len(paths))


if __name__ == '__main__':
    main()
