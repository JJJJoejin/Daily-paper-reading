#!/usr/bin/env python3
"""
evil-read-arxiv Streamlit UI
A user-friendly interface for the paper reading workflow.
"""

import streamlit as st
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


def load_config():
    """Load research config from vault."""
    vault = get_vault_path()
    if not vault:
        return None
    config_path = Path(vault) / "99_System" / "Config" / "research_interests.yaml"
    if config_path.exists():
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return None


def render_paper_card(paper, index, expanded=False):
    """Render a single paper as a card."""
    score = paper.get("scores", {}).get("recommendation", 0)
    title = paper.get("title", "Unknown")
    authors = paper.get("authors", [])
    domain = paper.get("matched_domain", "Unknown")
    keywords = paper.get("matched_keywords", [])
    summary = paper.get("summary", "") or paper.get("abstract", "") or ""
    url = paper.get("url", "")
    pdf_url = paper.get("pdf_url", "")
    arxiv_id = paper.get("arxiv_id", "")
    is_hot = paper.get("is_hot_paper", False)

    # Extract arxiv_id from URL if missing
    if not arxiv_id and url:
        m = re.search(r"/(\d{4}\.\d+)", url)
        if m:
            arxiv_id = m.group(1)

    # Score color
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
            author_str = ", ".join(authors[:5])
            if len(authors) > 5:
                author_str += " et al."
            st.markdown(f"**Authors**: {author_str}")

        if summary:
            with st.expander("Abstract", expanded=expanded):
                st.write(summary[:500] + ("..." if len(summary) > 500 else ""))

        link_parts = []
        if url:
            link_parts.append(f"[arXiv]({url})")
        if pdf_url:
            link_parts.append(f"[PDF]({pdf_url})")
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
    if not vault:
        st.warning("⚠️ Obsidian Vault path not set. Go to **Settings** to configure.")
        return

    config = load_config()
    if not config:
        st.warning("⚠️ Research config not found. Go to **Settings** to configure.")
        return

    st.success(f"✅ Vault: `{vault}`")

    domains = config.get("research_domains", {})
    st.markdown("### Your Research Domains")
    cols = st.columns(len(domains))
    for i, (name, info) in enumerate(domains.items()):
        with cols[i]:
            priority = info.get("priority", 0)
            kw_count = len(info.get("keywords", []))
            st.metric(name, f"{kw_count} keywords", f"Priority: {priority}")

    # Quick stats
    papers_dir = Path(vault) / "20_Research" / "Papers"
    daily_dir = Path(vault) / "10_Daily"
    note_count = len(list(papers_dir.rglob("*.md"))) if papers_dir.exists() else 0
    daily_count = len(list(daily_dir.glob("*paper-recommendations.md"))) if daily_dir.exists() else 0

    st.markdown("### Vault Stats")
    c1, c2 = st.columns(2)
    c1.metric("Paper Notes", note_count)
    c2.metric("Daily Recommendations", daily_count)


def page_start_my_day():
    """Start My Day - daily paper recommendations."""
    st.title("🌅 Start My Day")
    st.markdown("Search arXiv + Semantic Scholar for today's paper recommendations.")

    vault = get_vault_path()
    if not vault:
        st.error("Vault path not configured. Go to Settings.")
        return

    # Parameters
    col1, col2, col3 = st.columns(3)
    with col1:
        target_date = st.date_input("Target Date", value=datetime.now())
    with col2:
        max_results = st.number_input("Max arXiv Results", value=200, min_value=50, max_value=500)
    with col3:
        top_n = st.number_input("Top N Papers", value=10, min_value=5, max_value=30)

    categories = st.text_input(
        "arXiv Categories",
        value="cs.AI,cs.LG,cs.CL,cs.CV,cs.CY,cs.HC",
    )

    skip_hot = st.checkbox("Skip Semantic Scholar hot papers (faster)", value=False)

    if st.button("🚀 Search Papers", type="primary", use_container_width=True):
        config_path = Path(vault) / "99_System" / "Config" / "research_interests.yaml"
        if not config_path.exists():
            st.error("Research config not found.")
            return

        # Step 1: Scan existing notes
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

            # Step 2: Search papers
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

        # Load and display results
        results_path = PROJECT_DIR / "start-my-day" / "arxiv_filtered.json"
        if not results_path.exists():
            st.error("No results file found.")
            return

        with open(results_path) as f:
            data = json.load(f)

        papers = data.get("top_papers", [])

        # Fix missing arxiv_ids
        for p in papers:
            if not p.get("arxiv_id") and p.get("url"):
                m = re.search(r"/(\d{4}\.\d+)", p["url"])
                if m:
                    p["arxiv_id"] = m.group(1)

        st.session_state["search_results"] = data
        st.session_state["papers"] = papers

        # Summary
        st.markdown("---")
        st.markdown(f"### Results Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Recent Papers Found", data.get("total_recent", 0))
        c2.metric("Hot Papers Found", data.get("total_hot", 0))
        c3.metric("Unique After Dedup", data.get("total_unique", 0))

        # Display papers
        st.markdown("### Top Papers")
        for i, paper in enumerate(papers, 1):
            render_paper_card(paper, i, expanded=(i <= 3))

        # Generate note button
        if st.button("📝 Generate Recommendation Note", type="primary", use_container_width=True):
            generate_daily_note(papers, target_date, vault)


