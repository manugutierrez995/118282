# Durable URLs and authenticated accounts: investigation handoff

**Audit date:** 2026-07-30. **Status:** architecture proposal; no runtime feature or database migration is applied by this package.

## Purpose

This package records the current Vite application's routing, local-profile, reader, catalog, tag, deployment, and dormant Supabase systems, then defines one incremental route/account design. It supersedes the earlier remote-account assumptions formerly in this directory while preserving the repository's newer local-first work described in [`../local-first-browser-profiles.md`](../local-first-browser-profiles.md).

## Executive summary

### Current behavior (facts)

- A dependency-light Vite SPA is served through `index.html`. A hand-written router recognizes `/`, `/profiles`, `/profiles/new`, three `/account/*` paths, and legacy reader query parameters. Cloudflare serves nested requests through its SPA fallback.
- “Account” pages are currently **local browser profile** pages, not authenticated pages. IndexedDB stores profile fields, work-level bookmarks, and preferred/excluded tag arrays. There is no active Supabase client, Google login, email/password login, or restored remote session in application code.
- Search, rotunda, and chapter controls open the reader through `CustomEvent("open-reader")` and do not update the address bar. Only a pre-existing `?work=...&chapter=...` query is recognized at startup. This in-memory transition is the confirmed primary reason opened works lack stable URLs.
- The reader creates a placeholder for every page but keeps image elements only for the active page ±10. Placeholders have `data-page`, not IDs. It always scrolls to `#chapter-start`, and it neither reads nor writes a page position in the URL.
- Catalog identity is split: exact storage slugs locate bundled/R2 data, while every one of the 724 checked-in work manifests has a unique numeric `parent_work_id`. There are 725 catalog/tag entries, so identity coverage is not yet complete.
- Checked-in Supabase migrations define a public discussion `profiles` table, work-only `bookmarks`, and owner-only `user_tag_preferences`; however, the runtime was intentionally replaced with local profiles. SQL in source control does not prove production application state.

### Proposed behavior (decisions)

Retain Vite and extend the existing central router; do not add a framework. Establish a generated, validated work identity manifest first. Use an immutable work ID as authority and a readable, persisted slug as decoration:

```text
/
/works
/works/{work-id}/{slug}
/works/{work-id}/{slug}/read#page=3
/login
/signup
/account/profile
/account/bookmarks
/account/settings
```

Use `?chapter={chapter-key}` only when a non-default chapter is selected and reserve `?mode=continuous|single` for reader modes. The fragment is the canonical live position because it is client-owned and cache-neutral; accept legacy `#page-3` and `?page=3`, but emit `#page=3`.

Authenticated account pages should use one shared Supabase Auth session store. Google and email/password identities both resolve to `auth.users.id`; private rows use that UUID and owner-only RLS. Keep local profiles as an explicit offline/anonymous domain and offer a reviewed, idempotent import after sign-in rather than silently conflating a device profile with an account.

## Recommended route map

| Route | Current | Target |
|---|---|---|
| `/` | Landing/rotunda | Same, with canonical links and account control |
| `/profiles`, `/profiles/new` | Local profile chooser/create | Retain as local/offline profile management |
| `/login`, `/signup` | Redirect to `/profiles` | Real Supabase Auth views |
| `/account` | Redirect to profile | Keep redirect |
| `/account/profile` | Selected local profile | Authenticated user's private account profile |
| `/account/bookmarks` | Local work bookmarks | Authenticated work/chapter/page bookmarks |
| `/account/settings` | Local tag arrays | Authenticated preferences/settings |
| `/works` | Missing | Public browse view |
| `/works/{id}/{slug}` | Missing | Public canonical work detail |
| `/works/{id}/{slug}/read` | Missing | Public reader; query selects chapter/mode, fragment selects page |
| `/?source=…&work=…&chapter=…`, `/reader?…` | Legacy reader input | Parse, resolve, and replace with canonical URL |

## Major architectural decisions

1. **One router:** extend `src/router/router.js`; all surfaces call its URL builders/navigator rather than dispatching a second navigation system.
2. **ID plus slug:** `/works/{id}/{slug}` survives duplicate titles and renames; a valid ID plus stale slug is canonicalized with `replaceState`/redirect.
3. **Detail and reader are separate:** the work page is cacheable metadata and actions; `/read` owns heavy reader state.
4. **Private means RLS:** account UI guards improve UX, but Supabase policies enforce ownership.
5. **Local and remote are distinct:** preserve current local profiles, then explicitly import eligible local state into the authenticated UUID.
6. **Public/private cache split:** static catalog/work metadata may be shared; account rows and personalization responses must not be placed in shared caches.

## Documentation index

- [Current-state audit](current-state-audit.md)
- [Proposed route map](proposed-route-map.md)
- [Work URLs and reader deep links](work-url-and-reader-deep-links.md)
- [Account pages and shared navigation](account-pages.md)
- [Authentication and proposed data model](authentication-and-data-model.md)
- [Tag preferences and filtering](tag-preferences-and-filtering.md)
- [Deployment and cache analysis](deployment-and-cache-analysis.md)
- [Implementation phases and full test plan](implementation-phases.md)
- [Genuinely unresolved questions](open-questions.md)
- [Next Codex prompt: Phase 1 only](next-codex-prompt.md)

## Safe next step

Implement only Phase 1: generate and validate a public identity/route manifest from existing catalog inputs, investigate the single catalog mismatch, and prove or reject `parent_work_id` durability. Do not change navigation, authentication, SQL, or reader behavior in that phase.
