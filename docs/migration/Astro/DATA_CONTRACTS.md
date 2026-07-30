> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Data contracts

> **Existing canonical data contracts remain unchanged during the Astro migration.**

**VERIFIED IN GENERATED DATA:** the following families were sampled; adapters must tolerate optional/legacy fields rather than mutate inputs.

| Pattern / example | Producer → consumer | Fields / classification | Status, scale/version | Adapter and cache |
|---|---|---|---|---|
| `src/data/fetch.json` | ingest/split → work loader | v2, default, works `{slug,display,source,manifest,thumb}`; public projection input | committed/generated; ~725 pointers observed in prior audit; unversioned URL | validate/read build-time; release index immutable |
| `src/data/works/<slug>.json` | ingestion → `loadWork` | v1, slug/display/source/thumb/ordered chapters; optional details/archive/tags/parent ID | committed/generated; ~724 observed; filenames identity-sensitive | typed adapter; versioned per-work projection |
| CDN `<chapter>/item.json` | ingestion → reader | pages,padding,extension; optional base_url | remote generated; overwritten/unversioned today | copy knowledge into release manifest; compatibility short-cache |
| CDN `<chapter>/details.json` | ingestion/admin → not current reader | descriptive/source metadata varies | public-sensitive; remote | project allowed fields only; do not add runtime fetch |
| `src/data/rotunda.json` | ingestion/hide tool → Rotunda/policy | v2/default/public_rotunda/works; omit arrays | committed generated/editorial | future generator emits versioned static contract |
| `src/data/tags.json` | build_tags/ingest/admin → visibility/search | v1 `works[slug]` tags/sources/updated_at | administrative/canonical; committed | never wholesale publish; public projection only |
| nested work `tags.json` conventions | deletor/admin | public/private layers | private/admin possible | exclude private; `private,no-store` if served authenticated |
| `public/data/search.index.json`, `src/data/search.index.json` | search generator → Search | v2 metadata, entries/tokens/prefixes/compact/skipped; entry reader/manifest URLs | generated, ~MB, duplicate copies | one versioned release index/shards; compatibility alias |
| `scripts/storage-map.json/.jsonl/.csv` | ingestion → operators/generation | storage URLs, object/byte/archive facts | generated admin inventory, 377 works sampled | private build input; enables no-list release builds |
| `scripts/r2-audit-output/{manifest,search}.index.jsonl` | auditor → admin/search tools | line-delimited discovered records | generated admin; may expose storage facts | never direct public output; adapter/redaction |
| `src/data/storage.json` | operator → `Storage` | active profiles/source roots | committed config; environment endpoints | build/client adapter; no credentials |
| `src/data/blocks.json` | editor → Blocks | defaults and placement arrays with html/image/embed/iframe flags | committed public config | build/import or versioned public data |
| `public/data/side_column_images_cycle.json` | editor → embedded blocks | image cycle data | generated/static public | load once/shared promise; version/long-cache when immutable |
| `public/header-ticker.json`, `src/data/text_behind.json` | editor → landing/ghost | row/item/speed and phrase content | static public | build embed or versioned static |
| discussion rows/export contracts + SQL | Supabase/admin → discussion | accounts/comments; permissioned | private/dynamic | not release data; auth/no-store |
| future annotation snapshots | future generator → SVG overlay | schema/layer/revision, stable annotation ID, work/chapter/page, normalized geometry, provenance/visibility | new **generated projection**, not canonical rewrite | `/releases/<id>/annotations/...`; immutable public layer |
| future `current.json` | release publisher → HTML/client | release_id, base URL, schema compatibility, published_at | tiny mutable pointer | 60s browser/300s edge + ETag |

## Irregular filenames and knowledge

Current reader assumes a numeric padded pattern. **RECOMMENDATION:** ingestion/release validation records `page_pattern` only if proven; otherwise output explicit ordered filenames. Also project page/thumbnail dimensions, chapter order, content revision, and annotation location. This eliminates `item.json` discovery without changing it. Canonical administrative data, generated public projections, immutable release manifests, and browser indexes must be distinct output classes.
