> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Google login and account-isolation repair

## Symptom and repository root causes

The live UI replaced every provider error with “Google login could not be started,” so the precise external cause was unknowable from the UI. OAuth accepted an overly broad same-origin destination, durable active users could begin OAuth without an explicit sign-out boundary, asynchronous bookmark rendering lacked an identity guard, and navigation exposed three icons instead of one account disclosure. The repository has no remote/deployment credentials, so the current Supabase/Google dashboard configuration and live provider result could not be inspected; a build is not OAuth proof.

Repository repairs preserve Supabase JS 2.57-compatible `signInWithOAuth`, `linkIdentity`, `detectSessionInUrl`, `getSession`, auth events, and `signOut`. Return paths are allowlisted private routes. Durable users are signed out before an independent Google flow. Anonymous linking is fail-closed unless `VITE_ENABLE_ANONYMOUS_GOOGLE_LINKING=true` and the dashboard is verified. Errors are normalized and safely diagnosed without tokens/sessions. Identity generations discard stale bookmarks. Google/email users share Auth-derived profile fallbacks, routes, bookmark table, settings, dropdown, and sign-out.

Discussion profiles already bootstrap through `ensure_profile` in `202607170001_discussion_mvp.sql`: it keys by UUID, stores name/avatar (not email), and uses `ON CONFLICT DO NOTHING`, so no new profile schema was required. This static review does not prove the RPC/RLS is deployed.

## Exact external configuration

1. Supabase Dashboard → Authentication → Providers → Google: enable it and enter the Google OAuth **client ID** and **client secret**. Never commit either secret.
2. Copy the callback displayed by Supabase. Its shape is `https://<project-ref>.supabase.co/auth/v1/callback`. Google Cloud Console → APIs & Services → Credentials → the Web OAuth client → Authorized redirect URIs: add that exact HTTPS callback (not the application `/account/profile` URL).
3. Google Cloud OAuth client Authorized JavaScript origins: add exact production origin and only approved preview/local origins, e.g. `https://<production-host>` and `http://localhost:5173`. No path, credentials, or wildcard. Configure consent screen/test users as Google requires.
4. Supabase Dashboard → Authentication → URL Configuration: set Site URL to the exact production origin. Add exact Redirect URLs for `https://<production-host>/account/profile`, `/account/bookmarks`, `/account/settings`, approved preview equivalents, and `http://localhost:5173` equivalents. Avoid broad preview wildcards unless the organization has reviewed their takeover risk.
5. For intentional anonymous comment/bookmark preservation only: Dashboard → Authentication settings → manual identity linking must be supported/enabled; verify on staging that Google attaches to the same anonymous UUID. Only then set `VITE_ENABLE_ANONYMOUS_GOOGLE_LINKING=true` and deploy. Otherwise leave it unset: the UI fails clearly and preserves anonymous state.
6. Confirm Vite/Cloudflare provides `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` at build time. These are not the service-role key.

## Verification procedure

Open a private browser window; test signed-out → Google → chooser → callback → `/account/profile`; confirm Auth user email/avatar, all three account routes, own bookmarks, dropdown sign-out, and signed-out header. Check console’s redacted `Account authentication failed` object and Supabase Dashboard → Authentication → Logs on failure. Repeat Google → sign out → email → sign out → Google, then email → sign out → Google → sign out → email. Confirm each UUID recovers only its rows. Use browser Network tools to ensure no token/code is sent to analytics. Test cancelled consent and a deliberately unapproved staging redirect.

Apply tag preferences later with the Supabase CLI/database workflow, then compare `supabase migration list`, inspect the table/policies, and execute two-user live RLS select/insert/update/delete tests. Static SQL review alone is not verification.

## Completion/deviations table

| Requirement | Requested / actual / status | Evidence and reason | Dependency, risk, consequence, exact next step |
|---|---|---|---|
| Live Google completion | Complete OAuth / repository path repaired, **not live verified** | No remote, Supabase, Google Cloud, production origin, or test credentials are present | Owner configures steps above and runs both account orders. Claiming success would hide callback/provider risk. |
| Anonymous upgrade | Preserve UUID safely / fail-closed flag added, **manual verification required** | Linking depends on project manual-link setting | Supabase owner verifies staging, then enables build flag. Otherwise anonymous user sees a clear linking message; data is not silently reassigned. |
| Bookmark RLS | Owner isolation / SQL and queries statically verified, **not live verified** | Migration policies use `auth.uid()`; UI filters current UUID | DB owner applies/verifies migrations with two real users. Forcing a claim risks cross-account exposure. |
| Discussion profile | Equal safe bootstrap / existing idempotent RPC retained, **not live verified** | Existing migration uses UUID and no email | DB owner tests RPC/RLS. Account profile still works from Auth metadata if it fails. |
| Tag editing | Future personalized controls / remain disabled, **intentionally incomplete** | No reviewed/validated vocabulary exists | Next Codex run follows root `tags-latest.md`; enabling free text now would corrupt vocabulary/privacy expectations. |
| Push/draft PR | Requested / environment has no Git remote, **blocked externally** | `git remote -v` is empty | Repository operator adds the `thanks-cohn/10-year` remote, pushes branch/tag, and opens draft PR. |

## Tests, build, limitations, next step

Automated Node tests cover routes, redirect validation, normalization, presentation/menu markup, OAuth source invariants, owner queries, migration/static architecture, and handoff headings. Full tests and production build results are recorded in the PR/final report. DOM interaction is covered at the smallest credible static/unit level because no browser test framework exists; manual mouse/touch/keyboard/Escape/outside/focus testing remains required.

Known limitation: callback/provider correctness and live RLS cannot be proven without external project access. Exact next step is the final bold task in `tags-latest.md`, after the owner completes live OAuth/RLS verification above.
