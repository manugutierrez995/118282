> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Migration handoff

## Current architecture (compact)

This checkout is a Vite 8 multi-entry static build and Vanilla JS browser application. Cloudflare Wrangler serves `dist` with SPA not-found fallback; there is no repository Worker fetch handler or R2 binding. Landing concurrently mounts search, Rotunda, blocks and ticker. Catalog/work/Rotunda/storage/tag JSON is bundled or served statically. Media and chapter `item.json` are direct custom-CDN requests. `Storage` only constructs URLs; pages are numeric padded filenames and no R2 listing occurs.

Reader selection dispatches an in-page event and does not update URL. Only `?work&chapter&source` is parsed on startup; pathname/hash are ignored. Each chapter render fetches unversioned `item.json`. Reader retains up to 21 image nodes and relies on browser HTTP cache after unloading. Work promises and Rotunda maps are bounded; search is promise-deduped but uses no-store. Four embedded blocks duplicate the same no-store JSON. External Cloudflare headers/hits/tier/cache rules remain unknown. Supabase discussion is the legitimate dynamic subsystem.

## Recommended target (compact)

Astro static output supplies stable layout/landing and one generated `/work/<slug>/` per public work at current scale. It loads one coordinated Vanilla TypeScript reader—not component islands/framework hydration. Typed build adapters consume canonical JSON/JSONL unchanged, redact visibility/private data, and emit immutable release catalogs/shards, work manifests, search, Rotunda and annotation snapshots. Work manifests include chapter order, page count, validated pattern or explicit names, dimensions, revision, thumbnail and annotation URL.

Use `#page-<n>` plus future structured hash parsing; replace history during passive scroll and push for explicit navigation. Every session binds to one release. Hashed app and versioned release/media assets are year+immutable; HTML and compatibility aliases are short/moderate edge cached; `current.json` is tiny/short/ETag. Publish immutable artifacts first, HTML next, pointer last. Rollback switches pointer and compatible HTML, never purges objects. Astro owns no editorial selection; future `rotunda.py` publishes final static data consumed by existing motion.

## Start implementation exactly here

Phase 0 then Phase 1, **before installing Astro**: tag the deployed state; add browser/request/schema baselines; capture live headers and Cloudflare/R2 metrics; test canonical data invariance. First behavior files only after baseline: `src/components/search.js`, the four `public/blocks/*meme.html` scripts or a parent shared loader, and new tests. Do not change appearance. Phase 2 adds Astro only in a separate non-production tree/config.

## Do not rewrite

`src/page/reader.js` semantics, `src/components/rotunda.js`, CSS, canonical `src/data/*.json`/works, JSONL/storage maps, ingestion scripts, deletor/admin tools, Supabase migration/discussion, production Wrangler/workflows, deadman pages. Wrap/adapter-test them first.

## Highest risks, gates, rollback

Risks: hidden-data leak, DOM/CSS/motion drift, history-scroll loops, irregular names, mixed releases, overwritten “immutable” media, deadman semantics, decoded memory. Gates are the complete [test checklist](TEST_AND_PARITY_CHECKLIST.md) and [measurement criteria](MEASUREMENT_AND_ACCEPTANCE_CRITERIA.md). Recommended route strategy: generated pages plus query compatibility; million-scale fallback: shared shell+compact route index+tested rewrite. Recommended release strategy: per-work immutable projections and optional shards, pointer last. Known bypasses: search and four side blocks `no-store`; repeated chapter fetch; unversioned URLs. Roll back each phase by reverting/feature flag; cutover rolls pointer and HTML deployment to retained prior release.

Unresolved blockers are live Cloudflare config, authoritative host(s), deadman behavior, slug/visibility rules, and Node/tool pins; see [open questions](OPEN_QUESTIONS.md).

No Astro production migration was performed during this reconnaissance run.
