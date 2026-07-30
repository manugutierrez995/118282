# Genuinely unresolved questions

These are the issues repository evidence cannot settle. None prevents the recommended Phase 1 audit; defaults permit progress without inventing facts.

## 1. Is `parent_work_id` immutable and globally authoritative?

- **Why it matters:** every public URL and private foreign reference must survive re-ingestion, moves, and title changes.
- **Evidence searched:** all 724 work manifests (unique IDs), fetch/rotunda/search/tag data, active and legacy ingestion/deletion scripts, storage maps/backups, architecture/ingestion docs, tests, and git history. Assignment exists, but no allocation registry or immutability guarantee was found.
- **Default:** Phase 1 treats it as a candidate, traces generation/rerun fixtures, and refuses to publish a canonical guarantee if unproven. If unstable, introduce a persisted immutable ID registry before routes consume it.

## 2. What is the intended record for the 725th catalog entry without a checked-in work manifest?

- **Why it matters:** it cannot supply verified stable ID/chapter metadata and would create a broken or ambiguous route.
- **Evidence searched:** counts and exact entries across fetch, rotunda, tags, search, `src/data/works`, deletor backups, ingestion outputs.
- **Default:** generator emits a named validation exception and excludes it from canonical routes until repaired; do not fabricate an ID.

## 3. Are authenticated remote accounts now a confirmed product reversal of the local-first decision?

- **Why it matters:** current code deliberately replaced remote accounts with multiple browser-local profiles, while this requirement mandates Google/email users and private cross-device pages.
- **Evidence searched:** `docs/local-first-browser-profiles.md`, account foundation/deviation documents, git history (`Replace Supabase accounts with local browser profiles`), current runtime/tests, env and migration files.
- **Default:** preserve `/profiles` for local/offline identities and implement `/account` as authenticated only after Phase 5 confirmation; offer explicit import. Do not discard local data or label it authenticated.

## 4. What is actually deployed in Supabase and which Auth providers/redirects are enabled?

- **Why it matters:** checked-in migrations may already exist, differ, or conflict; Google/email/callback behavior is dashboard-controlled.
- **Evidence searched:** all migrations, env examples, package/source auth searches, discussion setup docs, workflows. No CLI config, schema dump, provider config, or live access evidence exists.
- **Default:** perform a read-only live schema/policy/migration/provider/redirect inventory before installing a client or applying SQL. Treat migrations as intended history, not deployed proof.

## 5. Must public comment display names/avatars remain public?

- **Why it matters:** current SQL exposes `profiles` for account-mode comments, while account profile must be private; policy changes could break comments.
- **Evidence searched:** discussion migration/docs/current local read-only UI and account architecture history.
- **Default:** owner-only `account_profiles` plus minimal `discussion_profiles`/allowlisted RPC; never expose email, provider, private dates, bookmarks, or preferences.

## 6. What are direct-link rules for globally hidden/private/adult works?

- **Why it matters:** resolver status, existence leakage, and personal-exclusion behavior need a stable publication policy.
- **Evidence searched:** `public_rotunda` omit/showcase rules, visibility utilities/tests, hide/deletion scripts/docs, tag catalog. They govern discovery/rotunda, not legal/adult direct access.
- **Default:** globally private/deleted/administratively hidden returns indistinguishable not-found; personal exclusion affects discovery only. Globally public adult links remain reachable unless a separately approved age/interstitial policy says otherwise.

## 7. Is GitHub Pages still a deployment target?

- **Why it matters:** clean nested routes require prebuilt paths or a `404.html` technique and base/OAuth decisions.
- **Evidence searched:** `.github/workflows`, Vite base/config, repository Pages/CNAME/fallback files, root and migration deployment docs. Only Cloudflare Wrangler has active SPA routing config.
- **Default:** Cloudflare is supported; GitHub Pages is unsupported until deliberately configured and tested. Do not compromise canonical routes with application-wide hash routing.

## 8. Which remote `details.json` fields are approved for work pages/social previews?

- **Why it matters:** raw remote metadata may contain internal/provenance/licensing-sensitive data and is not available in the checkout.
- **Evidence searched:** ingestion scripts/docs, manifest URLs, R2 audit tools, work projections, search/tags. No complete checked-in remote payload or publication allowlist exists.
- **Default:** build work pages from an explicit allowlisted checked-in/generated public projection (ID, public slug, display, cover, chapter/page information, approved tags); omit descriptions/source fields until reviewed.
