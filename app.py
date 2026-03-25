#!/usr/bin/env python3
"""
evil-read-arxiv Streamlit UI
A user-friendly interface for the paper reading workflow.
Integrates with the MCP paper database for persistent storage.
"""

import streamlit as st
import importlib.util
import json
import os
import sys
import subprocess
import re
from datetime import datetime
from pathlib import Path

# --- Configuration ---
PROJECT_DIR = Path(__file__).parent
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "")

# Ensure scripts can import each other
sys.path.insert(0, str(PROJECT_DIR / "start-my-day" / "scripts"))
sys.path.insert(0, str(PROJECT_DIR / "conf-papers" / "scripts"))

# --- Register mcp-paper-db as importable package "mcp_paper_db" ---
_mcp_pkg_dir = PROJECT_DIR / "mcp-paper-db"
if "mcp_paper_db" not in sys.modules and _mcp_pkg_dir.exists():
    _spec = importlib.util.spec_from_file_location(
        "mcp_paper_db",
        _mcp_pkg_dir / "__init__.py",
        submodule_search_locations=[str(_mcp_pkg_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["mcp_paper_db"] = _mod
    _spec.loader.exec_module(_mod)

DISABLE_MCP = os.environ.get("DISABLE_MCP", "").lower() in ("1", "true", "yes")

if not DISABLE_MCP:
    try:
        from mcp_paper_db.config import load_config as load_mcp_config
        from mcp_paper_db.db import PaperDatabase
        from mcp_paper_db.models import SearchRun
        from mcp_paper_db.tools import search as search_tools
        from mcp_paper_db.tools import scoring as scoring_tools
        from mcp_paper_db.tools import management as mgmt_tools
        from mcp_paper_db.tools import analytics as analytics_tools

        HAS_MCP = True
    except ImportError as e:
        HAS_MCP = False
        print(f"MCP import failed: {e}", file=sys.stderr)
else:
    HAS_MCP = False


# =============================================================================
# Helpers
# =============================================================================


def get_vault_path():
    """Get vault path from env or session state."""
    if "vault_path" in st.session_state and st.session_state.vault_path:
        return st.session_state.vault_path
    return VAULT_PATH


def run_script(script_path, args, cwd=None):
    """Run a Python script and return stdout, stderr, returncode."""
    cmd = [str(VENV_PYTHON), str(script_path)] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or str(PROJECT_DIR),
        env={**os.environ, "OBSIDIAN_VAULT_PATH": get_vault_path()},
    )
    return result.stdout, result.stderr, result.returncode


def fetch_tex_content(arxiv_id, max_chars=60000):
    """Download arXiv source and extract .tex file contents."""
    import tarfile
    import tempfile
    import urllib.request

    source_url = f"https://arxiv.org/e-print/{arxiv_id}"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "source.tar.gz")
            urllib.request.urlretrieve(source_url, tar_path)
            with tarfile.open(tar_path, "r:gz") as tar:
                safe = [
                    m for m in tar.getmembers()
                    if not m.name.startswith("/") and ".." not in m.name
                    and not m.issym() and not m.islnk()
                ]
                tar.extractall(path=tmp, members=safe)
            tex_contents = []
            for root, _, files in os.walk(tmp):
                for f in sorted(files):
                    if f.endswith(".tex"):
                        fp = os.path.join(root, f)
                        with open(fp, "r", errors="ignore") as fh:
                            tex_contents.append(f"% === {f} ===\n" + fh.read())
            combined = "\n\n".join(tex_contents)
            return combined[:max_chars] if combined else None
    except Exception:
        return None


def analyze_with_llm(title, authors, abstract, domain, tex_content, arxiv_id, image_files=None):
    """Call DeepSeek API to generate a filled-in analysis note."""
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        return None, "LLM_API_KEY environment variable not set"

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    date_str = datetime.now().strftime("%Y-%m-%d")

    image_list = ""
    if image_files:
        image_list = "\n".join(f"- {f}" for f in image_files)

    system_prompt = (
        "You are a research paper analyst. Given a paper's metadata and LaTeX source, "
        "generate a comprehensive analysis note in Markdown for an Obsidian vault. "
        "Fill in ALL sections with substantive content derived from the paper. "
        "Use $...$ for inline math and $$...$$ for block math. "
        "Use [[Paper Name]] wikilink format for related paper references. "
        "All string values in YAML frontmatter MUST be wrapped in double quotes. "
        "Output ONLY the Markdown note, starting with the --- frontmatter."
    )

    user_prompt = f"""Analyze this paper and generate a complete analysis note.

PAPER METADATA:
- Title: {title}
- Authors: {authors}
- arXiv ID: {arxiv_id}
- Domain: {domain}
- Date: {date_str}

ABSTRACT:
{abstract}

AVAILABLE IMAGES (reference as ![desc|800](images/filename)):
{image_list or "(no images)"}

LATEX SOURCE (may be truncated):
{tex_content or "(source unavailable - analyze based on abstract only)"}

Generate a comprehensive analysis note with these sections:
1. YAML frontmatter: date, paper_id, title, authors, domain, tags (use hyphens not spaces), quality_score, related_papers, created, updated, status
2. Core Information (ID, authors, institution, date, conference, links)
3. Abstract (original + key points: background, motivation, core method, main results, significance)
4. Research Background and Motivation
5. Method Overview (core idea, framework, detailed modules with math formulas, key innovations)
   - Reference paper images where relevant: ![desc|800](images/filename.pdf)
6. Experimental Results (objectives, datasets table, setup with baselines/metrics/environment, main results table with numbers, ablation studies, result figures)
7. Deep Analysis (research value, advantages, limitations, applicable scenarios)
8. Comparison with Related Papers (with tables)
9. Technical Lineage Positioning
10. Future Work Suggestions
11. Overall Assessment with scores (Innovation, Technical quality, Experimental sufficiency, Writing quality, Practicality - each X/10)
12. My Notes (empty placeholder)
13. Related Papers (wikilinks)
14. External Resources
15. Obsidian callout blocks: tip (key insight), warning (notes), success (recommendation)

Be thorough and specific. Extract actual numbers, methods, and results from the paper."""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=8000,
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, str(e)


def load_config():
    """Load config: project-level config.yaml first, vault fallback.

    Returns (raw_dict, mcp_Config) or (None, None) if no config found.
    """
    import yaml

    # Primary: project-level config.yaml
    project_config = PROJECT_DIR / "config.yaml"
    if project_config.exists():
        with open(project_config) as f:
            raw = yaml.safe_load(f)
        if raw and raw.get("research_domains"):
            if HAS_MCP:
                mcp_cfg = load_mcp_config(str(project_config))
                return raw, mcp_cfg
            return raw, None

    # Fallback: vault's research_interests.yaml
    vault = get_vault_path()
    if vault:
        fallback = Path(vault) / "99_System" / "Config" / "research_interests.yaml"
        if fallback.exists():
            with open(fallback) as f:
                raw = yaml.safe_load(f)
            if HAS_MCP:
                mcp_cfg = load_mcp_config(str(fallback))
                return raw, mcp_cfg
            return raw, None

    return None, None


def get_db():
    """Get or create the paper database (singleton per session)."""
    if not HAS_MCP:
        return None
    if "paper_db" not in st.session_state:
        db_path = PROJECT_DIR / "mcp-paper-db" / "papers.db"
        db = PaperDatabase(db_path)
        db.migrate()
        st.session_state["paper_db"] = db
    return st.session_state["paper_db"]


def get_mcp_config():
    """Get the MCP Config object."""
    _, mcp_cfg = load_config()
    return mcp_cfg


def store_papers_in_db(papers, source="arxiv"):
    """Store search results in the paper database."""
    db = get_db()
    mcp_cfg = get_mcp_config()
    if not db or not mcp_cfg:
        return 0

    stored = 0
    for p in papers:
        try:
            # Map JSON fields to upsert params
            authors = p.get("authors", [])
            if isinstance(authors, list) and authors and isinstance(authors[0], dict):
                authors = [a.get("name", "") for a in authors]

            pub_date = p.get("published_date") or p.get("publicationDate")
            if hasattr(pub_date, "strftime"):
                pub_date = pub_date.strftime("%Y-%m-%d")

            mgmt_tools.upsert_paper_impl(
                db,
                title=p.get("title", ""),
                arxiv_id=p.get("arxiv_id"),
                doi=p.get("doi"),
                abstract=p.get("summary") or p.get("abstract"),
                authors=authors,
                published_date=str(pub_date) if pub_date else None,
                categories=p.get("categories", []),
                conference=p.get("conference"),
                conference_year=p.get("year"),
                domain=p.get("matched_domain"),
                source=source,
            )
            stored += 1
        except Exception as e:
            pass  # Skip individual failures

    # Score all papers
    try:
        scoring_tools.score_papers_impl(db, mcp_cfg, limit=500)
    except Exception:
        pass

    return stored


def render_paper_card(paper, index, expanded=False):
    """Render a single paper as a card."""
    score = paper.get("scores", {}).get("recommendation", 0)
    title = paper.get("title", "Unknown")
    authors = paper.get("authors", [])
    domain = paper.get("matched_domain", "") or paper.get("domain", "") or "Unknown"
    keywords = paper.get("matched_keywords", [])
    summary = paper.get("summary", "") or paper.get("abstract", "") or ""
    url = paper.get("url", "") or paper.get("arxiv_url", "")
    pdf_url = paper.get("pdf_url", "")
    arxiv_id = paper.get("arxiv_id", "")
    is_hot = paper.get("is_hot_paper", False)

    if not arxiv_id and url:
        m = re.search(r"/(\d{4}\.\d+)", url)
        if m:
            arxiv_id = m.group(1)

    if score >= 9:
        score_color = "🟢"
    elif score >= 8:
        score_color = "🟡"
    else:
        score_color = "🟠"

    hot_badge = " 🔥 **HOT**" if is_hot else ""

    with st.container():
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            st.markdown(f"### {index}. {title}")
        with col2:
            st.markdown(f"### {score_color} {score}")

        st.markdown(f"**Domain**: `{domain}` | **Keywords**: {', '.join(f'`{k}`' for k in keywords[:5])}{hot_badge}")

        if authors:
            if isinstance(authors, list) and authors and isinstance(authors[0], dict):
                author_list = [a.get("name", "") for a in authors[:5]]
            else:
                author_list = authors[:5]
            author_str = ", ".join(author_list)
            if len(authors) > 5:
                author_str += " et al."
            st.markdown(f"**Authors**: {author_str}")

        if summary:
            with st.expander("Abstract", expanded=expanded):
                st.write(summary[:500] + ("..." if len(summary) > 500 else ""))

        link_parts = []
        if url:
            link_parts.append(f"[arXiv]({url})")
        elif arxiv_id:
            link_parts.append(f"[arXiv](https://arxiv.org/abs/{arxiv_id})")
        if pdf_url:
            link_parts.append(f"[PDF]({pdf_url})")
        elif arxiv_id:
            link_parts.append(f"[PDF](https://arxiv.org/pdf/{arxiv_id})")
        if arxiv_id:
            link_parts.append(f"ID: `{arxiv_id}`")
        if link_parts:
            st.markdown(" | ".join(link_parts))

        st.divider()


# =============================================================================
# Pages
# =============================================================================


def page_home():
    """Home page."""
    st.title("📚 evil-read-arxiv")
    st.markdown("*Your automated paper reading workflow*")

    vault = get_vault_path()
    raw_config, _ = load_config()

    if not raw_config:
        st.warning("⚠️ No config found. Go to **Settings** to configure.")
        return

    config_source = "project `config.yaml`" if (PROJECT_DIR / "config.yaml").exists() else "vault config"
    st.success(f"✅ Config loaded from {config_source}")
    if vault:
        st.caption(f"Vault: `{vault}`")

    domains = raw_config.get("research_domains", {})
    st.markdown("### Your Research Domains")
    cols = st.columns(min(len(domains), 4))
    for i, (name, info) in enumerate(domains.items()):
        with cols[i % len(cols)]:
            priority = info.get("priority", 0)
            kw_count = len(info.get("keywords", []))
            st.metric(name, f"{kw_count} keywords", f"Priority: {priority}")

    # Vault stats
    st.markdown("### Stats")
    c1, c2, c3, c4 = st.columns(4)

    if vault:
        papers_dir = Path(vault) / "20_Research" / "Papers"
        daily_dir = Path(vault) / "10_Daily"
        note_count = len(list(papers_dir.rglob("*.md"))) if papers_dir.exists() else 0
        daily_count = len(list(daily_dir.glob("*paper-recommendations.md"))) if daily_dir.exists() else 0
        c1.metric("Paper Notes", note_count)
        c2.metric("Daily Recommendations", daily_count)
    else:
        c1.metric("Paper Notes", "—")
        c2.metric("Daily Recommendations", "—")

    # DB stats
    db = get_db()
    if db:
        stats = db.get_stats()
        c3.metric("Papers in DB", stats["total_papers"])
        c4.metric("Analyzed", stats["papers_with_notes"])
    else:
        c3.metric("Papers in DB", "N/A")
        c4.metric("Analyzed", "N/A")


def page_start_my_day():
    """Start My Day - daily paper recommendations."""
    st.title("🌅 Start My Day")
    st.markdown("Search arXiv + Semantic Scholar for today's paper recommendations.")

    vault = get_vault_path()
    raw_config, mcp_cfg = load_config()

    if not raw_config:
        st.error("No config found. Go to Settings.")
        return

    # Parameters
    col1, col2, col3 = st.columns(3)
    with col1:
        target_date = st.date_input("Target Date", value=datetime.now())
    with col2:
        max_results = st.number_input("Max arXiv Results", value=200, min_value=50, max_value=500)
    with col3:
        top_n = st.number_input("Top N Papers", value=10, min_value=5, max_value=30)

    # Get categories from config
    all_cats = set()
    for d in raw_config.get("research_domains", {}).values():
        all_cats.update(d.get("arxiv_categories", []))
    default_cats = ",".join(sorted(all_cats)) if all_cats else "cs.AI,cs.LG,cs.CL"

    categories = st.text_input("arXiv Categories", value=default_cats)
    skip_hot = st.checkbox("Skip Semantic Scholar hot papers (faster)", value=False)

    # Choose search method
    use_mcp = HAS_MCP and st.checkbox("Use MCP database (persistent storage)", value=True)

    if st.button("🚀 Search Papers", type="primary", use_container_width=True):
        if use_mcp and mcp_cfg:
            _search_with_mcp(target_date, categories, max_results, top_n, skip_hot, mcp_cfg)
        else:
            _search_with_scripts(target_date, categories, max_results, top_n, skip_hot, vault, raw_config)

    # Show results from session state (persists across reruns)
    if "smd_papers" in st.session_state and st.session_state["smd_papers"]:
        papers = st.session_state["smd_papers"]
        target_date_saved = st.session_state.get("smd_target_date", target_date)

        st.markdown("---")
        if "smd_metrics" in st.session_state:
            metrics = st.session_state["smd_metrics"]
            c1, c2, c3 = st.columns(3)
            c1.metric(metrics[0][0], metrics[0][1])
            c2.metric(metrics[1][0], metrics[1][1])
            c3.metric(metrics[2][0], metrics[2][1])

        st.markdown("### Top Papers")
        for i, paper in enumerate(papers, 1):
            render_paper_card(paper, i, expanded=(i <= 3))

        if vault:
            if st.button("📝 Generate Recommendation Note", type="primary", use_container_width=True, key="gen_note_btn"):
                try:
                    generate_daily_note(papers, target_date_saved, vault)
                    st.session_state["smd_note_generated"] = True
                except Exception as e:
                    st.error(f"Failed to generate note: {e}")

    if st.session_state.get("smd_note_generated"):
        st.success("✅ Recommendation note saved to Obsidian vault!")
        st.session_state["smd_note_generated"] = False


def _search_with_mcp(target_date, categories, max_results, top_n, skip_hot, mcp_cfg):
    """Run search using MCP tools (persistent DB)."""
    db = get_db()
    if not db:
        st.error("Database not available.")
        return

    cat_list = [c.strip() for c in categories.split(",") if c.strip()]

    with st.status("Searching with MCP database...", expanded=True) as status:
        # Step 1: Sync vault notes
        vault = get_vault_path()
        if vault:
            st.write("📂 Syncing vault notes...")
            sync = mgmt_tools.sync_vault_notes_impl(db, mcp_cfg)
            st.write(f"Scanned {sync.get('scanned', 0)} notes, matched {sync.get('matched', 0)}")

        # Step 2: Search arXiv
        st.write("🔍 Searching arXiv...")
        arxiv_result = search_tools.search_arxiv_impl(
            db, mcp_cfg, categories=cat_list or None,
            days=30, max_results=max_results,
        )
        st.write(f"arXiv: {arxiv_result['fetched']} fetched, {arxiv_result['stored']} stored")

        # Step 3: Search S2 hot papers
        if not skip_hot:
            st.write("🔥 Searching Semantic Scholar hot papers...")
            s2_result = search_tools.search_semantic_scholar_impl(
                db, mcp_cfg, days=365, top_k=20,
            )
            st.write(f"S2: {s2_result['fetched']} fetched, {s2_result['stored']} stored")

        # Step 4: Score papers
        st.write("📊 Scoring papers...")
        scored = scoring_tools.score_papers_impl(db, mcp_cfg, limit=500)
        st.write(f"Scored {scored['scored']} papers")

        # Step 5: Get recommendations
        st.write("⭐ Getting top recommendations...")
        recs = scoring_tools.get_recommendations_impl(db, limit=top_n)

        status.update(label="Search complete!", state="complete")

    if not recs:
        st.warning("No recommendations found.")
        return

    # Convert to display format and save to session state
    papers = []
    for r in recs:
        arxiv_id = r.get("arxiv_id", "")
        papers.append({
            "title": r["title"],
            "arxiv_id": arxiv_id,
            "abstract": r.get("abstract", ""),
            "summary": r.get("abstract", ""),
            "authors": r.get("authors", []),
            "domain": r.get("domain", ""),
            "matched_domain": r.get("domain", ""),
            "matched_keywords": r.get("matched_keywords", []),
            "scores": r.get("scores", {"recommendation": r.get("recommendation_score", 0)}),
            "source": r.get("source", ""),
            "has_note": r.get("has_note", False),
            "is_hot_paper": r.get("is_hot_paper", False),
            "url": r.get("arxiv_url") or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""),
            "pdf_url": r.get("pdf_url") or (f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ""),
        })

    stats = db.get_stats()
    st.session_state["smd_papers"] = papers
    st.session_state["smd_target_date"] = target_date
    st.session_state["smd_metrics"] = [
        ("Total in DB", stats["total_papers"]),
        ("Scored", scored["scored"]),
        ("Recommendations", len(papers)),
    ]

    # Record events
    for i, r in enumerate(recs[:top_n], 1):
        try:
            mgmt_tools.record_event_impl(db, paper_id=r["id"], event_type="recommended", recommendation_rank=i)
        except Exception:
            pass


