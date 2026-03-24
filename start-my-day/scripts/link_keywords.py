#!/usr/bin/env python3
"""
Keyword linking script
Used by the start-my-day skill to find keywords in text and replace them with wikilinks
"""

import re
import json
import sys
import argparse
import logging
from typing import Dict, List, Set, Tuple

from common_words import COMMON_WORDS

logger = logging.getLogger(__name__)


def parse_markdown_lines(content: str) -> List[Tuple[str, str, str, bool]]:
    """
    Parse markdown content into a list of lines, each containing: original line, line type, line content, whether in frontmatter

    Line types:
    - 'frontmatter': frontmatter content
    - 'code': code block
    - 'inline_code': inline code
    - 'wikilink': existing wikilink
    - 'image': image link
    - 'link': regular link
    - 'heading': heading line (starts with #)
    - 'normal': normal text

    Args:
        content: markdown content

    Returns:
        List of lines: (original line, line type, line content, whether in frontmatter)
    """
    lines = []
    in_code_block = False
    code_fence_char = None
    in_frontmatter = False
    frontmatter_count = 0

    for line in content.split('\n'):
        # Check frontmatter start/end
        if line.strip() == '---':
            frontmatter_count += 1
            if frontmatter_count == 1:
                in_frontmatter = True
                lines.append((line, 'frontmatter', line, True))
                continue
            elif frontmatter_count == 2:
                in_frontmatter = False
                lines.append((line, 'frontmatter', line, False))
                continue

        if in_frontmatter:
            lines.append((line, 'frontmatter', line, True))
            continue

        # Check code block start/end
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_fence_char = '```'
            else:
                in_code_block = False
                code_fence_char = None
            lines.append((line, 'code', line, False))
            continue

        if in_code_block:
            lines.append((line, 'code', line, False))
            continue

        # Parse line type
        line_type = 'normal'
        processed_content = line

        # Check if heading line
        if line.strip().startswith('#'):
            line_type = 'heading'
            lines.append((line, 'heading', line, False))
            continue

        # Check inline code
        inline_code_matches = list(re.finditer(r'`[^`]+`', line))
        if inline_code_matches:
            # Replace inline code with placeholders (using counter to avoid index errors from pop)
            placeholders = []
            counter = [0]
            def _replace_code(m):
                idx = counter[0]
                placeholders.append(m.group(0))
                counter[0] += 1
                return f'__CODE_{idx}__'
            processed_content = re.sub(r'`[^`]+`', _replace_code, line)
            line_type = 'inline_code'

        # Check images (must be before wikilink check, since ![[x]] also contains [[x]])
        elif re.search(r'!\[\[.*?\]\]', line):
            line_type = 'image'

        # Check wikilink
        elif re.search(r'\[\[.*?\]\]', line):
            line_type = 'wikilink'

        # Check regular link
        elif re.search(r'\[.*?\]\(.*?\)', line):
            line_type = 'link'

        lines.append((line, line_type, processed_content, False))

    return lines


