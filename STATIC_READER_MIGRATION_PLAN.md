# Mostly-static reader migration plan

## Recommended target

Retain the existing lightweight Vite application and static-assets deployment. Generate a **public compact search catalog plus one public manifest per work**. The browser reads `/work/<encoded-slug>/`, fetches only that work's static manifest (or resolves it from a small loaded shard), reads the hash, constructs immutable direct media URLs, and changes pages entirely in browser state.

Do not publish the current administrative `tags.json` wholesale. Build public projections from canonical ingestion metadata. A proposed per-work schema matching observed data is:

```json
{
  "schema_version": 1,
  "catalog_version": "2026-07-29T08:59:51Z",
  "work": {
    "slug": "example",
    "title": "Example",
    "source_id": "e",
    "visibility": "public",
    "thumbnail": {"url": "https://cdn/.../thumb.<digest>.webp", "width": 600, "height": 900},
    "chapters": [{
      "id": "chapter_1",
      "label": "Chapter 1",
      "content_base": "https://cdn/.../chapter_1/r-<digest>",
      "page_count": 43,
      "page_pattern": "{page:03}.webp",
      "pages": null,
      "dimensions": [{"width": 1200, "height": 1800}],
      "annotation_manifest": "/metadata/annotations/example/chapter_1/v1.json"
    }]
  }
}
```

`pages` is an optional explicit filename array for exceptions; never assume uniform naming where ingestion found irregular files. `page_pattern` is used only when ingestion verified the sequence. Stable identities are `(work.slug, chapter.id, one-based page)`; annotation IDs are opaque and globally unique. Public manifests contain public display metadata only—no internal bucket keys, private tags, deletion markers, notes, credentials, or unpublished works.

## Routing choice

### Primary: shared static shell plus platform SPA fallback

Keep Cloudflare static asset SPA fallback (`wrangler.jsonc:6-9`) and teach `Page.start()` to recognize `/work/<slug>/`. This produces no application Worker invocation and one deploy object regardless of work count. It scales to millions of works, has short builds, and supports direct refresh on browsers that run JavaScript. Add a canonical URL and work title after manifest resolution. Limitation: generic HTML before JavaScript is weak for SEO/social previews and correctness depends on the platform fallback.

### Fallback: generated tiny `work/<slug>/index.html` files

For hosts without static fallback, generate an identical minimal redirect/bootstrap HTML file per public work. It gives reliable static 200s and per-work metadata/SEO, but creates one deployment object per work, lengthens builds/uploads, and can hit hosting file limits. Use this only for the current hundreds/thousands or for a curated SEO subset. Do not generate it for millions.

A shared `/work/index.html` rewrite is not preferable unless the hosting platform provides a static rewrite facility; a dynamic rewrite Worker would defeat the stated objective. Hash fragments never reach a server, so either routing option guarantees that page changes cannot invoke backend route logic.

## URL and browser behavior

Accept legacy `#page-23` links, but emit structured `#page=23`. Structured parameters naturally extend to `#page=23&annotation=ann_9b4f1a2&layer=public`. Parse with `URLSearchParams(location.hash.slice(1))`, falling back to the legacy regex. Rules:

1. resolve and validate the decoded pathname slug against the public manifest;
2. parse an integer page; default missing to 1; clamp or show an invalid-page message rather than silently displaying the wrong page;
3. once placeholders exist, scroll immediately (no smooth animation for initial deep links);
4. on active-page change, call `history.replaceState` during passive scroll to avoid hundreds of history entries; explicit next/previous actions call `history.pushState`;
5. handle `hashchange` and `popstate`, scrolling without rebuilding/fetching metadata;
6. preserve unknown hash parameters when changing `page` so future annotation deep links coexist;
7. canonical work navigation should use a real `<a href="/work/<slug>/#page=1">`, while in-page enhancement avoids reload.

The current IntersectionObserver already computes an active one-based page and bounded media window (`src/page/reader.js:244-325`), so hash synchronization is incremental, not a rewrite.

## Catalog generation and scale

Repository convention already generates pointer data and per-work manifests at ingestion (`scripts/ingest-work.py:1357-1394`). Evolve that pipeline:

