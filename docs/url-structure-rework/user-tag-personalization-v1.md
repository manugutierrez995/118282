# User tag personalization v1 implementation report

## Starting state

Work started at `c1bee635451c3f4c73871e9f262e0a61b8517b51` (the available PR #11 merge). This checkout had no Git remote or `main` ref, so it was impossible to fetch or fast-forward; a local `main` was recorded at that SHA before creating the requested branch.

## Product rules and data flow

The shared catalog is processed as: public data → global visibility → current UUID's exclusions → preferred weighting → render. Exclusion always wins. Preferred signals never add a textual nonmatch. Personal filtering never authorizes Reader access and never changes Bookmarks.

The reviewed `src/data/tag-vocabulary.json` is the chooser source and the migration seed mirrors it. The existing tag map joins Search through its verified `entry.work` field and Rotunda through `work.slug`. No manifest scan, R2 fetch, per-work preference query, or per-user artifact was added.

## Files and behavior

`src/personalization/data.js`, `store.js`, and `catalog.js` separate Supabase calls, auth lifecycle/state, and pure selection. Identity changes clear old sets immediately; generation checks discard old loads. Settings mutations update memory immediately and rollback on error. Search blocks authenticated output until readiness, excludes before 12, and recalculates. Rotunda prepares candidates before cards/images, preserves a surviving active slug, and aborts stale requests. Settings subscriptions and listeners are route-cleaned. Bookmarks and Reader remain deliberately unchanged.

## Schema, security, and privacy

Migration `202607300002_complete_user_tag_preferences_v1.sql` adds a public allowlist, validates existing data without silent deletion, adds FK/index/timestamp trigger, and exposes SECURITY INVOKER RPCs that derive ownership exclusively from `auth.uid()`. Existing owner RLS/cascade remain the boundary. Private values exist only in Supabase and active-user memory.

## Tests and build

`npm test`, `npm run build`, and `python -m unittest tests/test_build_tags.py` pass. Added real pure-function tests cover normalization, vocabulary rejection, exclusion/cap ordering, secondary ranking, exact weights, stable ordering, uniqueness, and neutral retention. Existing account, bookmark, reader-adjacent, Rotunda bounds, discussion, Blocks, and visibility tests remain green.

## Live verification and manual actions

Live verification is **pending**, not claimed: no project credentials or remote are present. Apply the new migration after reviewing any fail-safe invalid-row error; then test two users (including provider variety), persistence, A→B→A isolation, settings moves/reset, Search, Rotunda, bookmark/read exception, and Network requests. Push/open a draft PR once a Git remote is supplied.

## Incomplete requirements register

| Requirement | Requested | Actual/status | Reason/evidence | Risk | Exact next step / verification |
|---|---|---|---|---|---|
| Live migration/RLS | Apply and verify two owners | Pending external access; migration checked in | No Supabase credentials | Claiming static SQL as live would hide deployment failure | Apply staging migration; execute cross-owner select/mutate tests |
| Live two-user/UI/network | A→B→A and excluded-image audit | Pending external access | No configured project/browser users | Privacy or request regression could escape | Run scripted manual matrix and inspect Network |
| Public taxonomy breadth | Useful reviewed chooser | Architecture complete; one active tag | Corpus only has `favorite`, `futanari`, `iconic`, `manifest`, `ns`; only `futanari` is defensible | Exposing internal labels would mislead users | Review/add corpus tags, synchronize artifact and migration |
| Multi-tab convergence | Minimum convergence | Deferred/documented | No large synchronization framework requested | Another open tab can remain stale until auth/reload | Add small focus refetch with tests |
| Screenshot | Capture perceptible Settings change | Pending environment browser tooling | No browser/screenshot integration available | Visual issues need manual review | Capture desktop/mobile Settings screenshots in PR environment |

## Rollback

Revert application commit first. If database rollback is required, revoke/drop the three RPCs and trigger/index/FK/allowlist only after checking usage; do not drop or rewrite the historical preference table or delete preference rows.

## Next phase

Reuse the same store and catalog selectors for Blocks, landing rows and carousels, recommendations, related works, browse pages, random discovery, and recommendation explanations.
