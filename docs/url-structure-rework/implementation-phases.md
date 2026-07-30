# Safe implementation phases

Each phase is independently reviewable and reversible. Do not apply database changes until the remote schema/config has been inventoried and the migration phase is explicitly approved.

## Phase 1 — stable work identity and slug audit

- **Goal:** Generate a deterministic, checked/validated route identity manifest mapping `parent_work_id` → public slug, storage slug, source, manifest, chapters/default chapter, visibility; report collisions/missing catalog files. Establish whether current IDs are durable.
- **Likely files:** ingestion/search utilities under `scripts/`, a new generator/validator, generated public data under `src/data` or `public/data`, fixtures and tests. Do not edit 724 files by hand.
- **Dependencies:** current fetch/rotunda/work manifests; editorial decision only if ID instability is found.
- **Risks:** treating an ingestion parent ID as immutable without proof; catalog mismatch; public projection leaking hidden metadata; slug churn.
- **Tests:** all manifests parse; ID uniqueness/non-null/type; storage/public slug uniqueness rules; duplicate titles; unusual Unicode/punctuation/empty normalized titles; deterministic output; hidden projection; renamed-title fixture preserves assigned slug; no R2 calls.
- **Rollback:** delete generated artifact/generator; current app does not consume it.
- **Done:** CI validator passes, identity contract/schema is documented, all exceptions are explicit, generated output diff is deterministic, and no UI behavior changes.

## Phase 2 — canonical work URL resolver

- **Goal:** Add pure route parser/resolver for `/works/{id}/{slug}` and `/read`, canonical correction, not-found/hidden resolution, and legacy query translation behind a feature flag.
- **Likely files:** `src/page/page.js`, new `src/routing/*`, identity manifest loader, visibility utilities, unit tests.
- **Dependencies:** Phase 1.
- **Risks:** decoding/path traversal, generic fallback 200, hidden disclosure, breaking home.
- **Tests:** every route direct parse; duplicate/unusual/renamed/missing/hidden works; wrong slug correction; legacy query; trailing/case/encoding; no manifest fetch before visibility.
- **Rollback:** disable path-routing flag; legacy query dispatcher remains.
- **Done:** pure resolver returns typed state/canonical URL and existing landing/reader tests pass; UI links not yet required.

## Phase 3 — reader deep linking

- **Goal:** Resolve `#page=N`, accept `#page-N`, initialize virtual image window/scroll at target, and synchronize active page/history.
- **Likely files:** `src/page/reader.js`, reader styles/status UI, routing/page parser tests, virtualization checklist.
- **Dependencies:** Phase 2 and manifest page count.
- **Risks:** initial page-1 flash, ratio scroll drift, history spam, observer feedback loops, mobile Safari restoration.
- **Tests:** page 1/middle/final/0/negative/beyond/malformed; refresh/new tab/copy; back/forward; continuous mode; bounded images around target; reduced motion; mobile; same-chapter navigation avoids refetch.
- **Rollback:** feature flag disables fragment sync; legacy reader starts at chapter beginning.
- **Done:** canonical deep links restore reliably with accessible clamp notice and no reader/rotunda regression.

## Phase 4 — shared route configuration and navigation

- **Goal:** Make rotunda/search/chapter actions emit real canonical links through one navigator; add `/works` and work detail shell without redesign.
- **Likely files:** rotunda/search/reader components, `src/page/*`, routing module, detail view/styles.
- **Dependencies:** Phases 1–3.
- **Risks:** breaking coverflow pointer behavior, losing new-tab/context menu, duplicated event route systems.
- **Tests:** click/keyboard/context/open-new-tab; back/forward; direct refresh; rotunda active/focus; search result; canonical metadata.
- **Rollback:** compatibility `open-reader` adapter translates old events; feature flag link emission.
- **Done:** normal navigation changes URL before/with view, native links work, one route system is authoritative.

## Phase 5 — authentication/session guard cleanup

- **Goal:** Extract singleton auth/session service, loading state, Google + email/password flows, validated `next`, OAuth callback handling, and client account guards.
- **Likely files:** refactor `src/discussion/supabase.js`, new auth/session modules, login/signup views, router, env docs/tests.
- **Dependencies:** Phase 4 routing; verified Supabase redirect/provider settings.
- **Risks:** duplicate clients/listeners, anonymous linking loss, open redirect, signed-out flash, discussion regression.
- **Tests:** Google and email/password; anonymous upgrade; restored session; OAuth callback; signed-out account redirect/next; logout; offline/error; URL injection.
- **Rollback:** keep discussion adapter using shared client; hide account routes behind flag.
- **Done:** one session source serves discussion/router/nav and both durable providers reach the same user UUID.

