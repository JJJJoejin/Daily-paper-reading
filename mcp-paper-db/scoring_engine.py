"""Scoring engine — extracted from start-my-day/scripts/search_arxiv.py.

Calculates relevance, recency, popularity, quality, and composite
recommendation scores for papers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# ── Scoring constants ──

SCORE_MAX = 3.0

RELEVANCE_TITLE_KEYWORD_BOOST = 0.5
RELEVANCE_SUMMARY_KEYWORD_BOOST = 0.3
RELEVANCE_CATEGORY_MATCH_BOOST = 1.0

RECENCY_THRESHOLDS = [
    (30, 3.0),
    (90, 2.0),
    (180, 1.0),
]
RECENCY_DEFAULT = 0.0

POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE = 100

WEIGHTS_NORMAL = {
    "relevance": 0.40,
    "recency": 0.20,
    "popularity": 0.30,
    "quality": 0.10,
}
WEIGHTS_HOT = {
    "relevance": 0.35,
    "recency": 0.10,
    "popularity": 0.45,
    "quality": 0.10,
}


# ── Scoring functions ──


def calculate_relevance_score(
    title: str,
    abstract: str,
    categories: list[str],
    domains: dict,
    excluded_keywords: list[str],
) -> tuple[float, Optional[str], list[str]]:
    """Calculate relevance of a paper to research interests.

    Args:
        title: Paper title
        abstract: Paper abstract
        categories: Paper arXiv categories
        domains: {domain_name: DomainConfig or dict with 'keywords' and 'arxiv_categories'}
        excluded_keywords: Keywords that cause exclusion

    Returns:
        (relevance_score, matched_domain, matched_keywords)
    """
    title_lower = title.lower()
    abstract_lower = abstract.lower() if abstract else ""
    cat_set = set(categories)

    # Check exclusions
    for kw in excluded_keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower or kw_lower in abstract_lower:
            return 0, None, []

    max_score = 0.0
    best_domain = None
    matched_keywords: list[str] = []

    for domain_name, domain in domains.items():
        score = 0.0
        domain_matched: list[str] = []

        # Get keywords — handle both DomainConfig and raw dict
        keywords = getattr(domain, "keywords", None) or domain.get("keywords", [])
        domain_cats = getattr(domain, "arxiv_categories", None) or domain.get("arxiv_categories", [])

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in title_lower:
                score += RELEVANCE_TITLE_KEYWORD_BOOST
                domain_matched.append(kw)
            elif kw_lower in abstract_lower:
                score += RELEVANCE_SUMMARY_KEYWORD_BOOST
                domain_matched.append(kw)

        for cat in domain_cats:
            if cat in cat_set:
                score += RELEVANCE_CATEGORY_MATCH_BOOST
                domain_matched.append(cat)

        if score > max_score:
            max_score = score
            best_domain = domain_name
            matched_keywords = domain_matched

    return max_score, best_domain, matched_keywords


def calculate_recency_score(published_date: Optional[str | datetime]) -> float:
    """Calculate recency score (0-3) based on publication date."""
    if published_date is None:
        return 0.0

    if isinstance(published_date, str):
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                published_date = datetime.strptime(published_date, fmt)
                break
            except ValueError:
                continue
        else:
            return 0.0

    now = datetime.now(published_date.tzinfo) if published_date.tzinfo else datetime.now()
    days_diff = (now - published_date).days

    for max_days, score in RECENCY_THRESHOLDS:
        if days_diff <= max_days:
            return score
    return RECENCY_DEFAULT


def calculate_popularity_score(
    citation_count: int = 0,
    influential_citation_count: int = 0,
    is_hot: bool = False,
    published_date: Optional[str | datetime] = None,
) -> float:
    """Calculate popularity score (0-3).

    For hot papers: uses influential citation count.
    For regular papers: uses a recency-based heuristic when no citations.
    """
    if is_hot or influential_citation_count > 0:
        return min(
            influential_citation_count / (POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE / SCORE_MAX),
            SCORE_MAX,
        )

    if citation_count > 0:
        return min(citation_count / 200 * SCORE_MAX, SCORE_MAX * 0.7)

    # No citation data — estimate from recency
    if published_date:
        if isinstance(published_date, str):
            for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
                try:
                    published_date = datetime.strptime(published_date, fmt)
                    break
                except ValueError:
                    continue
            else:
                return 0.5

        now = datetime.now(published_date.tzinfo) if published_date.tzinfo else datetime.now()
        days_old = (now - published_date).days
        if days_old <= 7:
            return 2.0
        elif days_old <= 14:
            return 1.5
        elif days_old <= 30:
            return 1.0
        else:
            return 0.5

    return 0.5


def calculate_quality_score(abstract: str) -> float:
    """Infer quality score (0-3) from abstract text."""
    if not abstract:
        return 0.0

    score = 0.0
    text = abstract.lower()

    strong_innovation = [
        "state-of-the-art", "sota", "breakthrough", "first",
        "surpass", "outperform", "pioneering",
    ]
    weak_innovation = [
        "novel", "propose", "introduce", "new approach",
        "new method", "innovative",
    ]
    method_indicators = [
        "framework", "architecture", "algorithm", "mechanism",
        "pipeline", "end-to-end",
    ]
    quantitative_indicators = [
        "outperforms", "improves by", "achieves", "accuracy",
        "f1", "bleu", "rouge", "beats", "surpasses",
    ]
    experiment_indicators = [
        "experiment", "evaluation", "benchmark", "ablation",
        "baseline", "comparison",
    ]

    strong_count = sum(1 for ind in strong_innovation if ind in text)
    if strong_count >= 2:
        score += 1.0
    elif strong_count == 1:
        score += 0.7
    else:
        if any(ind in text for ind in weak_innovation):
            score += 0.3

    if any(ind in text for ind in method_indicators):
        score += 0.5

    if any(ind in text for ind in quantitative_indicators):
        score += 0.8
    elif any(ind in text for ind in experiment_indicators):
        score += 0.4

    return min(score, SCORE_MAX)


def calculate_recommendation_score(
    relevance: float,
    recency: float,
    popularity: float,
    quality: float,
    is_hot: bool = False,
) -> float:
    """Calculate composite recommendation score (0-10).

    Uses WEIGHTS_HOT for high-impact papers, WEIGHTS_NORMAL otherwise.
    """
    scores = {
        "relevance": relevance,
        "recency": recency,
        "popularity": popularity,
        "quality": quality,
    }
    normalized = {k: (v / SCORE_MAX) * 10 for k, v in scores.items()}
    weights = WEIGHTS_HOT if is_hot else WEIGHTS_NORMAL
    return round(sum(normalized[k] * weights[k] for k in weights), 2)


def score_paper(
    title: str,
    abstract: str,
    categories: list[str],
    published_date: Optional[str | datetime],
    citation_count: int,
    influential_citation_count: int,
    is_hot: bool,
    domains: dict,
    excluded_keywords: list[str],
) -> dict:
    """Score a single paper across all dimensions.

    Returns dict with all sub-scores, matched domain, and keywords.
    """
    relevance, domain, matched_kws = calculate_relevance_score(
        title, abstract or "", categories, domains, excluded_keywords
    )
    recency = calculate_recency_score(published_date)
    popularity = calculate_popularity_score(
        citation_count, influential_citation_count, is_hot, published_date
    )
    quality = calculate_quality_score(abstract or "")
    recommendation = calculate_recommendation_score(
        relevance, recency, popularity, quality, is_hot
    )

    return {
        "relevance_score": round(relevance, 2),
        "recency_score": round(recency, 2),
        "popularity_score": round(popularity, 2),
        "quality_score": round(quality, 2),
        "recommendation_score": recommendation,
        "domain": domain,
        "matched_keywords": matched_kws,
    }
