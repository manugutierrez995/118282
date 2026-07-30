# Account foundation manual actions

## Apply and verify database migrations
- **Priority:** required
- **Action:** Apply checked-in migrations in timestamp order to the target project.
- **Why required:** A repository SQL file does not prove live schema or RLS state.
- **Where performed:** Supabase CLI linked to the intended project or Dashboard SQL migration workflow.
- **Exact setting, command, or migration:** Review, then run `supabase db push`; it must include `202607170001_discussion_mvp.sql` before `202607300001_user_tag_preferences.sql`.
- **Expected result:** Discussion/bookmark schema remains and owner-only preferences table exists.
- **How to verify:** Inspect policies and use two non-anonymous users: each inserts/selects/updates/deletes its own preference; attempts against the other's `user_id` return no row or RLS error. Repeat select/delete isolation for `bookmarks`.
- **What remains broken until completed:** Preference persistence cannot be enabled; live RLS is unverified.
- **Security warning:** Never use a service-role key for browser or RLS tests; it bypasses policies.

## Configure email authentication and confirmation
- **Priority:** required
- **Action:** Enable email/password, choose confirmation policy, and configure production SMTP.
- **Why required:** Repository code cannot determine or alter live Auth provider settings safely.
- **Where performed:** Supabase Dashboard → Authentication → Providers/Email and SMTP settings.
- **Exact setting, command, or migration:** Enable Email provider; require email confirmation according to product policy; set branded confirmation templates and rate limits; configure a verified SMTP sender.
- **Expected result:** Signup returns either a session or the documented confirmation state; confirmations arrive without leaking account existence.
- **How to verify:** Test new, existing, malformed, confirmed, and unconfirmed addresses; UI always shows generic safe errors/results.
- **What remains broken until completed:** Signup, confirmation, and recovery email may fail or be unsuitable for production.
- **Security warning:** Do not disable confirmation merely to make testing appear successful.

## Configure exact Auth redirects
- **Priority:** required
- **Action:** Allow only deployed/local origins and account callback paths.
- **Why required:** Google, confirmation, and password recovery depend on Supabase redirect allow-listing.
- **Where performed:** Supabase Dashboard → Authentication → URL Configuration; Google Cloud OAuth client settings where applicable.
- **Exact setting, command, or migration:** Add the real production origin and controlled preview/local origins for `/account/profile`, `/login`, and `/reset-password`; update Google authorized callback to the Supabase callback shown by the dashboard. Do not add wildcard attacker-controlled domains.
- **Expected result:** OAuth returns to the fixed same-origin intended account route; recovery opens `/reset-password` once.
- **How to verify:** Exercise Google from signed-out and anonymous sessions, email confirmation, reset email, malformed `next`, `//evil.test`, and external URLs.
- **What remains broken until completed:** OAuth/recovery can be rejected or return to the wrong page.
- **Security warning:** Broad preview wildcards can recreate open-redirect/token exposure risk.

## Publish a safe tag vocabulary and enable preferences
- **Priority:** required for preference editing; optional for the rest of account foundation
- **Action:** Create a versioned public allow-list of user-facing tags and server-side validation.
- **Why required:** Current tags include the pipeline marker `manifest` and empty/unreviewed data.
- **Where performed:** Repository data pipeline plus a new forward migration/RPC if database validation is used.
- **Exact setting, command, or migration:** Define stable keys/labels/classification; reject internal/unknown keys in an RPC or synchronized vocabulary table; then enable the settings service/UI.
- **Expected result:** Preferred/excluded mutations upsert one row and moving sides replaces the enum value.
- **How to verify:** Internal/unknown tags fail; two-user RLS succeeds; add/move/remove tests pass.
- **What remains broken until completed:** Preference editor remains visibly disabled.
- **Security warning:** Client validation alone is not an authorization or integrity boundary.

## Deploy and verify Cloudflare SPA fallback
- **Priority:** required
- **Action:** Deploy a preview using the existing Wrangler asset configuration and refresh each nested path.
- **Why required:** Local build confirms assets, not production routing.
- **Where performed:** Cloudflare preview/production deployment.
- **Exact setting, command, or migration:** `npm run build` then the repository's approved `wrangler deploy` workflow; retain `assets.not_found_handling = "single-page-application"`.
- **Expected result:** `/login`, `/reset-password`, and all `/account/*` routes serve `index.html` and render without CDN-cached private data.
- **How to verify:** Direct-load and hard-refresh every route; back/forward; inspect response and browser console; verify unknown account view.
- **What remains broken until completed:** Refresh compatibility is repository-complete but deployment-unverified.
- **Security warning:** Do not prerender user email/session data into shared HTML or edge cache.
