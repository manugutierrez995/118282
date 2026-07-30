# Prompt for the next Codex run — Phase 1 only

Work in the `10-year` repository. Read all applicable `AGENTS.md` files and inspect the working tree before editing.

Implement **only Phase 1: stable work identity and public route-manifest audit/generation**. Begin with:

- `docs/url-structure-rework/README.md` (current facts and decisions)
- `docs/url-structure-rework/current-state-audit.md` (catalog evidence and 725/724 mismatch)
- `docs/url-structure-rework/work-url-and-reader-deep-links.md` (four identity layers)
- `docs/url-structure-rework/proposed-route-map.md` (ID+slug contract)
- `docs/url-structure-rework/implementation-phases.md` (Phase 1 acceptance)
- `docs/url-structure-rework/open-questions.md` (questions 1–2)

## Objective

Create a deterministic generator/validator for one canonical, public work identity/route manifest. For each resolvable work include:

- `work_id`, serialized consistently as an opaque string;
- persisted/current `public_slug` (lowercase ASCII kebab-case), separate from storage;
- exact `storage_slug` and `source`;
- bundled/remote work-manifest locator;
- exact chapter list and default chapter;
- public addressability/visibility derived from existing policy without leaking administrative tags/details;
- aliases only when a real persisted source supplies them.

Design the artifact so title-only changes do not silently regenerate an established public slug. Use a checked-in lock/baseline or another repository-native persisted mapping with documented update semantics. Duplicate public slugs may be allowed because routes include the unique ID, but enforce and document all other invariants.

## Required investigation

1. Machine-audit `src/data/fetch.json`, `rotunda.json`, `tags.json`, every `src/data/works/*.json`, both search indexes, relevant backups, and ingestion scripts.
2. Trace exactly how `parent_work_id` is allocated. Use history/fixtures and deterministic rerun tests to determine whether it survives re-ingestion/title/storage changes. If durability is not provable, do **not** call it canonical: produce a validation report and keep the artifact replaceable by a future registry.
3. Identify the exact 725th catalog entry lacking a checked-in work manifest and explain/handle it explicitly. Never invent its ID or silently omit it.
4. Reuse existing visibility normalization/policy where possible. Separate globally addressable state from Rotunda-only showcase eligibility if current data supports that distinction; do not expose raw omit lists/internal tags.
5. Choose one deploy source for the generated artifact. Do not create another unsynchronized `src`/`public` pair; document how Vite/runtime will consume it later.

## Slug contract to implement/test

Define deterministic Unicode normalization/transliteration, lowercase ASCII conversion, non-alphanumeric collapse, trim, maximum length, and `work-{id}` fallback. Test punctuation, non-Latin text, empty results, very long titles, duplicate titles, duplicate proposed slugs, and rename preservation. Use URL APIs in consumers/examples; never rename R2 directories or existing storage slugs.

## Constraints

- Do not change `src/router/router.js`, route behavior, UI links, Rotunda/Search events, reader behavior/CSS, account/auth code, or runtime data fetching.
- Do not create/apply Supabase migrations or inspect/mutate production/R2 over the network.
- Do not add a framework or speculative dependency.
- Do not edit hundreds of work manifests manually.
- Do not expose `details.json`, raw visibility configuration, or administrative/provenance tags.
- Preserve all existing tests/build and make two consecutive generator runs byte-identical.
- Update URL-rework documentation only with concrete Phase 1 outcomes/exceptions; do not rewrite later phases.

## Deliverables and tests

- repository-native generator/validator and clearly documented command;
- one canonical generated/locked identity artifact and schema/contract;
- focused tests for deterministic order/bytes, ID non-null/type/uniqueness, source+storage lookup uniqueness, slug normalization/persistence, duplicate/missing IDs/titles, unusual characters, catalog mismatch, chapter/default validity, and visibility redaction;
- a real-data validation report identifying every exception, especially the 725/724 mismatch;
- explicit conclusion: `parent_work_id` proven durable, rejected, or still unproven (with evidence).

Run focused Python/Node tests, the complete existing test suites, the generator twice with a clean diff check, and `npm run build`. Inspect the final diff. Commit on the current branch and create the required pull request. Do not claim later URL/account phases are implemented.
