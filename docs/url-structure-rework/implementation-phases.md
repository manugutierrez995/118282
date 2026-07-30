# Safe implementation phases and test plan

## Rules for every phase

Ship one reversible contract at a time; keep legacy reader/event behavior until its replacement passes parity tests. Do not combine route, auth, SQL, and reader changes in one patch. Each phase records generated artifacts/schema versions, runs existing tests plus focused tests, builds production assets, and verifies the rotunda/reader manually at responsive widths. Database changes require a separate reviewed migration and live-state inventory.

## Phase 1 — stable work identity and slug audit

- **Goal:** generate/validate one public identity manifest mapping candidate stable ID, persisted public slug, exact storage slug/source, manifest locator, chapters/default, and safe visibility; explain the 725/724 mismatch and prove or reject `parent_work_id` durability.
- **Likely files:** new generator under `scripts/`, tests, one canonical generated public data file, ingestion/contract docs; read `src/data/{fetch,rotunda,tags}.json`, `src/data/works/*.json`.
- **Dependencies:** none; product answer only if ID provenance cannot be proven.
- **Risks:** blessing unstable IDs, title-driven slug churn, leaking hidden metadata, creating another drifting artifact.
- **Tests:** deterministic consecutive output, uniqueness/non-null/type, mismatch report, duplicate titles, unusual Unicode/punctuation/empty titles, renamed-title persisted slug, missing/duplicate IDs, visibility, exact storage round-trip.
- **Rollback:** remove generator/artifact; runtime has not consumed it.
- **Done:** CI fails on identity contract violations; all exceptions are explicit; ID durability conclusion is documented without UI changes.

## Phase 2 — canonical work URL resolver

- **Goal:** pure parser/builders resolve ID/slug and legacy storage references; add public work-detail route/not-found without changing reader internals.
- **Likely files:** `src/router/router.js` (or focused router modules), `src/page/page.js`, new work view, route-manifest loader, tests.
- **Dependencies:** Phase 1.
- **Risks:** route parser conflicts with query reader; stale slug loops; hidden-work leakage.
- **Tests:** direct/refresh work route, duplicate title, unusual encoding/case, stale/renamed slug, missing/malformed/hidden work, canonical metadata state.
- **Rollback:** keep manifest but remove new route cases; legacy home/reader remains.
- **Done:** every manifest work resolves by ID; incorrect slug canonicalizes once; missing does not show home.

## Phase 3 — reader deep linking

- **Goal:** `/read`, chapter/mode parsing, stable page anchors, validated initial positioning, and controlled history.
- **Likely files:** `src/page/reader.js`, router/builders, reader styles/tests, virtualization checklist.
- **Dependencies:** Phases 1–2.
- **Risks:** page-1 flash, scroll feedback loops, unloaded target image, iOS anchoring, breaking existing continuous reader.
- **Tests:** page 1/middle/final, 0/negative/junk/beyond-end, refresh/new tab/copy, back/forward/hashchange, multi-chapter, continuous mode, virtual window centered near target, mobile and fallback observer.
- **Rollback:** canonical reader can temporarily ignore page and legacy query remains; remove anchor/history writer.
- **Done:** canonical link reproducibly opens correct work/chapter/page without crash or avoidable first-page jump; bounded image count remains.

## Phase 4 — shared route configuration and navigation migration

- **Goal:** make rotunda, search, work cards, chapter controls, and account links consume central URL builders; retire in-memory opens only after parity.
- **Likely files:** `src/components/{rotunda,search}.js`, `src/page/reader.js`, `src/account/*`, router, search generator.
- **Dependencies:** Phases 2–3.
- **Risks:** rotunda state/render regressions, duplicate listeners, stale search URLs.
- **Tests:** canonical hrefs with JS on/off semantics, click/modifier/new-tab behavior, chapter history, rotunda keyboard/swipe/window limits, search links, legacy event adapter.
- **Rollback:** restore event dispatch adapter and old search reader URLs.
- **Done:** user-visible opens assign a canonical URL and browser history; no competing route systems.

## Phase 5 — authentication/session guard cleanup

- **Goal:** inventory live Supabase; add one AuthStore/client with Google and email/password flows, callback, restoration, safe `next`, logout, and central guards.
- **Likely files:** package/env docs, new `src/auth/*`, router/page/auth views, tests; no table migration unless separately approved.
- **Dependencies:** shared routing; Supabase provider/redirect decisions.
- **Risks:** local-account semantic collision, OAuth redirect failure, account enumeration, stale-user data, unverified live schema.
- **Tests:** Google and email signup/login, confirmation/reset, restored/expired session, signed-out private routes, safe/hostile `next`, logout, user switching, auth-loading no-flash.
- **Rollback:** feature flag authenticated routes; `/profiles` and public reading remain.
- **Done:** both providers resolve to one UUID/session store; guards are centralized and public reader/rotunda are unaffected.

