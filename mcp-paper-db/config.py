"""Configuration loading for the paper database MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DomainConfig:
    """A research domain with keywords and categories."""

    name: str
    keywords: list[str] = field(default_factory=list)
    arxiv_categories: list[str] = field(default_factory=list)
    priority: int = 5


@dataclass
class Config:
    """Top-level configuration for the MCP server."""

    vault_path: Path = field(default_factory=lambda: Path.home() / "Documents" / "Obsidian Vault")
    papers_dir: str = "20_Research/Papers"
    db_path: Path = field(default_factory=lambda: Path("mcp-paper-db/papers.db"))
    language: str = "en"
    research_domains: dict[str, DomainConfig] = field(default_factory=dict)
    excluded_keywords: list[str] = field(default_factory=list)
    semantic_scholar_api_key: Optional[str] = None

    @property
    def papers_path(self) -> Path:
        return self.vault_path / self.papers_dir

    @property
    def all_keywords(self) -> list[str]:
        """All keywords across all domains."""
        kws = []
        for d in self.research_domains.values():
            kws.extend(d.keywords)
        return kws

    @property
    def all_categories(self) -> list[str]:
        """All arXiv categories across all domains."""
        cats = set()
        for d in self.research_domains.values():
            cats.update(d.arxiv_categories)
        return sorted(cats)

    def domain_for_keywords(self, matched: list[str]) -> Optional[str]:
        """Find the best matching domain for a set of matched keywords."""
        best_domain = None
        best_score = 0
        for name, domain in self.research_domains.items():
            overlap = len(set(k.lower() for k in matched) & set(k.lower() for k in domain.keywords))
            score = overlap * domain.priority
            if score > best_score:
                best_score = score
                best_domain = name
        return best_domain


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file and environment variables.

    Priority: env vars > config file > defaults.
    """
    # Find config file
    if config_path is None:
        config_path = os.environ.get("PAPER_CONFIG_PATH")
    if config_path is None:
        # Look relative to the project root
        candidates = [
            Path("config.yaml"),
            Path(__file__).parent.parent / "config.yaml",
        ]
        for c in candidates:
            if c.exists():
                config_path = str(c)
                break

    raw = {}
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}

    # Build domain configs
    domains = {}
    for name, dconf in raw.get("research_domains", {}).items():
        domains[name] = DomainConfig(
            name=name,
            keywords=dconf.get("keywords", []),
            arxiv_categories=dconf.get("arxiv_categories", []),
            priority=dconf.get("priority", 5),
        )

    # Resolve paths from env or config
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", raw.get("vault_path", ""))
    db_path = os.environ.get("PAPER_DB_PATH", "mcp-paper-db/papers.db")
    s2_key = os.environ.get(
        "SEMANTIC_SCHOLAR_API_KEY",
        raw.get("semantic_scholar_api_key"),
    )

    return Config(
        vault_path=Path(vault_path) if vault_path else Config.vault_path,
        papers_dir=raw.get("papers_dir", "20_Research/Papers"),
        db_path=Path(db_path),
        language=raw.get("language", "en"),
        research_domains=domains,
        excluded_keywords=raw.get("excluded_keywords", []),
        semantic_scholar_api_key=s2_key,
    )
