# Build and deployment plan

## Audit

**VERIFIED IN CONFIG:** package scripts are Vite `dev/build/preview`, Node test; no `engines`/`.nvmrc` pins Node. Vite 8 multi-page inputs are index/mobile/reveal and outputs static `dist`. Wrangler 4 serves `dist` with SPA fallback, no app Worker/bindings. No `_headers`, redirect file, Astro, explicit base path, GitHub Pages deploy workflow, or release pointer exists. A GitHub Actions deadman switch rewrites and commits `index.html`/`mobile.html`; it is an operational blocker requiring owner design. `.env.production`/`.env.example` and storage JSON define environments/domains; secrets must not be build output. Custom-domain/DNS/dashboard/cache headers are external unknowns.

## Future exact sequence

```text
Pin runtime/tool versions and validate canonical data
 -> generate redacted public release projections
 -> generate/validate static Rotunda data
 -> build Astro static output against one release ID
 -> validate routes, links, schemas, privacy, hashes
 -> upload immutable media/release artifacts
 -> deploy Astro HTML + hashed assets
 -> smoke/cache test without pointer switch
 -> switch current.json last (conditional write)
 -> monitor, retain prior release
```

Run Vite production in parallel until cutover. Astro static output should target a distinct directory/environment initially. Header rules become version-controlled only after live baselines; do not mark unversioned media immutable. GitHub Pages needs explicit custom-domain/project-base decision and generated paths/404. Cloudflare may keep an intentionally narrow fallback during compatibility, then generated work files should resolve directly. Rollback switches `current.json` and static HTML deployment to the previous compatible release.
