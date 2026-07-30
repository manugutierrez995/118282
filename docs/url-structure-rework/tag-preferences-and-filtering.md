# Tag preferences, filtering, and ranking

## Existing canonical work-tag contract

`src/data/tags.json` is `{version: 1, works: { [storageSlug]: {tags, sources, updated_at} }}`. `src/utils/tag.js` lowercases, trims, replaces whitespace with hyphens, deduplicates/sorts, joins by exact storage slug, and applies global rotunda policy. `scripts/build_tags.py` merges ingestion/manifest/manual sources. Many current tags are empty or `manifest`, so the corpus is not yet a vetted preference vocabulary.

Work tags are public catalog facts/provenance. User preferences are private rows (or current local-profile arrays). Changing a setting must never mutate `src/data/tags.json`, per-work manifests, R2 `tags.json`, search indexes, or global visibility policy.

## Current personalization

Local profiles contain `preferredTags` and `excludedTags`. `src/local-profile/personalization.js` filters any excluded match, stable-partitions entries with any preferred match first, and preserves source order otherwise. Rotunda first applies global visibility, then local personalization; search also personalizes. Current schema permits the same tag in both arrays, though exclusion wins because filtering happens first. Settings are comma-separated text.

## Target preference contract

One normalized `(user_id, tag_key)` row has exactly one `preference_type`: `excluded` or `preferred`, with nullable future `weight`. The primary key makes contradictory rows impossible. Adding excluded upserts excluded; adding preferred upserts preferred. Thus moving a tag is one atomic upsert (or delete+insert transaction), not two eventually consistent writes.

Normalization should be shared with canonical tag keys:

1. Unicode normalize (choose/document NFKC), trim, lowercase in a locale-independent way.
2. Collapse whitespace/separators to `-`; strip unsupported punctuation; collapse/trim hyphens.
3. Enforce 1–80 characters and an allowlisted key pattern.
4. Apply a future alias map (for example synonyms) before persistence; retain human label separately in the public tag vocabulary, not each preference row.
5. Do not offer provenance-only/internal tags such as `manifest` unless promoted to the public vocabulary.

The settings UI uses canonical suggestions and announces when an entry moves lists. Removing makes it neutral. Exclusions take priority in all stages and are understandable/editable.

## Stage 1 — deterministic filtering (initial)

Pipeline order for landing, `/works`, search, rotunda, and suggestion modules:

```text
publiclyEligible = applyGlobalPublicationAndSurfacePolicy(catalog)
visible = publiclyEligible minus works matching any excluded tag
ranked = stablePartition(visible, matchesAnyPreferredTagFirst)
```

Global hidden/private/deleted rules always run before personalization. Excluded works disappear from discovery, but a globally public direct URL and existing bookmark remain reachable; show a subtle “excluded by your settings” option only if product approves. Exclusions override preferences even during transient/local conflict. Neutral tags do nothing. Signed-out/no-profile users see public order.

Apply one pure shared function so Rotunda, landing/browse, search, and recommendations cannot drift. Preserve Rotunda's bounded DOM window and public showcase policy. Search should filter before result truncation. If preferences are still loading, show neutral public results and then intentionally re-rank without exposing another user's cached list.

## Stage 2 — simple weighted ranking

Keep explicit excluded as a hard filter. Default preferred may add a fixed score (for example +10); optional user `weight` later supports `romance: 25`, `fantasy: 10`, `gore: -100`. Negative hard-exclusion should remain represented by type, not inferred only from a magic weight. Score only among already eligible works; tie-break by deterministic public rank then stable ID. Explain ranking in settings and offer reset.

## Stage 3 — future recommendation system

Separate explicit preferences from inferred signals. Potential, opt-in inputs: reading history, bookmarks, explicit likes/dislikes, dismissals, time-decayed interests, and a recommendation reset. Store purpose-limited events/aggregates with retention controls; do not add invasive tracking during URL/account work. Explicit exclusions remain absolute and editable. Users must be able to inspect/reset recommendation inputs without losing bookmarks/account.

## Data/cache boundary

Canonical tag catalog is public and cacheable. Preference rows are private/no-store. Personalization should generally be computed client-side by combining cached public metadata with current user's private preferences. Never publish personalized HTML/search JSON into a shared Cloudflare key. In memory, key results by authenticated user generation and clear on sign-out/account switch.

## Required tests

- normalize casing, whitespace, Unicode/punctuation, duplicates, empty/oversized tags, and aliases;
- add/remove preferred; add/remove excluded; moving between lists leaves one polarity;
- exclusions win over preferred and global policy runs first;
- neutral order and ties are stable;
- filtering occurs before search/rotunda limits and remains consistent across surfaces;
- bookmarks remain available even when personally excluded;
- canonical work tags/files are byte-identical after preference operations;
- user A cannot read/write user B preferences under RLS;
- signed-out/loading/error states never reuse the prior user's personalized list.
