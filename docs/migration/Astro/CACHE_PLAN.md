# Cache-first policy

Policies apply only after immutable naming and live header verification.

| Resource / URL | Cache-Control | Validator/version/invalidation | Browser/edge/R2 effect |
|---|---|---|---|
| Astro HTML `/`, `/work/*/` | `public, max-age=0, s-maxage=300, stale-while-revalidate=86400, must-revalidate` | ETag; redeploy/purge small HTML set | browser validates; moderate edge reuse; current routes update promptly |
| hashed JS/CSS `/_astro/<hash>` | `public, max-age=31536000, immutable` | content hash; new URL | persistent browser/edge, rare origin |
| pointer `/current.json` | `public, max-age=60, s-maxage=300, stale-while-revalidate=3600` | strong ETag/conditional switch | small validations; atomic release selection |
| global/shards `/releases/<id>/catalog/...` | `public, max-age=31536000, immutable` | release/content digest; pointer switch | maximal reuse, no purge |
| work manifests `/releases/<id>/works/<slug>.json` | same immutable | release ID + content validation | one shared promise/work; no item discovery |
| search/Rotunda/public tags release data | same immutable | release ID | repeat visits cached; no no-store |
| compatibility JSON aliases | `public, max-age=300, s-maxage=3600, stale-while-revalidate=86400` | ETag/Last-Modified; update alias | bounded staleness |
| versioned thumbs/pages `/.../r-<digest>/...` | `public, max-age=31536000, immutable` | content/revision key; never overwrite | largest Class B/byte reduction |
| public annotation snapshot | same immutable | layer+revision/release | cached independently of image |
| frequently changing public layer | `public, max-age=30, s-maxage=60, stale-while-revalidate=300` | ETag | bounded freshness/edge reuse |
| private/admin/auth | `private, no-store` | auth-aware only | never shared/public |

## Discipline

Remove inappropriate `no-store` only from public versioned search/side data; retain it for secrets/private authenticated data. Maintain one in-flight promise per release pointer, work, chapter compatibility manifest, and JSON URL; evict rejected promises and use bounded LRU. Normalize/ignore only proven tracking query parameters at the CDN; reject arbitrary media query cache-busters and ensure transformations/Vary do not fragment keys. A release-selected page must resolve every artifact under the same release—do not refetch pointer mid-session.

Never overwrite immutable keys. Publish then switch pointer; rollback switches pointer, retaining assets, without mass purge. Verify cache key, conditional 304, `Age`, `CF-Cache-Status`, collapse and tier behavior empirically. Request collapsing/tiered caching are **EXTERNAL CONFIGURATION UNKNOWN**, not architectural guarantees. Native HTTP caching precedes any service worker; only a separately measured offline requirement can justify one.