* `public/data/catalog/v1/index.<release>.json`: compact public search/discovery rows only.
* `public/data/catalog/v1/shards/<prefix>.<release>.json`: optional slug-to-manifest maps once the compact index exceeds a chosen compressed budget (for example 500 KiB), sharded by the first 2 hex bytes of SHA-256(slug), not title characters.
* `public/data/catalog/v1/works/<encoded-or-hashed-slug>.<metadata-version>.json`: per-work public manifests.
* `src/data/admin/` or an external private store: private tags, source keys, audit state, deletion state. Never copy it to `public` or import it into the browser bundle.

JSON is preferable for per-work browser reads. JSONL is useful for offline inventory/export and incremental pipelines, but browsers cannot cheaply select one row without downloading it all. Publish a new release under versioned names, validate it, then atomically switch a tiny `current.json` pointer; retain the previous release for rollback. At millions of works, update only affected per-work manifests/shards and the pointer.

## Reversible phases

### Phase 0 — observation

Record Cloudflare route/cache analytics externally: static asset executions, CDN cache status for item/page/thumb, R2 Class A/B by operation, and request waterfalls. No code logging is presently necessary. Rollback: none. Test: baseline homepage and reader waterfall.

### Phase 1 — public work manifest pilot

Extend ingestion/generation for one fixture and one production-safe public work. Validate schema, explicit filenames/pattern, privacy projection, and missing fields. Keep current `item.json` fallback. Expected files: ingestion generator, schema validator, fixtures/tests, deployment artifact configuration. Rollback: delete pilot outputs/use fallback.

### Phase 2 — static work routing

Parse `/work/<slug>/`, load the pilot manifest, and emit real permanent links from search/rotunda while retaining query links as fallback. Expected files: `src/page/page.js`, `src/page/reader.js`, search generation, rotunda/search components, routing tests. Rollback: feature flag to legacy query resolver.

### Phase 3 — hash navigation

Add hash parser/history synchronization and deep-link scrolling around the existing virtual reader. Test direct hash, refresh, back/forward, invalid values, copy URL, mobile/desktop, and zero Worker resolver requests. Rollback: disable hash synchronization; reading remains unchanged.

### Phase 4 — remove runtime chapter metadata reads

Use manifest chapter fields to construct pages. Retain a guarded `item.json` fallback for old works until coverage reaches 100%. Automated network tests must fail if page navigation requests JSON or a Worker hostname. Rollback: re-enable fallback.

### Phase 5 — cache hardening

Publish versioned metadata/media, add version-controlled `_headers` or Cloudflare cache rules, remove accidental `no-store`, consolidate duplicate side-block requests, and tune the image window based on measurements. Rollback cache policy before deleting old versions.

### Phase 6 — scale and annotations

Shard catalogs, use atomic release pointers, add optional public annotation manifests and authenticated mutation APIs. Keep static reading independent from annotation availability.

## Tests by phase

* P1: schema fixtures for regular/irregular names, Unicode/spaces, zero/multiple chapters, dimensions/checksums, hidden/private exclusion, deterministic output and atomic release.
* P2: direct work URL/refresh, invalid slug, hidden work 404-equivalent, fallback query URL, missing manifest, canonical link.
* P3: `#page-1`, `#page=23`, invalid/negative/out-of-range page, explicit next/previous, scroll replace-state, Back/Forward, annotation parameter preservation, mobile/desktop.
* P4: request interception proving no JSON/Worker request on page change and no R2 list in ordinary reading; missing image retry; multi-chapter switching.
* P5: first/second visit cache headers, 304 behavior, release update/stale catalog, old immutable asset availability.
* P6: shard boundaries, million-row memory/performance test, public/private export diff, annotation deep links and permission failure isolation.

## Smallest safe first implementation

Generate and validate one public per-work manifest behind a feature flag, then support `/work/<slug>/#page=1` for that work while retaining the current query reader and `item.json` fallback. Do **not** remove a Worker route (none exists here), remove current catalogs, change cache headers to immutable, or remote-delete objects in that phase.

## What remains dynamic

After migration ordinary public reading needs only static asset/CDN GETs. Dynamic backends remain for authenticated discussion (`src/discussion/*`), future annotation writes/moderation/permissions, administrative publishing and deletion, private/signed content, abuse controls, and perhaps a tiny release pointer. None is called merely because a reader scrolls from page 1 to page 2.
