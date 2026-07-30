# Interchangeable live advertisement system

## Configuration and inventory

`src/data/monetization/ads.json` is the sole source of truth for provider markup. Its stable IDs are:

| Stable ID | Format | Declared size | Zone |
|---|---|---:|---:|
| `leaderboard_900x250` | banner | 900×250 | 5865240 |
| `top_banner_728x90` | banner | 728×90 | 5865232 |
| `banner_300x250` | banner | 300×250 | 5865344 |
| `video_slider` | video slider | provider-defined | 5880066 |
| `desktop_interstitial` | desktop interstitial | fullscreen | 5880058 |
| `mobile_interstitial` | mobile interstitial | fullscreen | 5880060 |
| `popunder` | popunder | window | 5962682 |

`src/data/monetization/placements.json` is the sole source of placement behavior. It maps the landing leaderboard, global top banner, Reader breaks and video slider, device-specific interstitials, and global popunder to inventory IDs. All are initially enabled. Page code knows placement IDs only; it never knows providers, URLs, classes, or zones.

## Rendering and fill detection

The renderer parses the complete configured snippet in an inert `template`. It clones ordinary nodes and recreates each script with `document.createElement("script")`, copying every attribute and inline text in source order. External loader promises are registered by exact URL; every slot retains its own provider node and inline queue command. No `eval`, `Function`, targeting context, or local-profile data is used.

A placement begins at `waiting`, becomes `loading`, and becomes `filled` only after an iframe, image, video, canvas, object, or embed has measurable width and height. Mutation and resize observers watch provider output until the finite configured timeout. Errors, blocking, invalid markup, and empty output become a black, responsive Doku-Doujins fallback. Failed interstitials and non-visible popunders collapse rather than blocking navigation. Cleanup disconnects all placement-owned observers and removes its DOM.

Delegate-CH head markup is parsed from the inventory and inserted into `document.head` only if an identical meta element is absent.

## Verification and operator procedures

Visible verification labels are disabled. Diagnostics belong in the browser console and network tooling, never in placement markup. Operators may replace a complete inventory snippet, change Reader frequency, or disable configuration before initialization. They must not inspect creative DOM to decide fill or trigger a replacement after initialization.

To replace a provider snippet, update the complete escaped `snippet` and its declared size in `ads.json`, validate JSON, test, and redeploy. Stable placement IDs remain unchanged. To disable an advertisement, disable its inventory entry or placement before it mounts; top-level monetization switches remain available for operational shutdown.

## Known limitations and rollback

Live fill cannot be established by unit tests or localhost because provider approval, browser policy, blockers, CSP, inventory, and network responses are external. Shared script deduplication assumes a provider loader can serve multiple independent `ins`/queue requests. The exact full provider-supplied popunder source was not present in this checkout or prompt beyond its declared configuration and boundary lines; deployment must not be treated as provider-verified until the authoritative full snippet is supplied and substituted.

To roll back, revert the implementation commit, or disable top-level monetization first for immediate operational mitigation. Reverting restores the previous house-campaign placement system.

## Simplified provider ownership rule

Before initialization, the application owns an advertisement placement. It creates one permanent outer placement and one provider host, attaches that host to the live document, inserts a fresh configured `ins`, and executes that placement's serve command exactly once. The external network script loader may be shared, but every placement initialization, `ins`, zone ID, and serve request is independent.

After successful initialization, the provider owns the host subtree. Application code must not inspect creative dimensions or structure, determine fill, clear, replace, hide, move, resize, or remount that content. There are no fill timeouts or creative observers. A provider no-fill remains a reserved black region so a late creative retains its host.

Reader breaks are created deterministically from the configured page interval. Each break has an identity derived from work, chapter, page break, and break index; it is not a numbered image page and is never recycled by image virtualization. The Rotunda always occupies a dedicated full-width flex row whose only principal child is the centered Rotunda container; advertisement rows are separate. Full-page formats use the body-level `#doku-interstitial-root`, and only the device-appropriate interstitial is initialized.

Fallback is deliberately limited to disabled or missing configuration and exceptions before provider initialization. Initialized placements are never automatically replaced. User-visible placement names, provider states, zone IDs, timeout reasons, and verification labels are disabled; development failures may be logged to the console.

### Known limitations

The application cannot promise provider fill, distinguish no-fill from a delayed creative, or validate live creative persistence without testing on an approved deployed domain. This is intentional: those decisions belong to the provider. Fixed-format hosts reserve their configured height and center content, but the site does not alter provider-created descendants.
