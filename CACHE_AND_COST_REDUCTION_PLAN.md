# Cache and cost reduction plan

## Current cache behavior

No version-controlled HTTP response header configuration exists. The only Cloudflare config is static assets plus SPA fallback (`wrangler.jsonc:6-9`); therefore CDN defaults/dashboard rules are unknown. No Worker cache API, custom cache key, range logic, service worker, or explicit ETag response generation exists. Vite hashes built JS/CSS filenames, but catalog and CDN media URLs are unversioned. Query strings affect only the shell request; hashes never enter HTTP cache keys.

Browser code makes two deliberate cache bypasses: search uses `cache: "no-store"` (`src/components/search.js:6-15`) and four side blocks fetch the same JSON with `no-store`. Work-manifest promises are cached in memory (40 entries) (`src/storage/work_manifest.js:23-33`); rotunda metadata/thumbnails have page-lifetime maps and abort stale requests (`src/components/rotunda.js:360-435`). Chapter `item.json` lacks an application cache (`src/page/reader.js:394-408`). No page preload link exists; the reader explicitly creates eager first-three images and a 21-image proximity window (`src/page/reader.js:8-13,217-251`).

## Required policy by resource

These values are recommended only after confirming Cloudflare/R2 headers and introducing versioned names where stated.

| Resource | Recommended public policy | Versioning/validators | Reason |
|---|---|---|---|
| Hashed app JS/CSS | `public, max-age=31536000, immutable` | Vite content hash; ETag optional | bytes never change at URL |
| Reader/home HTML | `public, max-age=0, s-maxage=300, stale-while-revalidate=86400, must-revalidate` | strong/weak ETag | fast edge shell, rapid deploy pickup |
| Tiny `current.json` release pointer | `public, max-age=60, s-maxage=300, stale-while-revalidate=3600` | ETag + conditional GET | bounded staleness and atomic release switch |
| Versioned global compact index | `public, max-age=31536000, immutable` | release/content hash | immutable and shared |
| Versioned catalog shards | same as index | release/content hash | immutable and independently cacheable |
| Versioned per-work manifest | `public, max-age=31536000, immutable` | metadata-version in URL | old deep links remain coherent |
| Unversioned compatibility manifest | `public, max-age=300, s-maxage=3600, stale-while-revalidate=86400` | ETag/Last-Modified | safe transition while overwrites remain possible |
| Versioned thumbnails | `public, max-age=31536000, immutable` | content hash in key | high reuse; prevents stale overwrite |
| Versioned full pages | same | content hash/revision directory; ETag optional | dominant Class B/bandwidth cache opportunity |
| Public annotation/tag layer | versioned snapshot: immutable; pointer: short policy as above | schema/layer version + ETag | annotation availability must not block images |
| Frequently updated public annotations | `public, max-age=30, s-maxage=60, stale-while-revalidate=300` | ETag | tolerates brief staleness without long poisoning |
| Hidden/private/admin metadata | `private, no-store`; authenticated endpoint only | authorization-aware ETag only if safe | must never enter shared/public cache |

Use `s-maxage` only where Cloudflare honors it. Ensure CDN cache keys normalize or reject irrelevant tracking query strings for immutable media; never use arbitrary query strings as the versioning scheme. Preserve `Range` and conditional headers at the CDN for archives, but normal WebP page images usually do not need range requests. Verify `Accept-Ranges`, ETag, `CF-Cache-Status`, `Age`, content encoding/Vary, and HEAD behavior empirically.

## Concrete request reductions

1. Remove `cache: "no-store"` from search and publish a versioned index. This saves repeated 3.2 MB downloads; it does not merely move them to another backend.
2. Let the parent load `side_column_images_cycle.json` once and pass it to blocks, or use a module-level shared promise. This eliminates duplicate browser requests; cache headers alone may only turn them into local cache lookups.
3. Put page count/padding/format/explicit exceptions into per-work public manifests at ingestion. This eliminates every reader-time `item.json` read, rather than moving it to a Worker.
4. Never run R2 `list` during reading. Maintain an append-only ingestion inventory and update affected manifests/index shards during upload. This turns periodic Class A full scans into bounded ingestion writes.
5. Version page/thumbnail keys. Edge and browser caches can then safely retain them for a year without purge operations or stale content.
6. Cache in-flight chapter/work manifest promises and abort obsolete chapter loads. The current work cache is a good pattern (`src/storage/work_manifest.js:23-33`).
7. Tune the current 10+1+10 page window. A cheaper policy is active ±2 loaded immediately and the next 1–2 prefetched only on fast/unmetered connections; preserve decoded nearby images until the memory budget is reached. This reduces speculative Class B cache misses, though it may trade some next-scroll latency.
8. Include page dimensions in manifests so placeholders do not require image decode before layout correction (`src/page/reader.js:192-204`). This improves stability/speed but does not itself save an R2 GET.
9. Keep thumbnails separate/small. Do not use the first full page as a thumbnail fallback unless already cached; generate WebP/AVIF derivatives at ingestion.
10. Use CDN request collapsing/tiered cache where available. This can reduce R2 origin GETs but shifts cost to Cloudflare CDN features; measure total spend rather than labeling it free.

## Invalidations and rollback

Never overwrite an immutable URL. Publish media and manifests, validate, publish indexes, then switch `current.json` last. Retain the prior release for at least the HTML/catalog maximum staleness plus rollback window. On rollback switch the pointer; do not purge millions of objects. ETags are useful on short/unversioned pointers but waste requests on already immutable objects.

A service worker is not recommended now: native HTTP caching plus versioned assets solves the cost goal without dual-cache invalidation, storage quotas, opaque cross-origin responses, or a stuck-reader failure mode. Reconsider only for a measured offline-reading requirement with explicit per-work opt-in and version-aware eviction.

## Measurement gates

For each phase record requests by URL type, transferred bytes, cache status, R2 Class A/B operations, p50/p95 image start, and browser decoded-image memory. Automated browser tests should intercept traffic and assert: no Worker/API JSON during page navigation; no list endpoint during ordinary reading; no duplicate catalog request; second visit serves versioned assets from browser/edge cache; stale pointers upgrade without mixing catalog/media versions.
