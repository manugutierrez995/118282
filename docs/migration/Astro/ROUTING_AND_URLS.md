# Routing and URLs

## Current verified behavior

`Page.start` reads `work` and `chapter` from `location.search`; source is also read. The app ignores pathname and hash. Search data emits `/reader?source=e&work=...&chapter=...`; in-page opens do not change URL. Wrangler's SPA fallback can return the shell for unknown paths, but that is not a functional work pathname. Invalid query manifests render “Failed to load chapter.” Trailing slash and GitHub Pages behavior are not configured/tested.

## Target

Canonical work: `/work/<percent-encoded canonical slug>/` (trailing slash). Canonical page: `#page-23`; parser also reserves structured `#page=23&annotation=ann_...`. Use `history.replaceState` for passive scroll tracking (avoids one history entry per pixel/page), `pushState` for explicit page/annotation jumps and chapter selections, and handle `hashchange`/`popstate`. Refresh resolves HTML+manifest then scrolls after layout is stable. Clamp/reject invalid pages visibly; 404 invalid/hidden works without leaking their existence beyond policy.

Compatibility query URLs should canonicalize after successful public resolution, preserving source/chapter/page. Never allow arbitrary source origins from URL. Platform redirects cannot synthesize a slug path reliably from query on all static targets, so a small static compatibility page/client is safest during transition.

## Strategy comparison

| Strategy | Static hosts | Scale | Risk |
|---|---|---|---|
| generated page/work | works on Cloudflare and GitHub Pages when files published | artifact per work | **primary now** |
| shared shell | requires 404 fallback/rewrite for clean deep paths | excellent | direct refresh/platform variance |
| hybrid generated + fallback | generated known routes plus safe compatibility | good transition | dual testing |
| platform rewrite | Cloudflare-specific rule | excellent | external config/portability |

**RECOMMENDATION:** generated pages plus legacy compatibility at current hundreds-scale. Fallback for millions: shared static shell with compact public route index and explicitly tested Cloudflare rewrite/404 behavior. GitHub project Pages may require a base path and custom 404 copy; current Vite config has no `base`. Cloudflare supports current SPA fallback but exact redirect/dashboard config is **EXTERNAL CONFIGURATION UNKNOWN**.