def _search_with_scripts(target_date, categories, max_results, top_n, skip_hot, vault, raw_config):
    """Run search using original Python scripts (subprocess)."""
    if not vault:
        st.error("Vault path not configured for script-based search. Go to Settings.")
        return

    config_path = Path(vault) / "99_System" / "Config" / "research_interests.yaml"
    # Also try project config
    if not config_path.exists():
        config_path = PROJECT_DIR / "config.yaml"
    if not config_path.exists():
        st.error("Research config not found.")
        return

    with st.status("Running paper search workflow...", expanded=True) as status:
        st.write("📂 Scanning existing notes...")
        stdout, stderr, rc = run_script(
            PROJECT_DIR / "start-my-day" / "scripts" / "scan_existing_notes.py",
            ["--vault", vault, "--output", str(PROJECT_DIR / "start-my-day" / "existing_notes_index.json")],
            cwd=str(PROJECT_DIR / "start-my-day"),
        )
        if rc != 0:
            st.error(f"Scan failed: {stderr}")
            return

        st.write("🔍 Searching arXiv + Semantic Scholar...")
        args = [
            "--config", str(config_path),
            "--output", str(PROJECT_DIR / "start-my-day" / "arxiv_filtered.json"),
            "--max-results", str(max_results),
            "--top-n", str(top_n),
            "--categories", categories,
            "--target-date", target_date.strftime("%Y-%m-%d"),
        ]
        if skip_hot:
            args.append("--skip-hot-papers")

        stdout, stderr, rc = run_script(
            PROJECT_DIR / "start-my-day" / "scripts" / "search_arxiv.py",
            args,
            cwd=str(PROJECT_DIR / "start-my-day"),
        )

        if rc != 0:
            st.error(f"Search failed: {stderr[-500:]}")
            return

        status.update(label="Search complete!", state="complete")

    results_path = PROJECT_DIR / "start-my-day" / "arxiv_filtered.json"
    if not results_path.exists():
        st.error("No results file found.")
        return

    with open(results_path) as f:
        data = json.load(f)

    papers = data.get("top_papers", [])

    for p in papers:
        if not p.get("arxiv_id") and p.get("url"):
            m = re.search(r"/(\d{4}\.\d+)", p["url"])
            if m:
                p["arxiv_id"] = m.group(1)

    st.session_state["smd_papers"] = papers
    st.session_state["smd_target_date"] = target_date
    st.session_state["smd_metrics"] = [
        ("Recent Papers Found", data.get("total_recent", 0)),
        ("Hot Papers Found", data.get("total_hot", 0)),
        ("Unique After Dedup", data.get("total_unique", 0)),
    ]

    # Store in DB if available
    if HAS_MCP:
        stored = store_papers_in_db(papers, source="arxiv")
        if stored:
            st.info(f"💾 Stored {stored} papers in database")


