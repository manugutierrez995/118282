# Current cache audit

## Verified repository behavior

* **VERIFIED IN CONFIG:** no `_headers`/`_redirects`, explicit response headers, cache rules, Worker Cache API, service worker, R2 binding, or app Worker entry. Wrangler serves `dist` with SPA fallback.
* **VERIFIED IN CODE:** search and four side-block scripts use `cache: "no-store"`. This blocks normal browser reuse.
* Work manifests use an LRU-like `Map` of at most 40 in-flight/resolved promises. Rejections are evicted.
* Search has one page-lifetime promise. Rotunda caps metadata and thumbnail maps at 40, concurrency at four, mounts at most 20 cards, and aborts stale image/metadata work.
* Chapter `item.json` has no promise cache and is fetched on every render. `Fetch.chapter()` is another uncached legacy path, apparently unused.
* Reader retains a maximum 21 image elements (10/active/10); first three are eager/high priority. Removing an image does not create an application decoded-image cache.
* Vite output JS/CSS is content-hashed. `fetch.json`, search/ticker/block JSON, work/chapter manifests, thumbs, and page paths are unversioned.
* Query strings select the shell but the app adds none for media. Hashes never reach HTTP/cache keys.

## External deployment verification required

**EXTERNAL CONFIGURATION UNKNOWN:** response `Cache-Control`, `ETag`, `Last-Modified`, `CF-Cache-Status`, `Age`, cache-key query treatment, R2 custom-domain behavior, conditional request forwarding, CDN request collapsing, tiered caching, dashboard rules/transforms, and cache eligibility. Capture cold/warm `curl -sSI` and browser DevTools for both site/CDN hostnames; do not infer an R2 read from a browser GET.

## Likely request sources, not origin assertions

Static shell/data request the static deployment. Direct immutable-looking media URLs request the CDN. Only CDN misses can become R2 Class B reads. Admin ingestion/audit/deletor may list/read/write storage; these are not ordinary reading. Known avoidable traffic: no-store search, four identical no-store side JSON calls, repeated chapter manifest render, speculative 21-page window, and thumbnail fallback candidates.

## Assumptions to test

**DEPLOYMENT ASSUMPTION:** Cloudflare may generate validators/default caching for static assets. **DEPLOYMENT ASSUMPTION:** the custom CDN terminates in R2. Neither proves cache status. See [cache plan](CACHE_PLAN.md) for policy, not present behavior.