def generate_daily_note(papers, target_date, vault):
    """Generate the daily recommendation note."""
    date_str = target_date.strftime("%Y-%m-%d")

    # Collect metadata
    all_keywords = set()
    domains = {}
    for p in papers:
        all_keywords.update(p.get("matched_keywords", []))
        d = p.get("matched_domain", "Other")
        domains[d] = domains.get(d, 0) + 1

    # Build note content
    note = f"""---
keywords: [{', '.join(sorted(all_keywords)[:10])}]
tags: ["llm-generated", "daily-paper-recommend"]
date: "{date_str}"
---

# {date_str} Paper Recommendations

## Today's Overview

Today's {len(papers)} recommended papers span **{', '.join(domains.keys())}**.

- **Score Range**: {papers[-1]['scores']['recommendation']} - {papers[0]['scores']['recommendation']}
- **Domain Distribution**: {', '.join(f'{d} ({c})' for d, c in domains.items())}

---

"""

    for i, p in enumerate(papers, 1):
        title = p.get("title", "N/A")
        authors = ", ".join(p.get("authors", [])[:5])
        if len(p.get("authors", [])) > 5:
            authors += " et al."
        score = p["scores"]["recommendation"]
        domain = p.get("matched_domain", "Other")
        summary = (p.get("summary", "") or p.get("abstract", ""))[:300]
        url = p.get("url", "")
        pdf_url = p.get("pdf_url", "")
        keywords = ", ".join(p.get("matched_keywords", []))
        note_filename = p.get("note_filename", "")
        hot = " **[HOT]**" if p.get("is_hot_paper") else ""

        note += f"""### [[{title}]]
- **Score**: {score}/10{hot}
- **Authors**: {authors}
- **Domain**: {domain}
- **Keywords**: {keywords}
- **Links**: [arXiv]({url}) | [PDF]({pdf_url})
"""
        if i <= 3 and note_filename:
            note += f"- **Detailed Report**: [[20_Research/Papers/{domain}/{note_filename}]]\n"

        note += f"\n**Summary**: {summary}...\n\n---\n\n"

    # Write the note
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
    domain = st.selectbox("Domain", ["LLM", "NLP", "Machine_Learning", "IS_Management", "Other"])

    if st.button("🔍 Analyze Paper", type="primary") and arxiv_id:
        with st.status("Analyzing paper...", expanded=True) as status:
            # Step 1: Fetch metadata from arXiv
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

            # Step 2: Extract images
            st.write("🖼️ Extracting images from arXiv source...")
            import re
            safe_title = re.sub(r'[ /\\:*?"<>|]+', '_', title).strip('_')
            images_dir = Path(vault) / "20_Research" / "Papers" / domain / safe_title / "images"
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

            # Step 3: Generate note
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

            # Step 4: Update knowledge graph
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

            status.update(label="Analysis complete!", state="complete")

        # Display result
        note_path = Path(vault) / "20_Research" / "Papers" / domain / f"{safe_title}.md"
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

    vault = get_vault_path()
    if not vault:
        st.error("Vault path not configured. Go to Settings.")
        return

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

    if st.button("🔍 Search Conference Papers", type="primary", use_container_width=True) and conferences:
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

        # Load results
        results_path = PROJECT_DIR / "conf-papers" / "conf_papers_filtered.json"
        if not results_path.exists():
            st.error("No results found.")
            return

        with open(results_path) as f:
            data = json.load(f)

        papers = data.get("top_papers", [])

        # Summary
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Found (DBLP)", data.get("total_found", 0))
        c2.metric("After Keyword Filter", data.get("total_filtered", 0))
        c3.metric("S2 Enriched", data.get("total_enriched", 0))

        # Display papers
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
    st.markdown("Search journal papers via OpenAlex. Shows open access status — paywalled papers are flagged for manual download.")

    vault = get_vault_path()

    # Search parameters
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

            # Import the search module
            sys.path.insert(0, str(PROJECT_DIR / "journal-search" / "scripts"))
            from search_journals import search_openalex, score_journal_paper, get_journal_info

            papers = search_openalex(
                query=query,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d"),
                min_citations=min_citations,
                journal_only=journal_only,
                open_access_only=oa_only,
                max_results=max_results,
            )

            # Score papers
            query_keywords = query.split()
            for p in papers:
                p["score"] = score_journal_paper(p, query_keywords)
            papers.sort(key=lambda x: x["score"], reverse=True)

            status.update(label=f"Found {len(papers)} papers!", state="complete")

        if not papers:
            st.warning("No papers found. Try different keywords or broader date range.")
            return

        st.session_state["journal_papers"] = papers

        # Access summary
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

        # Filter tabs
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
                st.warning("⚠️ These papers require institutional access or purchase. Links are provided for manual download.")
                render_journal_papers(pw_papers)
            else:
                st.success("All papers are freely available!")

        # Generate note button
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

        # Access badge
        if access_status == "open_access_pdf":
            badge = "🟢 Open Access"
        elif access_status == "open_access_html":
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

            # Links
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

        # Access icon
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