def _generate_daily_note_from_recs(recs, target_date, vault):
    """Generate daily note from MCP recommendation results."""
    date_str = target_date.strftime("%Y-%m-%d")

    all_keywords = set()
    domains = {}
    for r in recs:
        d = r.get("domain", "Other") or "Other"
        domains[d] = domains.get(d, 0) + 1

    # Build papers list for generate_daily_note
    papers = []
    for r in recs:
        papers.append({
            "title": r.get("title", "N/A"),
            "authors": r.get("authors", []),
            "scores": r.get("scores", {"recommendation": r.get("recommendation_score", 0)}),
            "matched_domain": r.get("domain", "Other"),
            "matched_keywords": [],
            "url": f"https://arxiv.org/abs/{r['arxiv_id']}" if r.get("arxiv_id") else "",
            "pdf_url": f"https://arxiv.org/pdf/{r['arxiv_id']}" if r.get("arxiv_id") else "",
            "note_filename": re.sub(r'[ /\\:*?"<>|]+', '_', r.get("title", "")).strip('_'),
            "is_hot_paper": False,
        })

    generate_daily_note(papers, target_date, vault)


def generate_daily_note(papers, target_date, vault):
    """Generate the daily recommendation note."""
    date_str = target_date.strftime("%Y-%m-%d")

    all_keywords = set()
    domains = {}
    for p in papers:
        all_keywords.update(p.get("matched_keywords", []))
        d = p.get("matched_domain", "Other")
        domains[d] = domains.get(d, 0) + 1

    note = f"""---
keywords: [{', '.join(sorted(all_keywords)[:10])}]
tags: ["llm-generated", "daily-paper-recommend"]
date: "{date_str}"
---

# {date_str} Paper Recommendations

## Today's Overview

Today's {len(papers)} recommended papers span **{', '.join(domains.keys())}**.

- **Score Range**: {papers[-1].get('scores', {}).get('recommendation', 0):.1f} - {papers[0].get('scores', {}).get('recommendation', 0):.1f}
- **Domain Distribution**: {', '.join(f'{d} ({c})' for d, c in domains.items())}

---

"""

    for i, p in enumerate(papers, 1):
        title = p.get("title", "N/A")
        authors = p.get("authors", [])
        if isinstance(authors, list) and authors and isinstance(authors[0], dict):
            authors = [a.get("name", "") for a in authors]
        author_str = ", ".join(authors[:5])
        if len(authors) > 5:
            author_str += " et al."
        score = p.get("scores", {}).get("recommendation", 0)
        domain = p.get("matched_domain", "Other")
        summary = p.get("summary", "") or p.get("abstract", "")
        url = p.get("url", "")
        pdf_url = p.get("pdf_url", "")
        keywords = ", ".join(p.get("matched_keywords", []))
        note_filename = p.get("note_filename", "")
        hot = " **[HOT]**" if p.get("is_hot_paper") else ""

        note += f"""### [[{title}]]
- **Score**: {score}/10{hot}
- **Authors**: {author_str}
- **Domain**: {domain}
- **Keywords**: {keywords}
- **Links**: [arXiv]({url}) | [PDF]({pdf_url})
"""
        if i <= 3 and note_filename:
            note += f"- **Detailed Report**: [[20_Research/Papers/{date_str}/{domain}/{note_filename}]]\n"

        note += f"\n**Summary**: {summary}\n\n---\n\n"

    note_dir = Path(vault) / "10_Daily"
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / f"{date_str}-paper-recommendations.md"

    with open(note_path, "w") as f:
        f.write(note)

    st.success(f"✅ Note saved to: `{note_path}`")


