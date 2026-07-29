# Open questions

| Question | Why/evidence | Options / safest assumption | Blocking / verification |
|---|---|---|---|
| What live headers/cache rules/routes exist on site and CDN? | none versioned; config only static fallback | dashboard defaults/rules; assume unknown, never immutable unversioned | blocks phase 7; export config + cold/warm HEAD/GET |
| Does CDN custom domain map directly to R2 and use tiered cache/collapse? | storage JSON names CDN only | R2 custom domain/proxy/Worker; assume browser GET ≠ origin read | measurement blocker; DNS/dashboard/analytics |
| Which deployment target is authoritative: Cloudflare assets, GitHub Pages, or both? | Wrangler exists; no Pages deploy; deadman GitHub workflow rewrites HTML | Cloudflare primary/dual | blocks route/deploy decision; owner + production history |
| How must deadman-switch semantics work with generated Astro HTML? | workflow overwrites index/mobile | deploy alternate release, generated placeholders, retire with approval; keep untouched | cutover blocker; operational design/test |
| Are current slugs permanently canonical and case/encoding rules fixed? | filenames/exact slug lookup include punctuation | exact UTF-8 percent encoding; do not normalize | route generation blocker; collision audit/owner approval |
| Are any works truly multi-chapter/irregular in production? | code supports; sampled/prior audit mostly one chapter; numeric pattern assumed | explicit ordered filenames whenever unproven | adapter test blocker; inventory all item/media keys at ingestion |
| Exact hidden/private policy for direct URLs/search? | Rotunda omits; reader lookup not consistent | public projection allowlist and 404 hidden | privacy blocker; owner policy + corpus audit |
| Exact reader zoom/source-preview baseline? | no dedicated symbol located | preserve browser/CSS behavior | parity nonblocking until baseline; manual capture |
| What memory/latency/cost budgets select preload window? | current 10/10 unmeasured | conservative adaptive experiment | phase 7 tuning; field/staging telemetry |
| Annotation schemas, permissions and update cadence? | vision only | optional versioned public SVG snapshots; no implementation | not Astro cutover blocker; separate design approval |
| Rotunda editorial precedence/draft authorization? | future request, not current schema | locked manual > generated with deterministic seed | not migration blocker; future generator spec |
| Required Node version and Astro version policy? | no engines/nvmrc; Astro absent | pin supported LTS and reviewed Astro at implementation time | phase 2 blocker; CI/runtime inventory |
