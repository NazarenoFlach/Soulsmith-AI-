# Data Sources

SoulSmith keeps a small local dataset instead of scraping live pages at runtime. The current item data is a curated seed built from Dark Souls community wiki pages, then normalized into JSON for predictable demos and tests.

Primary source:

- Fextralife Dark Souls Wiki: https://darksouls.wiki.fextralife.com/

Dataset files:

- `backend/app/data/items/*.json` stores item stats, build tags, acquisition notes, and source URLs split by item type.
- `backend/app/data/build_templates.json` stores opinionated build templates used by the build generator.
- `backend/app/data/build_guides.json` stores short guide notes used by RAG.

Notes:

- Long wiki descriptions are not copied into the app. Item descriptions and build notes are short summaries written for this project.
- `source_url` fields point reviewers back to the reference page used for acquisition/location details.
- The catalog is intentionally local and generated/curated from wiki pages rather than scraped at runtime. Some entries have exact acquisition notes, while list-only entries keep a source URL and short local description until they are manually enriched.
