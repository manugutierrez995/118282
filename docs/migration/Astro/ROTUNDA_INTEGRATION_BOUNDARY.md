# Rotunda integration boundary

## Current Rotunda

**VERIFIED IN CODE/GENERATED DATA:** `src/data/rotunda.json` provides work pointers plus `public_rotunda` omissions; `tags.json` is joined and pure visibility helpers filter candidates. `Rotunda.start` owns active index, bounded card pool (max 20), center/adjacent coverflow classes, captions, pointer swipe threshold, hover/pause, arrow and keyboard behavior. Work metadata/thumbnail candidate URLs are loaded with concurrency four, LRU-like max-40 caches and AbortControllers. CSS owns perspective, scale, reflection/glow, mobile and reduced-motion presentation. Selecting a card dispatches `open-reader`. Preserve exact DOM/class/event contract.

## Future generator contract (not implemented)

`rotunda.py` is an external release-generation concern:

```json
{"schema_version":1,"release_id":"r...","seed":"editorial-...","generated_at":"...","policy":{"omit_works":[],"omit_tags":[]},"layout":{"hero":"slug","top_three":[],"landing_five":[],"rows":[]},"works":{"slug":{"weight":1,"center_probability":0.1,"top_three_probability":0.2,"landing_five_probability":0.4,"appearance_probability":0.8,"background_row_probability":0.5}},"locks":[],"collections":[],"promotions":[]}
```

The final schema must support omit work/tag, pinned works/tags, work/tag/collection weights, all requested placement probabilities, deterministic seeds, collections, time windows, manual layouts, locked regions, drafts, preview/published state, overrides and version history. It must contain only public slugs and resolved placement/order; Astro must not reproduce selection algorithms.

```text
canonical archive metadata -> rotunda.py policy/editorial computation
 -> validated immutable `/releases/<id>/rotunda/rotunda.json`
 -> Astro landing identity/mount -> existing client motion/cards/thumb loading
```

Probability generation and manual curation can coexist: locks/manual positions win under an explicitly versioned precedence rule; remaining slots use deterministic generation. Publishing validates visibility, referential integrity, duplicates, probabilities and release ID. Draft URLs remain private/no-store; published snapshots immutable. Astro only consumes final output and may embed a subset for first paint.
