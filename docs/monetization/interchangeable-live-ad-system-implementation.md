# Interchangeable live advertisement system — implementation report

- **Starting tag:** `cute-local-profile` was requested but is not present in this checkout.
- **Starting commit:** `ebfb3df0e9cd1eb377d26071edf62e051496459f`
- **Ending commit:** the commit containing this report on `codex/add-interchangeable-live-ad-system`.
- **Branch:** `codex/add-interchangeable-live-ad-system`
- **Inventory:** `src/data/monetization/ads.json`
- **Placements:** `src/data/monetization/placements.json`
- **Files changed:** inventory and placement JSON; monetization configuration, registry, loader, renderer, fallback, global initializer, styles and validation; landing, Reader, and application integrations; tests; these documents.

## Status

All seven advertisement entries, all seven placements, global monetization, and all verification switches are enabled. Automated zone verification covers 5865240, 5865232, 5865344, 5880066, 5880058, 5880060, and 5962682; the rejected zone is absent. Delegate-CH markup is centrally configured and insertion is identity-deduplicated.

The landing leaderboard, below-header banner, Reader breaks, Reader video location, device-exclusive interstitials, and once-per-page global popunder are wired by stable placement ID. Reader breaks derive from configuration, appear after each four pages, avoid trailing breaks, are lazy initialized, retain page elements/anchors, and are destroyed on chapter cleanup. Global initialization is guarded, preventing repeated route initialization. No local-profile value enters provider context or diagnostics.

Executable snippets are template-parsed; scripts are recreated in sequence with attributes and text intact. Exact-URL loader promises deduplicate safe external loader requests. MutationObserver, ResizeObserver, measurable-media inspection, script errors, and a 3000 ms timeout determine fill/failure. Visible failure produces a responsive black Doku-Doujins identity panel; interstitial failure collapses and cannot block navigation. Verification labels report configured identity, size, provider, state, and fallback reason.

## Verification performed

- `npm test`: passed 43 tests, covering existing landing, Reader, search, Rotunda, and local-profile behavior plus inventory, zones, configuration, Reader frequencies, source-order implementation, privacy boundary, fallbacks, and integrations.
- `npm run build`: passed. Vite reported only pre-existing-style bundle-size/dynamic-import warnings.
- JSON checks: all entries enabled, placement references resolve, prohibited zone/placeholder/fences absent.
- Manual viewport verification: not completed in a real browser at the eight requested widths in this non-browser execution session.
- Live provider verification: not performed on an approved deployed domain; no claim of fill is made.
- Popunder extraction: **partial**. The task input supplied boundary text and configuration but not the intervening complete provider source. The inventory contains the supplied configuration wrapper, but an operator must replace it with the authoritative complete snippet before considering the popunder production-ready.

## Known limitations and rollback

Provider fill, popunder behavior, popup policy, and approved-domain delivery remain externally dependent and unverified. Video slider fallback uses a safe non-floating Reader region. Shared loader deduplication should be reevaluated if live provider testing proves a loader element is required per slot. Manual responsive screenshots remain outstanding.

Rollback by disabling `placements.enabled`, then revert this branch's implementation commit if full code rollback is desired. Do not merge automatically; review and provider-domain testing are required.
