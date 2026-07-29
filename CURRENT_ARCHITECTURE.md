# Current architecture

## Scope and evidence

This report describes the repository at 2026-07-29. It distinguishes observed code from deployment assumptions. There is **no Worker JavaScript/TypeScript entry point, `fetch()` handler, R2 binding, Pages Function, service worker, `_headers`, or `_redirects` file in this repository**. `wrangler.jsonc` deploys `./dist` as static assets and applies Cloudflare's SPA not-found handling (`wrangler.jsonc:1-9`). Consequently, any Cloudflare Worker invocation attributed to ordinary site delivery is the platform's static-assets routing/billing behavior, an uncommitted dashboard rule, or infrastructure outside this repository—not application Worker code that can be removed here.

The build is a Vite multi-page build with `index.html`, `mobile.html`, and `reveal.html` as inputs (`vite.config.js:1-13`). The public application is otherwise a framework-free browser application started by `src/main.js:6-31`.

## Identity and stored data

* A work's stable identity is its exact `slug`. `fetch.json` is the bundled pointer catalog; each pointer contains a display title, source, per-work manifest path, and thumbnail URL (`src/storage/work_manifest.js:36-46`). There are currently 725 pointers and 724 per-work manifests; that count is an audit observation, not a schema guarantee.
* A work manifest is repository JSON at `src/data/works/<slug>.json`. It contains `slug`, `display`, source, ordered chapter path strings, thumbnail, optional details/archive URLs, tags, and optional `parent_work_id`. `loadWork()` resolves pointer manifests through Vite's static glob and keeps an in-memory LRU-like cache of 40 promises (`src/storage/work_manifest.js:5-33,44-73`).
* A chapter is identified by its relative chapter path (currently all observed manifests have one chapter, normally `chapter_1`; the code supports multiple strings). The chapter's R2/CDN `item.json` supplies `pages`, `padding`, `extension`, and optionally `base_url` (`src/page/reader.js:180-190`; `src/storage/manifest_resolver.js:3-13`).
* Page filenames are not listed at reader time. They are constructed as `String(page).padStart(padding, "0") + "." + extension` under `base_url` (`src/page/reader.js:189-190`). Ingestion determines pages and emits `item.json` and the work manifest (`scripts/ingest-work.py:1321-1392`).
* Storage roots are bundled from `src/data/storage.json`; `Storage` concatenates source, encoded slug, chapter, and `item.json` without making requests (`src/storage/storage.js:32-75`). Production media points at the custom CDN in that data file.
* Public tags used by discovery are consolidated in `src/data/tags.json`. Per-work public/private nested tag documents are a separate, administrative convention supported by the current deletor (`scripts/deletor.py:609-681`) and are not read by the public frontend.
* Rotunda hiding is `src/data/rotunda.json.public_rotunda.omit_works`. The frontend normalizes this policy and filters candidates (`src/components/visibility_policy.js:10-31`; `src/components/rotunda.js:507-513`). `public: false` remains a legacy/ingestion visibility signal (`scripts/ingest-work.py:1037-1053`), but ordinary reader lookup does not enforce it. Deletion is removal from repository catalogs/manifests, not remote object deletion (`scripts/deletor.py:338-368,442-455`).

## Current request flows

### Homepage

1. Cloudflare static assets serves `index.html` (or SPA fallback serves it for an unknown path).
2. The browser downloads Vite's versioned JS/CSS build output. `main.js` invokes `Page.start()` (`src/main.js:6-12`).
3. With no `?work` and `?chapter`, `Page` starts the landing UI (`src/page/page.js:8-19`).
4. Landing starts search, rotunda, content blocks, and ticker concurrently (`src/page/landing.js:83-88`). Bundled `rotunda.json`, tags, storage, and work pointers require no runtime catalog endpoint. HTML blocks, ticker JSON, ghost text, and the search index are static fetches (`src/page/landing.js:9-13`; `src/components/search.js:3-18`; `src/components/blocks.js:19-31`).
5. The rotunda initially constructs cards from pointer data, then statically fetches only manifests for its small virtual window and fetches thumbnail URLs from the CDN (`src/components/rotunda.js:360-380,388-435`).

### Selecting a work and opening the reader

Search and rotunda dispatch an in-page `open-reader` custom event rather than navigating (`src/components/search.js:26-29`; `src/page/reader.js:490-507`). The handler:

1. derives work and chapter from the selected entry;
2. constructs/follows the CDN `item.json` URL;
3. fetches that chapter metadata (`src/page/reader.js:373-408`);
4. loads the repository-hosted work manifest for chapter navigation (`src/page/reader.js:409-415`);
5. builds page placeholders and direct media URLs; and
6. loads a bounded window of 21 images around the active viewport (`src/page/reader.js:217-251`).

The selection does **not** change the browser URL. A reload therefore returns to the homepage.

### Advancing one page

There is no discrete next-page control. The reader is a continuous scroll. IntersectionObserver selects the nearest visible page, moves the 10-before/10-after image window, directly assigns CDN image `src` values, and unloads images outside the window (`src/page/reader.js:244-315`). It does not update a hash or history and does not call a Worker route. It can cause media requests as newly nearby pages enter the window; revisiting an unloaded page may reassign the same URL and relies on browser/CDN caching.

### Direct URL

The only implemented direct reader form is `/?source=e&work=<slug>&chapter=<path>` (also emitted as `/reader?...` in the generated search index). `Page.start()` requires both query parameters (`src/page/page.js:8-15`). Cloudflare's SPA not-found fallback makes `/reader?...` return the shared shell (`wrangler.jsonc:6-9`). `/work/<slug>/` is also sent to the shell, but the application does not parse that pathname, so it displays the landing page. Hashes are currently ignored.

### Metadata and media

The initial chapter request is a direct CDN GET for `works/<encoded-slug>/<chapter>/item.json`; it is repeated when a chapter is reopened because reader code has no chapter-manifest promise cache (`src/page/reader.js:394-401`). The work manifest is a static Vite asset and is promise-cached (`src/storage/work_manifest.js:23-33,52-73`), though a reader opening path can call `loadWork()` twice and benefits from that cache (`src/page/reader.js:411,439`). Full pages and thumbnails are direct CDN GETs. No frontend code lists R2.

```text
Browser -> Cloudflare static assets -> index.html + hashed JS/CSS
        -> static catalog pointer/work manifest
        -> CDN/R2 custom domain /works/<slug>/<chapter>/item.json
        -> direct CDN media /works/<slug>/<chapter>/<padded-page>.<ext>
        -> viewport scroll: browser state + more direct media GETs only
```

## Current strengths and gaps

The repository is already substantially Workerless: routing data is generated during ingestion and bundled, pages are computed, and media goes directly to the CDN. The remaining architectural gaps are permanent pathname/hash handling, canonical navigation updates, visibility enforcement at every public resolver, explicit cache policy, duplication among large bundled catalogs, and repeated/non-cacheable static requests caused by explicit `cache: "no-store"` (`src/components/search.js:6-15` and four side-block scripts).

No runtime R2 list operation was found. Runtime listing exists only in administrative tooling such as optional `build_tags.py --from-r2-details`, which runs `rclone lsf` and downloads details during an explicit build/admin operation (`scripts/build_tags.py:108-125`).
