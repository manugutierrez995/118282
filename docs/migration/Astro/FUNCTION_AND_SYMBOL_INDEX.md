# Function and symbol index

Line ranges describe this reconnaissance checkout.

| Symbol | File:lines | Purpose/callers/dependencies/state | Network/DOM/cache | Action/destination |
|---|---|---|---|---|
| `boot` | `src/main.js:6-31` | module startup; Page/Footer/ghost | `#reader-container`; indirect requests | wrap in `client/site.ts` |
| `Page.start` | `src/page/page.js:6-20` | query-only router, called by boot | location.search | replace by Astro route + compatibility |
| `Landing.start` | `src/page/landing.js:55-89` | builds shell; concurrent starts | replaces reader root; ticker fetch | split static markup/client |
| `startHeaderTicker` | `landing.js:4-45` | ticker rows/interval | fetch static ticker; no promise cache | build/embed or shared release fetch |
| `loadSearchIndex` | `search.js:6-18` | singleton promise | fetch no-store; search mount | versioned URL/default cache |
| `Search.start` | `search.js:45-179` | input/result lifecycle, AbortController | delegated click/open-reader | retain coordinated client module |
| `VisibilityPolicyStore.refresh` | `visibility_policy.js:18-29` | provider normalization/change event | bundled default, page state | build filter + defense-in-depth |
| `filterRotundaCandidates` | `utils/tag.js:77-79` | omission/tag/public filtering | no network/DOM | shared typed pure adapter |
| `Rotunda.start` | `rotunda.js:103-523` | coverflow/card pool/motion/drag/keyboard | thumbnail/work fetches; LRU + abort | preserve client; static data input |
| `rotundaWindow` | `rotunda_window.js:11+` | bounded cyclic indices | no network | keep pure/tested |
| `loadWork` | `work_manifest.js:44-78` | pointer lookup and manifest merge | fetch; 40 promise LRU | typed release manifest loader |
| `Storage.manifest` | `storage.js:72-75` | direct CDN URL constructor | no fetch | adapter/fallback only |
| `resolveManifest` | `manifest_resolver.js:3-13` | fills `base_url` | no fetch | preserve adapter |
| `Reader.start` | `reader.js:464-488` | direct query reader | CDN manifest | route-provided identity |
| `renderManifestInto` | `reader.js:373-458` | session disposal/render/chrome/discussion | uncached `fetch(item.json)`; root DOM | coordinated reader; work promise/abort |
| `createVirtualReader` | `reader.js:180-326` | page placeholders/window/retry | computed img URLs; max 21 nodes | retain, instrument/tune |
| `unload` / `load` | `reader.js:207-242` | image lifecycle | removes src/node; browser cache only | add bounded decoded retention policy |
| `openChapter` | `reader.js:23-27` | custom event chapter switch | no URL/history | update work hash/history state |
| `installReaderChromeAutohide` | `reader.js:144-178` | timing/focus/scroll | DOM/event listeners | preserve |
| `renderBlocksIntoContainers` | `blocks.js:224-240` | concurrent placement | fetched HTML/external iframes | stable mounts/shared data |
| `Fetch.load/chapter` | `fetch/fetch.js:12-70` | legacy loaders | catalog cache only; uncached chapter | deprecate after import audit |
| ingestion `main` / manifest emission | `scripts/ingest-work.py` around `1321-1392` and CLI tail | validates/uploads/emits item/work/storage maps | admin R2/rclone, not reader | keep; feed release projection |
| `build_plan` / `apply_plan` | `scripts/deletor.py:338-368,442-455` | safe repository deletions | no implicit remote delete | keep admin only |
| `conditional_fetch` | `scripts/deletor.py:180-245` | admin metadata validators/cache | ETag/Last-Modified | keep admin |
| `mountDiscussion` | `src/discussion/discussion.js` | per-work UI | Supabase dynamic | retained separate client |

**VERIFIED IN CODE:** chapter render uses generation/session disposal but does not abort its `fetch`; Rotunda does use AbortController. Hash parsing/history synchronization symbols do not exist, so they are target work, not current features.