## Phase 6 — private account shell

- **Goal:** make `/account/*` authenticated, with one accessible shared account nav across landing/reader/account and explicit `/profiles` local boundary.
- **Likely files:** `src/account/navigation.js`, views/styles, landing/reader/page/router.
- **Dependencies:** Phase 5.
- **Risks:** inaccessible menus, reader-control overlap, accidental local-profile deletion.
- **Tests:** four auth states, desktop/mobile, keyboard/Escape/outside click, focus restoration, close on route/unmount, reader auto-hide interaction.
- **Rollback:** hide new account shell behind flag; keep login and local profiles.
- **Done:** Profile/Bookmarks/Settings/Sign out are consistent; private views never render before session resolution.

## Phase 7 — private profile page

- **Goal:** owner-only profile record and Auth metadata presentation; split public discussion identity.
- **Likely files:** reviewed Supabase migration, account data/view, AuthStore, RLS tests, discussion SQL/docs.
- **Dependencies:** live schema audit and Phase 6.
- **Risks:** current `profiles_public_read`, avatar abuse, comment display regression.
- **Tests:** Google/email metadata, create/update, two-user ownership isolation, public/anon denial, provider-linked user, XSS/length, comment regression.
- **Rollback:** revert UI; roll forward DB policy/schema safely rather than destructive down migration.
- **Done:** private account fields are owner-only at DB level; public discussion data is minimal and separate.

## Phase 8 — bookmark persistence

- **Goal:** remote work bookmarks first, schema ready for chapter/position; list joins stable ID to public metadata; local import preview.
- **Likely files:** migration/RLS, bookmark service/view/buttons, identity resolver, import tests.
- **Dependencies:** stable IDs, Auth/account shell.
- **Risks:** duplicate existing `bookmarks`, slug copies, optimistic state drift, hidden metadata leak.
- **Tests:** create/remove/clear, uniqueness, two-user isolation/direct forged writes, missing/hidden/excluded works, local idempotent import, canonical links.
- **Rollback:** disable writes/UI; retain rows for forward recovery.
- **Done:** no redundant work metadata; all ownership policies proven with real JWT roles.

## Phase 9 — settings and tag preferences

- **Goal:** remote normalized preferred/excluded rows with atomic polarity moves and accessible controls.
- **Likely files:** reconcile existing preference SQL, preference service/settings UI, normalization utilities/RLS tests.
- **Dependencies:** Auth/profile and vetted public tag vocabulary.
- **Risks:** migration already applied differently, normalization drift, conflicting states.
- **Tests:** add/remove/move both directions, conflicts, casing/Unicode/invalid input, two-user isolation, reset, canonical tags unchanged.
- **Rollback:** disable remote preference consumption while retaining rows; local settings still exportable.
- **Done:** one polarity per normalized tag, owner-only DB enforcement, weights remain optional/unused.

## Phase 10 — landing/browse filtering

- **Goal:** apply deterministic exclusions and stable preferred promotion to landing and `/works`.
- **Likely files:** shared personalization utility, landing/work list, session preference loader.
- **Dependencies:** Phase 9.
- **Risks:** loading flicker, empty result, prior-user memory leak.
- **Tests:** exclusion precedence, preferred ordering/ties, loading/signed-out/error, all-excluded empty state, cross-user cache clearing.
- **Rollback:** use neutral public ordering.
- **Done:** public eligibility first, private filtering second, identical pure contract across surfaces.

## Phase 11 — rotunda/search ranking

- **Goal:** adopt the same filtering/ranking without weakening global showcase or bounded virtualization.
- **Likely files:** `src/components/{rotunda,search}.js`, shared personalization, tests.
- **Dependencies:** Phase 10.
- **Risks:** index/window discontinuity, filtering after result limit, tag-source drift.
- **Tests:** Rotunda window/memory/keyboard/swipe, search filtering before limit, no-result states, preference changes, global hidden always excluded.
- **Rollback:** restore public candidate ordering while keeping account preferences.
- **Done:** landing/browse/search/rotunda give consistent deterministic outcomes.

## Phase 12 — reader account/navigation and progress integration