def page_paper_analyze():
    """Paper Analysis page."""
    st.title("🔬 Paper Analysis")
    st.markdown("Generate a detailed analysis note for a specific paper.")

    vault = get_vault_path()
    if not vault:
        st.error("Vault path not configured. Go to Settings.")
        return

    arxiv_id = st.text_input("arXiv ID", placeholder="e.g., 2603.22213")

    # Get domains from config
    raw_config, _ = load_config()
    domain_list = list(raw_config.get("research_domains", {}).keys()) if raw_config else []
    domain_list.append("Other")
    domain = st.selectbox("Domain", domain_list)

    if st.button("🔍 Analyze Paper", type="primary") and arxiv_id:
        with st.status("Analyzing paper...", expanded=True) as status:
            st.write("📄 Fetching paper metadata from arXiv...")
            import urllib.request
            import xml.etree.ElementTree as ET

            api_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
            try:
                with urllib.request.urlopen(api_url, timeout=30) as resp:
                    xml_content = resp.read().decode("utf-8")
            except Exception as e:
                st.error(f"Failed to fetch from arXiv: {e}")
                return

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(xml_content)
            entry = root.find("atom:entry", ns)
            if entry is None:
                st.error("Paper not found on arXiv.")
                return

            title = entry.find("atom:title", ns).text.strip()
            summary = entry.find("atom:summary", ns).text.strip()
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            author_str = ", ".join(authors)

            st.write(f"📋 Found: **{title}**")

            # Store in DB
            db = get_db()
            if db:
                mgmt_tools.upsert_paper_impl(
                    db, title=title, arxiv_id=arxiv_id, abstract=summary,
                    authors=authors, domain=domain, source="arxiv",
                )

            # Extract images
            st.write("🖼️ Extracting images from arXiv source...")
            safe_title = re.sub(r'[ /\\:*?"<>|]+', '_', title).strip('_')
            today_str = datetime.now().strftime("%Y-%m-%d")
            images_dir = Path(vault) / "20_Research" / "Papers" / today_str / domain / safe_title / "images"
            index_path = images_dir / "index.md"

            stdout, stderr, rc = run_script(
                PROJECT_DIR / "extract-paper-images" / "scripts" / "extract_images.py",
                [arxiv_id, str(images_dir), str(index_path)],
                cwd=str(PROJECT_DIR / "extract-paper-images"),
            )

            image_count = 0
            if rc == 0:
                image_paths = [line for line in stdout.strip().split("\n") if line.startswith("images/")]
                image_count = len(image_paths)
                st.write(f"✅ Extracted {image_count} images")
            else:
                st.write("⚠️ Image extraction failed, continuing without images.")

            # Generate note
            st.write("📝 Generating analysis note...")
            stdout, stderr, rc = run_script(
                PROJECT_DIR / "paper-analyze" / "scripts" / "generate_note.py",
                [
                    "--paper-id", arxiv_id,
                    "--title", title,
                    "--authors", author_str,
                    "--domain", domain,
                    "--vault", vault,
                    "--language", "en",
                ],
                cwd=str(PROJECT_DIR / "paper-analyze"),
            )

            if rc != 0:
                st.error(f"Note generation failed: {stderr}")
                return

            # LLM-powered analysis (overwrites template if successful)
            if os.environ.get("LLM_API_KEY"):
                st.write("🤖 Analyzing paper with LLM...")
                tex_content = fetch_tex_content(arxiv_id)
                if tex_content:
                    st.write(f"📚 Extracted {len(tex_content):,} chars of LaTeX source")
                else:
                    st.write("⚠️ No LaTeX source, analyzing from abstract only")

                # List available images for the LLM to reference
                img_files = []
                if images_dir.exists():
                    img_files = [f.name for f in images_dir.iterdir() if f.suffix in (".pdf", ".png", ".jpg")]

                llm_note, llm_error = analyze_with_llm(
                    title, author_str, summary, domain, tex_content, arxiv_id, img_files
                )

                if llm_note and not llm_error:
                    llm_note_path = Path(vault) / "20_Research" / "Papers" / today_str / domain / f"{safe_title}.md"
                    llm_note_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(llm_note_path, "w", encoding="utf-8") as f:
                        f.write(llm_note)
                    st.write("✅ LLM analysis complete")
                else:
                    st.write(f"⚠️ LLM analysis skipped ({llm_error or 'unknown error'}), template preserved")
            else:
                st.write("ℹ️ Set LLM_API_KEY env var to enable AI-powered analysis")

            # Update knowledge graph
            st.write("🔗 Updating knowledge graph...")
            run_script(
                PROJECT_DIR / "paper-analyze" / "scripts" / "update_graph.py",
                [
                    "--paper-id", arxiv_id,
                    "--title", title,
                    "--domain", domain,
                    "--score", "0",
                    "--vault", vault,
                    "--language", "en",
                ],
                cwd=str(PROJECT_DIR / "paper-analyze"),
            )

            # Mark as analyzed in DB
            if db:
                note_path = f"20_Research/Papers/{today_str}/{domain}/{safe_title}.md"
                mgmt_tools.upsert_paper_impl(
                    db, title=title, arxiv_id=arxiv_id, domain=domain,
                    has_note=True, note_path=note_path, source="arxiv",
                )
                paper = db.get_paper(arxiv_id=arxiv_id)
                if paper:
                    mgmt_tools.record_event_impl(db, paper_id=paper.id, event_type="analyzed")

            status.update(label="Analysis complete!", state="complete")

        note_path = Path(vault) / "20_Research" / "Papers" / today_str / domain / f"{safe_title}.md"
        st.success(f"✅ Note saved to: `{note_path}`")

        st.markdown("### Paper Info")
        st.markdown(f"**Title**: {title}")
        st.markdown(f"**Authors**: {author_str}")
        st.markdown(f"**Images**: {image_count} extracted")

        with st.expander("Abstract", expanded=True):
            st.write(summary)

        st.markdown(f"**Links**: [arXiv](https://arxiv.org/abs/{arxiv_id}) | [PDF](https://arxiv.org/pdf/{arxiv_id})")


