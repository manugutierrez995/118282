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

## Verification labels

`verification` in `placements.json` controls the labels without a source edit. Labels contain only placement ID, advertisement ID, declared size, provider, state, and (for fallback) a reason. Set `verification.enabled` or `verification.showPlacementLabels` to `false` to hide them; restore both to `true` to inspect failures. Provider state and fallback-reason fields have independent switches.

## Operator procedures

1. **Replace a provider or snippet:** open `ads.json`, locate the stable ID, replace its entire escaped `snippet`, validate JSON, test, and redeploy. No page, Reader, layout, or adapter edit is required. The snippet is authoritative; do not split its zone or URL into code.
2. **Change size:** change the same ad entry's `size.width` and `size.height` (or `size.mode`). Reservation, fallback proportions, and label update automatically.
3. **Change Reader frequency:** change `reader_between_pages.frequency.everyPages`. Fixed mode accepts `3`, `4`, or another positive interval. Ranged mode deterministically selects between `minimumPages` and `maximumPages`; `adsPerBreak` supports the same modes.
4. **Disable one ad:** set that inventory entry's `enabled` to `false`.
5. **Disable one placement:** set that placement's `enabled` to `false`.
6. **Disable everything:** set top-level `enabled` to `false` in `placements.json` (or `ads.json`), or set `global.enabled` to `false`.
7. **Inspect a failure:** enable all verification switches, inspect the state/reason label, Network panel, provider script response, iframe creation, and CSP or blocker messages. A visible region must resolve to a creative or branded fallback.
8. **Replace ExoClick later:** replace each complete inventory snippet and provider/name metadata. Keep stable IDs and placement mappings; page components remain unchanged.

## Known limitations and rollback

Live fill cannot be established by unit tests or localhost because provider approval, browser policy, blockers, CSP, inventory, and network responses are external. Shared script deduplication assumes a provider loader can serve multiple independent `ins`/queue requests. The exact full provider-supplied popunder source was not present in this checkout or prompt beyond its declared configuration and boundary lines; deployment must not be treated as provider-verified until the authoritative full snippet is supplied and substituted.

To roll back, revert the implementation commit, or disable top-level monetization first for immediate operational mitigation. Reverting restores the previous house-campaign placement system.
