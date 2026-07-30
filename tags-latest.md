# Tag personalization: next implementation handoff

## Status, decisions, and scope

As of 2026-07-30, personalization is **not implemented**. Account settings intentionally render disabled controls in `src/account/views.js`. The existing `user_tag_preferences` migration is an owner-isolated foundation, not proof that the migration is live. The next leap is a reviewed, versioned public vocabulary plus a generated work/tag index, validated preference writes, and a preference-aware catalog pipeline that finishes before any personalized surface renders.

Decided: `auth.users.id` is the sole owner; exclusion always wins; preferences weight rather than filter; private lists never enter static HTML, public JSON, analytics, shared/CDN caches, or unkeyed local storage; direct work URLs remain accessible because personalization is not authorization. No provider/email ownership keys or account merging.

Still undecided and requiring product review: the public sensitive/adult taxonomy labels; tuning constants after measurement; whether hidden bookmarked works need a dedicated settings panel in the first release. Recommended bookmark rule: hide them from ordinary discovery, never delete the bookmark, and expose them in a settings-only “excluded bookmarks” manager.

## Current repository audit

* `src/data/tags.json` is the canonical-looking version-1 work map used by `src/utils/tag.js`, but contains raw/unreviewed and empty tag arrays. `src/data/fetch.json` and individual `src/data/works/*.json` also contain tags; `scripts/build_tags.py` merges local/R2 data. These are inputs, not a safe user vocabulary.
* `src/components/rotunda.js`, `Rotunda.start()`, currently reads `rotunda.works`, awaits `visibilityPolicyStore.refresh()`, and calls `filterRotundaCandidates(rawWorks, policy, tagCatalog)` before creating cards. This is the exact personalization insertion boundary.
* `src/page/landing.js`, `Landing.start()`, launches Search, Rotunda, Blocks, and ticker concurrently. `src/components/search.js` and `src/components/blocks.js` independently render public candidates, so a shared readiness service is needed to prevent excluded-work flashes.
* `supabase/migrations/202607300001_user_tag_preferences.sql` has `(user_id, tag_key)` primary key, an enum enforcing one state per tag, cascade deletion, timestamps, and owner SELECT/INSERT/UPDATE/DELETE RLS. It supports upsert/move via conflict update and delete. It lacks vocabulary validation, an `updated_at` trigger, an explicit weight constraint/decision, and proof of live application. The PK is sufficient; an additional `(user_id, preference_type)` index is useful once lists grow.
* Bookmark ownership is the single `public.bookmarks` table from `202607170001_discussion_mvp.sql`, keyed by `(user_id, work_id)` with `auth.uid()` owner RLS. Static SQL is not live RLS verification.

## Required vocabulary and schema

Add a migration after `202607300001` creating `public.public_tag_vocabulary(tag_key text primary key, label text, aliases text[], category text, sensitivity text, status text, replacement_key text, vocabulary_version integer, user_selectable boolean)`. Stable keys must be lowercase ASCII kebab-case; trim/case-fold aliases at ingestion; reject empty/unknown/internal-only/deprecated keys. Merged/deprecated keys point to replacements. Sensitive classifications require reviewed labels and explicit `user_selectable`; internal manifest markers never become options.

Enforce integrity server-side with a SECURITY INVOKER RPC (or FK if vocabulary is database-authoritative) that verifies `user_selectable`, locks one user/tag row, and atomically upserts/moves/removes. It must derive `user_id` from `auth.uid()`, never accept another owner, update `updated_at`, and return the resulting two lists. Add `(user_id, preference_type)` index and a trigger for timestamps. Decide whether to remove unused `weight`; recommendation: omit per-user weight in v1 and tune globally. Verify migration ordering and record `supabase migration list` output; do not claim live status from files.

The UI reads vocabulary from a public versioned artifact generated from the same reviewed source as the database seed. A CI check must compare artifact hash/version, database seed migration, and mappings so they cannot drift.

## Public work-to-tag index and performance

Make a reviewed source file (for example `catalog/tag-vocabulary.v2.json`) authoritative. Extend `scripts/build_tags.py` to normalize aliases, strip internal/unknown tags, emit `public/data/work-tags.v2.json` containing only `{version, vocabularyHash, works:{slug:[keys]}}`, and fail on empty keys, stale replacements, duplicate aliases, or unknown public mappings. Include source input hashes/build timestamp for staleness detection. Do not repeatedly scan work manifests in the browser.

Load catalog and this compact index once; represent each tag as an integer/bitset or cached `Set` for thousands of works. A user-keyed in-memory personalization snapshot may contain `{userId,generation,preferred,excluded}` and must be destroyed on identity change. Filter before constructing DOM nodes or assigning thumbnail URLs. Mobile and desktop consume the same eligible/weighted candidate service.

