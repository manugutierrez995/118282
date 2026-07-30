# Current-state audit

## Scope and evidence

This audit inspected all tracked documentation (`docs/`, root architecture/audit/cache plans, and the Astro migration package), application entry points, every `src` subsystem, deployment/build files, GitHub workflow, tests, ingestion/search/deletion scripts, checked-in Supabase migrations, catalog indexes, and machine-audited work manifests. Searches covered auth/OAuth, profiles, bookmarks, preferences, browser storage/history, hashes/queries, service workers, middleware, redirects/rewrites, `item.json`, `details.json`, and `tags.json`.

The Astro documents are a future migration design, not the running framework (`docs/migration/Astro/README.md`, `docs/migration/Astro/ROUTING_AND_URLS.md`). Root plans such as `CURRENT_ARCHITECTURE.md`, `STATIC_READER_MIGRATION_PLAN.md`, `caching.md`, and `WORKER_AND_R2_AUDIT.md` are valuable context but sometimes describe desired rather than active behavior.

## Framework, build, and entry points

- `package.json`: native ES modules; Vite/Wrangler dev dependencies; no UI framework and no Supabase JS dependency currently installed.
- `vite.config.js`: Rollup inputs are `index.html`, `mobile.html`, and `reveal.html`. `index.html`/`reveal.html` load `/src/main.js`; `mobile.html` is a maintenance image, not an alternate reader.
- `src/main.js`: starts ghost text, `Page`, local profiles, monetization, and footer. Startup is client-only.
- `wrangler.jsonc`: static assets from `dist`, `not_found_handling: "single-page-application"`; no Worker script or request handler.
- `.github/workflows/deadman-switch-new.yml`: maintenance/deadman automation only. There is no Pages deploy, base-path setting, or `404.html` fallback.
- Repository search found no service worker registration/file, `_redirects`, `_headers`, `404.html`, middleware, edge function, Cloudflare Cache API code, or application cookies.

## Active routing

`src/router/router.js` is a small History API router. It recognizes `/`, `/profiles`, `/profiles/new`, `/account/profile`, `/account/bookmarks`, and `/account/settings`; redirects `/account`; and treats `/login`, `/signup`, forgot/reset paths as legacy redirects to `/profiles`. It intercepts only anchors marked `data-route`, uses `pushState`/`replaceState`, listens for `popstate`, and emits local not-found views. `safeNext` currently permits only the three account paths.

`src/page/page.js` renders those routes. Its “guard” checks for a selected local IndexedDB profile, not an authenticated session. Unknown `/account/*` gets an account not-found view. A query containing both `work` and `chapter` wins regardless of pathname and invokes `Reader.start`; this is the legacy reader contract.

There is no `/works`, work-detail, canonical reader, auth callback, or true auth route.

## Why opened works have no stable URL (confirmed)

`src/components/rotunda.js` and `src/components/search.js` dispatch `open-reader` with source/work/chapter. Reader chapter controls do the same (`src/page/reader.js`). The global listener renders into existing landing/block DOM and never calls the router or History API. Rotunda selection is runtime state. Consequently the initial URL remains `/`; refresh/back/copy cannot reproduce the opened work. This is a code-path choice, not a demonstrated static generation, R2, caching, or efficiency limitation. Legacy search data does contain `/reader?source=...&work=...&chapter=...`, and Cloudflare's SPA fallback happens to serve it, but the active route table has no `/reader` route.

## Work data and identifiers

- `src/data/fetch.json`: 725 work catalog entries and default source. `src/storage/work_manifest.js` matches exact `slug`, loads a bundled per-work JSON using `import.meta.glob`, and keeps up to 40 promises.
- `src/data/rotunda.json`: 725 candidates plus public showcase/omit policy.
- `src/data/works/*.json`: 724 valid manifests. Machine audit found all 724 have `slug`, `display`, `source`, `chapters`, and a unique `parent_work_id`; none has a literal `id` field.
- `parent_work_id` is passed to local discussion/bookmark UI as work identity (`src/page/reader.js`, `src/discussion/discussion.js`). Ingestion writes it into work/chapter metadata (`scripts/ingest-work.py`, `scripts/ingest-work-skip-invalid.py`), but allocation and immutability are not documented. It is a **candidate**, not yet a proven permanent ID.
- Exact storage slugs are long, case-sensitive, underscore/punctuation-heavy directory names. `src/storage/storage.js` percent-encodes the work slug but appends chapter paths as supplied. A separate public slug is necessary.
- The 725/724 mismatch must be reported by Phase 1; silently omitting it would create a broken canonical route.

### Remote metadata

No runtime `item.json` or `details.json` is checked in. Ingestion writes chapter `item.json` with `pages`, `padding`, `extension`, `base_url`, and parent data; the reader fetches it from R2/CDN (`src/page/reader.js`, `src/storage/manifest_resolver.js`, `docs/ingestion.md`). `details.json`, `tags.json`, archives, and images live beside remote work/chapter assets. Checked-in work manifests are the available deploy projection; raw remote details must not become public route metadata without an allowlist.

### Search indexes

