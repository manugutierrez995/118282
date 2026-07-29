# Measurement and acceptance criteria

## Baseline record (Phase 0; values currently not measured)

For cold/warm/repeat visits and representative small/large/multi-chapter works record HAR plus: request count/bytes by HTML, hashed assets, catalog, manifest, thumbnail, page, annotation, Supabase; memory/disk cache; `CF-Cache-Status`/`Age`; conditional 304; R2 Class A/B dashboards; Worker invocations; p50/p95 image start and work-open; duplicate URLs; decoded image memory; build duration and artifact count. Label CDN GET versus proven R2 miss. Current repository facts: 21 maximum reader image nodes, max-40 work/Rotunda caches, and explicit no-store sites; performance percentiles and live cache headers are **OPEN QUESTION**.

## Gates

* zero reader-time R2 listing and zero application Worker invocation for ordinary open/advance;
* zero duplicate catalog/search and unchanged chapter manifest downloads within a session;
* page advancement causes zero HTML, catalog, work or chapter-manifest request;
* warm immutable media/data is browser-cache reusable and staging repeat is edge-cache eligible;
* canonical work/page refresh, Back/Forward, invalid/hidden handling pass;
* existing canonical contract fixtures unchanged; public privacy scan has zero findings;
* visual/pixel/interaction parity approved across desktop/mobile/reduced motion;
* p95 work-open/image-start do not regress beyond an owner-approved Phase-0 budget; transferred bytes, speculative misses, and decoded memory meet explicitly selected budgets;
* build duration/artifact count stay within deployment limits at projected scale;
* immutable write guard and pointer rollback drill pass.

No numeric performance improvement is claimed until Phase 0 supplies samples. Recommended reporting compares median of ≥5 warm/cold browser runs and Cloudflare analytics over representative traffic windows.