## Phase 6 — private account shell and navigation

- **Goal:** Add guarded `/account` routes, shared AccountMenu, landing icon, reader account icon/settings gear, responsive accessible shell.
- **Likely files:** landing/reader components and CSS, new account components/views, router.
- **Dependencies:** Phase 5.
- **Risks:** reader-control collision/autohide, duplicated auth logic, focus loss.
- **Tests:** loading/signed-in/signed-out; desktop/mobile/zoom; keyboard/screen-reader labels; outside click/Escape/route close; reader page controls unaffected.
- **Rollback:** feature flag account UI/routes; shared auth remains.
- **Done:** all surfaces use one component/session state and private routes never render before guard resolution.

## Phase 7 — private profile page and schema correction

- **Goal:** Deliver owner-only profile and separate existing public discussion identity from private profile semantics.
- **Likely files:** new reviewed Supabase migration, profile service/view, discussion compatibility code/tests.
- **Dependencies:** deployed schema audit, Phase 6, product decision on public discussion names.
- **Risks:** breaking comments, public data leak, migration applied out of order.
- **Tests:** own CRUD, A/B isolation via direct REST, public discussion display compatibility, provider metadata, deletion boundaries.
- **Rollback:** reversible view/table compatibility and prior policies; do not drop old structure until verified.
- **Done:** profile select/update is owner-only and discussion exposes only intentional public fields.

## Phase 8 — bookmark persistence and page

- **Goal:** Evolve/migrate work bookmarks and provide account listing; distinguish work/chapter/page bookmarks.
- **Likely files:** reviewed SQL migration, discussion bookmark service migration, reader/detail controls, account page/tests.
- **Dependencies:** stable IDs, Phases 6–7.
- **Risks:** anonymous rows, duplicates, stale work metadata, migration data loss.
- **Tests:** migration/dedup; add/remove all kinds; ownership isolation; deleted/missing work tombstone; canonical links; two tabs; no metadata copies.
- **Rollback:** compatibility view/dual read, retain old table until verification.
- **Done:** owner-only normalized records and page display work for both Google/email users.

## Phase 9 — settings and tag preferences

- **Goal:** Owner-only preferred/excluded settings with mutual exclusion and public vocabulary.
- **Likely files:** tag vocabulary generator, SQL migration, account settings UI/service/tests.
- **Dependencies:** taxonomy audit and Phase 6; stable IDs useful but not required.
- **Risks:** exposing internal tags, inconsistent normalization, race conflicts.
- **Tests:** add/remove/switch lists; aliases/case; conflict/concurrency; A/B isolation; RLS; canonical work tags unchanged.
- **Rollback:** hide preference UI/reads; table rows do not alter public catalog.
- **Done:** one row per user/tag, exclusion/preference conflict impossible, understandable UI.

## Phase 10 — landing-page filtering

- **Goal:** Apply shared deterministic selector: global policy → exclusions → preferred ranking.
- **Likely files:** landing/catalog selectors, search integration, tests.
- **Dependencies:** Phase 9 and public tag vocabulary.
- **Risks:** excluded-content flash, unstable order, empty results.
- **Tests:** excluded/preferred/neutral; global hidden priority; auth loading/sign-out; all search matches filtered before result cap; deterministic ties.
- **Rollback:** feature flag unpersonalized public ordering.
- **Done:** landing/browse/search use one tested selector without mutating/caching personalized catalog publicly.

## Phase 11 — rotunda filtering and ranking

- **Goal:** Feed personalized candidates into existing bounded rotunda while preserving interaction/performance.
- **Likely files:** `src/components/rotunda.js`, selector integration, window/performance tests.
- **Dependencies:** Phase 10.
- **Risks:** active-index drift, focus removal, too few cards, thumbnail churn.
- **Tests:** existing rotunda suite plus exclusion/rank updates, stable-ID focus preservation, mount/image bounds, mobile gestures/keyboard.
- **Rollback:** unpersonalized candidate list flag.
- **Done:** same windowing limits and visual behavior with correctly filtered/ranked inputs.

