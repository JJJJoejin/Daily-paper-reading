# Future Improvements

## 1. Search Performance — Too Slow

The full Start My Day search (arXiv + S2 + DBLP + OpenAlex + scoring + auto-analyze) takes too long.

**Ideas:**
- Add search logging with timestamps to identify bottlenecks
- Save search logs to `mcp-paper-db/search_logs/` for analysis
- Cache API results — skip re-fetching if searched within last N hours
- Run arXiv / S2 / DBLP / OpenAlex searches in parallel (async or threading)
- Make DBLP enrichment optional (S2 enrichment is the slowest part)
- Add a "Quick mode" that only searches arXiv (fastest source)
- Show elapsed time per step in the Streamlit status

## 2. Paper Database Management

Currently no way to manage the database from the UI beyond basic stats.

**Ideas:**
- Add ability to delete papers from DB (single or bulk)
- Add ability to edit paper metadata (domain, score, tags)
- Export DB to CSV/JSON for external analysis
- Import papers from BibTeX or CSV
- DB backup/restore functionality
- Show DB growth over time (papers added per day chart)
- Add a "Clean up" button to remove low-score papers older than N days

## 3. Avoid Duplicate Recommendations Across Days

Different days may recommend the same papers if they stay high-scored.

**Ideas:**
- Track which papers were already recommended (reading_history table has this)
- Exclude papers with event_type="recommended" from past N days in `get_recommendations`
- Add a "freshness penalty" — reduce score for papers recommended before
- Show a badge on papers that were recommended previously
- Option to "dismiss" a paper so it never appears again

## 4. Image Extraction — Reconsider Necessity

Extracting images from arXiv source adds time and storage but may not always be needed.

**Ideas:**
- Make image extraction optional (checkbox, default off for auto-analyze)
- Only extract images when user explicitly clicks "Analyze Paper"
- Skip image extraction for auto-analyzed papers in Start My Day
- Store image references (arXiv URLs) instead of downloading files
- Only extract key figures (first 3-5) instead of all images
- Lazy extraction — extract on first view in Obsidian rather than upfront

## 5. News-Driven Keyword Enrichment

Use trending finance/tech news to dynamically expand paper search keywords, so paper recommendations stay aligned with what's happening in the real world.

**Ideas:**
- Pull daily headlines from finance-news MCP (WSJ, Bloomberg, CNBC, etc.)
- Extract key topics/entities from news titles and descriptions (e.g., "DeepSeek", "AI regulation", "quantum computing")
- Merge extracted topics into the existing research domain keywords as temporary "trending keywords"
- Weight trending keywords lower than core keywords (e.g., 0.3x) so they boost relevance without dominating
- Add a "Trending Topics" section in Start My Day showing which news topics influenced today's search
- Let users pin a trending keyword to make it permanent, or dismiss it
- Track which news-driven keywords led to good paper discoveries over time
- Use the rss MCP to target specific feeds (e.g., WSJ Tech, MIT Technology Review) for more relevant topics

## 6. Add Working Paper Sources

Working papers are critical for IS/management research but aren't covered by our current arXiv/S2/DBLP setup. Add SSRN, NBER, and other working paper repositories.

**Ready now (via rss-mcp, no new code):**
- NBER all new papers: `https://back.nber.org/rss/new.xml`
- NBER Productivity & Innovation: `https://back.nber.org/rss/newpr.xml`
- NBER Corporate Finance: `https://back.nber.org/rss/newcf.xml`
- Fed working papers (FEDS): `https://www.federalreserve.gov/feeds/feds.xml`

**Needs building:**
- **SSRN working papers** via OpenAlex API — filter by SSRN source (`primary_location.source.id:S4210172589`) + research keywords. Our project already uses OpenAlex for journal search, so extend `openalex` queries to include SSRN working papers
- **RePEc/IDEAS** via OpenAlex — filter by RePEc source (`source.id:S4306401271`)
- Add a "Working Papers" section to Start My Day that pulls from these sources alongside arXiv/S2
- Add a "Working Papers" page in the Streamlit UI (similar to Journal Search)
- Parse RSS results into the same paper schema and feed into `score_papers` / `upsert_paper`
- Tag working papers with `paper_type: "working_paper"` to distinguish from published/preprint
- Add IS conference proceedings to DBLP search (ICIS, ECIS, HICSS, PACIS, AMCIS)

## 7. Replace Search with paper-search-mcp

