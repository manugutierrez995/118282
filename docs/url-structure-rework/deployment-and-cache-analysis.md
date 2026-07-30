# Deployment, direct navigation, and cache analysis

## Active deployment facts

Vite emits static assets. `vite.config.js` has three HTML inputs; there is no static route generation. `wrangler.jsonc` serves `./dist` with `not_found_handling: "single-page-application"`, so Cloudflare's asset runtime can return the application shell for an unknown nested pathname. There is no custom Worker handler, Pages Functions directory, `_redirects`, service worker, middleware, Cache API usage, or checked-in cache headers.

The repository has no GitHub Pages deployment workflow, Vite `base`, CNAME, or SPA `404.html`. Root architecture documents discuss GitHub Pages historically/futuristically, but it is **not an active supported target proven by configuration**. R2/CDN is the public media/metadata store addressed by `src/data/storage.json` and `src/storage/storage.js`.

## Direct navigation requirements

Cloudflare's fallback is necessary but insufficient: the client parser must recognize the path. After each route phase, test fresh direct GET and refresh for `/account/profile`, bookmarks, settings, a real work detail, and `/read#page=3`; a shell that silently renders home is failure.

For Cloudflare static assets:

1. Retain SPA not-found handling for client routes.
2. Ensure real asset requests containing dots still return asset 404s, not misleading HTML where possible.
3. Use root-absolute asset paths (current `/src` is transformed by Vite); keep no base-path assumption.
4. Normalize no trailing slash and encoded segments in the client initially. If an edge handler is later added, mirror rules exactly.
5. Recognize that fallback responses may have HTTP 200. True 301/308, HTTP 404/403, per-work canonical metadata/social cards, and bot-friendly HTML require prebuilt files or a thin Worker/Pages Function later.

Do not add hundreds of manually maintained HTML files. A generated work identity manifest plus SPA resolution is the first safe step; measure SEO/share requirements before prebuilding/edge rendering.

## GitHub Pages compatibility

GitHub Pages does not provide arbitrary SPA rewrites. Supporting project Pages later requires all of:

- decide custom-domain root versus `/repository/` base and configure Vite consistently;
- emit/copy a `404.html` fallback that restores the original path, or prebuild route directories (`route/index.html`);
- ensure scripts, public data, icons, and R2 URLs honor the chosen base;
- test direct navigation, refresh, query and fragment preservation on the actual Pages URL.

A generic `404.html` hack often returns HTTP 404 and can break OAuth callback allowlists. Hash-routing the whole application would avoid rewrites but conflicts with clean work URLs and reader page fragments; do **not** introduce it. Until explicit support is chosen and tested, document GitHub Pages checks as skipped/not supported rather than claim parity.

## URL details

- Canonical path has no trailing slash except `/`.
- Public slug is lowercase ASCII; percent-encode every dynamic path/query segment with URL APIs. Storage slug remains exact/case-sensitive and never comes directly from the public path without resolver lookup.
- Preserve `#page=3` across OAuth `next` and legacy conversion; fragments are not sent to Cloudflare/Supabase.
- Cloudflare/Linux/R2 keys are case-sensitive; do not lowercase storage paths.
- Query order should be deterministic (`chapter`, then `mode`); strip unknown tracking/state parameters from canonical URLs where policy allows.

## Public/private cache matrix

| Resource | Shared edge/browser cache? | Notes |
|---|---:|---|
| hashed JS/CSS | Yes, immutable | Vite assets |
| application shell | Yes, short/revalidated | Must contain no user state |
| work identity/catalog/tags/search | Yes | version/fingerprint; one canonical source |
| work detail public projection/cover | Yes | allowlisted metadata only |
| R2 `item.json`, images, thumbnails | Yes | immutable/versioned preferred; CORS as needed |
| auth callback/login response | No/shared bypass | `Cache-Control: no-store` where a dynamic layer exists |
| profile/bookmark/preference/progress rows | **Never shared** | Supabase RLS + private/no-store; browser memory/IndexedDB only by explicit design |
| personalized ordering | Not as a shared response | compute client-side from public list + private preferences |

Never embed authenticated data in cacheable HTML, public JSON, build output, URL, analytics payload, or service-worker Cache Storage. Do not vary shared HTML solely on cookies unless the edge cache key/bypass is rigorously designed; simplest is a neutral shell plus private hydration.

Supabase's public URL/publishable key may be shipped; service-role keys may not. RLS protects every request. Clear user-scoped memory on auth generation changes and cancel stale fetches so user A's results cannot paint after user B signs in.

## Service-worker implications

None exists now. If offline work later adds one:

- precache only versioned public shell/assets/catalog;
- use cache-first/stale-while-revalidate only for public resources;
- network-only (or explicit encrypted/user-keyed local design) for Supabase Auth/private endpoints;
- never cache OAuth callbacks, authorization headers, or responses with `Set-Cookie`/private/no-store;
- delete incompatible caches on activate/logout and test account switching/offline leakage;
- prevent fallback navigation cache from turning missing works into stale home/work pages.

## Verification matrix

Run production `vite build`/preview and Wrangler local/preview direct requests. Verify paths with duplicate titles, punctuation/Unicode, stale slug canonicalization, missing/hidden works, and reader fragments. Inspect response status/headers/body and browser Cache Storage/IndexedDB/network. For two accounts, prove a warm public edge cache never serves private data. GitHub Pages direct-route tests remain an explicit environment warning until configuration exists.
