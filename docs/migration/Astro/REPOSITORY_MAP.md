> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Migration-relevant repository map

| File/group | Purpose / symbols | Role and network behavior | Migration action |
|---|---|---|---|
| `index.html`; `src/main.js` | DOM shell; `boot()` | runtime entry, starts ghost/Page/Footer | WRAP in layout/page; import one client entry |
| `mobile.html`, `reveal.html`, `placeholder.html`, hash-verification HTML | alternate/deadman/static pages | static host only | KEEP/REVIEW; never silently absorb into Astro |
| `src/page/page.js` | `Page.start` query router | reads `?work`, `?chapter` | DEPRECATE AFTER PARITY |
| `src/page/landing.js` | `Landing.start`, ticker | concurrent modules; `/header-ticker.json` | SPLIT static shell/client startup |
| `src/page/reader.js` | reader chrome, `createVirtualReader`, render session | CDN `item.json`, direct page images, discussion | CONVERT minimally TO TYPESCRIPT; coordinated module |
| `src/components/search.js` | shared search promise/UI | `/data/search.index.json`, currently `no-store` | IMPORT; version URL and default cache |
| `src/components/rotunda.js`, `rotunda_window.js` | coverflow, bounded cards, caches/abort | work metadata and thumbnails | IMPORT/TS later; consume static Rotunda release |
| `src/components/blocks.js`, `footer.js`; `src/effects/ghost_text.js` | peripheral UI | static HTML/JSON, external iframe | WRAP/IMPORT; share duplicate block data request |
| `src/components/visibility_policy.js`, `src/utils/tag.js` | policy normalization/filtering | bundled data; no fetch | MOVE visibility enforcement to public projection and retain defense-in-depth |
| `src/storage/storage.js`, `manifest_resolver.js`, `work_manifest.js` | URL/adapters, 40-promise cache | static work manifest fetch; direct URLs | typed adapters; preserve contracts |
| `src/fetch/fetch.js` | legacy `Fetch` class | catalog/chapter fetch if called; no current imports found | REVIEW, then deprecate after import audit |
| `src/discussion/*`; `supabase/migrations/*` | authenticated discussion | Supabase network, not R2/Worker | KEEP separate dynamic system |
| `src/styles/*.css` | visual behavior | Vite hashed output | KEEP/IMPORT unchanged initially |
| `src/data/fetch.json`, `works/*.json`, `rotunda.json`, `tags.json`, `storage.json`, other JSON | canonical/generated catalogs/config | mostly bundled | KEEP UNCHANGED; typed build adapters |
| `public/data/*.json`, `public/header-ticker.json`, `public/blocks/*` | browser-facing static data/content | same-origin fetch; block scripts duplicate no-store | preserve; version projections/centralize request |
| `scripts/ingest-work*.py`, `run-ingest.sh`, `src/storage/common.py` | ingest/media/manifests/storage map | administration/build; R2/rclone operations | KEEP; extend projection generation separately |
| `scripts/generate_search.py`, `src/tools/generate_search.py`, `scripts/build_tags.py`, `split-work-manifests.py` | generated indexes/contracts | build/admin | consolidate only after equivalence tests |
| `scripts/deletor.py`, beta/legacy navigators/auditors | admin mutation/audit | explicit remote reads; conditional cache in deletor | KEEP FOR ADMINISTRATION; never bundle |
| `tests/*` | Node/Python unit/static tests | no production network expected | retain and add route/cache/schema parity |
| `vite.config.js`, `package*.json` | Vite multi-entry build | build time | keep production in parallel, then Astro replacement after parity |
| `wrangler.jsonc` | static `dist` + SPA fallback | platform static routing | REVIEW at route cutover; no Worker code |
| `.github/workflows/deadman-switch-new.yml` | rewrites root/mobile on schedule | GitHub Actions push | HIGH RISK: explicitly adapt only with operational approval |

**VERIFIED IN CODE:** no TypeScript currently exists in the application; Vanilla JS is organized by behavior. **RECOMMENDATION:** see the compact machine inventory in [`inventory/repository-map.json`](inventory/repository-map.json).
