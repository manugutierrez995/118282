# Proposed canonical route map

## Policy

Extend the existing History API router in `src/router/router.js`; do not introduce a parallel router. Cloudflare continues serving one static shell. Route parsing, URL construction, navigation, canonicalization, and legacy conversion should live in one module (or a small `src/router/` family) consumed by landing, search, rotunda, reader, and account views.

Canonical paths are lowercase, percent-encoded by segment, and have **no trailing slash** except `/`. Paths are case-sensitive: noncanonical casing either redirects only when an unambiguous resolver match exists or returns not found. Never interpolate untrusted raw strings into HTML or URLs.

## Route table

| Route | Visibility | Auth | Rendering strategy | Data source | Cache policy | Status |
|---|---|---:|---|---|---|---|
| `/` | Public | No | Static shell + client landing | bundled rotunda/tags; public search | public shell/assets; private overlay memory-only | Current, links need migration |
| `/works` | Public | No | Static shell + client catalog | public route manifest/search/tags | public/cacheable | Future |
| `/works/{id}/{slug}` | Public subject to publication policy | No | shell + public work detail | public identity/work projection | public/cacheable; canonical metadata may later be edge-rendered/prebuilt | Future |
| `/works/{id}/{slug}/read` | Public subject to publication policy | No | shell + client reader | route manifest, work manifest, R2 `item.json`/images | shell/metadata/media public; progress private | Future |
| `/profiles` | Device-private | No | local profile chooser | IndexedDB | browser-only, never shared | Current; retain offline meaning |
| `/profiles/new` | Device-private | No | local profile creation | IndexedDB | browser-only | Current |
| `/login` | Public form | Signed-out | shell + auth view | Supabase Auth | shell public; responses no-store/private | Future (currently redirects) |
| `/signup` | Public form | Signed-out | shell + auth view | Supabase Auth | same | Future (currently redirects) |
| `/auth/callback` | Public callback | Flow-dependent | validate Supabase callback, sanitize `next` | Supabase Auth | no-store | Future |
| `/forgot-password`, `/reset-password` | Public auth flow | Flow-dependent | auth views | Supabase Auth | no-store | Future (currently redirects) |
| `/account` | Private | Yes | replace redirect | session store | no-store | Current redirect; guard changes |
| `/account/profile` | Private | Yes | shell + private hydration | Auth user + private profile | no-store/private | Current local view; replace semantics |
| `/account/bookmarks` | Private | Yes | shell + private hydration + public metadata join | user bookmark rows + public work map | no-store private rows; public metadata cacheable | Current local view; remote future |
| `/account/settings` | Private | Yes | shell + private hydration | preferences/settings rows | no-store/private | Current local view; remote future |
| `/404` | Public | No | application not-found view | none | public/no short error caching during rollout | Future explicit alias |
| unknown path | Public | No | not-found view with 404 semantics where host permits | none | short/no-store | Partial current |

## Work identity and slug rules

Canonical form is `/works/{work-id}/{public-slug}`. `{work-id}` is the immutable authority, serialized as a decimal/string token after Phase 1 proves `parent_work_id` or assigns a persisted replacement. `{public-slug}` is a persisted lowercase ASCII kebab-case presentation value, separate from the R2 storage slug. Normalize Unicode, transliterate when deterministic, collapse non-alphanumerics to `-`, trim, cap length, and fall back to `work-{id}`. Duplicate public slugs are safe because IDs differ.

A valid ID with stale/wrong slug resolves the work and uses `replaceState` (client) or 308 (edge, if added) to the current canonical slug. Keep old slug aliases only if a persisted source exists; never infer redirect history from current titles. A malformed/unknown ID is a real not-found. Globally private/deleted/hidden works should be indistinguishable from missing unless policy explicitly requires 403. Personal exclusions hide discovery but do not make a public direct URL unauthorized.

## Reader state and browser history

Canonical examples:

```text
/works/9115320062/sinfullust-05-06-sp-upd/read
/works/9115320062/sinfullust-05-06-sp-upd/read?chapter=chapter_2#page=3
/works/9115320062/sinfullust-05-06-sp-upd/read?chapter=chapter_2&mode=single#page=3
```

- Omit default chapter, default `continuous` mode, and page 1 from emitted URLs.
- Opening a work/chapter is a navigational `pushState`; canonical corrections use `replaceState`.
- Passive scrolling updates `#page=N` with throttled `replaceState`, not one history entry per pixel/page. Explicit “go to page,” chapter, or mode changes use `pushState`.
- `popstate` and `hashchange` re-resolve state without remount loops. Set `history.scrollRestoration = "manual"` only while the reader owns restoration.
- Preserve route when account menu opens; menus do not affect the URL.

## Redirect and legacy matrix

| Input | Action |
|---|---|
| `/account` | guarded replace to `/account/profile` |
| correct ID + stale slug | replace/308 to current slug, preserving allowed chapter/mode/page |
| trailing slash | replace/308 to no-slash form |
| `/?source=S&work=W&chapter=C` | resolve exact storage slug/source; replace canonical reader URL |
| `/reader?source=S&work=W&chapter=C` | same legacy conversion |
| `?page=N` on canonical reader | validate then replace with `#page=N` |
| `#page-N` | accept alias and replace with `#page=N` |
| old local `/login` redirect behavior | remove when real auth view ships |
| unknown account child | account-scoped not-found; do not redirect blindly |
| unknown/malformed work | not-found; do not fall back home |

Legacy conversion must preserve only allowlisted parameters and reject open redirects. Search and rotunda should emit canonical anchors progressively; retain the event adapter only until all callers migrate.

## Authentication navigation

A signed-out visitor to a private route is redirected to `/login?next=` with only an allowlisted same-origin destination. After successful Google or email/password authentication, consume `next` once with `replaceState`. A signed-in visitor to login/signup is returned to a safe account/default route. Do not put access tokens in application-managed query strings.

## Metadata and errors

The work detail route owns `<title>`, description, canonical link, and allowlisted Open Graph image/data. Reader pages canonicalize indexing to the work detail page and should normally be `noindex,follow` to avoid duplicate page-state URLs. Because a pure SPA fallback returns HTTP 200 before client resolution, true HTTP 404/redirect/metadata requires prebuilt work pages or an edge handler later; the initial client phase must still render an explicit not-found and never silently show home.
