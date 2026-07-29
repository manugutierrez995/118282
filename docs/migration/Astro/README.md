# Astro migration reconnaissance

## Why Astro, and why now

**VERIFIED IN CODE:** this is already a mostly Workerless, framework-free Vite browser application deployed as Cloudflare static assets. `wrangler.jsonc:1-9` has an assets directory and SPA fallback, but no Worker entry point or R2 binding. Astro is therefore **not** proposed as a Worker replacement. **RECOMMENDATION:** use Astro for static layouts, permanent work routes, build-time adapters, and release artifacts while retaining the coordinated reader and CSS.

The goal is a mostly static route graph whose request order is memory → browser HTTP cache → Cloudflare edge → R2/origin. R2 remains durable truth, never first resort. Existing JSON/JSONL and ingestion/admin behavior are immutable migration constraints. No React/Vue/Svelte or service worker is justified. Preserve the Rotunda presentation while placing future editorial selection behind versioned static JSON.

## Future Codex: Start Here

Read, in this exact order, before changing code:

1. [Migration handoff](MIGRATION_HANDOFF.md)
2. [Source document index](SOURCE_DOCUMENT_INDEX.md)
3. [Current runtime flow](CURRENT_RUNTIME_FLOW.md)
4. [Current cache audit](CURRENT_CACHE_AUDIT.md)
5. [Data contracts](DATA_CONTRACTS.md)
6. [Routing and URLs](ROUTING_AND_URLS.md)
7. [Target architecture](ASTRO_TARGET_ARCHITECTURE.md)
8. [Component boundaries](ASTRO_COMPONENT_BOUNDARIES.md)
9. [Static release plan](STATIC_RELEASE_AND_CATALOG_PLAN.md)
10. [Cache plan](CACHE_PLAN.md)
11. [Reader loading plan](READER_LOADING_AND_MEMORY_PLAN.md)
12. [Rotunda boundary](ROTUNDA_INTEGRATION_BOUNDARY.md)
13. [File matrix](FILE_MIGRATION_MATRIX.md), [symbol index](FUNCTION_AND_SYMBOL_INDEX.md), and [repository map](REPOSITORY_MAP.md)
14. [Phases](MIGRATION_PHASES.md), [tests](TEST_AND_PARITY_CHECKLIST.md), and [acceptance gates](MEASUREMENT_AND_ACCEPTANCE_CRITERIA.md)
15. [Open questions](OPEN_QUESTIONS.md)

## Implementation order

Freeze/measure → cache-only corrections → parallel Astro shell → typed adapters/public projections → generated work routes → wrap reader → hash/history → cache hardening → static Rotunda boundary → measured cutover. Each phase has an immediate rollback in [MIGRATION_PHASES.md](MIGRATION_PHASES.md).

## Non-negotiable acceptance criteria

* Zero reader-time R2 listing and zero application Worker calls for normal reading/page advancement.
* Canonical `/work/<slug>/#page-<n>` refresh, Back, and Forward behavior.
* No duplicate catalog/chapter-manifest request per session; immutable media reused across visits.
* Canonical JSON/JSONL, ingestion outputs, admin tools, CSS, and reader interaction remain compatible.
* Hidden/private metadata never enters a public release.
* Rotunda visuals remain client-owned; future editorial logic remains generator-owned.
* Production switches only after parity/cache measurement and remains pointer-rollbackable.

**DOCUMENTED INTENT:** annotations remain normalized, non-destructive SVG overlays with persistent IDs. **RECOMMENDATION:** Astro provides the shell and static manifest link, not annotation semantics.
