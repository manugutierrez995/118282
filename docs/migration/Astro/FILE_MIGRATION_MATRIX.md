# File migration matrix

| Current file | Current purpose | Target location | Action | Cache impact | Risk | Notes |
|---|---|---|---|---|---|---|
| `index.html` | shell | `SiteLayout.astro`, `index.astro` | WRAP | hashed bundles/static HTML | high | preserve IDs/startup guard |
| `mobile.html`, `placeholder.html`, `reveal.html` | operational alternate pages | static/operational equivalent | REVIEW | none | high | deadman workflow rewrites them |
| `src/main.js` | global boot | `client/site.ts` | CONVERT TO TYPESCRIPT | none | medium | preserve failure isolation |
| `src/page/page.js` | query router | Astro routes + compatibility | DEPRECATE AFTER PARITY | avoids fallback | medium | no pathname/hash today |
| `src/page/landing.js` | landing markup/start | page + `client/landing.ts` | SPLIT | build static shell | high | four concurrent starts |
| `src/page/reader.js` | reader system | `client/reader/index.ts` | CONVERT TO TYPESCRIPT | manifest dedupe/versioned pages | high | minimal semantic change |
| `src/components/search.js` | search UI/index | `client/search.ts` | IMPORT | remove no-store/version URL | medium | shared promise preserved |
| `src/components/rotunda*.js` | Rotunda/mount window | `client/rotunda*.ts` | IMPORT | release JSON + bounded thumbs | high | preserve motion/drag/keyboard |
| `src/components/blocks.js`, `public/blocks/*` | side content | component/client | WRAP | share image-cycle promise | medium | embedded scripts/external iframe |
| `src/components/visibility_policy.js`, `src/utils/tag.js` | visibility | adapter + client defense | MOVE TO BUILD | prevents private output | high | retain client filter too |
| `src/storage/*.js` | URL/manifest loaders | `data/*.ts`, reader loaders | CONVERT TO TYPESCRIPT | promise caches/version URLs | medium | Storage itself makes no request |
| `src/fetch/fetch.js` | legacy loader | none after audit | DEPRECATE AFTER PARITY | removes duplicate path | low | no current caller found |
| `src/discussion/*`, `supabase/*` | discussion/auth | retained client/backend | KEEP UNCHANGED | private responses no-store | high | not static data |
| `src/styles/*.css` | visuals | `src/styles/*` | KEEP UNCHANGED | Astro hashes build result | high | first parity phase imports directly |
| `src/data/fetch.json`, `works/*.json`, `rotunda.json`, `tags.json`, `storage.json` | canonical/generated input | same + adapters | KEEP UNCHANGED | projections become immutable | high | never schema-rewrite |
| `public/data/*.json`, ticker JSON | public runtime | compatibility + releases | GENERATE | immutable releases | medium | keep short-cache aliases |
| `scripts/ingest-work*.py`, `run-ingest.sh` | ingestion | same | KEEP UNCHANGED | later emits revision knowledge | high | do not couple to Astro |
| search/tag/split generators | indexes | release-generation scripts | MOVE TO BUILD | versioned indexes | medium | equivalence tests first |
| `scripts/deletor.py` | delete/hide/tag/admin | same | DO NOT MIGRATE | none reader | high | repo delete, remote reads explicit |
| beta/legacy admin scripts | audit/navigation | same | REVIEW | none reader | medium | exclude public build |
| `scripts/storage-map.{json,jsonl,csv}`; audit JSONL | operational inventories | same/private build input | KEEP UNCHANGED | enables no-list generation | high | public projection must redact |
| `package*.json`, `vite.config.js` | current build | parallel configs, later replace | REVIEW | Astro hashes | high | preserve Vite prod until cutover |
| `wrangler.jsonc` | static deploy/fallback | future static dist config | REVIEW | explicit header/routing later | high | do not add Worker |
| `.github/workflows/*` | deadman switch | adapted workflow after approval | REVIEW | n/a | critical | never alter during early phases |
| `tests/*` | regression suite | retained + Astro tests | KEEP UNCHANGED | proves behavior | low | expand first |
