# Current-state audit

## Scope and method

The investigation read every Markdown file under `docs/`, the root architecture/migration reports, all application entry points and application modules, Vite/Wrangler/package configuration, the only GitHub workflow, the Supabase migration, ingestion/search/tag scripts, tests, and representative/generated catalog data. Broad searches covered auth, bookmarks, profiles, browser storage/history/fragments, middleware, redirects, service workers, `item.json`, `details.json`, and `tags.json`. Generated work manifests and catalog/index files were also machine-audited rather than assuming uniformity.

Important existing plans include `STATIC_READER_MIGRATION_PLAN.md`, `CURRENT_ARCHITECTURE.md`, and the complete `docs/migration/Astro/` reconnaissance. They correctly identify query-only routing, static SPA fallback, virtual reader behavior, and a future static-manifest approach. This package narrows those findings to URLs/accounts; it does not declare the proposed Astro migration complete or currently active.

## Framework, entry points, and routing

- `package.json` identifies a dependency-light ES-module application: Vite plus Supabase JS, not React/Vue/Astro.
- `vite.config.js` builds `index.html`, `mobile.html`, and `reveal.html`. `index.html` and `reveal.html` contain the same application shell and load `/src/main.js`; `mobile.html` is a standalone maintenance image.
- `src/main.js` imports landing CSS, starts ghost text, awaits `Page.start()`, then starts the footer. It has no router lifecycle.
- `src/page/page.js` is the complete startup dispatcher. It reads `work` and `chapter` from `window.location.search`; if both exist it calls `Reader.start`, otherwise `Landing.start`. Pathname and hash are ignored. There is no route table, not-found route, middleware, or account guard.
- A search of source found no calls to `history.pushState`, `history.replaceState`, `popstate`, or `hashchange`. Existing mentions are plans only.

Current direct reader URL shape is effectively:

```text
/?source=e&work={storage-slug}&chapter={chapter-path}
```

The generated search index also carries `/reader?source=e&work=...&chapter=...`, but `/reader` works on Cloudflare only because the SPA fallback serves the shell; it is not a distinct Vite HTML entry or recognized pathname.

## Landing page, rotunda, and search opening flow

`src/page/landing.js` replaces the center container with header/search, rotunda, ticker, and blocks, then starts those modules concurrently. There is no account control.

`src/components/rotunda.js` builds a bounded coverflow window. Clicking a card dispatches `CustomEvent("open-reader")` with source, slug, and first chapter. `src/components/search.js` similarly renders buttons and dispatches `open-reader` with the index entry. Neither uses a link, changes the address bar, nor preserves a history entry. Chapter controls in `src/page/reader.js` dispatch the same event. This is the confirmed primary reason works opened through the application lack stable URLs: navigation is an in-memory DOM transition, while startup routing understands only legacy query parameters. It is not caused by R2 performance or a proven decision against route generation.

The rotunda keeps its active logical index in module/runtime state; it does not serialize it to the URL. It filters via `src/components/visibility_policy.js` / `src/utils/visibility.js` and `public_rotunda` fields in `src/data/rotunda.json`, not user preferences.

## Work catalog, identifiers, and metadata

### Checked-in contract

- `src/data/fetch.json` and `src/data/rotunda.json` each currently contain 725 entries. Entries use `slug`, `display`, `source`, `manifest`, and `thumb` (with occasional tags/public fields).
- `src/storage/work_manifest.js` looks up catalog entries by exact slug and loads bundled `src/data/works/*.json` via `import.meta.glob`, using a 40-entry in-memory LRU-like promise cache.
- There are 724 valid JSON files in `src/data/works/`. Every one contains `version`, `slug`, `display`, `source`, `thumb`, `chapters`, and `parent_work_id`; 548 include remote `details` and `archive` URLs; 424 contain `tags`. None contains a field literally named `id`.
- `parent_work_id` is numeric in the sampled/audited manifests and is passed as a string to `mountDiscussion` in `src/page/reader.js`. The database calls it `work_id`. Its creator is ingestion: `scripts/ingest-work.py` and `scripts/ingest-work-skip-invalid.py` write parent IDs into chapter/work metadata. The repository does not document whether the value is globally immutable or how it is allocated.
- Storage slugs are exact, case-sensitive directory identifiers, often long, underscore-heavy, punctuated, and unsuitable as a clean public slug. `Storage.work()` percent-encodes the whole work slug; chapter strings are appended without segment-by-segment encoding (`src/storage/storage.js`).

