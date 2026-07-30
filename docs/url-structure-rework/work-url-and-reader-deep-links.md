# Work URLs and reader deep links

## Identity layers

Do not use one string for four jobs:

| Concept | Current source | Proposed contract |
|---|---|---|
| stable work ID | per-work `parent_work_id`; used by discussion | immutable opaque text in public identity manifest and DB references |
| storage slug | `slug` in fetch/work/rotunda; R2 directory | exact opaque locator; never changed merely for URL aesthetics |
| public slug | absent as a separate field | stable, human-readable kebab-case path component |
| display title | `display` | mutable presentation text; duplicate values allowed |

Phase 1 must prove all `parent_work_id` values are non-null, unique, and stable across ingestion reruns. If not, allocate a durable ID (UUID/ULID or retained ingestion ID) once and persist it in canonical ingestion metadata. Never derive the durable ID from title, array position, hash of mutable metadata, or current filename.

## Recommended canonical URL

Use `/works/{work-id}/{slug}` and `/works/{work-id}/{slug}/read`. Compared with alternatives:

- `/works/{slug}` is attractive but requires slug immutability or an alias/redirect store and cannot safely absorb duplicate/colliding normalized titles.
- `/works/{work-id}/{slug}` is verbose but rename-safe, collision-safe, independently resolves before trusting the slug, and works with current numeric IDs.
- `/w/{work-id}/{slug}` is shorter but less descriptive and creates another vocabulary. There is no current route compatibility benefit.

The identity map should contain `work_id`, `public_slug`, `storage_slug`, `source`, `manifest`, `visibility`, `aliases` (optional), and default chapter. Search/rotunda entries should eventually reference it rather than independently constructing URLs.

## Duplicate titles, rename, and aliases

Duplicate titles produce the same public slug but distinct IDs, so both URLs remain unique. When title changes, retain the existing public slug by default to minimize churn; an editorial rename may update it. A request with valid ID and old slug canonicalizes to the current slug. Optional alias history supports true edge 301s and slug-only legacy inputs, but is not needed to resolve ID-bearing URLs. Never reassign a retired ID or alias to another work.

Storage moves are separate: the identity map can point the same ID/public slug to a changed storage slug/source. Publish the new object/catalog atomically before removing the old R2 path.

## Hidden, adult-filtered, private, and missing works

Resolve global visibility before fetching chapter metadata. Missing, deleted, hidden, or unauthorized private IDs render the same not-found response to unauthenticated callers. A user's excluded tag does **not** make a public URL unauthorized: hide it from lists/recommendations but allow an intentional direct URL, optionally with a local warning according to product policy. Global legal/safety removal is not bypassable by preferences. A future private work must be served by authenticated/signed asset rules, not merely omitted from rotunda.

## Why the current UI has no stable URL

Rotunda/search/chapter controls dispatch `open-reader`; `src/page/reader.js` swaps the current layout. No link, pushState, or route parser participates. Startup accepts query-only work/chapter. The solution is to make URLs the input to reader state and make UI actions call the central navigator—not to add another custom event-only path.

## Exact page format recommendation

Canonical:

```text
/works/1234567890/example-title/read#page=3
/works/1234567890/example-title/read?chapter=chapter_2#page=3
/works/1234567890/example-title/read?chapter=chapter_2&mode=single#page=3
```

Defaults are first/default chapter and `continuous`. Accept legacy `#page-3`; do not emit it. Reserve the fragment as form-encoded reader-local state so future `annotation`/`layer` keys remain possible.

### Comparison

| Form | Advantages here | Disadvantages here | Decision |
|---|---|---|---|
| `.../read#page-3` | simple; native-looking anchor; fragment never reaches host/CDN | hard to extend; native anchor alone cannot preselect media window; server/analytics cannot see it | accept alias |
| `.../read#page=3` | same static/cache benefit; parsed with `URLSearchParams`; extendable; no extra route | still client-only; analytics needs client event; must implement scroll/history explicitly | **canonical** |
| `.../read?page=3` | server/prerender/analytics can see page; query supports mode/chapter | page changes can fragment CDN/cache analytics; query mixes document selection and viewport position; passive updates look like new resources | support as input only during migration, reserve query for chapter/mode |
| `.../read/page/3` | fully path-addressable; server-visible | every page becomes a fallback route/canonical document; high route/cache/SEO duplication; awkward passive continuous scroll and chapter/mode | reject initially |

Search engines should index the work detail, not every reader position. Canonical metadata on reader points to the work detail (or reader base without fragment if product chooses), and page fragments are excluded from server cache keys by browser design.

