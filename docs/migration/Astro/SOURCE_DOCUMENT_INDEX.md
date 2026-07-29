# Source document index

Code is the source of truth for current behavior; approved vision documents are direction. Dates are file-content dates when stated, otherwise **date unavailable**. This index covers every architecture/vision/migration-relevant Markdown document found under the required directories plus relevant root documents.

| Path | Date | Status | Conclusions / inherited decision | Code checked; contradiction |
|---|---|---|---|---|
| `CURRENT_ARCHITECTURE.md` | 2026-07-29 | current observation | Static Vite, direct CDN, no app Worker; preserve browser reader | `wrangler.jsonc`, `src/page/*`, `src/storage/*`; current code agrees |
| `WORKER_AND_R2_AUDIT.md` | 2026-07-29 | current observation | No reader listing; direct object GETs; Supabase is separate | repo-wide Worker patterns, reader fetches; agrees |
| `CACHE_AND_COST_REDUCTION_PLAN.md` | 2026-07-29 | proposal | version releases, fix `no-store`, shared promises | fetch sites/config; agrees; live headers unverified |
| `STATIC_READER_MIGRATION_PLAN.md` | 2026-07-29 | proposal | per-work static route/manifests and hashes | `Page`, `Reader`; routes are not implemented yet |
| `architecture.md` | unavailable | mixed | browser/static-first and immutable assets | `Storage`, ingestion; aspirational permanence exceeds unversioned keys |
| `caching.md` | unavailable | mixed | cache hierarchy, immutable naming | config/fetch sites; repository has no header policy and has `no-store` contradictions |
| `repository.md` | unavailable | mixed | intended responsibility map | actual tree; stale/incomplete for newer discussion/admin modules |
| `AUDIT.md` | unavailable | current observation | global ghost layer and reader rail constraints | `src/effects/ghost_text.js`, CSS; agrees |
| `EDIT.md` | unavailable | mixed | historical operational notes | current scripts/config; not authoritative where code differs |
| `explain_search.md` | unavailable | mixed | search generation/deployment diagnosis | `search.js`, generators; older passages say default cache, current code uses `no-store` |
| `docs/Our_Vision/future-reader-architecture.md` | unavailable | proposal | stable addresses, normalized SVG annotations, layers | reader has no hashes/overlay yet; inherit identity goals |
| `docs/Our_Vision/future-reader-architecture(continued).md` | unavailable | proposal | permissioned/provenance layers | discussion/admin code only partial; preserve layer boundary |
| `docs/deletor.md` | unavailable | mixed | repo-only safe delete/hide/tag and future remote preview | `scripts/deletor.py`; current deletion does not remote-delete |
| `docs/discussion-setup.md` | 2026-era migration name | current observation | Supabase accounts/discussion are dynamic and portable | `src/discussion/*`, migration SQL; keep outside static reader |
| `docs/ingestion.md` | unavailable | current observation | item/details/work/search/storage outputs and upload ordering | ingestion scripts and samples; generally agrees |
| `docs/reader-virtualization-checklist.md` | unavailable | current observation | manual reader virtualization checks | `createVirtualReader`; agrees |
| `docs/reasons.md` | unavailable | mixed | performance work and promise caches | contradiction: says no-store removed, current search and four blocks still use it |
| `docs/rotunda-coverflow-report.md` | unavailable | mixed | active center, keyboard, visual dependencies | `rotunda.js`/CSS; largely current, accumulated sections are historical |
| `docs/rotunda-virtualization.md` | unavailable | current observation | bounded mounted cards | `rotunda_window.js`, tests; agrees |

## Non-Markdown operational evidence

**VERIFIED IN CONFIG:** `package.json`, `vite.config.js`, `wrangler.jsonc`, `.github/workflows/deadman-switch-new.yml`, `.env.example`, and `.env.production` were reviewed. **VERIFIED IN GENERATED DATA:** representative `fetch.json`, work manifests, Rotunda, tags, storage map JSON/JSONL/CSV, search index, audit JSONL, ticker, blocks, and search data were inspected. **EXTERNAL CONFIGURATION UNKNOWN:** Cloudflare dashboard routes/rules, custom-domain cache configuration, tiered cache, request collapsing, and production response headers are not versioned here.
