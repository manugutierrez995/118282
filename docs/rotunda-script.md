# rotunda.py

> **Status:** Vision Proposal (Long-Term)

## Purpose

`rotunda.py` is the presentation engine for the archive.

The archive answers:

> *What exists?*

The Rotunda answers:

> *What deserves attention first?*

The archive remains immutable.

The Rotunda is a generated, editorial, cacheable presentation layer.

---

## Core Philosophy

The archive preserves knowledge.

The Rotunda curates discovery.

Nothing in `rotunda.py` should modify works or metadata. Its sole purpose is to generate static presentation artifacts.

---

## Static Outputs

Example outputs:

```text
rotunda.json
homepage.json
featured.json
collections.json
landing-layout.json
```

Visitors should never require a Worker to determine homepage layout.

---

## Presentation Profiles

Presentation should be driven by reusable profiles rather than dozens of independent flags.

```yaml
hero:
  center_weight: 1.00
  top_three_weight: 1.00
  landing_weight: 1.00
  background_weight: 0.50

classic:
  center_weight: 0.20
  top_three_weight: 0.50
  landing_weight: 0.90
  background_weight: 1.00

hidden:
  landing_weight: 0.00
```

Profiles may be applied to works, tags, artists, collections, series, publishers, or languages.

---

## Weighted Presentation

Every entity may influence where and how frequently it appears.

Possible regions include:

- Hero Center
- Top Three
- Landing Five
- Featured Shelf
- Background Rows
- Discovery Rotation

Weights express editorial preference rather than guarantees.

---

## Layered Generation

1. Locked editorial placements.
2. Required collections and tags.
3. Weighted featured works.
4. Discovery selection.
5. Background population.

---

## Deterministic Randomness

Randomness should be seeded so layouts remain reproducible while still changing over time.

---

## Editorial Curation

Automation creates the default.

Editors refine the experience.

Future capabilities:

- Drag-and-drop layout.
- Pin works.
- Pin collections.
- Lock regions.
- Create drafts.
- Preview changes.
- Publish static layouts.

Automation fills whatever the editor leaves open.

---

## Cache-First Design

The generated Rotunda should cooperate with:

- Browser Cache
- Cloudflare Edge Cache
- R2

R2 should become the durable source of truth rather than the first destination for every request.

---

## Long-Term Vision

Ultimately `rotunda.py` becomes the publishing system for the homepage, combining:

- Editorial judgment
- Presentation profiles
- Weighted probabilities
- Deterministic randomness
- Collections
- Promotions
- Personalization
- Static generation

without coupling presentation to the archive.

---

## Guiding Principle

The archive preserves knowledge.

The Rotunda curates attention.

One determines **what exists**.

The other determines **what people discover first**.
