# User tag personalization v1

## Status (2026-07-30)

Repository implementation is complete for Settings, Search, and the landing Rotunda. Live Supabase migration and two-user browser verification remain pending because this checkout has no configured remote or project credentials. Ownership is always `auth.users.id`; Google and password users share the same table, RPCs, store, and UI.

## Implementation

* `src/data/tag-vocabulary.json` is the reviewed v1 chooser source. The corpus currently has only one defensible public content tag (`futanari`); editorial/pipeline values `manifest`, `favorite`, `iconic`, and `ns` are not exposed. `src/data/tags.json` remains the shared work/tag map.
* `src/personalization/data.js` performs one owner-scoped preference load and calls owner-derived RPCs. `store.js` follows the existing auth subscription and identity generation, clears sets synchronously on identity changes, ignores stale loads, exposes loading/ready/error and optimistic mutations with rollback. It stores no private data outside active memory.
* `catalog.js` provides exclusion, preferred counts, Search ranking, named weights (1.0 + 0.75 per match capped at a 2.0 bonus), and stable seeded unique Rotunda ordering with neutral candidates interleaved.
* `/account/settings` has allowed-option inputs, removable named chips, explanations, loading/empty/saving/success/error announcements, retry, and confirmed reset. Selecting a tag in the opposite list invokes the atomic move RPC.
* Search waits for preference readiness, finds all textual matches, excludes before the 12-result cap, uses preferred count as stable secondary ordering, and reruns an active query on store changes. Errors never fall back to unfiltered results.
* Rotunda applies global visibility first, then exclusions and stable weighting before `initialCard`, DOM cards, metadata, or thumbnail assignment. Preference/policy changes rebuild the candidates, retain the active slug where possible, abort stale rendering, and safely show an empty state/settings link.
* Bookmarks and direct Reader URLs are intentionally unchanged. Exclusion is discovery filtering, not authorization; bookmark rows remain visible/readable and are never deleted by preference operations.

## Database and privacy

`supabase/migrations/202607300002_complete_user_tag_preferences_v1.sql` adds the synchronized allowlist, fail-safe invalid-row detection, FK, owner/type index, timestamp trigger, and SECURITY INVOKER set/move/remove/reset RPCs. RPC ownership comes only from `auth.uid()`, with existing RLS retained. Apply after `202607300001_user_tag_preferences.sql`; review any invalid-row exception rather than deleting data. No service key, per-user static artifact, query-string preference, or localStorage mirror exists.

## Verification and limitations

Node unit/regression tests, production Vite build, and Python tag-generation tests pass locally. Static SQL inspection is not live RLS verification. Apply the migration to staging, run two durable users through persistence/account switching/bookmark exception flows, and inspect Network for excluded thumbnails and the single compact load. The v1 chooser is honestly small until reviewed corpus tagging expands. Multi-tab convergence beyond auth/session events is deferred.

## Next expansion

Reuse this same store and pure catalog functions for Blocks, landing rows/carousels, recommendations, related works, browse pages, random discovery, and recommendation explanations. Do not introduce a second tag interpretation or behavioral recommendation engine.

## Detailed implementation checklist

### Required vocabulary and schema
The v1 artifact and forward migration are implemented as described above.

### Exclusion pipeline
The pipeline is catalog → global policy → exclusion → preference → render; exclusion always wins in Search and `Rotunda.start`.

### Preferred weighting
Named 1.0/0.75/2.0 constants and stable neutral-preserving ordering are implemented.

### Settings UI
The validated chooser, chips, announcements, retry, rollback, and reset are enabled.

### Security, privacy
RLS and `auth.uid()` remain authoritative; no private static cache was added.

### Tests and rollout order
Local tests/build precede staging migration and the pending live two-user matrix.

**Exact next Codex task:** apply the forward migration in staging, perform the documented two-user and Network verification, then reuse the same subsystem for Blocks and other discovery surfaces.
