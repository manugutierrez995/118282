> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Genuine open questions

These questions cannot be proven from the repository. None prevents Phase 1's read-only generator/validator; defaults below allow progress.

## 1. Is `parent_work_id` immutable and globally unique across ingestion sources and reruns?

- **Why it matters:** it is the recommended authoritative URL/database work ID. Reuse or regeneration would break links, discussion, bookmarks, and progress.
- **Evidence searched:** all 724 work manifests (all contain it), fetch/rotunda/search data, ingestion scripts, storage maps, ingestion/deletor documentation, current/static/Astro architecture plans, and discussion SQL. No allocation/immutability contract was found.
- **Default:** treat it as a candidate only. Phase 1 validates current uniqueness and rerun stability on fixtures/backups. If it cannot be guaranteed, allocate a persisted UUID/ULID in canonical ingestion metadata before public routes ship.

## 2. Which Cloudflare product/pipeline is production: Wrangler Worker Static Assets, Pages, or both?

- **Why it matters:** SPA fallback, rewrites, status codes, headers, preview commands, and generated-route deployment differ.
- **Evidence searched:** `wrangler.jsonc`, package scripts/lock, `.github`, root deployment/cache reports, and Astro deployment docs. Only Wrangler static-assets configuration is executable evidence; documents use “Pages” more broadly.
- **Default:** support/test `wrangler deploy` static assets as canonical. Do not claim Cloudflare Pages separately until deployment settings are supplied.

## 3. Is GitHub Pages still a required serving target?

- **Why it matters:** nested direct navigation will fail without generated routes/404 bootstrap and possibly a project base path.
- **Evidence searched:** `.github/workflows`, Vite config, repository files for Pages/CNAME/404/redirects, and architecture/caching docs. Only a deadman-switch workflow exists.
- **Default:** GitHub Pages is not supported for the rework; Cloudflare is canonical. If required later, choose generated route shells or a documented 404 bootstrap and add a separate acceptance gate.

## 4. Has `202607170001_discussion_mvp.sql` been applied, and what is the live Supabase schema/provider configuration?

- **Why it matters:** safe profile/bookmark migrations and Google/email/linking behavior depend on live tables, policies, redirects, anonymous auth, and provider settings.
- **Evidence searched:** `supabase/migrations`, `.env.example`/`.env.production` variable names, discussion code/setup docs, package configuration. No remote schema snapshot/config is committed.
- **Default:** run a read-only live schema/policy/provider inventory before Phase 5 or any SQL. Treat checked-in SQL as intended state, never proof of deployed state.

## 5. Should discussion display names/avatars remain public?

- **Why it matters:** existing public profile reads support account-mode comments, while the new “profile” must be private.
- **Evidence searched:** discussion migration, service/UI, and `docs/discussion-setup.md`. Public discussion names are deliberate, but no current privacy product decision is recorded.
- **Default:** keep a minimal public `discussion_profiles` projection for display name/avatar and make the private `profiles` table owner-only. Never expose email, provider, bookmarks, preferences, or account timestamps publicly.

## 6. What is the authoritative hidden/adult/direct-link policy?

- **Why it matters:** route resolver status and whether user-excluded works remain directly reachable must be consistent and non-leaking.
- **Evidence searched:** rotunda visibility configuration/utilities/tests, deletion/hide docs, canonical tags, architecture plans. They define catalog omission, not direct URL/legal/adult policy.
- **Default:** globally hidden/deleted/private returns indistinguishable not-found; personal exclusions affect discovery only; public adult content direct links remain reachable with an interstitial only if existing policy later requires it.

## 7. Are work title/description/tag fields in remote `details.json` safe and licensed for public work pages/social previews?

- **Why it matters:** detail pages need a clearly public metadata projection; blindly publishing administrative/raw details can leak or violate policy.
- **Evidence searched:** all local files for `details.json`, ingestion scripts/docs, static-reader plan, work manifest URLs. The remote files are not checked in and were not treated as repository evidence.
- **Default:** build an explicit allowlisted public projection from checked-in canonical ingestion metadata; omit uncertain fields until reviewed. Never expose raw administrative tags/details wholesale.
