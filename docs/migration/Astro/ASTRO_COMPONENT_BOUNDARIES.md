> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Astro component boundaries

| Layer | Owns | Must not own |
|---|---|---|
| Astro pages | `/`, generated `/work/[slug]/`, compatibility/404 | scroll/page state, editorial selection |
| Astro layout | head, global shell, stable mounts, hashed imports | per-page hydration islands |
| Astro components | static header/footer/reader root/block mounts | independent reader subtrees |
| build adapters | validate canonical formats, visibility, release projections/routes | mutate canonical JSON or fetch R2 at reader time |
| client TypeScript | one reader session; search, Rotunda, blocks/ghost landing modules | route generation/private data |
| retained CSS | all initial visual behavior/selectors | migration-time redesign |
| SVG annotation module | page overlay rendering/hit testing, lazy snapshot load | canonical annotations/editorial algorithms |
| ingestion | media validation/upload, item/details/work/storage outputs | Astro coupling |
| release scripts | projection/shard/Rotunda validation, atomic publish manifest | admin mutation UI |
| administration | deletor, audit, tags, auth/discussion tools | public bundle |

Hydration is limited to a single page-specific entry (landing or reader), not React-style islands. Astro components create markup; Vanilla TypeScript coordinates all reader state, cancellation, image lifecycle, hash/history, keyboard and future SVG. Keep Supabase discussion as a separable client mount with dynamic authenticated responses.