Use [openags/paper-search-mcp](https://github.com/openags/paper-search-mcp) as the primary search backend instead of our custom arXiv/S2/DBLP/OpenAlex clients. Keep our paper-db MCP for scoring, storing, and organizing.

**Ideas:**
- Add paper-search-mcp to `.mcp.json` (`uvx paper-search-mcp` — one command, no cloning)
- Use its unified `search_papers` tool (queries 24 sources in parallel, deduplicates automatically)
- Leverage `download_with_fallback` for smart PDF fetching (native → Unpaywall → Sci-Hub opt-in)
- Use its `read_*` tools to extract full paper text for LLM analysis (no more LaTeX-only)
- Retire our custom `arxiv_client.py`, `s2_client.py`, `dblp_client.py` over time
- Keep our `scoring_engine.py` and `get_recommendations` — paper-search-mcp doesn't score
- Map paper-search-mcp results into our paper-db schema via `upsert_paper`

## 7. Two-Stage Analysis (Skim → Deep Dive)

Inspired by [PaperMind](https://github.com/Color2333/PaperMind). Currently every paper gets the same full analysis, which is slow and expensive. Split into two stages so Start My Day stays fast.

**Ideas:**
- **Skim stage** (fast, cheap): LLM reads title + abstract only → one-line summary, innovation points, relevance score (0–1)
- **Deep dive stage** (on demand): Full PDF text + figure analysis → methodology breakdown, experiment summary, limitations, comparison with related work
- Run skim on all candidates during Start My Day, deep dive only on top N papers
- Add a "Deep Dive" button in the UI to trigger full analysis on any skimmed paper
- Use a cheaper/faster model for skim (e.g., DeepSeek-Chat), capable model for deep dive
- Store both skim and deep-dive results in the DB with separate fields
- Show skim results as preview cards, deep dive as full Obsidian notes
- Track cost per stage — skim should be <10% of deep dive cost

## 8. Citation Graph & Relationship Mapping

Inspired by [PaperMind](https://github.com/Color2333/PaperMind). Go beyond scoring individual papers — map the relationships between them.

**Ideas:**
- Add `build_citation_tree` tool to paper-db MCP — given a paper, fetch its references and citations via Semantic Scholar API
- Store citation edges in the existing `citations` table with context (e.g., "extends", "contradicts", "applies")
- **Bridge paper detection** — find papers that connect two different research domains
- **Research frontier detection** — identify papers with high citation velocity (many recent citations)
- **Co-citation clustering** — group papers that are frequently cited together
- **PageRank scoring** — rank papers by influence within the citation network
- Visualize the citation graph in the Streamlit UI (e.g., using pyvis or streamlit-agraph)
- Export graph data to Obsidian PaperGraph for knowledge graph visualization
- Add "Related Papers" section to analysis notes based on citation proximity
- Use citation context to improve scoring — a paper cited by many high-scored papers should score higher

## 9. Daily Email Digest

Inspired by [PaperMind](https://github.com/Color2333/PaperMind). Push the morning paper recommendations to email so you don't need to open the UI.

**Ideas:**
- After Start My Day completes, generate an HTML email with today's top papers
- Include: paper title, authors, skim summary, relevance score, arXiv link
- Use Python `smtplib` + `email.mime` or a service like SendGrid / Resend
- Add email config to `config.yaml` (SMTP host, recipient, send time)
- Option to set a schedule (e.g., 7:00 AM daily) via APScheduler or cron
- Include a "Trending Topics" section from the news-driven keyword enrichment (#5)
- Add a "Read More" link that opens the full analysis in the Streamlit UI
- Keep it lightweight — the email is a teaser, not the full analysis
- Option to disable email and only use the UI

## 10. Cloud Deployment, Production Database & Mobile App

Move from local-only Streamlit to a cloud-hosted service with a proper database, and ship a mobile-friendly app. Extend beyond CS/AI to support any research field.

**Multi-Field Support:**
- Add an onboarding / profile page where users define their research fields
- User inputs: field name, keywords, relevant journals, conferences, arXiv categories
- Provide presets for common fields (Biology, Physics, Medicine, Economics, etc.) that users can customize
- Map fields to the right data sources — arXiv categories, S2 topic filters, OpenAlex concepts, PubMed for biomedical, SSRN for social sciences
- Per-user scoring weights (e.g. a biologist may care more about journal impact factor than arXiv recency)
- Store user profiles and field configs in the database (per-user, not a single config.yaml)

**Cloud & Infrastructure:**
- Deploy backend to a cloud server (AWS/GCP/Fly.io/Railway)
- Replace SQLite with a production database (PostgreSQL or PlanetScale/Turso)
- Add a REST or GraphQL API layer (FastAPI) between the frontend and DB
- Set up scheduled search jobs (cron / cloud scheduler) instead of on-demand
- Environment-based config (dev/staging/prod)
- Add authentication (OAuth / API keys) for multi-user support

**App UI & Mobile:**
- Redesign UI for mobile-first (responsive layout, touch-friendly)
- Evaluate frameworks: React Native, Flutter, or PWA (Progressive Web App)
- PWA is the fastest path — wrap the existing web UI with a service worker for offline + home-screen install
- Native app alternative: build with React Native / Expo for iOS & Android
- Push notifications for daily paper recommendations
- Offline reading — cache paper metadata and notes locally on device
- Swipe-based paper triage (swipe right = bookmark, left = dismiss)

**Data & Sync:**
- Cloud DB as single source of truth, synced to mobile
- Replace Obsidian vault dependency with in-app note editor
- Export to Obsidian / Notion / Zotero as an optional integration
