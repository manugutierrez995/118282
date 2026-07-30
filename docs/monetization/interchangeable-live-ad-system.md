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

A visible placement follows `configured` → `mounting` → `provider-loading` → (`provider-claimed` | `filled` | `genuinely-empty` | `failed`) → optional `fallback`. `filled` is terminal for the mounted lifecycle: observers and fallback timers are cancelled, and no resize, late mutation, render, or timeout may downgrade it. A meaningful provider mutation claims a slot. Claimed slots receive the centralized grace period and are never classified as completely empty.

Fill inspection covers the entire stable provider host, because a provider may wrap, move, or replace its original `ins`. Any iframe is fill without reading `contentDocument` or `contentWindow`; this safely handles cross-origin creatives. Provider children, visible media, measurable descendants, and replacement of the original `ins` also fill. Verification labels and fallback DOM are marked and excluded. Immediately before fallback the renderer synchronously inspects the complete host; fallback is appended only when the provider subtree remains untouched and empty, never over or in place of live provider DOM.

The exact external loader URL is the only shared resource. Magsrv and Pemsrv therefore have separate registry entries. Every mount creates a private host and fresh `ins`, attaches it before executing that placement's inline serve request, and executes that request exactly once. Labels remain outside the provider-owned host, and state changes retain the same host.

The landing Rotunda has a dedicated full-width flex row whose only child is the centered Rotunda mount. Top and leaderboard advertisements occupy separate rows above or below it. Advertisements, verification labels, fallbacks, invisible columns, and reserved rails are prohibited beside the Rotunda.

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
