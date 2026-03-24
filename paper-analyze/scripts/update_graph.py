#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update knowledge graph script
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime

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


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description='Update knowledge graph')
    parser.add_argument('--paper-id', type=str, required=True, help='Paper arXiv ID')
    parser.add_argument('--title', type=str, required=True, help='Paper title')
    parser.add_argument('--domain', type=str, required=True, help='Paper domain')
    parser.add_argument('--score', type=float, default=0.0, help='Quality score')
    parser.add_argument('--related', type=str, nargs='*', default=[], help='Related paper IDs')
    parser.add_argument('--vault', type=str, default=None, help='Obsidian vault path')
    parser.add_argument('--language', type=str, default='en', choices=['zh', 'en'], help='Language: zh (Chinese) or en (English)')
    args = parser.parse_args()

    vault_root = get_vault_path(args.vault)
    date = datetime.now().strftime("%Y-%m-%d")

    graph_dir = os.path.join(vault_root, "20_Research", "PaperGraph")
    os.makedirs(graph_dir, exist_ok=True)
    graph_path = os.path.join(graph_dir, "graph_data.json")

    try:
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
    except FileNotFoundError:
        graph = {
            "nodes": [],
            "edges": [],
            "last_updated": date
        }

    try:
        year = int(date[:4])
    except (ValueError, IndexError):
        year = datetime.now().year

    # Language-aware tags
    if args.language == "zh":
        tags = ["paper-notes", args.domain]
    else:
        tags = ["paper-notes", args.domain]

    paper_node = {
        "id": args.paper_id,
        "title": args.title,
        "year": year,
        "domain": args.domain,
        "quality_score": args.score,
        "tags": tags,
        "analyzed": True
    }

    # Safely build node index (skip nodes without id)
    existing_nodes = {
        node.get("id"): i
        for i, node in enumerate(graph["nodes"])
        if node.get("id")
    }
    if args.paper_id in existing_nodes:
        graph["nodes"][existing_nodes[args.paper_id]].update(paper_node)
    else:
        graph["nodes"].append(paper_node)

    if args.related:
        # Safely build edge index (skip edges without source/target)
        existing_edges = {
            (edge.get("source"), edge.get("target"))
            for edge in graph["edges"]
            if edge.get("source") and edge.get("target")
        }
        for related_id in args.related:
            # Prevent self-references
            if related_id and related_id != args.paper_id and (args.paper_id, related_id) not in existing_edges:
                graph["edges"].append({
                    "source": args.paper_id,
                    "target": related_id,
                    "type": "related",
                    "weight": 0.7
                })

    graph["last_updated"] = date

    try:
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
    except (IOError, TypeError) as e:
        logger.error("Failed to write graph: %s", e)
        sys.exit(1)

    print(f"Graph updated: {graph_path}")
    print(f"Nodes: {len(graph['nodes'])}")
    print(f"Edges: {len(graph['edges'])}")


if __name__ == '__main__':
    main()
