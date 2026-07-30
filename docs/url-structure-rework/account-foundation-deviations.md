# Account foundation deviations

## Live Supabase and provider verification
- **Requirement:** Verify authentication, bookmark ownership, preference ownership, migrations, and RLS live.
- **Requested behavior:** Google and email flows and two-user isolation are live-verified.
- **Actual behavior:** Repository implementation and policy SQL are tested statically; no project credentials or administrative/live test-user access was available.
- **Status:** blocked-by-missing-access
- **Reason:** Browser publishable configuration may be supplied only at deploy time and no Supabase CLI project linkage or test credentials are checked in.
- **Repository evidence:** `src/auth/supabase.js`; `.env` is absent; `supabase/migrations/202607170001_discussion_mvp.sql` and `202607300001_user_tag_preferences.sql` are local files only.
- **External or Supabase dependency:** Supabase project dashboard/database and two test users.
- **Risk of forcing the requested implementation:** Inventing state or committing credentials could expose the project; client-only filters cannot prove RLS.
- **What was implemented instead:** Owner filters plus owner RLS SQL, safe failure states, static tests, and exact manual verification steps.
- **Files affected:** auth/account services, both migrations, tests, manual actions.
- **User-visible consequence:** Flows work only after provider/redirect configuration; preferences remain deliberately disabled.
- **Security or privacy consequence:** No live cross-user claim is made.
- **Exact next step:** Apply migrations in order and execute the two-user policy checks in the manual action document.
- **Who or what must perform the next step:** Supabase project administrator.
- **How completion can be verified:** User A and User B cannot select/delete each other's rows; all auth callback scenarios succeed.

## Tag preferences
- **Requirement:** Persist preferred and excluded tags when safe.
- **Requested behavior:** Editable, owner-specific tag lists.
- **Actual behavior:** Owner-only normalized migration and service boundary are prepared, but the UI is explicitly disabled.
- **Status:** partially-implemented
- **Reason:** `src/data/tags.json` contains empty values and internal `manifest` markers and has no reviewed public vocabulary.
- **Repository evidence:** `docs/url-structure-rework/tag-preferences-and-filtering.md`; `src/data/tags.json`.
- **External or Supabase dependency:** Product/editorial vocabulary review and migration application.
- **Risk of forcing the requested implementation:** Users could save internal pipeline labels or arbitrary tags that never match catalog content.
- **What was implemented instead:** Settings/account summary, disabled labeled controls, and owner-RLS table migration.
- **Files affected:** `src/account/views.js`, preference migration.
- **User-visible consequence:** Preferences cannot yet be edited.
- **Security or privacy consequence:** No preferences are stored publicly or locally.
- **Exact next step:** Publish a versioned allowed vocabulary, add validation/RPC, apply migration, then enable the editor.
- **Who or what must perform the next step:** Product/data owner and Supabase administrator.
- **How completion can be verified:** Internal tags are rejected and add/move/remove operations persist per owner.

## Identity linking
- **Requirement:** Google and email are methods for one UUID; safely preserve anonymous upgrades.
- **Requested behavior:** Anonymous-to-Google/email upgrade and provider unification.
- **Actual behavior:** Existing anonymous-to-Google `linkIdentity` is preserved. Email signup/login uses Supabase Auth UUIDs, but no unsafe email-string merge or unverified anonymous-to-email link was added.
- **Status:** implemented-with-deviation
- **Reason:** Safe email identity linking requires provider/dashboard behavior and reauthentication to be verified live.
- **Repository evidence:** `src/auth/session.js` uses `linkIdentity` only for the established Google anonymous path and Supabase native email APIs.
- **External or Supabase dependency:** Supabase identity-linking configuration and verified reauthentication design.
- **Risk of forcing the requested implementation:** Duplicate or hijacked accounts and loss/misattribution of anonymous UUID-owned data.
- **What was implemented instead:** Canonical Auth UUID use and no custom merge.
- **Files affected:** `src/auth/session.js`, auth views.
- **User-visible consequence:** An anonymous user choosing email may receive a separate durable user depending on live Supabase configuration.
- **Security or privacy consequence:** Safer non-merge behavior; existing anonymous records may not transfer.
- **Exact next step:** Implement a verified reauthenticated `linkIdentity` email upgrade after live testing.
- **Who or what must perform the next step:** Application and Supabase administrators.
- **How completion can be verified:** UUID remains unchanged across the explicit upgrade and existing bookmarks/comments remain owned.

## Deployment, push, and draft PR
- **Requirement:** Verify direct refresh, push branch, and open draft PR.
- **Requested behavior:** Deployed nested routes refresh through Cloudflare; branch is pushed; draft PR opened.
- **Actual behavior:** `wrangler.jsonc` contains SPA fallback and build succeeds. Deployment is not performed in this environment; Git remote operations are attempted at completion and their exact result is recorded in the implementation report.
- **Status:** blocked-by-live-configuration
- **Reason:** Cloudflare deployment and remote GitHub authorization are external state.
- **Repository evidence:** `wrangler.jsonc` `not_found_handling`; completion command output.
- **External or Supabase dependency:** Cloudflare/GitHub credentials.
- **Risk of forcing the requested implementation:** Cannot safely assert production behavior or bypass repository authorization.
- **What was implemented instead:** Path router is refresh-compatible with the configured fallback.
- **Files affected:** router and documentation.
- **User-visible consequence:** None after correct deployment; unverified hosts may return origin 404.
- **Security or privacy consequence:** Private data remains client-fetched rather than static HTML.
- **Exact next step:** Deploy preview, refresh every nested route, push branch, and inspect the draft PR.
- **Who or what must perform the next step:** Deployment/repository operator where credentials are unavailable.
- **How completion can be verified:** All nested URLs return `index.html`, render correctly, and PR is marked Draft.
