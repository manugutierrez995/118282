> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Worker and R2 boundaries

**VERIFIED IN CONFIG/CODE:** no application Worker entry, `fetch()` handler, R2/KV/D1 binding, Pages Functions directory, Cache API, or service worker exists. Static asset routing is a Cloudflare platform function, not repository Worker logic.

| Responsibility | Classification | Caller/endpoint/R2/list/frequency | Static replacement/cache/phase |
|---|---|---|---|
| HTML/JS/CSS/public files | ALREADY STATIC / KEEP STATIC | browser → site; no R2 binding/list | Astro static; explicit headers, phase 2/7 |
| SPA route fallback | KEEP TEMPORARILY | platform → index; no R2 | generated routes, remove/restrict after parity phase 4/9 |
| bundled pointers/work/Rotunda/tags | ALREADY STATIC | Vite imports/static assets | versioned public projections, phase 3 |
| chapter `item.json` | REPLACE WITH VERSIONED DATA | reader → CDN object, once/render; no list | integrate fields into immutable work manifest, phase 3/5 |
| thumbs/pages | KEEP STATIC | browser → CDN object; R2 read only on miss; no list | versioned keys, edge/browser immutable, phase 7 |
| search index | REPLACE WITH VERSIONED DATA | browser → same-origin, once promise but no-store | release index/shards, phase 1/3 |
| block cycle/ticker/ghost | KEEP STATIC | browser static; cycle duplicated four times | shared promise/build embed/version URL, phase 1/2 |
| discussion/auth | KEEP FOR AUTHENTICATION | browser → Supabase, per reader/use; no R2 | retain dynamic/private, all phases |
| ingestion upload/list/audit | MOVE TO INGESTION / KEEP FOR ADMINISTRATION | CLI/rclone/R2, operator-triggered | inventory-driven bounded generation; no reader coupling |
| deletor inspect/thumb | KEEP FOR ADMINISTRATION | explicit CDN conditional GET, local validators | keep out of public bundle |
| dashboard Worker/cache rules | EXTERNAL OR UNKNOWN | not in checkout | export/verify before cutover |

R2 `list` is neither called nor required during ordinary reading. Browser CDN requests are not automatically origin reads; distinguish `CF-Cache-Status:HIT` from a miss and correlate R2 metrics. Astro must not introduce route resolution or metadata discovery Workers.
