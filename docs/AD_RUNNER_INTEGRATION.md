# Landing advertising integration

Doku-Doujin uses Ad Runner's native browser contract. The site owns only the landing composition and disclosure frame; Ad Runner continues to own accounts, units, complete provider markup, device eligibility, partner shares, routing, timeouts, fallbacks, fill reporting, and sandboxed execution.

## Production configuration

Edit `public/ad-runner.json`. The production-safe default is disabled because no production Ad Runner origin was supplied:

```json
{"enabled": false, "siteId": "564578634.xyz", "baseUrl": ""}
```

Deployment must set `enabled` to `true` and `baseUrl` to the HTTPS Ad Runner origin. That origin must permit the canonical `https://www.564578634.xyz` publisher origin for bootstrap, selection, outcome, and event requests. A missing, invalid, disabled, or unreachable configuration silently removes advertising while the archive remains usable. There is deliberately no localhost production fallback.

## Landing anchors

The initial viewport selects one non-changing layout group, preventing resize-driven remounts:

- Wide desktop (1500px and above): `left-rail` and `right-rail`, each reserved at 160x600.
- Laptop/tablet (768–1499px): `banner`, reserved at 728x90.
- Mobile (below 768px): `mobile-intermission`, reserved at 300x250 after the rotunda and ticker.

To add a unit, import its complete provider tag through Simple Partner CSV, choose the matching ad name/dimensions, enable its placement in the Ad Runner workbook, publish the manifest, and enable the site configuration. Use separate Left and Right Skyscraper rows; never reuse one placement for both rails. `Top Banner`, `Leaderboard`, `Between Content`, and `Rectangle` are canonical display vocabulary available for explicitly configured future hosts.

Intrusive formats (`mobile-sticky`, interstitials, video slider, and popunder) are not mounted by this landing integration. They remain Ad Runner capabilities and require a separate explicit opt-in design decision.

## Vocabulary and migration

The GUI and CSV importer share `vendor/ad-runner/placement_vocabulary.py`. Canonical display IDs are `left-rail`, `right-rail`, `top-banner`, `leaderboard`, `banner`, `between-content`, `in-content`, and `mobile-intermission`. Existing manifests/workbooks do **not** require migration: legacy anchors `top`, `between-pages-banner`, `left-skyscraper`, `right-skyscraper`, and `mobile-bottom` remain documented aliases and are not rewritten. New GUI/CSV imports use canonical IDs. Sticky and interstitial aliases are not reinterpreted as inline display slots.

## Security and failure behavior

Simple CSV imports the complete provider code as unit markup. Its Client Hints remain unit-level `head_markup`. The `external-tag`/ExoClick adapter constructs a sandboxed iframe `srcdoc`, inserts `head_markup` inside that iframe's `<head>`, and leaves provider scripts out of the publisher document. Partner shares, protected-share/open-yield selection, candidate timeouts, fallbacks, collapse, and outcomes remain controlled by Ad Runner.

The landing integration loads one runtime script only after search, rotunda, blocks, and ticker startup has been initiated. It catches configuration/runtime failures, prevents duplicate sessions, calls the runtime's `stop()` during cleanup, removes its script and hosts, and never runs on direct reader entry.
