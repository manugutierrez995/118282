# Monetization placement system

> **Pages own space. Providers supply optional content.**

## Objective and principles

This system creates restrained, valuable inventory that may offset hosting and R2 costs without making Doku-Doujin deceptive, interruptive, or advertisement-dependent. It deliberately excludes popunders, redirects, autoplay, overlays, fake controls, and advertisements between reader pages. Public content and local-profile restoration remain outside the monetization path.

A **placement** is a permanent, page-owned region. A **provider** is a replaceable source that may fill it. Pages call only `renderAdRegion({ placement, mount })`; they contain no network identifiers, scripts, credentials, or provider markup. A provider error, timeout, block, or no-fill progresses the waterfall or collapses the region without affecting its page.

## Manifest and naming

`src/data/monetization/placements.json` is versioned and checked in. Names use lowercase, semantic `page_location` identifiers. Every entry declares its page type, layout, formats, dimensions, item limit, behavior at all three viewport categories, empty behavior, fallback, and lazy threshold. Validation rejects unsupported versions, invalid names, formats, dimensions, counts, behaviors, and collapse settings. Invalid configuration disables monetization safely.

Nine permanent placements exist. Five are initially enabled:

| Placement | Purpose | Mobile | Initial state |
| --- | --- | --- | --- |
| `rotunda_side_rail_right` | One quiet desktop promotion beside, never over, the Rotunda | hidden | enabled |
| `landing_below_rotunda` | Banner after primary landing content | inline | enabled |
| `search_after_6` | Distinct sponsored/house tile after six organic matches | inline | enabled |
| `reader_chapter_end` | Promotion after all chapter pages and before bottom navigation | inline | enabled |
| `global_footer_banner` | Low-priority promotion inside the footer | inline | enabled |
| `work_below_metadata` | Future work-detail inventory | inline | disabled until a work page exists |
| `bookmarks_footer` | Future account-page inventory | inline | disabled |
| `profile_footer` | Future account-page inventory | inline | disabled |
| `download_below_action` | Future honest download-adjacent inventory | inline | disabled |

## Responsive layout and side rail

Viewport categories are mobile below 600 px, tablet from 600–1099 px, and desktop from 1100 px. The Rotunda rail has an additional CSS composition threshold of 1400 px so there is genuinely enough space. Below it, the rail is `display:none`; it leaves neither a blank column nor horizontal overflow. At large widths, the page keeps a flexible main column and a 240 px rail. The advertisement never overlays or changes Rotunda controls. The rail is not fixed and cannot trap content above the footer. Reduced-motion mode removes creative transitions.

Mobile receives only natural inline/banner/native regions. Creatives use bounded grids, never force horizontal scrolling, and hide secondary copy when narrow. Empty regions use `[hidden]` and collapse.

## Search, Reader, and downloads

Search inserts one labelled `role=group` after six organic buttons only when more than six results exist. It is not added to `activeMatches`, organic result indices, limits, or keyboard arrow counting. Provider failure cannot remove or truncate organic nodes.

Reader creates `reader_chapter_end` only after virtualized chapter pages. The placement is before, and independent of, bottom chapter navigation. It does not cover images, intercept reader controls, reduce page width, or enter the per-page virtualization loop. It is lazy at a 600 px margin and its observer and request are destroyed with the reader session.

`download_below_action` is intentionally disabled. If a real download surface is introduced, the authentic download action must remain visually dominant and separate. Providers may never add a false download button, countdown, wait, redirect chain, or click-confusing control.

## Provider contract and waterfall

A provider implements:

```js
{ id, initialize, supports, request, render, destroy }
```

Requests normalize to `filled`, `no-fill`, `timeout`, `blocked`, `error`, or `invalid`; the controller additionally returns `stale` for superseded generations. The current ordered waterfall is house campaign → local meme → clean collapse. It is deliberately sequential: only one provider is attempted at a time and only one can win. No live external adapter or script is included.

