# Static release and catalog plan

## Recommended release tree

```text
/releases/<release-id>/catalog/index.json
/releases/<release-id>/catalog/shards/<prefix>.json
/releases/<release-id>/works/<encoded-slug>.json
/releases/<release-id>/search/index.json
/releases/<release-id>/rotunda/rotunda.json
/releases/<release-id>/annotations/<work>/<layer>.json
/current.json
```

Use content/release-qualified media paths (for example `/works/<slug>/<chapter>/r-<digest>/001.webp`) and never overwrite them. `release-id` is opaque/time+digest; schemas are independently numbered.

## Options

| Shape | Benefit | Cost / recommendation |
|---|---|---|
| one global catalog | simplest, good at hundreds | large repeat download; use compact route/search index now only if measured acceptable |
| shards | bounded discovery and updates | extra generation/routing; introduce as catalog grows into thousands |
| per-work manifest | one work payload, permanent identity | many artifacts; **primary** |
| generated page/work | real refreshable path/SEO/no rewrite dependency | build/artifact count; **primary at current scale** |
| shared shell | constant build size | rewrite/fallback dependence and no per-work static metadata | fallback at very large scale |
| hybrid generated + fallback | known works static, compatibility for newly published | two paths to test; preferred transition |
| compact route index | validates fallback/redirects | global payload; keep minimal |

At hundreds: generate every public route and manifest. At thousands: still generate routes, shard catalog/search. At millions: shared shell or batched/on-demand deployment may be necessary, while immutable per-work projections remain; do not add runtime R2 listing.

## Atomic publication and rollback

1. Generate/upload versioned media and manifests.
2. Validate hashes, page order, privacy, links and schemas.
3. Upload catalog indexes/shards/search.
4. Upload Rotunda/annotation snapshots.
5. Deploy Astro HTML/hashed assets bound to that release.
6. Switch `current.json` last with conditional write.

Retain old release/media beyond maximum shell/pointer staleness plus rollback window. Roll back by switching pointer (and HTML deployment if it embeds release ID), never mass purge. Compatibility aliases stay short-cache+SWR and redirect/point to immutable content. A work projection must list explicit irregular page filenames, otherwise validated padding/extension/pattern; clients never list R2.