- **Goal:** finalize account icon/settings gear placement; optionally add consented progress only after deep-link semantics are stable.
- **Likely files:** reader chrome/styles, account nav, progress service and separately reviewed migration.
- **Dependencies:** Phases 3, 6, 8–9.
- **Risks:** mobile overlap, excessive writes/tracking, stale page events.
- **Tests:** mobile/desktop controls, focus/auto-hide, debounced updates, page/chapter/mode, ownership/offline/retry, progress distinct from bookmarks.
- **Rollback:** disable progress writes/gear panel; reading stays public.
- **Done:** controls do not interfere with reading; progress is opt-out/resettable and owner-only if shipped.

## Phase 13 — legacy URL redirects

- **Goal:** canonicalize root/`/reader` query inputs, stale slugs, page aliases, and trailing slashes; update generated search URLs.
- **Likely files:** router, search generator/artifacts, optional Cloudflare rules/edge code, docs.
- **Dependencies:** canonical UI traffic stable.
- **Risks:** redirect loops, dropped fragments/chapters, false matches.
- **Tests:** every legacy shape, unknown work/chapter, encoding, query allowlist, one-hop canonical result, old shared links.
- **Rollback:** retain parser but stop automatic replace/edge redirects.
- **Done:** old valid links resolve once; application emits only canonical links.

## Phase 14 — tests and deployment verification

- **Goal:** enforce full matrix in CI and actual targets; decide if edge/prebuilt rendering is required for true statuses/social previews.
- **Likely files:** browser/integration tests, workflow, Wrangler/deploy docs; GitHub config only if support approved.
- **Dependencies:** all shipped phases.
- **Risks:** SPA preview differs from Cloudflare; OAuth automation limitations; cache leaks.
- **Tests:** matrix below plus status/headers/cache inspection and accessibility/performance regression.
- **Rollback:** halt rollout/route traffic; static prior artifact remains deployable.
- **Done:** direct/refresh works in production-like Cloudflare, ownership/cache isolation proven, documented GitHub support status, rollback artifact retained.

## Cross-phase acceptance matrix

### Routes and deployment

- Directly navigate to and refresh `/`, auth routes, every account route, `/works`, real work detail, reader, and unknown routes.
- Test Cloudflare direct-route fallback with production build; confirm nested route is parsed, not home.
- Test trailing slash, case, percent encoding, base/asset paths, canonical query order, stale slug, legacy root and `/reader` URLs.
- GitHub Pages direct/refresh is tested only if support is configured; otherwise record an environment/support warning, not a pass.

### Authentication and ownership

- Google user and email/password user each reach identical private pages.
- Signed-out private access preserves safe destination; hostile external/protocol-relative `next` is rejected.
- Returning user restoration, auth loading, token refresh/expiry, logout, two-tab sign-out, and rapid user switching.
- User A cannot select/insert/update/delete user B profile, bookmarks, preferences, or progress via direct API; anon denied.

### Catalog/work

- Duplicate titles, duplicate proposed slugs, unusual Unicode/punctuation/very long/empty-normalized titles, renamed works, missing IDs/manifests, unknown works, globally hidden/private/deleted works, personally excluded works.
- Correct ID with old slug canonicalizes; stable work ID remains unchanged; public metadata contains only allowlisted fields.

### Bookmarks/preferences

- Work, chapter, and page bookmarks remain distinct; automatic last position is not treated as a bookmark.
- Add/remove/clear; unique conflicts; missing metadata; page/mode/label/notes validation; local anonymous import is previewed/idempotent.
- Add/remove preferred and excluded; move in both directions; simulated legacy conflict; exclusion priority; reset; tag normalization; canonical tags remain unchanged.

### Reader

- Open page 1, middle, final, 0, negative, decimal/junk, and beyond length; invalid values announce and clamp/fallback without crash.
- Multi-chapter/default/invalid chapter; continuous mode and unsupported/single mode fallback until implemented.
- Refresh, copy/open new tab, browser back/forward, explicit page action versus passive scrolling, hash alias/query migration.
- Verify no visible page-1 jump when practical, active virtual image window targets requested page, loaded images remain bounded, failed target retry, IntersectionObserver fallback, mobile responsive navigation and iOS-style anchoring.

### Cache/privacy/accessibility

- Warm public cache under user A, then signed-out/user B; inspect shell/HTML/JSON/headers for no A data.
- Supabase private calls are not cached by service/shared edge; clear memory on switch/logout; stale requests cannot repaint.
- Keyboard-only menus/routes/reader, screen-reader labels/status, focus after navigation/close, outside click/Escape/route close, touch targets, reduced motion, and no mobile control overlap.