def page_search():
    """Search existing paper notes."""
    st.title("🔍 Paper Search")
    st.markdown("Search your existing paper notes in the vault.")

    vault = get_vault_path()
    if not vault:
        st.error("Vault path not configured. Go to Settings.")
        return

    query = st.text_input("Search query", placeholder="e.g., hallucination, RAG, transformer")

    if query:
        papers_dir = Path(vault) / "20_Research" / "Papers"
        if not papers_dir.exists():
            st.warning("No papers directory found.")
            return

        results = []
        for md_file in papers_dir.rglob("*.md"):
            if md_file.name == "index.md":
                continue
            try:
                content = md_file.read_text(errors="replace")
                # Simple relevance: count query term occurrences
                query_lower = query.lower()
                title_match = query_lower in md_file.stem.lower()
                content_match = content.lower().count(query_lower)

                if title_match or content_match > 0:
                    score = (10 if title_match else 0) + min(content_match, 10)
                    # Extract title from frontmatter
                    title = md_file.stem.replace("_", " ")
                    import yaml as _yaml
                    fm_match = re.match(r"^---\s*\n(.*?)^---\s*\n", content, re.MULTILINE | re.DOTALL)
                    if fm_match:
                        try:
                            fm = _yaml.safe_load(fm_match.group(1))
                            title = fm.get("title", title)
                        except Exception:
                            pass

                    domain = md_file.parent.name
                    results.append({
                        "title": title,
                        "domain": domain,
                        "path": str(md_file.relative_to(vault)),
                        "score": score,
                        "title_match": title_match,
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)

        st.markdown(f"### Found {len(results)} results")
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

    # Research config
    config = load_config()
    if config:
        st.markdown("### Current Research Configuration")
        st.json(config, expanded=False)

        st.markdown("### Edit Research Domains")
        st.info("Edit the config file directly and reload:")
        config_path = Path(vault) / "99_System" / "Config" / "research_interests.yaml"
        st.code(str(config_path))

        if st.button("📂 Open config in editor"):
            subprocess.Popen(["open", str(config_path)])
    else:
        st.warning("No config found. Create one from the template:")
        if st.button("Create default config"):
            src = PROJECT_DIR / "config.yaml"
            if src.exists():
                dst_dir = Path(vault) / "99_System" / "Config"
                dst_dir.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(src, dst_dir / "research_interests.yaml")
                st.success("Config created! Reload the page.")
                st.rerun()


# =============================================================================
# Main App
# =============================================================================

st.set_page_config(
    page_title="evil-read-arxiv",
    page_icon="📚",
    layout="wide",
)

# Sidebar navigation
with st.sidebar:
    st.markdown("## 📚 evil-read-arxiv")
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠 Home", "🌅 Start My Day", "🔬 Analyze Paper", "🎓 Conference Papers", "📰 Journal Search", "🔍 Search Notes", "⚙️ Settings"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"Vault: `{get_vault_path() or 'Not set'}`")

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
elif page == "🔍 Search Notes":
    page_search()
elif page == "⚙️ Settings":
    page_settings()
