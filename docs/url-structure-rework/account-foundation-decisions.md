# Account foundation decision log

Each decision uses the requested record format.

## Shared client and session ownership
**Decision:** Shared Supabase client location and session ownership.  
**Alternatives considered:** Keep discussion client; create per-view clients; global singleton modules.  
**Chosen approach:** `src/auth/supabase.js` owns the sole lazy client; `src/auth/session.js` owns the sole restoration and auth subscription.  
**Reason:** Prevent duplicate refresh/storage listeners and signed-out flashes.  
**Repository evidence:** Discussion previously owned `createClient` and called `getSession` lazily.  
**Compatibility impact:** `src/discussion/supabase.js` is now a facade preserving imports.  
**Privacy impact:** Identity changes synchronously invalidate account rendering.  
**Rollback:** Revert auth modules and facade.  
**Future consequence:** All private queries must consume this identity boundary.

## Router and direct-route deployment
**Decision:** Central pathname router and one popstate handler.  
**Alternatives considered:** Framework router; independent page listeners; server routes.  
**Chosen approach:** `src/router/router.js` with real anchors, push/replace state, strict known routes, and legacy query-reader recognition.  
**Reason:** Existing app is framework-free and Cloudflare declares SPA fallback.  
**Repository evidence:** Old `src/page/page.js` only parsed query parameters; `wrangler.jsonc` uses `single-page-application`.  
**Compatibility impact:** `/` and legacy reader queries remain; unknown account paths show not-found.  
**Privacy impact:** Guards are presentation only; RLS remains authorization.  
**Rollback:** Restore query dispatcher.  
**Future consequence:** Canonical work routes can be added centrally later.

## Google OAuth and anonymous upgrades
**Decision:** Preserve native Google OAuth and established anonymous `linkIdentity`.  
**Alternatives considered:** Always start new OAuth user; custom merge; provider-specific accounts.  
**Chosen approach:** Fixed same-origin redirect and Supabase `linkIdentity` only for an active anonymous user.  
**Reason:** It preserves the Auth UUID where Supabase already safely supports it.  
**Repository evidence:** Previous discussion auth already used this split.  
**Compatibility impact:** Existing Google comment/bookmark identities remain Supabase users.  
**Privacy impact:** No merge by email string.  
**Rollback:** Restore former discussion-local call.  
**Future consequence:** Email anonymous upgrade needs a verified reauthentication/link flow.

## Email/password and identity linking
**Decision:** Use current Supabase `signUp`, `signInWithPassword`, `resetPasswordForEmail`, and `updateUser`.  
**Alternatives considered:** Custom password storage/hashing; account table; email matching.  
**Chosen approach:** Supabase Auth only, canonical `auth.users.id`, generic recovery result.  
**Reason:** Avoid password custody and enumeration.  
**Repository evidence:** Installed `@supabase/supabase-js` 2.x.  
**Compatibility impact:** Provider UI changes do not alter private-table key contracts.  
**Privacy impact:** Passwords never enter repository storage.  
**Rollback:** Remove auth routes without schema changes.  
**Future consequence:** Dashboard email/SMTP/redirect configuration remains mandatory.

## Profile privacy and public discussion identity
**Decision:** Read private email/provider/account time from current Auth user; keep `profiles` as explicitly public discussion identity.  
**Alternatives considered:** Put email in `profiles`; change old profile policy; new private table.  
**Chosen approach:** No additional private profile row because no extra private field is needed.  
**Reason:** Existing public policy supports comment names and cannot safely hold private metadata.  
**Repository evidence:** `profiles_public_read` and `get_work_discussion` join in the discussion migration.  
**Compatibility impact:** Comment display remains unchanged; profile editing/avatar upload deferred.  
**Privacy impact:** Email/providers never enter public rows/static HTML.  
**Rollback:** Account view can be removed independently.  
**Future consequence:** New private fields require a separate owner-only table.

## Bookmark source and private caching
**Decision:** Query existing `bookmarks` under RLS, map IDs client-side to bundled public manifests, and keep results only in current DOM memory.  
**Alternatives considered:** Copy metadata into rows; localStorage cache; public joins.  
**Chosen approach:** Owner query plus catalog map and missing-work tombstones.  
**Reason:** Preserves current toggle/schema and prevents stale duplicated metadata.  
**Repository evidence:** Existing primary key `(user_id,work_id)` and owner select/delete policies.  
**Compatibility impact:** Existing work bookmark toggle remains work-level.  
**Privacy impact:** No private localStorage or static/cache content.  
**Rollback:** Remove listing service; existing toggles continue.  
**Future consequence:** Chapter/page bookmarks remain a later normalized evolution.

## Settings persistence, migration, RLS, and tag vocabulary
**Decision:** Create a forward owner-RLS preference migration but disable UI persistence until a reviewed vocabulary exists.  
**Alternatives considered:** Free text; expose `tags.json`; skip schema.  
**Chosen approach:** One `(user_id,tag_key)` row with preference enum and all owner policies; no editor writes yet.  
**Reason:** Current tags include internal `manifest`; free text cannot be validated meaningfully.  
**Repository evidence:** tag audit documentation and current catalog.  
**Compatibility impact:** Discovery is unchanged as required.  
**Privacy impact:** Schema is owner-only; no misleading/public preference storage.  
**Rollback:** Drop the new table/type only if migration was applied and no data is needed.  
**Future consequence:** Add vocabulary validation/RPC before enabling UI.

## Landing controls, reader controls, and mobile
**Decision:** Reuse one account navigation presenter at both surfaces; expose three direct authenticated links.  
**Alternatives considered:** Separate controls; ARIA menu; floating reader overlay.  
**Chosen approach:** Semantic icon anchors in landing header and reader nav right group. Bottom-reader duplicates are hidden narrowly while the top remains direct.  
**Reason:** All destinations stay one tap away and no menu semantics/focus trap is required.  
**Repository evidence:** Existing landing header and `buildReaderNavBar`.  
**Compatibility impact:** Home/chapter/Last/search behavior remains.  
**Privacy impact:** Controls display state only, not private values.  
**Rollback:** Remove the mounts and CSS.  
**Future consequence:** Measurement may justify a disclosure overflow later.
