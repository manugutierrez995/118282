# Visual and interaction parity inventory

| Behavior | Source/symbol/selectors/DOM & timing | Request assumption | Risk / preservation |
|---|---|---|---|
| moving alternating rows/infinite wrap/no gaps | `rotunda.js`, `rotunda.css`, `.rotunda-*`; cyclic bounded window | nearby thumbnails available | high; snapshot DOM/classes and long-run wrap video |
| coverflow hero/opening | `Rotunda.start`, active index/card click | work metadata resolved | high; retain client ownership/event |
| drag/swipe/hover | pointer handlers; threshold 42, pause state | abort stale thumbs | high; Playwright pointer parity |
| keyboard | window keydown, typing-target guard | none | high; preserve focus guard/arrows/Enter |
| living background/ghost | `ghost_text.js`, landing CSS, body child layer | `/text_behind` bundled/fetched module | medium; preserve fixed noninteractive rails |
| reader continuous scroll/transitions | `createVirtualReader`, `.reader-pages/.reader-page` | 21-window and computed URLs | high; preserve scroll anchoring/session cleanup |
| zoom | CSS/browser behavior; no dedicated reader zoom symbol found | high-resolution page | **OPEN QUESTION** baseline exact behavior |
| mobile/desktop | CSS media queries, compact nav labels, side rail hiding | dimensions arrive after load today | high; screenshot matrices |
| title/description/caption | Rotunda caption/card metadata; reader chrome | work manifest | medium; compare text/wrapping |
| image retry | `.reader-page-retry`, retry closure | identical URL/cache | medium; preserve explicit accessible button |
| thumbnail loading | Rotunda imageReady/candidate loop | CDN candidates; bounded caches | high; no full-page fallback |
| source preview | archive/details/block features vary; no unified symbol found | external URLs | OPEN QUESTION; record baseline |
| focus/autohide | `installReaderChromeAutohide`, search events, 1400ms | none | high; keyboard/screen-reader tests |
| reduced motion | HTML/CSS media rules and Rotunda CSS | none | high; no movement and usable controls |

Astro markup must preserve IDs `#app`, `#layout`, `#reader-column`, `#reader-container`, side/footer mounts, and behavioral selectors until CSS/DOM parity is proven. Record desktop/mobile/reduced-motion screenshots and request logs before migration; any selector cleanup is a later isolated phase.
