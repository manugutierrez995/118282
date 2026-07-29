# Test and parity checklist

## Functional

- [ ] homepage, deferred search and zero-result/error states
- [ ] Rotunda opening, center/top visuals, hover, arrows, keyboard, drag/swipe, alternating motion, infinite wrap with no black gaps, living background
- [ ] work selection and reader opening from search/Rotunda
- [ ] direct canonical work URL and `#page-1`/middle/last refresh
- [ ] passive scroll hash, explicit jump, Back and Forward
- [ ] invalid/encoded/hidden work, invalid page, trailing slash and 404
- [ ] missing image and retry; multiple chapters; explicit irregular filenames
- [ ] mobile/desktop orientations; reduced motion; focus/autohide/search focus
- [ ] continuous scroll, transitions, layout stability, zoom baseline, title/description, thumbnail/source preview
- [ ] discussion remains isolated and failures do not block reading

## Network/cache/data assertions

- [ ] no application Worker request during open/page navigation
- [ ] no R2 list operation during ordinary reading
- [ ] no duplicate catalog/search request; no duplicate work/chapter promise
- [ ] page advancement makes no document/manifest request
- [ ] second visit uses browser cache for immutable data/media
- [ ] repeat edge request shows eligible HIT/Age; distinguish origin miss
- [ ] immutable URL upload is create-only and bytes never overwritten
- [ ] HTML/pointer/release cannot mix incompatible versions
- [ ] pointer conditional switch and previous-release rollback work
- [ ] no arbitrary cache-busting query; cache-key test covers tracking normalization
- [ ] public output contains no private tags, credentials, unpublished/hidden works, admin storage keys
- [ ] canonical JSON/JSONL byte/schema compatibility fixtures pass
- [ ] compatibility aliases have short cache; private responses are `private,no-store`

Automate pure adapters/history/parsers, schemas/privacy, generated route enumeration and browser flows. Use real Cloudflare staging for `CF-Cache-Status`, `Age`, collapse/tier/conditional assertions; local preview cannot prove edge behavior.