def page_conf_papers():
    """Conference paper search page."""
    st.title("🎓 Conference Paper Search")
    st.markdown("Search top conference papers via DBLP + Semantic Scholar.")

    raw_config, mcp_cfg = load_config()
    vault = get_vault_path()

    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", value=2025, min_value=2015, max_value=2026)
    with col2:
        top_n = st.number_input("Top N Papers", value=10, min_value=5, max_value=30)

    conferences = st.multiselect(
        "Conferences",
        ["CVPR", "ICCV", "ECCV", "ICLR", "AAAI", "NeurIPS", "ICML"],
        default=["ICLR", "NeurIPS", "ICML"],
    )

    skip_enrichment = st.checkbox("Skip Semantic Scholar enrichment (faster)", value=False)
    use_mcp = HAS_MCP and st.checkbox("Use MCP database (persistent storage)", value=True)

    if st.button("🔍 Search Conference Papers", type="primary", use_container_width=True) and conferences:
        if use_mcp and mcp_cfg:
            _conf_search_mcp(year, conferences, top_n, skip_enrichment, mcp_cfg)
        else:
            _conf_search_scripts(year, conferences, top_n, skip_enrichment, vault)


def _conf_search_mcp(year, conferences, top_n, skip_enrichment, mcp_cfg):
    """Conference search via MCP tools."""
    db = get_db()
    if not db:
        st.error("Database not available.")
        return

    with st.status("Searching with MCP database...", expanded=True) as status:
        st.write(f"🔍 Searching {', '.join(conferences)} {year} via DBLP...")
        result = search_tools.search_conference_papers_impl(
            db, mcp_cfg,
            venues=conferences,
            year=year,
            enrich=not skip_enrichment,
        )
        st.write(f"Fetched: {result['fetched']}, Stored: {result['stored']}")

        st.write("📊 Scoring papers...")
        scored = scoring_tools.score_papers_impl(db, mcp_cfg, limit=500)

        recs = scoring_tools.get_recommendations_impl(db, limit=top_n)
        status.update(label="Search complete!", state="complete")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Fetched", result["fetched"])
    c2.metric("Stored in DB", result["stored"])
    c3.metric("Recommendations", len(recs))

    st.markdown(f"### Top {len(recs)} Papers")
    for i, r in enumerate(recs, 1):
        paper = {
            "title": r["title"],
            "arxiv_id": r.get("arxiv_id"),
            "authors": r.get("authors", []),
            "domain": r.get("domain", ""),
            "matched_domain": r.get("domain", ""),
            "matched_keywords": [],
            "scores": r.get("scores", {"recommendation": 0}),
        }
        render_paper_card(paper, i, expanded=(i <= 3))