def link_keywords_in_text(
    text: str,
    keyword_index: Dict[str, List[str]],
    existing_wikilinks: Set[str]
) -> str:
    """
    Link keywords in text

    Args:
        text: Text content
        keyword_index: Keyword index
        existing_wikilinks: Set of existing wikilinks

    Returns:
        Processed text
    """
    # Filter out common words and too short/too long keywords
    filtered_keywords = {}
    for keyword, paths in keyword_index.items():
        keyword_lower = keyword.lower()
        # Skip common words
        if keyword_lower in COMMON_WORDS:
            continue
        # Skip keywords that are too short (<3 chars) or too long (>30 chars)
        if len(keyword) < 3 or len(keyword) > 30:
            continue
        # Skip pure numbers
        if keyword.isdigit():
            continue
        filtered_keywords[keyword] = paths

    # Sort keywords by length in descending order, prioritizing longer keyword matches
    sorted_keywords = sorted(
        filtered_keywords.keys(),
        key=lambda k: len(k),
        reverse=True
    )

    result = text
    matched_keywords = set()

    for keyword in sorted_keywords:
        # Skip already matched keywords
        if keyword in matched_keywords:
            continue

        # Find all matches (not using \b word boundary, to support CJK text)
        # Only match complete keywords, avoid matching part of a word
        pattern = r'(?<![a-zA-Z0-9_-])' + re.escape(keyword) + r'(?![a-zA-Z0-9_-])'

        matches = list(re.finditer(pattern, result, re.IGNORECASE))

        if matches:
            # Get note path
            note_paths = filtered_keywords[keyword]
            if note_paths:
                # Use the first note path
                note_path = note_paths[0]

                # Replace all matches (from back to front to avoid index shifts)
                for match in reversed(matches):
                    start, end = match.span()

                    # Check if this match is already inside a wikilink
                    # Find the nearest [[ and ]] around the match position
                    bracket_before = result.rfind('[[', 0, start)
                    bracket_after = result.find(']]', end)

                    # If [[ exists before and ]] exists after, and the match is between them, it's already in a wikilink
                    if bracket_before != -1 and bracket_after != -1 and bracket_before < start and bracket_after > end:
                        # This match is already inside a wikilink, skip
                        continue

                    # Use the matched text from the original, preserving original case
                    original_text = match.group(0)
                    wikilink = f'[[{note_path}|{original_text}]]'

                    # Replace with wikilink
                    result = result[:start] + wikilink + result[end:]

                matched_keywords.add(keyword)

    return result


def link_keywords_in_file(
    input_file: str,
    output_file: str,
    keyword_index: Dict[str, List[str]]
) -> None:
    """
    Process input file and write output

    Args:
        input_file: Input file path
        output_file: Output file path
        keyword_index: Keyword index
    """
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse into lines
    lines = parse_markdown_lines(content)

    # Collect existing wikilinks
    existing_wikilinks = set()
    for original_line, line_type, _, _ in lines:
        if line_type == 'wikilink':
            # Extract content from wikilinks
            matches = re.findall(r'\[\[(.*?)\]\]', original_line)
            for match in matches:
                # Extract the path part of the wikilink
                parts = match.split('|')
                if parts:
                    existing_wikilinks.add(parts[0].lower())

    # Process each line
    processed_lines = []
    for original_line, line_type, line_content, in_frontmatter in lines:
        if line_type in ['frontmatter', 'code', 'wikilink', 'image', 'link', 'heading']:
            # Do not process frontmatter, code blocks, existing wikilinks, images, links, headings
            processed_lines.append(original_line)
        elif line_type == 'inline_code':
            # Do not replace content inside inline code
            processed_lines.append(original_line)
        else:
            # Process normal text
            processed_line = link_keywords_in_text(line_content, keyword_index, existing_wikilinks)
            processed_lines.append(processed_line)

    # Merge results
    result = '\n'.join(processed_lines)

    # Write output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)

    # Statistics
    original_links = len(re.findall(r'\[\[.*?\]\]', content))
    new_links = len(re.findall(r'\[\[.*?\]\]', result))
    added_links = new_links - original_links

    logger.info("Processed file: %s", input_file)
    logger.info("  Original wikilinks: %d", original_links)
    logger.info("  New wikilinks: %d", new_links)
    logger.info("  Added wikilinks: %d", added_links)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Link keywords to existing notes')
    parser.add_argument('--index', type=str, required=True,
                        help='Path to keyword index JSON file')
    parser.add_argument('--input', type=str, required=True,
                        help='Input file path (markdown)')
    parser.add_argument('--output', type=str, required=True,
                        help='Output file path (markdown)')

    args = parser.parse_args()

    # Read keyword index
    with open(args.index, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    keyword_index = index_data.get('keyword_to_notes', {})

    # Filter common words
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    filtered_count = len([k for k in keyword_index if k.lower() in COMMON_WORDS])
    logger.info("Loaded index with %d keywords", len(keyword_index))
    if filtered_count > 0:
        logger.info("  Filtered %d common words", filtered_count)

    link_keywords_in_file(args.input, args.output, keyword_index)

    logger.info("Output saved to: %s", args.output)


if __name__ == '__main__':
    main()
