"""
Common words set -- shared by scan_existing_notes.py and link_keywords.py.
These words should be excluded during automatic keyword extraction and auto-linking.

Supports loading additional custom filter words from a config file.
"""

# Default common words set
COMMON_WORDS = {
    # English function words
    'and', 'the', 'for', 'of', 'in', 'on', 'at', 'by', 'with', 'from',
    'to', 'as', 'or', 'but', 'not', 'a', 'an', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'should', 'could', 'may', 'might', 'must',
    'can', 'need', 'use', 'using', 'via', 'through', 'over',
    'under', 'between', 'among', 'during', 'without', 'within',
    'this', 'that', 'these', 'those', 'it', 'its', 'they', 'their',
    'we', 'you', 'your', 'our', 'my', 'his', 'her',
    # ML terms too common in paper titles/abstracts to be discriminative
    'model', 'learning', 'training', 'data', 'system', 'method',
    'approach', 'framework', 'network', 'algorithm', 'task',
}


def load_extra_common_words(config_path=None):
    """
    Load additional common words from a config file and merge into COMMON_WORDS.

    Args:
        config_path: Path to the config file (YAML)
    """
    if not config_path:
        return

    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        extra_words = config.get('extra_common_words', [])
        if extra_words:
            COMMON_WORDS.update(w.lower() for w in extra_words)
    except Exception:
        pass  # Config loading failure does not affect default behavior
