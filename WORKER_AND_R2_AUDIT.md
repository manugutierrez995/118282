# Worker and R2 audit

## Worker entry points and dependency map

There are no application Worker entry points or routes. `wrangler.jsonc` declares only a static asset directory and SPA fallback (`wrangler.jsonc:1-9`). It declares no `main`, R2 binding, KV/D1 binding, route, or Worker compatibility module. Repository-wide inspection found no `export default { fetch }`, `addEventListener("fetch")`, `caches.default`, or Pages Functions directory.

| Responsibility / route | Caller | R2? | Dynamic logic | Classification | Migration difficulty |
|---|---|---:|---|---|---|
| Static asset request, including `/` | Browser | No | Platform asset lookup | KEEP AS EXCEPTIONAL BACKEND FUNCTION (platform only) | none |
| SPA not-found fallback for `/reader` or `/work/*` | Browser | No | Platform returns shared shell | REPLACE WITH STATIC DATA / static routing | low |
| `/reader?source=&work=&chapter=` | No Worker handler; SPA shell parses query | Direct CDN GET follows | Browser only | REPLACE WITH permanent static work URL | medium |
| `/work/<slug>/` | No app handler; fallback returns shell | No | Browser currently ignores path | REPLACE WITH STATIC DATA | low–medium |
| Search, rotunda, work manifests | Static Vite/public assets | No | Browser filtering/resolution | KEEP; harden cache/privacy | low |
| Chapter `item.json`, thumbnails, pages | Browser -> CDN/R2 custom domain | Object GET | CDN/origin lookup only | KEEP as unavoidable media/metadata origin; make metadata generated and cached | low |
| Discussion API | Browser -> Supabase, not Worker | No | authenticated database logic | KEEP AS EXCEPTIONAL BACKEND FUNCTION | none for reader migration |

The claimed “Worker-dependent architecture” is not supported by this checkout. Before deleting external infrastructure, confirm Cloudflare Analytics by hostname/route and export dashboard Worker routes/rules. Treat unknown dashboard transforms, cache rules, Access policies, and the origin behind `cdn.564578634.xyz` as **UNCERTAIN**.

## Frontend request inventory

* Ticker: `/header-ticker.json` (`src/page/landing.js:4-13`).
* Search index: `/data/search.index.json`, forced `no-store`, promise-deduplicated per page lifetime (`src/components/search.js:3-18`).
* Blocks: static paths from bundled blocks configuration (`src/components/blocks.js:19-31`). Four side blocks separately fetch the same image-cycle JSON with `no-store`, creating up to four duplicate transfers/revalidations (`public/blocks/top_left_meme.html:48`, `public/blocks/top_right_meme.html:48`, `public/blocks/penultimate_left_meme.html:48`, `public/blocks/penultimate_right_meme.html:48`).
* Rotunda work manifests and thumbnail URLs: bounded/windowed, with aborts and in-memory maps (`src/components/rotunda.js:360-435`).
* Chapter metadata: `item.json` on each reader render (`src/page/reader.js:373-408`).
* Work manifest: static asset, promise cached up to 40 entries (`src/storage/work_manifest.js:23-73`).
* Pages: direct computed CDN URLs, up to a 21-image retained window (`src/page/reader.js:180-251`).
* Ghost text: one static JSON request (`src/effects/ghost_text.js:43-56`).
* Discussion: Supabase requests are outside R2 and must remain dynamic (`src/discussion/service.js`).

`src/fetch/fetch.js` contains an older catalog loader capable of fetching `/src/data/fetch.json` and CDN chapter manifests (`src/fetch/fetch.js:6-69`), but no current import of its `Fetch` class was found. Classify it **REMOVE** after an import/deployment check.

## R2 operations

### Unavoidable ordinary media GETs (Class B)

Each displayed thumbnail and full page eventually requires an origin/cache fill. Page URLs are assigned directly to `<img>` (`src/page/reader.js:217-242`); thumbnail candidates use pointer/manifest/CDN locations (`src/components/rotunda.js:360-380`). Effective edge/browser hits may avoid R2, but the repository does not define headers or edge cache rules, so actual origin rates are uncertain.

### Runtime metadata GETs (Class B)

One CDN `item.json` is fetched for every chapter render (`src/page/reader.js:394-408`). Work metadata is repository-static. `details.json`, archive URLs, and remote `tags.json` are not fetched by the public reader. The deletor's explicit inspect/thumbnail actions make conditional CDN reads and locally cache ETag/Last-Modified state (`scripts/deletor.py:171-245,683-724`); these are admin-time, not reader-time.

### Directory listings (Class A)

None occur in browser or deployed Worker code. Ingestion uploads a known local tree and generates known manifests (`scripts/ingest-work.py:1321-1392`). `build_tags.py --from-r2-details` invokes an explicit `rclone lsf -R --files-only` and then downloads matching details in a thread pool (`scripts/build_tags.py:108-125`), an administrative full-bucket listing whose cost grows with object count. R2 audit/navigator scripts are also operator tools, not production request paths.

### Writes/deletes and administration

Ingestion is the principal R2 writer and uses rclone or built-in S3-compatible credentials; defaults are declared at `scripts/ingest-work.py:40-46`, credential validation at `scripts/ingest-work.py:1280-1282`, and generated chapter/catalog metadata at `scripts/ingest-work.py:1321-1394`. This is ingestion-time Class A work and is appropriate, but should emit all public manifests in one transaction/release.

Critically, neither current nor requested legacy deletor calls R2, rclone, boto3, S3, Wrangler, or an API for hide/delete. Both share identical local mutation code through `set_rotunda_omissions`; local deletion edits catalogs and removes only repository manifests (`scripts/deletor.py:338-368,442-455`; `scripts/working _legacy/best/deletor-new.py:338-455`). Remote pages, thumbnails, details, and archives remain. Any recollection that the legacy file deleted remote objects is not evidenced by this file.

## High-volume risks

1. The 3.2 MB search index is explicitly `no-store`; every visit/focus can require a new transfer and edge/origin validation (`src/components/search.js:3-18`).
2. Four embedded blocks fetch the same JSON independently with `no-store`.
3. Reader startup eagerly marks the first three pages high-priority and loads a 21-page window; for very large images this is aggressive even though DOM/image virtualization is bounded (`src/page/reader.js:8-13,217-251`).
4. Reopening a chapter refetches `item.json`; an in-flight/cache map would eliminate browser-level duplicate calls.
5. Unversioned media paths are assumed immutable but can be overwritten by ingestion. Long immutable caching is unsafe until object keys include a content/revision version.
6. `build_tags.py --from-r2-details` lists the whole bucket. Replace with ingestion-maintained metadata, not another periodic listing.

## Responsibility decisions

* **REMOVE:** unused `src/fetch/fetch.js` after validation; any external Worker slug/page resolver; reader-time list APIs if external code has them.
* **REPLACE WITH STATIC DATA:** query-only route resolution, pathname slug resolution, chapter `item.json` where its fields can be included in per-work public manifests.
* **MOVE TO BUILD OR INGESTION:** page filenames/counts/dimensions/checksums; search/catalog generation; visibility projection; R2 inventory updates.
* **KEEP AS EXCEPTIONAL BACKEND FUNCTION:** Supabase discussion, future authenticated annotations, administrative publication/deletion, signed private access, rate-limited mutation.
* **UNCERTAIN:** Cloudflare dashboard rules and the CDN origin/cache configuration, which are absent from version control.