## Actual virtualization implications

The current reader creates all `.reader-page` placeholder elements, so this is media virtualization, not DOM virtualization. Add stable `id="page-N"` while preserving `data-page`. Before the first paint where practical:

1. Parse and validate requested page after the chapter manifest gives `pages`.
2. Set the initial active media window around requested page instead of calling `updateWindow(0)`.
3. Build placeholders with known estimated aspect ratio.
4. Insert the final reader DOM.
5. Scroll the requested placeholder with `behavior: "auto"` (respect reduced motion; never smooth on initial restore).
6. Let loaded images correct ratios while applying existing scroll compensation.

If future DOM virtualization removes distant placeholders, expose a reader adapter `goToPage(N)` that computes/mounts the target range before scrolling. URLs must never depend solely on `document.getElementById` existing.

## Invalid pages

Parse ASCII base-10 positive integers only. Reject floats, signs, exponent notation, empty values, duplicate ambiguous keys, and unsafe integers. Behavior:

- missing page → page 1;
- `0`, negative, malformed → show a non-blocking “Invalid page; opened page 1” status and replace URL with `#page=1`;
- beyond final page → open final page, announce “Requested page exceeds this chapter; opened page N,” and replace URL;
- valid final/middle/first → open exactly that page;
- invalid chapter/mode → use default only with visible explanation; unknown work remains not found.

Clamping prevents crashes and dead links, while the visible/accessible notice avoids silently changing user intent.

## Chapter and mode support

A chapter is document selection, so use a query value that must match the resolved work's chapter IDs. Do not expose raw R2 paths. Omit the default. Reader mode is an enum (`continuous`, later `single`); omit continuous. Page is relative to the selected chapter. If future works need stable cross-chapter pages, add explicit stable `chapter_id` to manifests before relying on mutable `chapter_1` paths.

## History, refresh, and sharing

- Opening a work/read route from rotunda/search pushes a history entry.
- Explicit next/previous chapter and go-to-page push.
- IntersectionObserver active-page changes call throttled `replaceState` only when N changes.
- `hashchange`/`popstate` call `goToPage`; they do not rebuild the same chapter.
- Refresh parses route before reader render and selects the initial media window.
- Copy/share copies `location.href` after active-page synchronization. Offer “copy work” and “copy current page” distinctly.
- The native hash may focus/scroll an element unexpectedly. Prevent default competing scroll, keep reader pages non-focusable, and send announcements through an `aria-live="polite"` status. A separate “Page N of M” control can receive focus after explicit jumps; passive scroll must not steal focus.

## Resolver pseudocode

```text
resolveReaderUrl(url, identityIndex, session):
  route = parseKnownPath(url.pathname)              // decode once; strict segments
  require route.kind == WORK_READ

  work = identityIndex.byId(route.workId)
  if work is absent: return NOT_FOUND
  if !visibilityPolicy.mayResolve(work, session): return NOT_FOUND

  canonicalPath = `/works/${encode(work.id)}/${encode(work.publicSlug)}/read`
  if route.slug != work.publicSlug: canonicalizeWithReplace(canonicalPath + url.search + url.hash)

  chapter = url.searchParams.get("chapter") or work.defaultChapter
  if chapter not in work.chapters:
      chapter = work.defaultChapter
      warning = INVALID_CHAPTER

  mode = url.searchParams.get("mode") or "continuous"
  if mode not in supportedModes: mode = "continuous"; warning += INVALID_MODE

  manifest = loadChapterManifest(work.source, work.storageSlug, chapter)
  rawPage = parseStructuredHash(url.hash).page
            or parseLegacyPageDash(url.hash)
            or migrationPageQuery(url.searchParams)
            or 1
  page = parseStrictPositiveInteger(rawPage)
  if invalid(page): page = 1; warning += INVALID_PAGE
  if page > manifest.pages: page = manifest.pages; warning += PAGE_CLAMPED

  return { work, chapter, page, mode, manifest, canonicalPath, warning }
```

Never fetch a manifest until work identity/visibility and chapter membership are resolved.

## Migration from current event behavior

First make rotunda/search entries real `<a href>` elements where interaction allows; enhance clicks through central navigation while retaining native open-new-tab/copy-link behavior. Keep `open-reader` as a short-lived compatibility adapter that translates detail into a canonical URL and calls `navigate`. Change chapter controls the same way. Parse legacy query URLs at startup and replace them after successful ID lookup. Remove the adapter only after tests show no remaining dispatchers.