Each attempt has a configurable timeout (800 ms by default). A controller generation increments on every request and destroy. Results from older generations are rejected, so a late response can never replace a later winner. Initialization is lazy and once-per-provider-object. Abort signals, timers, observers, provider cleanup, and DOM sessions are disposed on replacement/navigation.

Future ordering may be direct sponsor → primary network → secondary network → affiliate → house → meme → collapse. Auction or mediation can be implemented inside a provider/controller policy later, but should preserve one winner, bounded timing, the privacy context, and sequential external script loading.

## House campaigns and meme fallback

House content lives in `src/data/monetization/house-campaigns.json`, not pages. Campaigns declare ID, title/body/image/destination, formats, enabled state, optional dates, placement allowlist, priority, weight, and accessible label. Eligibility and priority are resolved by the house provider. The initial campaign promotes collection discovery using a local SVG.

The meme provider uses the same contract. Its deterministic, lightweight copy and locally hosted artwork are intentionally labelled “Site intermission,” do not mimic broken ads, and load only after selection. A placement configured with `fallback: collapse` skips it.

## Privacy boundary

`publicAdContext()` allowlists only placement, page type, viewport, selected format, and an optional public work category. Everything else is discarded. Never add local profile ID, display name, bookmarks, preferred/excluded tags, history, notes, archived comments, or backup data. Local browser preferences are not targeting inputs. Public images, downloads, catalogs, Search personalization, and profile storage never route through monetization code.

## Performance boundary

Content mounts first; optional regions then request content. Eligible lower-page regions use `IntersectionObserver` and per-placement root margins. Ineligible/disabled regions do not initialize providers. There are no external scripts, network preconnects, or advertisement work in the startup shell. Local SVGs are lazy-decoded. Dimensions are bounded, and optional space collapses on no-fill. Rotunda, Search, Reader, and profile code never await monetization.

## Development and ad-free modes

Set `settings.developmentVisualization` in the manifest for region diagnostics: placement, state, format, attempts, winner, fallback, measured dimensions, and whether an attempt timed out. It uses only the configured local providers and never enables a real advertisement.

Set `settings.enabled` to `false` for ad-free operation. Every region becomes hidden before provider creation: no script or provider initializes and no blank space remains. A single placement or campaign can instead be disabled with its own `enabled` flag.

## Provider operations

### Add or replace a provider

1. Add an adapter under `src/monetization/providers/` implementing the normalized contract.
2. Accept only the allowlisted public context; keep account IDs and credentials in deployment configuration.
3. Load its script lazily, at most once, inside `initialize`; never in a page.
4. Normalize all responses and honor abort/destroy.
5. Insert the adapter into the controller registry/waterfall, not page components.
6. Add deterministic fake-adapter tests for fill, no-fill, error, timeout, stale responses, cleanup, privacy, and script deduplication.
7. Measure its lazy chunk and runtime cost before enabling it.

Replacing a provider changes only the registry/order. To disable one, omit it from the waterfall or gate its adapter configuration; do not remove placements.

## Evaluating placement quality

Review fill rate and revenue alongside layout shift, interaction latency, bundle transfer, Reader completion, Search success, accidental-click indicators, dismiss/complaint signals, and mobile overflow. A placement should be removed or disabled if it degrades core use even when it earns revenue. Manually review 320, 375, 390, 768, 1024, 1280, 1440, and 1920 px across landing/Rotunda, Search, Reader, accounts/bookmarks, footer, future work metadata, and future downloads.

## Known limitations

- The application currently has no dedicated work-detail or download surface, so those permanent placements remain disabled rather than being forced into an unsuitable page.
- Search is an autocomplete capped at twelve matches; the sponsored tile therefore appears once after six, not on a separate results route.
- House selection honors priority and eligibility; weighted rotation is represented in data but intentionally deferred until measurement/storage rules are defined.
- No live network, consent integration, reporting beacon, revenue tracking, auction, frequency cap, or remote campaign service is included.
- Development visualization is a checked-in switch rather than a runtime administration UI.