## Exclusion pipeline for every surface

Create `src/personalization/store.js` to wait for auth restoration, fetch rows for exactly the current UUID, generation-check late results, and publish `loading|ready|error`. Create `src/personalization/catalog.js` pure functions for canonical matching, hard exclusion, and scoring. Signed-out/no-preference users immediately use the public catalog; authenticated users hold a neutral skeleton until preferences resolve, preventing flashes.

Apply hard exclusion before rendering/image preload to landing displays, `Rotunda.start`, Blocks rows/carousels, browse/discovery, default search results, recommendations, random selections, future related works, and virtualized/preloaded collections. Search should offer an explicit temporary “include hidden” action, default off, without changing saved settings. If exclusions remove everything, render an honest empty state with a settings link; never silently ignore exclusions. Direct legacy reader URLs remain accessible.

## Preferred weighting and rotunda algorithm

For eligible work `w`, recommend `weight(w) = 1 + min(2.0, 0.75 * distinctPreferredMatches(w))`. Examples: 0 matches → 1.00; 1 → 1.75; 2 → 2.50; 3+ → 3.00. Exclusion yields 0 regardless of matches. Constants are named/configured and tuned with offline distribution tests—not unexplained magic values.

Select with session-seeded weighted sampling without replacement (Efraimidis–Spirakis keys are suitable), then apply: no duplicate slug; cap consecutive same-category works; multiply recently shown items by 0.2 for the session; preserve at least 30% baseline/nonmatching candidates when available. A session seed makes rerenders stable while retaining randomness between sessions. Cold start uses weight 1. Few preferred matches fill from baseline. Near-total exclusions respect exclusions and show a smaller/empty selection. Track recent slugs only in user-keyed memory and clear on identity change.

Exact order in `Rotunda.start`: load public rotunda + normalized index; await auth and preference snapshot; call shared hard filter; calculate weights; diversity/repeat suppression; weighted sample without replacement; only then call `initialCard` and render/load thumbnails. Smallest safe refactor: extract candidate preparation ahead of current cache/DOM setup, leaving gestures, reader URLs, metadata cache, and virtualization unchanged.

## Settings UI

Implement an ARIA searchable combobox backed only by selectable vocabulary options, plus removable chips in Preferred and Excluded fieldsets. This scales better than a long categorized chooser while categories can group results. Keyboard support: labelled input/listbox, arrows, Enter, Escape, announced counts/status, chip remove buttons, and visible focus; use the same responsive control on mobile.

Selecting a tag already in the other list invokes the atomic move RPC after confirmation/clear explanation. Prevent duplicates client-side and server-side. Use optimistic chips with per-operation “Saving”, success announcement, rollback/retry on network failure, and authoritative reload after ambiguous errors. Include empty/error/no-catalog-match states, explanations (“excluded hides discovery; preferred increases frequency”), and Reset personalization with confirmation. Never accept arbitrary free text.

## Security, privacy, and cache rules

RLS remains authorization. Browser code uses publishable/anon key only; service role never ships. Emails remain Auth-only, not public profile fields. Public tag indexes contain no preferences. Never log tokens, private lists, or personalized HTML into shared static/CDN caches. Provider is not ownership. Every request/result carries user UUID plus identity generation; User A responses are discarded after User B becomes active.

## Tests and rollout order for the next Codex run

1. Review/version vocabulary; add normalization and artifact/schema drift tests.
2. Add schema/RPC migration, timestamp trigger/index, local Supabase RLS tests for two users, invalid/internal tag rejection, atomic move/remove/reset, and cascade deletion. Apply staging migration and verify live separately.
3. Build the compact index and CI freshness checks; benchmark hundreds/thousands of works.
4. Add the identity-generation-aware preference store; test A→B and late A response isolation, signed-out/cold-start/error states.
5. Add pure exclusion/scoring/seeded-sampling tests: exclusion-wins, examples above, diversity, duplicates, recent suppression, few/zero matches.
6. Wire Rotunda at `Rotunda.start`, then Blocks and Search, ensuring no excluded image request occurs. Preserve direct/legacy reader URLs.
7. Enable the combobox/chips settings UI through validated RPC only; test keyboard, screen reader states, mobile, moves, rollback, reset.
8. Browser-test two accounts in both orders; inspect network requests for excluded thumbnails and caches; measure selection distributions and tune named weights.

**Exact next Codex task:** implement and review vocabulary v2, its database validation/RPC migration and generated work-tag index, then add the generation-safe preference store and wire hard exclusion plus the documented weighted sampling into `Rotunda.start` before any card/image creation; enable validated settings controls only after those boundaries pass two-user RLS and stale-response tests.