The one-entry mismatch (725 catalog entries versus 724 work files) and unusual filenames are reasons to generate a validated identity map rather than equating filenames with canonical public paths.

### `item.json` and `details.json`

No local `item.json` or `details.json` exists. They are R2/CDN objects referenced/generated by ingestion. Chapter `item.json` is the runtime reader manifest: page count, padding, extension, base URL and parent identifiers are written by ingestion (`scripts/ingest-work.py`; `docs/ingestion.md`). Work manifests point at remote `details.json` when present. This means their production contents cannot be completely audited offline; the checked-in per-work projections are the deploy-time public metadata available to routing.

### Search indexes

Both `public/data/search.index.json` and `src/data/search.index.json` exist, plus audit/backups. `src/components/search.js` fetches only `/data/search.index.json` with `cache: "no-store"`. The public file has 1,450 entries—duplicates are expected from the current generator/input history—and includes `reader_url`, `manifest_url`, source/work/chapter, display, normalized tokens, tags, and `parent_work_id` where available. `scripts/generate_search.py` and `src/tools/generate_search.py` are duplicate generator locations; `explain_search.md` documents prior synchronization problems.

## Reader behavior and identifiers

`src/page/reader.js`:

1. Resolves source from `?source=` (default `e`), builds the remote chapter `item.json` URL, fetches it, and runs `resolveManifest`.
2. Loads the bundled work manifest to obtain chapter order.
3. Creates one `.reader-page` placeholder for every page with `data-page="N"` and an estimated aspect ratio.
4. Loads images only within active page ±10; the first three are eager/high-priority. Thus DOM positions are **not** virtualized, but image elements are. This distinction makes anchor/deep-linking feasible after placeholders exist.
5. Uses IntersectionObserver (or an `elementFromPoint` fallback) to select an active page and shift the media window. Diagnostics report the active one-based page.
6. Adds no `id="page-N"`, does not read a page from the URL, and does not update history.
7. After render, waits 50 ms and smooth-scrolls to `#chapter-start`. A deep-link implementation must replace this unconditional behavior to avoid jumping through page 1.
8. Desktop and mobile share the same JS and responsive CSS. Top chrome auto-hides after 1.4 seconds unless hovered, focused, or search is open. Side blocks are hidden/reflowed by media rules; there is no separate functional mobile reader.

`docs/reader-virtualization-checklist.md` and tests confirm bounded loaded images. Future-reader documents propose persistent annotation coordinates and deep links but are vision, not active code.

## Authentication and user data

### Client

`src/discussion/supabase.js` lazily imports Supabase and creates one client when `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` exist. Auth options are `persistSession`, `autoRefreshToken`, and `detectSessionInUrl`, all true. It exposes `getSession`, anonymous sign-in, and Google OAuth. If an anonymous session exists, Google uses `linkIdentity`, preserving the same user; otherwise it uses `signInWithOAuth`. Redirect target is the current reader URL.

There is no email/password sign-up/sign-in/reset UI or call, no top-level AuthProvider/session store, no `onAuthStateChange` subscription, and no route guard. Discussion mounts lazily near the reader and independently gets the session. Drafts use `sessionStorage`; Supabase itself owns persisted auth token storage. No application cookies are used directly.

### Database migration (repository proposal; applied state unknown)

`supabase/migrations/202607170001_discussion_mvp.sql` defines:

- `profiles`, keyed by `auth.users(id)`, with display name/avatar;
- public comments and private authorship/votes/reports;
- `bookmarks(user_id, work_id, created_at)` with a composite primary key;
- owner-only bookmark select/insert/delete RLS;
- `ensure_profile()` sourced from Auth metadata;
- public profile reads, because names are displayed with public comments.