Both `public/data/search.index.json` and `src/data/search.index.json` exist and currently contain 1,450 entries (work + chapter records). Entries include source, storage work slug, chapter, legacy `reader_url`, remote manifest URL, and search tokens. `src/components/search.js` fetches `/data/search.index.json` with `cache: "no-store"`. `scripts/generate_search.py` and `src/tools/generate_search.py` duplicate generator roles; `explain_search.md` records prior stale-copy problems. A new route manifest must have one canonical generated source.

## Reader architecture

`src/page/reader.js` fetches chapter `item.json`, resolves `base_url`, loads work chapter order, builds responsive top/bottom chrome, search, advertisements, blocks, and discussion/bookmark controls.

The reader is continuous scroll on desktop and mobile. It creates every `.reader-page` placeholder with `data-page="N"` and estimated aspect ratio; only image elements outside active ±10 are unloaded. IntersectionObserver updates the virtual media window (with an `elementFromPoint` fallback). Therefore layout nodes exist and anchors are feasible, but target media may need explicit window activation. The first three images alone are initially eager. There is no single-page mode.

No placeholder has `id="page-N"`; URL page/chapter/mode is not parsed; scrolling does not update history; progress is not persisted. After render, a timer always smooth-scrolls to `#chapter-start`, which would cause a deep-link jump unless replaced. Responsive CSS, not separate JS, supplies mobile behavior; auto-hiding top chrome remains visible on hover/focus/search.

## Current “account,” bookmarks, and personalization

The runtime is deliberately local-first:

- `src/local-profile/database.js`: IndexedDB `doku-local-profiles`, `profiles` and `meta` stores.
- `src/local-profile/schema.js`: versioned profile with random device-local `profileId`, display name/avatar, `preferredTags`, `excludedTags`, `bookmarks`, free-form settings, archived comments, timestamps.
- `src/local-profile/store.js`: initialization/selection CRUD, import/export support, and work bookmark toggle.
- `src/account/views.js`: `/profiles` chooser/create/import, profile editing/deletion/export, bookmark list, and comma-separated tag settings.
- `src/account/navigation.js`: shared local-profile/account navigation mounted by landing and reader.
- `src/account/data.js`: presentation/bookmark metadata and current legacy reader URL helpers.
- `src/local-profile/personalization.js`: excludes matching tags, then stable-partitions works having any preferred tag. Rotunda and search use this local state.
- `src/discussion/service.js`: local work bookmark state; there is no remote runtime discussion client.

Bookmarks are unique by `workId`; they optionally retain one chapter, but not page, label, notes, mode, or update time. They are arrays within each local profile record. There is no automatic reading progress. Settings normalization lowercases, trims, hyphenates whitespace, deduplicates, and sorts, but currently permits the same tag in preferred and excluded arrays; exclusion wins at filtering time.

These routes are private only in the device-local sense. They are **not authenticated** and cannot satisfy cross-device Google/email account requirements.

## Dormant Supabase/Auth evidence

`.env.example` and `.env.production` declare public Supabase URL/key variables, but source search finds no active Supabase client/import or Google/email auth call. `package.json` has no `@supabase/supabase-js`. Git history and `docs/local-first-browser-profiles.md` confirm remote accounts were replaced.

Checked-in SQL is still important evidence:

- `supabase/migrations/202607170001_discussion_mvp.sql` proposes `profiles`, comments, and work-only `bookmarks`. Bookmark RLS is owner-only. `profiles_public_read` deliberately exposes discussion display profiles and conflicts with a private account profile.
- `supabase/migrations/202607300001_user_tag_preferences.sql` proposes one row per `(user_id, tag_key)`, enum preferred/excluded, optional weight, cascade deletion, and owner-only CRUD policies.

Migration files do not prove they are applied. Google/email provider configuration and redirect allowlists are not in the repository. A future auth implementation must inventory the live project first and must separate public discussion identity from private account information.

## Tags and visibility

`src/data/tags.json` is version 1: `works[storageSlug] = { tags: string[], sources: string[], updated_at }`. `src/utils/tag.js` normalizes tag text, joins tags to catalog works, and implements public rotunda visibility. Many catalog tags are empty or the provenance-like `manifest`; there is no canonical vocabulary/alias registry.

Global visibility (`public_rotunda.showcase_tags`, omit tags, explicit omitted works) and user preferences are different layers. Current local personalization applies after public eligibility in Rotunda. Search applies personalization too. Canonical work tags must remain immutable from account settings.

## Risks and technical debt

1. Candidate stable IDs lack a written durability guarantee; one catalog item lacks a checked-in manifest.
2. Storage slug, display title, public slug, and stable identity are not separated.
3. In-memory reader transitions bypass URL/history; the query reader condition bypasses pathname semantics.
4. Local `/account/*` naming now conflicts with the requested authenticated meaning.
5. Checked-in public profile RLS conflicts with private-profile requirements; live database state is unknown.
6. Duplicate search artifacts/generators invite drift.
7. No non-Cloudflare nested-route fallback exists; GitHub Pages is not currently supported.
8. Reader startup always targets chapter start and does not expose its active-page window to a URL controller.
9. Client-side visibility is discovery policy, not authorization for hidden/private works.
10. No service worker exists today, but future cache plans could leak private responses if user data enters shared caches.
