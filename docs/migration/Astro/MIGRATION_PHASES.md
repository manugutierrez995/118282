# Reversible migration phases

| Phase | Files/change | Tests & measurements | Request reduction / rollback / completion |
|---|---|---|---|
| 0 Freeze & Measure | no behavior; baseline fixtures/screens/log tooling | routes, desktop/mobile/reduced motion, request/bytes/cache headers/memory/R2+Worker analytics/failures | none; tag/deploy ID rollback; baseline approved |
| 1 Cache Corrections Without Astro | search loader, block data ownership, tests, versioned public alias/header plan | no visual diff; duplicate/no-store assertions; warm visit | removes search bypass/up to 3 duplicate cycle calls; revert commit; **do before Astro** after baseline |
| 2 Astro Parallel | new isolated Astro config/layout/pages only | static build, no prod workflow change, shell DOM snapshots | none yet; delete parallel tree; build reproducible |
| 3 Data Adapters | typed readers/release generator/new output only | canonical fixtures unchanged, privacy/schema/link/irregular pages | eliminates future metadata discovery; discard generated release; projections validated |
| 4 Static Work Routes | generated work pages + legacy compatibility | direct refresh/404/hidden/trailing slash/base | avoids SPA resolution for known works; retain old prod/routes; route set passes |
| 5 Reader Shell | Astro markup + minimally converted reader TS | full visual/interaction/virtualization/discussion parity | no extra requests; Vite remains rollback; DOM/network parity |
| 6 Hash & History | parser/state/history tests | direct page, passive replace, explicit push, refresh/back/forward/invalid | no document navigation/manifest reload per page; disable canonical feature flag; all navigation gates pass |
| 7 Cache Hardening | release media keys, `_headers`/rules/config after verification | cold/warm headers, CF status/Age/304, mixed-release tests | browser/edge hits and fewer R2 misses; pointer/headers rollback; immutable keys never overwritten |
| 8 Rotunda Boundary | release Rotunda adapter only | candidate/layout/visual/drag/wrap snapshots | cacheable one snapshot; fall back bundled current JSON; exact presentation parity |
| 9 Production Cutover | deploy workflow/pointer/static target; approved deadman adaptation | complete functional/network/load/privacy gates and monitoring | production reductions realized; switch pointer+HTML back immediately; acceptance met |

Risks peak at reader DOM/CSS, visibility leakage, deadman workflow, mixed releases, hash scroll stability, and media immutability. Each phase is a separate reviewable commit; no canonical migration or destructive storage operation belongs in any phase.