## Phase 12 — reader account/navigation and reading progress integration

- **Goal:** Finalize bookmark/current-position affordances; add automatic progress only if explicitly approved.
- **Likely files:** reader nav/observer, account service; optional progress migration/table.
- **Dependencies:** Phases 3, 6, 8; progress schema approval.
- **Risks:** excessive writes, observer/history loops, private cache leak.
- **Tests:** mobile controls; bookmark current page; throttled/idempotent progress; continue link; provider parity; reader works with Supabase offline.
- **Rollback:** disable writes/progress while URL tracking remains.
- **Done:** navigation does not interfere with reading and private failures do not block public media.

## Phase 13 — legacy redirects and canonical metadata

- **Goal:** Convert old query/slug forms, choose client versus generated/edge 301s, and publish canonical/share metadata.
- **Likely files:** router, generator, deployment config, metadata view.
- **Dependencies:** route adoption/analytics from Phases 2–4.
- **Risks:** redirect loops, broken encoded slugs, hidden leakage, crawler fallback 200.
- **Tests:** all known legacy forms, renamed aliases, fragments preserved, status/location on deployed target, social preview, missing/hidden.
- **Rollback:** client resolver remains; remove edge/generated redirects atomically.
- **Done:** emitted links are canonical and legacy traffic reaches correct work without loops.

## Phase 14 — tests and deployment verification

- **Goal:** Complete end-to-end/security/cache/accessibility matrix on every claimed host.
- **Likely files:** browser tests, deployment scripts/docs, cache assertions; minimal fixes only.
- **Dependencies:** prior shipped phases.
- **Risks:** treating local Vite fallback as Cloudflare/GitHub proof.
- **Tests:** direct/refresh every route; Google/email/restored/signed-out; profile/bookmark/preference A/B ownership; preference CRUD/conflicts; duplicate/unusual/renamed/missing/hidden works; all page edge cases; back/forward/new tab; mobile/continuous/virtualized behavior; Cloudflare fallback/status; GitHub only if supported; public/private cache isolation.
- **Rollback:** phase-specific flags/config release rollback; database migrations require rehearsed down/compatibility path.
- **Done:** evidence recorded for each matrix item, no private leakage, cache/reader/rotunda budgets retained, unsupported hosts explicitly labeled.

## Cross-phase acceptance test matrix

The responsible phases above must automate these where practical and record manual/deployed evidence where not:

- **Routes/deployment:** direct navigation and refresh for `/`, `/login`, `/signup`, `/works`, every account route, valid work detail, valid reader deep link, and error routes; Cloudflare direct-route behavior; asset paths/status/MIME; GitHub Pages direct-route behavior only if support is retained.
- **Authentication:** Google-authenticated and email/password users reach the identical account system; signed-out account access; intended-destination return; returning/restored sessions; anonymous upgrade; logout and user switching.
- **Authorization:** profile ownership isolation, bookmark ownership isolation, and preference ownership isolation using direct Supabase API attempts as users A and B—not UI hiding.
- **Preferences:** add/remove preferred tags; add/remove excluded tags; switching a conflicting tag in both directions; normalization/aliases; exclusions across landing, rotunda, search, browse, and suggestions.
- **Work identity:** duplicate titles, unusual/Unicode/punctuation titles, renamed works/old slugs, missing works, globally hidden works, and user-filtered-but-public direct links.
- **Reader position:** page 1, a middle page, final page, page 0, a negative page, malformed values, and a page beyond the chapter length; refresh; browser back/forward; copy/open in a new tab; exact chapter/mode retention.
- **Reader layouts:** mobile navigation and safe areas, desktop keyboard controls, continuous-scroll mode, bounded virtualized-image behavior at distant targets, and any future DOM-virtualized mode through the same `goToPage` adapter.
- **Cache/security:** a public work response stays identical/cacheable across users; private account/Supabase data is never in shared HTML/CDN/Cache Storage; switching A→B never flashes A's profile/bookmarks/preferences; public reading survives Supabase failure.
- **Regression/performance/accessibility:** current reader and rotunda suites, bounded loaded images/cards, reader controls do not collide with account controls, keyboard/focus/screen-reader announcements, reduced motion, and no duplicate session subscriptions.
