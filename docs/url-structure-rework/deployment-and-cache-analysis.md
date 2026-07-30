# Deployment and cache analysis

## Verified deployment model

The application is built by Vite. `vite.config.js` declares HTML inputs for main, mobile maintenance, and reveal shells. Wrangler publishes `dist` as static assets and uses `not_found_handling: "single-page-application"` (`wrangler.jsonc`). No Worker script, Pages Function, middleware, `_redirects`, `_headers`, service worker, or Cache API usage is checked in. R2/media origins are selected from `src/data/storage.json`; production source `e` uses the custom CDN host.

The GitHub workflow is a deadman switch that copies placeholder/reveal content and pushes to main. It is not a GitHub Pages deployment. No Pages action/config, `404.html`, CNAME, base path, or nested-route fallback exists. Documents discuss GitHub Pages as an architectural option, but current support is unproven.

## Direct navigation

### Cloudflare Wrangler static assets

SPA not-found handling should return `index.html` for `/account/profile` and `/works/...` while preserving the requested browser URL. The new router must then recognize it. Verify with `wrangler dev`/deployed preview because asset precedence, status, and fallback behavior are platform behavior, not guaranteed merely by client tests. A fallback shell typically returns 200 and generic metadata even for missing works; true 404/301/social cards require generated route HTML or an edge resolver later.

Ensure actual assets (`/data/*`, bundled chunks, favicon, blocks) win over fallback. A route parser must not treat file-like unknown requests as app pages. Refresh and paste tests are mandatory for every nested route.

### Cloudflare Pages (if separately configured)

No Pages `_redirects` is present. If the target is Pages rather than Wrangler Worker Assets, add/test an SPA fallback such as a platform-supported rewrite only in the deployment phase; do not assume `wrangler.jsonc` applies to a different Pages pipeline. Avoid redirect loops and ensure missing static assets do not receive HTML with status 200 unnoticed.

### GitHub Pages

Project Pages cannot rewrite arbitrary nested paths to `index.html` by default. Hash positions help only after the document path resolves; `/works/.../read#page=3` still requests the nested pathname first. Options if Pages is truly required:

1. generate `index.html` at each supported public route and a safe account shell/fallback;
2. use a copied `404.html` SPA bootstrap that restores the original path (status remains 404 and has SEO/asset-base limitations);
3. use only hash routing (rejected because it compromises the canonical structure);
4. declare GitHub Pages unsupported and use Cloudflare canonical hosting (recommended default now).

Configure Vite `base`, router basename, root/project asset paths, and custom domain explicitly before claiming support. Account routes can use generic static shells; work count affects generated-file feasibility.

## Static export limitations and strategy

Current Vite build is a static bundle, not per-route SSG. The smallest safe solution is one shell plus client resolver, taking advantage of Cloudflare fallback. This preserves build speed/cache-first behavior. Later, generate detail HTML for public works if SEO/share previews/real 404s warrant it. Do not prebuild every page-position URL; fragments never reach the host.

Public work page HTML can be prebuilt from a public metadata projection and cached. Account page shell contains no user data and may be cached, but its private fetches and rendered state are client-only. An edge auth implementation is optional later, not required to protect Supabase data because RLS does that.

## Cache matrix

| Resource | Shared edge/browser policy | Notes |
|---|---|---|
| versioned JS/CSS/assets | public, long-lived, immutable | Vite hashed assets |
| HTML shell | public, revalidate/short TTL | must contain no private state |
| public work identity/catalog/tag vocabulary | public, versioned, revalidate or immutable release | atomic release pointer/version |
| public work detail projection | public, cacheable | no user bookmark/preference fields |
| R2 `item.json`/work manifests | public cacheable; version/revalidate according to publication | page counts/chapter metadata |
| page images/thumbs/archives | public long-lived when immutable | R2/CDN; no auth tokens in public URL |
| Supabase profile/bookmark/preference/progress | `Cache-Control: private, no-store`; browser memory scoped to user | never Cache API/shared CDN |
| OAuth/session/token endpoints | no-store/private per provider | never log tokens/fragments |
| personalized work list | compute locally from public catalog + private prefs | never shared URL/cache |

Do not put user UUID/access tokens into public cache keys or analytics URLs. Clear in-memory private query caches on sign-out/user change. If IndexedDB caching of private state is introduced later, namespace by user ID, encrypting is not equivalent to authorization, and remove it on sign-out/account deletion according to policy.

## R2 and Supabase request behavior

Public reading currently fetches a chapter `item.json`, bounded image window, bundled/static work manifest, and blocks. R2 is media/static metadata only; keep it that way. Resolve work visibility and chapter membership before forming R2 URLs. Public CDN cache hits should not vary by user preference.

Supabase calls should begin only after session resolution and only for current-view private needs. Account shell may parallelize owner profile/preferences after auth; bookmarks paginate. Landing can fetch compact preferences, then compute locally. Reader discussion remains independently resilient: public pages should load when Supabase is unavailable.

## Service workers

None exists. Do not add one merely for routing. If introduced later:

- navigation fallback must understand deployed base and exclude auth callbacks/static/API URLs;
- never Cache Storage private Supabase responses/account HTML;
- version public catalogs atomically to avoid code/schema mismatch;
- OAuth responses/fragments and no-store requests bypass cache;
- sign-out posts a clear-private-cache message to all controlled tabs;
- test offline missing/hidden work behavior and stale catalogs.

Browser HTTP cache/CDN, not a service worker, is the current cache architecture.

## URL details

- Canonical application paths have no trailing slash; `/` is the exception.
- Slugs are lowercase ASCII kebab-case and percent-encoded by segment; IDs are constrained opaque values.
- Route matching is case-sensitive and malformed encoding is a 404.
- Use root-absolute assets on current Cloudflare custom-domain deployment; do not concatenate route-relative asset paths.
- Hash is client-only; query affects the requested URL and analytics/cache semantics. Cloudflare never receives `#page=3`.
- Sanitize `next` and OAuth redirects as same-origin relative routes.

## Cache-leak prevention tests

1. Sign in as A, visit all private pages, sign out, sign in as B in the same browser: no A content flashes or remains in DOM/memory/storage.
2. Inspect response/cache headers for Supabase/private proxy responses; ensure shared CDN cache status never reports a hit for private data.
3. Compare account HTML source signed in/out: it is the same data-free shell.
4. Fetch public work metadata with different auth cookies/headers: same public response and no private fields/Vary explosion.
5. Attempt cross-user REST queries under RLS.
6. Run two browser contexts through bookmarks/preferences and confirm isolation.
7. Verify a service-worker registration remains absent unless deliberately introduced.

## Deployment verification matrix

For Cloudflare preview/production, paste and refresh `/`, `/login`, `/signup`, all account routes, `/works`, valid detail/read, missing work, old slug, and deep-link pages. Verify assets MIME/status, canonical correction, back/forward, and real observed fallback status. Repeat on Pages only if that is an actual target. For GitHub Pages, mark nested routes unsupported until one of the explicit fallback/generation strategies passes; do not report click-only success as support.
