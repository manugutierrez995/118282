# URL and private-account structure rework

## Purpose

This package is the implementation handoff for giving Doku-Doujin durable public work URLs, exact reader links, and a private account area without replacing the current Vite application, reader, rotunda, or static/CDN delivery model. It records repository behavior as of 2026-07-30 and separates **current facts** from **proposals**. No application code or database migration was changed in this investigation.

## Executive summary

### Current behavior

The deployed application is a Vite multi-page build whose usable application shell is `index.html`; `src/main.js` starts a hand-written `Page` dispatcher. That dispatcher reads only `?work=` and `?chapter=` and otherwise renders the landing page. It does not inspect the pathname or fragment. Rotunda, search, and chapter controls dispatch an in-memory `open-reader` event; this swaps DOM content without changing browser history. Consequently a work opened from the UI has no newly assigned shareable URL. The old query URL works only when it already contains both work and chapter. Cloudflare's static-assets SPA fallback can serve the shell for nested paths, but the application currently interprets those paths as home.

There is already more account/data groundwork than the UI suggests: Supabase Auth persists/restores sessions, supports anonymous auth and Google OAuth/linking, and a migration defines `profiles` and work-level `bookmarks`. There is no email/password UI, private account router, bookmark list page, preference table, or reading-progress store. The existing `profiles_public_read` policy deliberately makes discussion display profiles public, which conflicts with the new meaning of a private account profile and must be separated rather than reused blindly.

The 724 checked-in per-work manifests all have a `parent_work_id`, slug, chapter list, display title, source, and thumbnail; none has an `id` field. The numeric `parent_work_id` is already passed to discussion/bookmark code as `work_id`, while slugs address bundled manifests and R2 directories. That makes the parent ID the best existing candidate for a stable identity, but its generation and immutability contract are not documented and must be audited before treating it as permanent.

### Proposed behavior

Adopt one pathname router within the existing client application first; do not introduce Astro or another framework during this rework. Use readable URLs backed by the stable ID:

```text
/
/login
/signup
/works
/works/{work-id}/{slug}
/works/{work-id}/{slug}/read#page=3
/account/profile
/account/bookmarks
/account/settings
```

`/account` redirects to `/account/profile`. The ID is authoritative and the slug is decorative/canonicalized: a correct ID with an old or incorrect slug redirects/replaces to the current slug. This makes renames and duplicate titles safe without a mandatory alias database. Continue accepting legacy `/?source=e&work=...&chapter=...`, `/reader?...`, `#page-3`, and query page inputs during migration, but emit only the canonical form.

Use `#page=3` as the initial canonical exact-position syntax. A fragment does not alter CDN cache keys or require another fallback route and is naturally client-owned. The current reader creates a placeholder DOM node for every page and only virtualizes image elements, so it can assign `id="page-3"` and resolve the position before loading the surrounding image window. Accept `#page-3` for compatibility. Keep optional `mode` and `chapter` in a query when introduced (`?chapter=chapter_2&mode=continuous#page=3`); default first chapter and continuous mode need no query.

Build public work detail pages separately from the active reader. Detail pages are cacheable/shareable catalog views; the reader remains an interaction-heavy surface. Fetch private Supabase rows only after the static shell hydrates, never into shared HTML or public cache.

## Recommended route map (summary)

| Route | Purpose | Access |
|---|---|---|
| `/` | landing, search, rotunda | public |
| `/works` | browse/searchable work listing | public |
| `/works/{work-id}/{slug}` | canonical work detail | public subject to visibility policy |
| `/works/{work-id}/{slug}/read` | canonical reader; position in fragment | public subject to visibility policy |
| `/login`, `/signup` | authentication | signed-out (redirect signed-in users safely) |
| `/account/profile` | own private profile | authenticated |
| `/account/bookmarks` | own saved works/positions | authenticated |
| `/account/settings` | own preferences/settings | authenticated |
| `/account` | convenience redirect | authenticated |
| `/404` | application not-found view | public |

## Major findings

1. The router is query-only and ignores `pathname` and hashes (`src/page/page.js`); in-page opens are custom events (`src/components/rotunda.js`, `src/components/search.js`, `src/page/reader.js`).
2. Cloudflare deploys `dist` as static assets with SPA fallback (`wrangler.jsonc`); no Worker request handler or service worker exists. Vite only declares three HTML inputs (`vite.config.js`).
3. GitHub Actions exists only for a deadman-switch file replacement and push. There is no GitHub Pages build, base path, fallback, or `404.html` configuration (`.github/workflows/deadman-switch-new.yml`). Treat GitHub Pages as unsupported until a product owner confirms it.
4. Reader image virtualization retains all page placeholders but loads only active ±10 images. Page placeholders have `data-page`, not IDs; startup always smooth-scrolls to `#chapter-start` (`src/page/reader.js`).
5. Existing authentication is discussion-scoped: Google and anonymous only. Supabase client session persistence, token refresh, and OAuth URL detection are enabled (`src/discussion/supabase.js`). Email/password is not implemented.
6. The applied migration status cannot be inferred from a checked-in SQL file. The SQL proposes public-readable discussion profiles and work-only bookmarks (`supabase/migrations/202607170001_discussion_mvp.sql`).
7. Work tags are keyed by existing storage slug in `src/data/tags.json`; many are empty or only the pipeline marker `manifest`. They are not yet a mature recommendation taxonomy.

## Major decisions

- Retain Vite and the shared static shell for the first migration.
- Add a centralized path parser/navigator instead of independent routing code in each view.
- Use `/works/{work-id}/{slug}` with `parent_work_id` as a candidate ID pending Phase 1 validation.
- Separate work detail and reader routes.
- Canonicalize exact position as `#page=N`; parse `#page-N` as an alias.
- Use Supabase Auth UUID (`auth.users.id`) as the account/user ID for every provider.
- Make private account records owner-only under RLS. Do not expose the private profile via the existing public discussion profile contract.
- Store bookmarks, preferences, and progress as normalized rows, not arrays in `profiles`.
- Keep public catalog metadata cacheable and overlay private state client-side.

## Documents

- [Current-state audit](current-state-audit.md)
- [Proposed route map](proposed-route-map.md)
- [Work URLs and reader deep links](work-url-and-reader-deep-links.md)
- [Account pages and navigation](account-pages.md)
- [Authentication and data model](authentication-and-data-model.md)
- [Tag preferences and filtering](tag-preferences-and-filtering.md)
- [Deployment and cache analysis](deployment-and-cache-analysis.md)
- [Implementation phases](implementation-phases.md)
- [Open questions](open-questions.md)
- [Prompt for the next Codex run](next-codex-prompt.md)

## Start here in the next run

Implement only Phase 1: produce and validate a generated public route/work-identity manifest, with collision and stability tests. Do not switch UI links, apply SQL, or change reader behavior yet. See [implementation phases](implementation-phases.md#phase-1--stable-work-identity-and-slug-audit) and [next Codex prompt](next-codex-prompt.md).