def _conf_search_scripts(year, conferences, top_n, skip_enrichment, vault):
    """Conference search via subprocess scripts."""
    config_path = PROJECT_DIR / "conf-papers" / "conf-papers.yaml"

    with st.status("Searching conference papers...", expanded=True) as status:
        st.write(f"🔍 Searching {', '.join(conferences)} {year}...")

        args = [
            "--config", str(config_path),
            "--output", str(PROJECT_DIR / "conf-papers" / "conf_papers_filtered.json"),
            "--year", str(year),
            "--conferences", ",".join(conferences),
            "--top-n", str(top_n),
        ]
        if skip_enrichment:
            args.append("--skip-enrichment")

        stdout, stderr, rc = run_script(
            PROJECT_DIR / "conf-papers" / "scripts" / "search_conf_papers.py",
            args,
            cwd=str(PROJECT_DIR / "conf-papers"),
        )

        if rc != 0:
            st.error(f"Search failed: {stderr[-500:]}")
            return

        status.update(label="Search complete!", state="complete")

    results_path = PROJECT_DIR / "conf-papers" / "conf_papers_filtered.json"
    if not results_path.exists():
        st.error("No results found.")
        return

    with open(results_path) as f:
        data = json.load(f)

    papers = data.get("top_papers", [])

    # Store in DB
    if HAS_MCP:
        stored = store_papers_in_db(papers, source="dblp")
        if stored:
            st.info(f"💾 Stored {stored} papers in database")

    # Summary
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Found (DBLP)", data.get("total_found", 0))
    c2.metric("After Keyword Filter", data.get("total_filtered", 0))
    c3.metric("S2 Enriched", data.get("total_enriched", 0))

    st.markdown(f"### Top {len(papers)} Papers")
    for i, paper in enumerate(papers, 1):
        score = paper.get("scores", {}).get("recommendation", 0)
        title = paper.get("title", "Unknown")
        authors = paper.get("authors", [])
        conf = paper.get("conference", "")
        citations = paper.get("citationCount", 0)
        inf_citations = paper.get("influentialCitationCount", 0)
        abstract = paper.get("abstract", "") or ""
        dblp_url = paper.get("dblp_url", "")
        arxiv_id = paper.get("arxiv_id", "")

        with st.container():
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.markdown(f"### {i}. {title}")
            with col2:
                st.markdown(f"### {'🟢' if score >= 7 else '🟡'} {score}")

            st.markdown(f"**{conf} {year}** | Citations: {citations} (influential: {inf_citations})")
            if authors:
                st.markdown(f"**Authors**: {', '.join(authors[:5])}")
            if abstract:
                with st.expander("Abstract"):
                    st.write(abstract[:500])
            links = []
            if dblp_url:
                links.append(f"[DBLP]({dblp_url})")
            if arxiv_id:
                links.append(f"[arXiv](https://arxiv.org/abs/{arxiv_id})")
                links.append(f"[PDF](https://arxiv.org/pdf/{arxiv_id})")
            if links:
                st.markdown(" | ".join(links))
            st.divider()


