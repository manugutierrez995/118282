> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Tag preferences and filtering

## Existing work-tag contract

`src/data/tags.json` is a versioned object keyed by the current storage/work slug. Each record contains an array of strings plus provenance (`sources`) and `updated_at`. `scripts/build_tags.py` merges tags from fetch, rotunda, per-work manifests, and ingestion. Per-work manifests sometimes contain the same `tags` field. Current values are not yet a clean consumer taxonomy: many arrays are empty and many contain `manifest`, apparently a pipeline marker. Global rotunda visibility separately uses `showcase_tags`, `omit_public_tags`, `omit_everyone_tags`, and explicit omitted work slugs in `src/data/rotunda.json`.

Before preferences ship, generate a public tag vocabulary with stable `tag_key`, display label, aliases, and classification (`content`, `format`, `provenance/internal`). Only user-facing content tags may be selected. Never offer `manifest` or internal visibility/provenance markers as preferences.

## Separate domains

Canonical work tags answer “what is this work?” and are generated/published with public metadata. User preferences answer “how should this user discover content?” and are private owner rows. Editing a preference must not mutate `src/data/tags.json`, work manifests, rotunda configuration, R2 details, or search records. Joining occurs by normalized tag key at read/ranking time.

Global visibility and safety policy runs first and cannot be overridden by a preferred tag. Personal exclusion/ranking runs afterward.

## Normalization

Recommended tag keys: Unicode NFKC input, trim, locale-independent lowercase/casefold, map canonical aliases, convert whitespace/underscore runs to `-`, collapse hyphens, and reject unknown/non-public vocabulary values. Display labels retain friendly casing/spaces separately. Server/database checks must not depend only on JavaScript normalization; use known vocabulary validation in an RPC or a synchronized constraint/table when practical.

Case variants (`Gore`, `gore`) and aliases resolve to one key. Do not use fuzzy matching when saving a setting. Slug normalization and tag normalization are different contracts.

## Preference model and conflicts

One row per `(user_id, tag_key)` with `preference_type in ('excluded','preferred')` makes overlap structurally impossible. Adding excluded uses an upsert that replaces preferred; adding preferred replaces excluded. The UI immediately moves the chip between lists, announces the change, and rolls back if persistence fails. Concurrent tabs converge on the last committed update timestamp; optionally subscribe/refetch on focus.

Initial `weight` is nullable. Product defaults interpret excluded as a hard negative and preferred as a simple positive. Future explicit weights may use `-100` for excluded and positive values for preference, but preference type remains understandable and editable. Exclusion always wins if malformed legacy data somehow contains both; repair it and log a diagnostic rather than showing contradictory UI.

## Stage 1: deterministic behavior

For each globally visible work:

```text
canonicalTags = public content tag keys for work
if canonicalTags intersects excluded: omit from discovery
else preferenceScore = count(canonicalTags intersects preferred)
```

Preserve deterministic base ordering among equal scores (editorial order, then stable work ID). Preferred tags raise prominence but do not hide neutral works. Apply the same shared selector to landing lists, rotunda candidates, `/works` browse/search, and suggestion modules. Search may optionally show an explicit “N results hidden by your settings” affordance with a temporary reveal; exclusions still take precedence. A directly entered public URL remains available because discovery preference is not access control.

For signed-out/auth-loading users, render the unpersonalized globally visible list. Do not briefly show excluded cards while a known signed-in user's preferences load: reserve/hold personalized surfaces or reuse only a device-safe in-memory snapshot associated with the current user and clear it on sign-out. The cacheable catalog itself remains unchanged.

## Stage 2: simple weighted ranking

After measurement, score preferred matches using explicit weights or a fixed default (for example 10 each), perhaps normalize for works with many tags, and retain exclusions as a pre-filter. Tie-break deterministically. Keep a UI explaining why an item ranked (“Matches romance, fantasy”) and let users edit/reset. Do not infer weights from reading activity in this stage.

## Stage 3: future recommendations

A separate, consent-aware system may use reading progress, bookmarks, likes/dislikes, dismissed works, and time-decayed interests. Store events/derived interests separately from explicit `user_tag_preferences`; never silently overwrite exclusions. Provide recommendation reset, data deletion, and explanation controls. Do not add invasive tracking in the URL/account foundation.

## Surface integration

- **Landing:** filter/rank any public work sections after loading preferences; header account state comes from shared auth.
- **Rotunda:** pass already-visible, personalized candidates into its existing windowing algorithm. Do not modify windowing or use hidden cards to fill slots. Preserve absolute active selection by stable work ID when the list changes; choose the nearest survivor.
- **Search/browse:** index public canonical tags; filter result entries through the same selector before the 12-result limit so hidden hits do not consume slots.
- **Suggestions:** share the selector/scorer, not a separate preference interpretation.
- **Reader:** settings link edits preferences but current direct work remains open. Warn only according to explicit product policy; never mutate work tags.

## Data/cache boundaries

Public tag vocabulary and work-to-tag projections can be versioned and CDN-cached. Owner preferences come from Supabase and must be private/no-store. Filtering can be computed in browser from these two inputs. Never publish a personalized catalog at a shared URL or use a shared edge cache without a verified per-user private key and `private, no-store` semantics; browser computation is safer initially.

## Tests

- normalization/case/alias and unknown/internal-tag rejection;
- add/remove preferred and excluded;
- changing side removes/replaces the opposite row atomically;
- injected conflicting legacy data gives exclusion priority and repair signal;
- excluded works disappear from landing, rotunda, search, browse, and suggestions;
- preferred works rank higher without removing neutral works;
- global hidden works stay hidden even if preferred;
- direct public link behavior is independent of discovery exclusion;
- signed-out/auth-loading behavior and no excluded-content flash;
- cross-user RLS and sign-out cache clearing;
- deterministic tie order and rotunda focus/active-card preservation.
