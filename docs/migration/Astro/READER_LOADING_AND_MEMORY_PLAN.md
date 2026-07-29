# Reader loading and memory plan

## Current verified implementation

`WINDOW_BEFORE=10`, `WINDOW_AFTER=10`, `PRIORITY_PAGES=3`: up to 21 image elements. All page placeholders exist; ratio starts at 2:3 then corrects from natural dimensions with scroll compensation. IntersectionObserver uses a 50% vertical margin. Outside-window images lose `src` and node; revisits rely on HTTP cache. A failed image stays failed until its button retry. Chapter fetch is not aborted/cached; render generations discard stale results. Rotunda, unlike reader chapter loading, has abort controllers and bounded maps.

## Measured policy, not magic constants

1. Instrument page distance, time-to-visible, transfer/cache source, decoded dimensions/bytes, aborts and revisits.
2. Start experiments at 2 behind/3 ahead on normal links; 1/1 for `saveData`, 2G/slow-2G, high memory pressure; expand only when p95 neighbor start regresses.
3. Preserve active and immediate decoded neighbors within a budget (initial test ceilings: 64 MiB mobile, 192 MiB desktop, not commitments). Estimate RGBA decoded bytes `width*height*4`; evict LRU outside safety radius.
4. Keep one URL promise/state record per image to prevent duplicate assignments while pending; browser cache remains durable byte store. Removing DOM must not force application refetch with cache-busting.
5. One promise per work/chapter URL; AbortController on obsolete chapter manifest and practical pending image preload fetches. Do not abort already nearly complete visible images blindly.
6. Use manifest dimensions for stable aspect ratio. Generate real thumbnails; never fetch full page as fallback unless the identical URL is already cached/known loaded.

## Effects

| Improvement | Primary effect | Tradeoff |
|---|---|---|
| immutable URLs + native cache | fewer R2 reads/repeated bytes | requires revisioned ingestion |
| shared promises/dedupe | fewer duplicate browser requests | bounded state complexity |
| smaller connection-aware window | fewer speculative misses/bytes/Class B | possible next-page latency |
| decoded LRU | lower memory/redecode balance | may retain bytes but no new HTTP request |
| dimensions/placeholders | visual stability only | manifest size |
| abort obsolete work/chapter | fewer wasted bytes | race/error handling |

Measure p50/p95 visible image start, work open, bytes, Class B proxy/cache misses, decoded memory and revisit latency on representative short/long/large chapters before selecting constants.
