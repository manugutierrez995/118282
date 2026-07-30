# Proposed canonical route map

## Principles

Use one centralized client-side route definition and navigator in the existing Vite shell. Cloudflare may serve the same HTML shell, but route parsing, auth loading, not-found rendering, canonicalization, and history behavior must be explicit application responsibilities. Public metadata and private user state remain separate.

Recommended public work pattern:

```text
/works/{work-id}/{slug}
/works/{work-id}/{slug}/read?chapter={chapter-id}&mode={mode}#page={N}
```

The numeric/string work ID is authoritative. The readable slug is lower-case ASCII kebab-case and decorative for lookup. Omitting `chapter` means the first/default chapter; omitting `mode` means continuous. The common link is therefore `/works/1234567890/title/read#page=3`.

## Route table

| Route | Visibility | Auth | Rendering | Data source | Cache policy | Status |
|---|---|---:|---|---|---|---|
| `/` | public | no | existing static shell + client landing | bundled catalog/rotunda, public blocks | shell/public metadata shared-cacheable | current, retain |
| `/works` | public | no | shell + client browse view initially | generated public work index/search | shared-cacheable; personalization overlay private | future |
| `/works/:workId/:slug` | public subject to visibility | no | shell + client work detail; optionally prebuild later | generated identity/index + work manifest | public shared-cacheable | proposed |
| `/works/:workId/:slug/read` | public subject to visibility | no | shell + existing virtual reader | work manifest + R2 `item.json`/media | shell/metadata/media public; progress private | proposed |
| `/login` | public-auth | no | shell + auth form | Supabase Auth | shell cacheable; auth responses no-store/private | proposed |
| `/signup` | public-auth | no | shell + auth form | Supabase Auth | same | proposed |
| `/account` | private | yes | replace redirect to profile | session only | no-store/private user layer | proposed |
| `/account/profile` | private | yes | shell + account view | Auth user + owner profile | no-store/private | proposed |
| `/account/bookmarks` | private | yes | shell + account view | owner bookmark rows + public work index join | private rows no-store; public metadata reusable | proposed |
| `/account/settings` | private | yes | shell + account view | owner preferences | no-store/private | proposed |
| `/404` | public | no | explicit application error view | route/visibility resolver | shell cacheable | proposed |
| legacy `/?source&work&chapter` | public | no | parse then `replaceState` canonical route | legacy catalog lookup | no additional caching | compatibility |
| legacy `/reader?source&work&chapter` | public | no | same | same | same | compatibility |

## Auth routes and intended destination

An unauthenticated account request becomes `/login?next=<relative-path-and-fragment>`. Accept only same-origin paths beginning with `/`; reject protocols, `//`, encoded traversal, auth pages as loops, and control characters. After successful OAuth/email auth, use `history.replaceState`/central navigator to `next` (default `/account/profile`). Signed-in users visiting login/signup should go to validated `next` or profile. Preserve `next` through OAuth using a validated local value in `sessionStorage` or Supabase OAuth state flow; do not set `redirectTo` to an arbitrary external URL.

## Redirect and canonical rules

1. `/account` → `/account/profile` using replace, not push.
2. Correct work ID + old/wrong slug → current canonical slug (edge 301 if generated/edge support exists; client `replaceState` initially).
3. Legacy work query → ID resolver → canonical reader route. Preserve valid chapter/source and supported page fragment.
4. `/works/:id/:slug/read/` → no-trailing-slash canonical form.
5. Repeated slashes, dot segments, malformed percent encoding, unknown route → 404; do not guess.
6. Work ID not found → not-found view. A hidden/private work should also appear not found to an unauthorized visitor to avoid existence disclosure. Adult-but-public works filtered only by a user's preference remain directly reachable with a clear content-policy interstitial if policy requires; preferences are not authorization.
7. Correct ID is enough to survive renaming. An ID-only convenience URL may redirect to the canonical ID+slug URL but should not be emitted.
8. Never redirect solely by title. Duplicate titles are allowed.

## Slug policy

Public slugs are generated from display title using Unicode normalization, transliteration where deterministic, lowercase, sequences of non-ASCII-alphanumeric characters to `-`, collapsed/trimmed hyphens, and a length ceiling (recommended 80 characters). If empty, use `work-{id}`. The route remains unique because ID is present. Preserve a checked-in/generated current public slug; do not regenerate it silently on every build. Storage slugs remain exact opaque R2/catalog keys and may differ.

Slugs are compared case-sensitively after URL decoding; only the canonical lowercase form is emitted. Decode each segment once, reject invalid encoding, and never treat decoded `/`, `\`, `.` or `..` as storage paths. Query names are lowercase and values are constrained enums/known chapter IDs.

## Trailing slash and asset policy

Canonical application routes have **no trailing slash**, except `/`. This matches fileless SPA URLs and avoids duplicate forms. Static asset URLs keep their exact generated form. All application assets use root-absolute paths on the current custom-domain/Cloudflare deployment. If GitHub project Pages is revived, configure a base path and router basename deliberately; do not make the canonical production URLs inherit the project base.

## Browser history

- Internal work/card/search navigation calls central `navigate(url)` and pushes one entry.
- Canonical correction, auth guard redirects, passive scroll page tracking, and legacy conversion replace the current entry.
- Explicit chapter selection and explicit “go to page” actions push an entry.
- Passive continuous scrolling updates `#page=N` with `replaceState`, throttled only when active page changes.
- `popstate` and `hashchange` re-resolve route/position. Same work/chapter position changes scroll existing placeholders without refetch/rebuild. A different work/chapter performs a reader transition.
- Set `history.scrollRestoration = "manual"` while the reader owns restoration; restore prior setting on teardown. Landing/account pages may use browser default.

## Work-page behavior and metadata

Keep detail and reader separate. Rotunda/search should first navigate to the work detail by default; a deliberate quick-read affordance may go directly to `/read`. The detail page shows cover, title, description when safe/public, canonical tags, page/chapter count, Read/Continue/Bookmark, and source attribution. It sets title, canonical link, Open Graph fields, and JSON-LD client-side initially. Real crawler/share-preview support requires prebuilt HTML or an edge metadata layer later; SPA mutation is not sufficient for all bots.

## Error semantics

Client SPA fallback cannot produce a true origin 404 after the shell has returned 200. Render a full not-found state immediately and send no R2 request for unresolved IDs. Phase 2 may generate public work pages/redirect objects or add a narrowly scoped edge resolver to return real 404/301 and social metadata. Private/hidden works should resolve as 404 unless an explicit authenticated private-work product is later introduced. Transient catalog/Supabase failures are 503-style retry states, not 404.
