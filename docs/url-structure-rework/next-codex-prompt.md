# Prompt for the next Codex run: Phase 1 only

Work in the `10-year` repository. Read and follow all applicable `AGENTS.md` files.

Implement **only Phase 1: stable work identity and public-slug audit/generation** from:

- `docs/url-structure-rework/README.md`
- `docs/url-structure-rework/current-state-audit.md`
- `docs/url-structure-rework/work-url-and-reader-deep-links.md`
- `docs/url-structure-rework/proposed-route-map.md`
- `docs/url-structure-rework/implementation-phases.md` (Phase 1)
- `docs/url-structure-rework/open-questions.md` (especially question 1)

## Objective

Create a deterministic generator and validator for a **public work identity/route manifest**. It must map the existing candidate stable `parent_work_id` to:

- `work_id` (serialized consistently, preferably string),
- persisted/current `public_slug`,
- exact `storage_slug`,
- storage `source`,
- bundled/remote manifest locator,
- chapter list and default chapter,
- public visibility state derived from the existing visibility policy without exposing hidden administrative metadata,
- optional aliases only if a real existing source supplies them (do not invent history).

The public slug is a URL-facing lowercase ASCII kebab-case value separate from the storage slug. Define/test deterministic normalization, maximum length, empty-result fallback, unusual Unicode/punctuation, and duplicate titles. Because the URL includes work ID, duplicate public slugs across different IDs may be valid; document the invariant you enforce. Do not silently regenerate previously persisted slugs on title-only changes: design a generated-source/lock mechanism or clearly stage the first baseline so later builds preserve it.

## Required investigation during implementation

1. Re-audit all `src/data/works/*.json`, `src/data/fetch.json`, `src/data/rotunda.json`, `src/data/tags.json`, and search index inputs.
2. Trace exactly how ingestion assigns `parent_work_id`; use repository backups/fixtures to test whether reruns preserve it. If durability cannot be proven, stop short of declaring IDs canonical: emit a clear validation/report and implement the artifact so a future persisted ID can replace the candidate.
3. Explain the current 725 catalog versus 724 work-manifest mismatch and handle/report it deterministically.
4. Reuse current visibility utilities/contracts where possible; do not create a conflicting hidden-work system.

## Constraints

- Do **not** change routing, rotunda/search click behavior, reader behavior, authentication UI, or CSS.
- Do **not** apply or create a Supabase migration.
- Do **not** add a framework or dependency.
- Do **not** fetch or mutate R2/production data.
- Do **not** edit hundreds of manifests manually; generate from canonical inputs.
- Do not expose raw `details.json` or administrative/internal tags in the public projection.
- Keep current build/tests passing and make output deterministic across two consecutive runs.
- Add focused automated tests for identity uniqueness/non-null/type, deterministic order/output, slug normalization, duplicate titles, unusual characters, missing/duplicate IDs, catalog mismatch, hidden visibility, and a renamed-title/preserved-slug fixture.

## Deliverables

- generator/validator code in the repository's existing scripting conventions;
- generated identity manifest at one clearly justified canonical deploy source (avoid another unsynchronized duplicate);
- schema/contract documentation near the artifact or in the URL rework docs;
- automated tests and exact commands;
- a validation report listing unresolved real-data exceptions, if any;
- update `docs/url-structure-rework/implementation-phases.md` only to record Phase 1 outcomes/decisions, not to erase later plans.

Before finishing, run the relevant Node/Python tests and `npm run build`, inspect `git diff`, commit the changes on the current branch, and create a pull request according to the repository instructions. Report whether `parent_work_id` was actually proven durable; do not overstate the result.
