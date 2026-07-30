# Work URLs and reader deep links

## Identity layers

Do not use one value for four jobs:

1. **Stable work ID:** immutable database/catalog identity; candidate is unique `parent_work_id` in all 724 checked-in manifests, pending provenance/durability audit.
2. **Public slug:** persisted readable lowercase kebab slug in the route manifest.
3. **Storage slug:** existing exact `slug` used by `src/storage/storage.js`, catalog lookup, R2 directory, tags, and search.
4. **Display title:** mutable localized UI copy.

Recommended canonical path: `/works/{work-id}/{public-slug}`. ID+slug is longer than `/works/{slug}` but safely handles duplicate titles, renames, and slug normalization changes without relying on an alias database. It is clearer than abbreviated `/w/`; retain `/works` for discoverability. The ID is authoritative; title/slug changes do not change saved foreign keys.

Phase 1 must generate a deterministic map containing ID, public slug, storage slug, source, manifest locator, chapters/default chapter, public visibility, and any real aliases. It must fail/report missing and duplicate IDs and the current 725 catalog versus 724 manifest mismatch. Do not claim `parent_work_id` canonical until its ingestion allocation and rerun stability are proven.

## Work detail versus reader

Keep both routes. `/works/{id}/{slug}` is a lightweight, cacheable work page with cover, title, allowlisted description/tags, page/chapter count when known, Read/Continue, Bookmark, and source attribution where appropriate. `/read` is the high-memory continuous reader with controls, ads, discussion, progress, and deep linking. Search and rotunda should link to detail by default; an explicit “read” affordance may link directly to `/read`.

## Canonical reader state

```text
/works/{id}/{slug}/read
/works/{id}/{slug}/read?chapter={chapter-key}#page=3
/works/{id}/{slug}/read?chapter={chapter-key}&mode=single#page=3
```

Defaults: first/default chapter, continuous mode, page 1. Omit defaults from emitted URLs. Chapter keys are opaque identifiers from the work manifest and must be matched exactly, then percent-encoded per segment/value. Do not derive chapter order from labels. Future chapter IDs may be introduced without changing the route shape.

### Position alternatives

| Format | Advantages here | Disadvantages here | Decision |
|---|---|---|---|
| `#page=3` | Client-owned; no new host route; excluded from CDN request/cache key; share/refresh works; can map to DOM ID | server/analytics cannot see it; native anchor alone cannot activate virtual media; hash history needs control | **Canonical initial format** |
| `#page-3` | Natural with `id="page-3"`; familiar anchor | harder to extend/parse consistently; still client-only | Accepted compatibility alias |
| `?page=3` | Server/analytics visible; combines with mode/chapter | fragments CDN cache unless normalized; personalized position can pollute cache/SEO; query changes may remount | Accept input; canonicalize to fragment |
| `/read/page/3` | semantic server route/HTTP status possible | many fallback/cache/index routes; chapter/mode expansion awkward; overkill for continuous client reader | Do not use initially |

Keep chapter and mode in query because they alter the loaded representation; keep live page in fragment because it is a client scroll position. Analytics may receive a separately consented, bounded event rather than relying on server logs.

## Actual virtualization implications

`src/page/reader.js` creates all page placeholder nodes, so deep linking does not need to materialize layout nodes. It virtualizes **images**, not page DOM. Add stable `id="page-N"` and keep `data-page`. Before scrolling, validate the page, tell the virtual window to activate around `N`, and render placeholders using estimates. Avoid the current unconditional smooth scroll to `#chapter-start`; choose the initial target before first visible reader paint (or hide the content with an accessible busy state until positioned). Once actual image ratios above the target are known, preserve scroll anchoring.

A future renderer that virtualizes DOM nodes must expose `scrollToPage(N)` and cannot rely on `element.scrollIntoView()`.

## Resolver pseudocode

```text
resolveReaderUrl(url, routeManifest, requestedVisibility, session):
  parsed = parseCanonicalOrLegacy(url)
  work = parsed.id
    ? routeManifest.byId[normalizeId(parsed.id)]
    : routeManifest.byStorageSource[parsed.source + ":" + parsed.storageSlug]
  if work is missing: return NOT_FOUND
  if work is not publicly addressable:
      return NOT_FOUND              // avoid existence leakage

  canonicalSlug = work.publicSlug
  chapter = parsed.chapter ?? work.defaultChapter
  if chapter not exactly in work.chapters: return READER_ERROR("chapter unavailable")

  mode = parsed.mode ?? "continuous"
  if mode not in supportedModes: mode = "continuous" with canonical replacement

  page = parse positive base-10 integer from `#page=N`, `#page-N`, or legacy `?page=N`
  if absent: page = 1
  if page < 1 or not integer: page = 1 with nonfatal message and replacement

  item = fetch/validate Storage.manifest(work.source, work.storageSlug, chapter)
  if item.pages is not a positive integer: return READER_ERROR("manifest invalid")
  if page > item.pages: page = item.pages with nonfatal "opened final page" message and replacement

  canonical = buildReaderUrl(work.id, canonicalSlug, nondefault chapter/mode, page)
  return {work, chapter, page, mode, item, canonical, replace: canonical != input}
```

Do not clamp an unknown page before `item.json` supplies page count. Page 0, negatives, decimals, junk, and overflow must never crash. Recommended behavior is page 1 for invalid/nonpositive input and final page for an otherwise valid too-large integer, with an `aria-live` notice and canonical replacement.

## Mount and history sequence

1. Parse pathname/query/fragment before reader mount; show a stable `aria-busy` shell.
2. Resolve ID/storage slug and canonicalize stale slug/legacy route with `replaceState`.
3. Resolve chapter and fetch `item.json`; validate page against count.
4. Build all placeholders, assign IDs, prime media window around target, then position without smooth animation on initial load.
5. Restore focus to the reader heading/control, not the page image; announce requested page.
6. Passive visible-page changes throttle `history.replaceState` and do not steal focus. Explicit page/chapter/mode actions use `pushState`.
7. On `popstate`/`hashchange`, if work/chapter is unchanged call `scrollToPage`; otherwise remount once. Suppress URL-write feedback loops.
8. Copy/share reads the already canonical current URL. Page images retain useful `alt="Page N"`; anchor nodes need no redundant tab stop.

## Renames, duplicates, hidden and missing works

Duplicate titles/public slugs are allowed because work ID disambiguates. A renamed work retains its ID; its current persisted slug becomes canonical and old links still resolve by ID, even without an alias. Globally unpublished/deleted/private works return not-found to public users. Personally excluded works remain directly addressable if globally public; settings are discovery preferences, not publication authorization. Adult/interstitial behavior remains a product-policy question, but must not be implemented as a cache-varying private HTML response.

## Migration from current events

First introduce URL builders/resolver without changing UI. Next teach the router canonical work/reader paths. Then change search/rotunda cards and reader chapter controls to call `navigate(canonicalUrl)`; keep `open-reader` as a short-lived adapter that converts its detail to a URL. Finally convert legacy query URLs and remove direct DOM-opening calls only after parity tests prove the rotunda and reader remain intact.