def page_journal_search():
    """Journal paper search page."""
    st.title("📰 Journal Paper Search")
    st.markdown("Search journal papers via OpenAlex.")

    vault = get_vault_path()

    query = st.text_input("Search Topic", placeholder="e.g., LLM hallucination, digital transformation IS")

    col1, col2, col3 = st.columns(3)
    with col1:
        from_date = st.date_input("From Date", value=datetime(2023, 1, 1))
    with col2:
        to_date = st.date_input("To Date", value=datetime.now())
    with col3:
        min_citations = st.number_input("Min Citations", value=0, min_value=0, step=5)

    col4, col5, col6 = st.columns(3)
    with col4:
        max_results = st.number_input("Max Results", value=30, min_value=10, max_value=200)
    with col5:
        journal_only = st.checkbox("Journal articles only", value=True)
    with col6:
        oa_only = st.checkbox("Open access only", value=False)

    if st.button("🔍 Search Journals", type="primary", use_container_width=True) and query:
        with st.status("Searching OpenAlex...", expanded=True) as status:
            st.write(f"🔍 Searching for: **{query}**")

            sys.path.insert(0, str(PROJECT_DIR / "journal-search" / "scripts"))
            from search_journals import search_openalex, score_journal_paper

            papers = search_openalex(
                query=query,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d"),
                min_citations=min_citations,
                journal_only=journal_only,
                open_access_only=oa_only,
                max_results=max_results,
            )

            query_keywords = query.split()
            for p in papers:
                p["score"] = score_journal_paper(p, query_keywords)
            papers.sort(key=lambda x: x["score"], reverse=True)

            status.update(label=f"Found {len(papers)} papers!", state="complete")

        if not papers:
            st.warning("No papers found. Try different keywords or broader date range.")
            return

        st.session_state["journal_papers"] = papers

        oa_count = sum(1 for p in papers if p["access_status"] in ("open_access_pdf", "open_access_html"))
        arxiv_count = sum(1 for p in papers if p["access_status"] == "arxiv_preprint")
        paywalled_count = sum(1 for p in papers if p["access_status"] == "paywalled")

        st.markdown("---")
        st.markdown("### Access Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(papers))
        c2.metric("🟢 Open Access", oa_count)
        c3.metric("🔵 arXiv Preprint", arxiv_count)
        c4.metric("🔴 Paywalled", paywalled_count)

        tab_all, tab_open, tab_paywalled = st.tabs(["All Papers", "🟢 Freely Available", "🔴 Need Access"])

        with tab_all:
            render_journal_papers(papers)
        with tab_open:
            free_papers = [p for p in papers if p["access_status"] != "paywalled"]
            if free_papers:
                render_journal_papers(free_papers)
            else:
                st.info("No freely available papers found.")
        with tab_paywalled:
            pw_papers = [p for p in papers if p["access_status"] == "paywalled"]
            if pw_papers:
                st.warning("⚠️ These papers require institutional access or purchase.")
                render_journal_papers(pw_papers)
            else:
                st.success("All papers are freely available!")

        if vault and st.button("📝 Generate Journal Search Note", use_container_width=True):
            generate_journal_note(papers, query, vault)


def render_journal_papers(papers):
    """Render journal paper results."""
    for i, p in enumerate(papers, 1):
        title = p.get("title", "Unknown")
        authors = p.get("authors", [])
        journal = p.get("journal_name", "Unknown journal")
        citations = p.get("cited_by_count", 0)
        pub_date = p.get("publication_date", "")
        abstract = p.get("abstract", "")
        score = p.get("score", 0)
        access_status = p.get("access_status", "unknown")
        access_message = p.get("access_message", "")
        doi = p.get("doi", "")
        pdf_url = p.get("pdf_url", "")
        arxiv_id = p.get("arxiv_id", "")
        landing_url = p.get("landing_url", "")
        concepts = p.get("concepts", [])

        if access_status in ("open_access_pdf", "open_access_html"):
            badge = "🟢 Open Access"
        elif access_status == "arxiv_preprint":
            badge = "🔵 arXiv Preprint"
        elif access_status == "paywalled":
            badge = "🔴 Paywalled"
        else:
            badge = "⚪ Unknown"

        with st.container():
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                st.markdown(f"### {i}. {title}")
            with col2:
                st.markdown(f"**{badge}**")
                st.caption(f"Score: {score}")

            st.markdown(f"**{journal}** | {pub_date} | Citations: **{citations}**")

            if authors:
                author_str = ", ".join(authors[:5])
                if len(authors) > 5:
                    author_str += " et al."
                st.markdown(f"**Authors**: {author_str}")

            if concepts:
                st.markdown("**Topics**: " + ", ".join(f"`{c}`" for c in concepts))

            if abstract:
                with st.expander("Abstract"):
                    st.write(abstract[:600] + ("..." if len(abstract) > 600 else ""))

            links = []
            if pdf_url:
                links.append(f"[📄 PDF]({pdf_url})")
            if arxiv_id:
                links.append(f"[arXiv](https://arxiv.org/abs/{arxiv_id})")
            if landing_url:
                links.append(f"[Publisher]({landing_url})")
            if doi:
                links.append(f"[DOI]({doi})")

            if access_status == "paywalled":
                st.info(f"⚠️ {access_message}")
                if landing_url:
                    st.markdown(f"👉 **[Go to publisher to download]({landing_url})**")
            elif links:
                st.markdown(" | ".join(links))

            st.divider()


def generate_journal_note(papers, query, vault):
    """Generate a journal search results note."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_query = re.sub(r'[/\\:*?"<>|]+', '_', query)

    oa_count = sum(1 for p in papers if p["access_status"] != "paywalled")
    pw_count = sum(1 for p in papers if p["access_status"] == "paywalled")

    note = f"""---
tags: ["llm-generated", "journal-search"]
date: "{date_str}"
query: "{query}"
---

# Journal Search: {query}

**Date**: {date_str}
**Total Results**: {len(papers)} | **Open Access**: {oa_count} | **Paywalled**: {pw_count}

---

"""

    for i, p in enumerate(papers, 1):
        title = p.get("title", "N/A")
        authors = ", ".join(p.get("authors", [])[:5])
        journal = p.get("journal_name", "")
        citations = p.get("cited_by_count", 0)
        pub_date = p.get("publication_date", "")
        access_status = p.get("access_status", "")
        access_message = p.get("access_message", "")
        doi = p.get("doi", "")
        pdf_url = p.get("pdf_url", "")
        arxiv_id = p.get("arxiv_id", "")
        landing_url = p.get("landing_url", "")
        abstract = (p.get("abstract", "") or "")[:300]

        if access_status == "paywalled":
            icon = "🔴"
        elif access_status == "arxiv_preprint":
            icon = "🔵"
        else:
            icon = "🟢"

        note += f"""### {i}. [[{title}]]
- **Access**: {icon} {access_message}
- **Journal**: {journal}
- **Date**: {pub_date} | **Citations**: {citations}
- **Authors**: {authors}
"""
        links = []
        if pdf_url:
            links.append(f"[PDF]({pdf_url})")
        if arxiv_id:
            links.append(f"[arXiv](https://arxiv.org/abs/{arxiv_id})")
        if landing_url:
            links.append(f"[Publisher]({landing_url})")
        if doi:
            links.append(f"[DOI]({doi})")
        if links:
            note += f"- **Links**: {' | '.join(links)}\n"

        if abstract:
            note += f"\n**Abstract**: {abstract}...\n"

        note += "\n---\n\n"

    note_dir = Path(vault) / "10_Daily"
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / f"{date_str}-journal-search-{safe_query[:30]}.md"

    with open(note_path, "w") as f:
        f.write(note)

    st.success(f"✅ Note saved to: `{note_path}`")


def page_paper_database():
    """Paper Database page — browse, search, and manage the paper DB."""
    st.title("🗄️ Paper Database")

    db = get_db()
    if not db:
        st.error("MCP paper database not available. Check that mcp-paper-db/ exists.")
        return

    # Stats
    stats = db.get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Papers", stats["total_papers"])
    c2.metric("With Notes", stats["papers_with_notes"])
    c3.metric("Domains", len(stats["by_domain"]))
    c4.metric("Sources", len(stats["by_source"]))

    if stats["by_domain"]:
        st.markdown("### Papers by Domain")
        cols = st.columns(min(len(stats["by_domain"]), 4))
        for i, (domain, count) in enumerate(stats["by_domain"].items()):
            with cols[i % len(cols)]:
                st.metric(domain, count)

    if stats["by_source"]:
        st.markdown("### Papers by Source")
        cols = st.columns(min(len(stats["by_source"]), 4))
        for i, (source, count) in enumerate(stats["by_source"].items()):
            with cols[i % len(cols)]:
                st.metric(source, count)

    st.divider()

    # Search
    st.markdown("### Search Database")
    search_col1, search_col2, search_col3 = st.columns(3)
    with search_col1:
        db_query = st.text_input("Query", placeholder="Search by title, abstract...")
    with search_col2:
        domain_options = ["All"] + list(stats.get("by_domain", {}).keys())
        db_domain = st.selectbox("Domain", domain_options)
    with search_col3:
        db_min_score = st.slider("Min Score", 0.0, 10.0, 0.0, 0.5)

    if db_query or db_domain != "All" or db_min_score > 0:
        results = search_tools.search_papers_impl(
            db,
            query=db_query or None,
            domain=db_domain if db_domain != "All" else None,
            min_score=db_min_score if db_min_score > 0 else None,
            limit=30,
        )

        st.markdown(f"### Found {len(results)} papers")
        for i, r in enumerate(results, 1):
            score = r.get("recommendation_score", 0)
            title = r.get("title", "Unknown")
            domain = r.get("domain", "")
            arxiv_id = r.get("arxiv_id", "")
            has_note = r.get("has_note", False)
            note_icon = "📝" if has_note else ""

            with st.container():
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    st.markdown(f"**{i}. {title}** {note_icon}")
                with col2:
                    st.caption(f"Score: {score:.1f}")
                st.caption(f"Domain: `{domain}` | Source: `{r.get('source', '')}` | arXiv: `{arxiv_id or 'N/A'}`")
                st.divider()

    # Recommendations
    st.markdown("### Top Recommendations (unread)")
    mcp_cfg = get_mcp_config()
    if mcp_cfg:
        recs = scoring_tools.get_recommendations_impl(db, limit=5)
        if recs:
            for i, r in enumerate(recs, 1):
                score = r.get("scores", {}).get("recommendation", 0)
                st.markdown(f"**{i}.** [{r['title']}](https://arxiv.org/abs/{r.get('arxiv_id', '')}) — Score: {score:.1f} | Domain: `{r.get('domain', '')}`")
        else:
            st.info("No unread recommendations. Run a search first!")

    # Recent activity
    st.divider()
    st.markdown("### Recent Activity (7 days)")
    if stats.get("recent_events_7d"):
        for event_type, count in stats["recent_events_7d"].items():
            st.markdown(f"- **{event_type}**: {count}")
    else:
        st.info("No recent activity.")


def page_search():
    """Search existing paper notes + database."""
    st.title("🔍 Paper Search")

    vault = get_vault_path()
    db = get_db()

    query = st.text_input("Search query", placeholder="e.g., hallucination, RAG, transformer")

    if not query:
        return

    # Use tabs if both vault and DB are available
    if vault and db:
        tab_db, tab_vault = st.tabs(["🗄️ Paper Database", "📂 Vault Notes"])
    elif db:
        tab_db = st.container()
        tab_vault = None
    elif vault:
        tab_vault = st.container()
        tab_db = None
    else:
        st.error("No search source available.")
        return

    # Database search
    if db and tab_db:
        with tab_db:
            results = search_tools.search_papers_impl(db, query=query, limit=20)
            st.markdown(f"### Found {len(results)} papers in database")
            for r in results:
                score = r.get("recommendation_score", 0)
                has_note = "📝" if r.get("has_note") else ""
                arxiv_id = r.get("arxiv_id", "")
                link = f"[arXiv](https://arxiv.org/abs/{arxiv_id})" if arxiv_id else ""
                st.markdown(f"- **{r['title']}** {has_note} — `{r.get('domain', '')}` | Score: {score:.1f} {link}")

    # Vault search
    if vault and tab_vault:
        with tab_vault:
            papers_dir = Path(vault) / "20_Research" / "Papers"
            if not papers_dir.exists():
                st.warning("No papers directory found in vault.")
                return

            results = []
            for md_file in papers_dir.rglob("*.md"):
                if md_file.name == "index.md":
                    continue
                try:
                    content = md_file.read_text(errors="replace")
                    query_lower = query.lower()
                    title_match = query_lower in md_file.stem.lower()
                    content_match = content.lower().count(query_lower)

                    if title_match or content_match > 0:
                        score = (10 if title_match else 0) + min(content_match, 10)
                        title = md_file.stem.replace("_", " ")
                        import yaml as _yaml
                        fm_match = re.match(r"^---\s*\n(.*?)^---\s*\n", content, re.MULTILINE | re.DOTALL)
                        if fm_match:
                            try:
                                fm = _yaml.safe_load(fm_match.group(1))
                                title = fm.get("title", title)
                            except Exception:
                                pass
                        results.append({
                            "title": title,
                            "domain": md_file.parent.name,
                            "path": str(md_file.relative_to(vault)),
                            "score": score,
                            "title_match": title_match,
                        })
                except Exception:
                    continue

            results.sort(key=lambda x: x["score"], reverse=True)
            st.markdown(f"### Found {len(results)} notes in vault")
            for r in results[:20]:
                icon = "⭐" if r["title_match"] else "📄"
                st.markdown(f"{icon} **{r['title']}** — `{r['domain']}` (relevance: {r['score']})")
                st.caption(f"`{r['path']}`")


def page_settings():
    """Settings page."""
    st.title("⚙️ Settings")

    # Vault path
    vault = st.text_input(
        "Obsidian Vault Path",
        value=get_vault_path(),
        help="Path to your Obsidian vault directory",
    )
    if vault:
        st.session_state.vault_path = vault
        if Path(vault).exists():
            st.success(f"✅ Vault found: `{vault}`")
        else:
            st.error("❌ Path does not exist")

    st.divider()

    # Config
    raw_config, mcp_cfg = load_config()
    if raw_config:
        config_source = str(PROJECT_DIR / "config.yaml") if (PROJECT_DIR / "config.yaml").exists() else "vault config"
        st.markdown(f"### Research Configuration (from `{config_source}`)")
        st.json(raw_config, expanded=False)

        if st.button("📂 Open config in editor"):
            config_path = PROJECT_DIR / "config.yaml"
            if config_path.exists():
                subprocess.Popen(["open", str(config_path)])
            elif vault:
                fallback = Path(vault) / "99_System" / "Config" / "research_interests.yaml"
                if fallback.exists():
                    subprocess.Popen(["open", str(fallback)])
    else:
        st.warning("No config found.")

    st.divider()

    # Paper Database
    st.markdown("### Paper Database")
    db = get_db()
    if db:
        stats = db.get_stats()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Papers", stats["total_papers"])
        c2.metric("With Notes", stats["papers_with_notes"])
        c3.metric("Sources", len(stats["by_source"]))

        st.json(stats, expanded=False)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Sync Vault Notes"):
                if mcp_cfg:
                    result = mgmt_tools.sync_vault_notes_impl(db, mcp_cfg)
                    st.json(result)
                else:
                    st.error("MCP config not available")
        with col2:
            if st.button("📊 Re-score All Papers"):
                if mcp_cfg:
                    result = scoring_tools.score_papers_impl(db, mcp_cfg, limit=500)
                    st.success(f"Scored {result['scored']} papers")
                else:
                    st.error("MCP config not available")
        with col3:
            if st.button("🔍 Find Duplicates"):
                dupes = analytics_tools.find_duplicates_impl(db)
                if dupes:
                    st.warning(f"Found {len(dupes)} duplicate groups")
                    st.json(dupes)
                else:
                    st.success("No duplicates found")

        st.caption(f"DB path: `{PROJECT_DIR / 'mcp-paper-db' / 'papers.db'}`")
    else:
        st.warning("MCP paper database not available.")

    st.divider()
    st.markdown("### MCP Server Status")
    st.markdown(f"**MCP Available**: {'✅ Yes' if HAS_MCP else '❌ No'}")
    if HAS_MCP:
        st.code(json.dumps({
            "command": str(VENV_PYTHON),
            "args": [str(PROJECT_DIR / "mcp-paper-db" / "server.py")],
            "env": {
                "OBSIDIAN_VAULT_PATH": vault or "(not set)",
                "PAPER_DB_PATH": str(PROJECT_DIR / "mcp-paper-db" / "papers.db"),
            }
        }, indent=2), language="json")
        st.caption("Add this to `.claude/settings.json` under `mcpServers.paper-db` to use with Claude Code.")


# =============================================================================
# Main App
# =============================================================================

st.set_page_config(
    page_title="evil-read-arxiv",
    page_icon="📚",
    layout="wide",
)

with st.sidebar:
    st.markdown("## 📚 evil-read-arxiv")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "🏠 Home",
            "🌅 Start My Day",
            "🔬 Analyze Paper",
            "🎓 Conference Papers",
            "📰 Journal Search",
            "🗄️ Paper Database",
            "🔍 Search",
            "⚙️ Settings",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    vault = get_vault_path()
    st.caption(f"Vault: `{vault or 'Not set'}`")
    if HAS_MCP:
        db = get_db()
        if db:
            st.caption(f"DB: {db.count_papers()} papers")

# Route to page
if page == "🏠 Home":
    page_home()
elif page == "🌅 Start My Day":
    page_start_my_day()
elif page == "🔬 Analyze Paper":
    page_paper_analyze()
elif page == "🎓 Conference Papers":
    page_conf_papers()
elif page == "📰 Journal Search":
    page_journal_search()
elif page == "🗄️ Paper Database":
    page_paper_database()
elif page == "🔍 Search":
    page_search()
elif page == "⚙️ Settings":
    page_settings()