The reader passes `parent_work_id` to discussions and exposes a work-level Bookmark button through `src/discussion/discussion.js`. `src/discussion/service.js` can query/toggle only the current work bookmark. There is no bookmarks page, chapter/page bookmark, label/notes, update time, progress, preferences, or local anonymous-progress migration. Anonymous users can currently create bookmark rows because `toggleBookmark` calls anonymous auth and the policy role behavior depends on the resulting JWT; product semantics must be tightened for account bookmarks.

The existing `profiles_public_read` policy is a material privacy mismatch. The rework should either (recommended) keep a minimal separately named `discussion_profiles` public projection and make `profiles` private, or remove public account display entirely. A private account page must never rely on this current public policy.

## Tags and visibility

`src/data/tags.json` version 1 is a dictionary keyed by storage slug. Each value is `{tags: string[], sources: string[], updated_at}`. Tags are merged by `scripts/build_tags.py` from fetch, manifest, rotunda, and ingestion sources. Many values are empty; many contain only `manifest`, which appears to be pipeline provenance rather than a reader-facing content category. Per-work manifests may repeat the array. No canonical tag vocabulary, ID, alias table, casing contract, or user preference store exists.

Visibility is separate: `src/data/rotunda.json` contains showcase/omit tag lists and explicit omitted slugs; `src/components/visibility_policy.js` and `src/utils/visibility.js` decide public rotunda inclusion. User exclusions must layer after global visibility and must never rewrite these canonical files.

## Bookmarks, profiles, and personalization search result

Confirmed present: Supabase work-level bookmarks, discussion profiles, Google/anonymous Auth, session drafts. Confirmed absent from application source: account pages, profile editor, settings, email/password flows, recommendation engine, per-page/chapter bookmark schema, reading progress, user tag preferences, IndexedDB content/progress cache, service worker, middleware, edge auth handler, and personalization cookies/local storage. The only direct `localStorage` calls are cycling indices inside four decorative public block HTML files.

## Deployment and cache

- `wrangler.jsonc` deploys `./dist` as Worker static assets with `not_found_handling: "single-page-application"`. There is no Worker JavaScript entry, Pages Functions directory, `_redirects`, or `_headers`.
- The repository language sometimes says Cloudflare Pages, Worker assets, and GitHub Pages. The checked-in deploy configuration is Wrangler static assets. It provides a shell fallback, not server-side route status/metadata/auth.
- `.github/workflows/deadman-switch-new.yml` mutates `index.html`/`mobile.html` based on `date.txt`; it is not a Pages deployment. No `404.html`, GitHub Pages action, CNAME, or Vite `base` is configured.
- No service worker registration/file was found. Browser HTTP cache and CDN/R2 caching are the live public layers. Search explicitly bypasses browser cache; work manifests use normal fetch caching; Supabase calls are dynamic.

## Why individual works lack URLs (confirmed)

The immediate cause is architectural, not scale: work selections dispatch a custom event into a single already-loaded document and `renderManifestInto` replaces the central DOM without invoking history. The only startup routing is a legacy query parser. Existing slugs and IDs are sufficient to identify works internally, and Cloudflare already has SPA fallback, but no canonical route resolver/link generator exists. Static generation limitations are therefore a deployment concern for the solution, not the cause of current behavior.

## Risks and technical debt

1. `parent_work_id` looks usable but lacks a written immutability/uniqueness contract.
2. Storage slug, public slug, and title are conflated; renames can break R2 paths.
3. Catalog counts differ and search entries duplicate.
4. Hidden-work policy is rotunda-centric; direct-route disclosure behavior is undefined.
5. Cloudflare SPA fallback returns generic HTML/status for missing routes; true edge 404/canonical metadata is unavailable without generated pages or edge logic.
6. GitHub Pages support is documentation-only/aspirational and direct nested routes would fail as configured.
7. Auth is discussion-local and anonymous-first; private account semantics need a shared session boundary.
8. Public-readable `profiles` conflicts with private profiles.
9. Existing bookmarks only identify works and may include anonymous users.
10. Tags contain pipeline markers and lack normalization/taxonomy.
11. `chapter` values and legacy work slugs require safe decoding/validation; never interpolate untrusted paths into R2 URLs.
12. The unconditional reader startup scroll conflicts with deep links and native scroll restoration.
