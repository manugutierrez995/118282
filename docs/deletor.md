# `deletor.py` audit and safe unification plan

## Executive finding

The two files do **not** contain different storage mutation engines. They are byte-for-byte equivalent from the imports through `set_rotunda_omissions`; the only substantive diff is that current `scripts/deletor.py` replaces the legacy curses selector with Tkinter, thumbnail caching, and add-only per-work public/private tag editing (`scripts/deletor.py:609-949`; `scripts/working _legacy/best/deletor-new.py:609-818`). Both then use the same main-path local hide/unhide and deletion functions.

Neither file deletes, moves, hides, or writes R2 objects. They contain no rclone/boto3/S3/Wrangler mutation call. Remote access is read-only `urlopen` for lazy metadata and thumbnails (`scripts/deletor.py:180-245,696-724`). “Delete” removes a work from repository catalogs and deletes its repository manifest, then regenerates search (`scripts/deletor.py:338-368,442-455`). “Hide” only changes `rotunda.json.public_rotunda.omit_works` (`scripts/deletor.py:542-607`). Thus legacy remote deletion cannot be “restored” from the named file; its existence elsewhere is **UNCERTAIN**.

The likely perceived GUI regression is provable: the current Tk actions merely store `action/slugs` and destroy the window (`scripts/deletor.py:912-926`). Main subsequently prompts with terminal `input()` for hide/unhide or delete (`scripts/deletor.py:991-1043`). The legacy curses UI runs in—and returns to—the same terminal (`scripts/working _legacy/best/deletor-new.py:609-818`), so that prompt is visible. When current Tkinter is launched from a desktop/no attached terminal, the post-window confirmation is invisible or raises EOF; no mutation occurs. Buttons are connected, but confirmation was not ported into the GUI workflow.

## Purpose and architecture

Current `scripts/deletor.py` is a repository catalog editor with durable read cache, safe local backups/rollback, duplicate detection, a graphical catalog/search/thumbnail interface, add-only per-work tags, rotunda omission control, and repository catalog deletion (`scripts/deletor.py:43-245,338-535,609-949`). The legacy “best” file is the same engine with a terminal curses chooser and no tag editor/thumbnail UI (`scripts/working _legacy/best/deletor-new.py:609-818`).

Work selection resolves the actual slug from catalog rows and per-work manifests (`scripts/deletor.py:278-301`). No operation uses a title as a destructive identity. Local delete constructs manifest paths, resolves them, and deletes only when beneath `data_dir` (`scripts/deletor.py:362-365`). This prevents manifest path escape, but there is no remote prefix resolver because there is no remote delete.

## Capability matrix

| Capability | Current | Legacy | Unified target |
|---|---|---|---|
| Discover/list/search/select works | **FULLY WORKING**; local catalogs/manifests, Tk search and extended selection (`scripts/deletor.py:278-301,726-949`) | **FULLY WORKING**; same discovery, curses filtering/multiselect (`.../deletor-new.py:278-301,609-818`) | Preserve current GUI; expose visibility state |
| Incremental loading | **PARTIALLY WORKING**; list is fully populated, thumbnails load in a thread | **REMOVED**; full terminal list | Virtualize only if measured |
| Thumbnail preview/cache/refresh | **FULLY WORKING** subject to Pillow/network; SHA-256 local cache and background thread (`scripts/deletor.py:683-724,813-873`) | **REMOVED** | Preserve; validate content type/size |
| Metadata display/public URL/copy | **PARTIALLY WORKING**; slug/thumb/tag path shown, `--inspect` prints metadata; no public reader URL/copy | **PARTIALLY WORKING**; `--inspect` only | Add canonical URL/copy and exact mutation target |
| Read tags | **PARTIALLY WORKING**; discovery tags searchable; per-work nested file loaded for edits but existing values not rendered | **PARTIALLY WORKING**; catalog tags only | Render both canonical public tags and private admin tags separately |
| Add public/private nested tags | **FULLY WORKING locally**; preserves unknown top-level/nested data, atomic write + backup (`scripts/deletor.py:621-681,877-905`) | **REMOVED** | Preserve, then explicitly publish public projection |
| Remove tags | **REMOVED** | **REMOVED** | Add tested remove operations |
| Input/schema validation | **PARTIALLY WORKING**; trims empty input and repairs non-dict public/private blocks, but accepts arbitrary names and may silently replace malformed blocks (`scripts/deletor.py:621-669`) | **REMOVED** | Validate without discarding malformed/unknown data |
| Missing `tags.json` | **IMPLEMENTED DIFFERENTLY**; creates `src/data/<slug>.json`, not CDN `tags.json` or canonical global `src/data/tags.json` (`scripts/deletor.py:609-643`) | **REMOVED** | Choose one private admin location; never collide with content data |
| Hide/unhide | **PARTIALLY WORKING**; buttons connected and local atomic mutation works, but GUI confirmation continues in terminal and only rotunda discovery changes (`scripts/deletor.py:912-925,991-1035`) | **FULLY WORKING for local rotunda semantics** in terminal (`.../deletor-new.py:782-786,861-905`) | GUI confirmation + canonical visibility projection + catalog rebuild |
| Visibility state display | **REMOVED** | **REMOVED** | Show current canonical state and no-op states |
| Delete repository catalog entry/manifest | **PARTIALLY WORKING**; transactional backup/rollback/validation, GUI terminal-prompt defect (`scripts/deletor.py:338-455,1037-1045`) | **FULLY WORKING for local files** in terminal | Preserve local transaction after remote outcome is defined |
| Delete R2 prefix/pages/metadata/thumb/archive | **REMOVED / never implemented** | **REMOVED / never implemented** | Add only behind an explicit remote backend, preview, allowlisted prefix, tests |
| Delete local thumbnail cache | **REMOVED** | **REMOVED** | Optional post-success cleanup |
| Dry run | **FULLY WORKING for local plan** (`scripts/deletor.py:1000-1009,1037-1039`) | **FULLY WORKING** | Add remote object preview/count/bytes |
| Partial remote failure/retries/timeouts | **REMOVED** | **REMOVED** | Stop catalog mutation; report every failed key; retry boundedly |
| Confirmation | **BROKEN for GUI-only launch**, functional in terminal | **FULLY WORKING in terminal** | Modal confirmation includes title, slug, exact prefix; typed delete phrase |
| Refresh after mutation | **PARTIALLY WORKING**; window closes; search regenerates after delete; hide changes rotunda only | Same | Keep window open and reload only after success |
| Credentials/logging/responsiveness | No mutation credentials; read timeout 15/20s, thumbnail threaded, mutations synchronous; no durable operation log | Same except no thumbnail thread | Worker thread/queue, redacted structured log, bounded retry |

## Complete operation paths

### Tags

Selection stores a `Work` by the tree's slug, dialogs split comma-separated input, `add_work_tags()` loads/creates a per-work nested document, preserves the payload, inserts `{tag: {}}`, backs up an existing file, and atomically replaces it (`scripts/deletor.py:806-905`). The UI updates only its path/status; it neither refreshes work tags in search nor updates global `src/data/tags.json`, work manifest tags, public catalog, or R2. It supports add, not remove. Therefore “tag editing works” means local nested add-only editing, not publication.

### Hide/unhide

GUI `finish()` derives selected slugs and closes (`scripts/deletor.py:912-926`). Main prints title/slug, optionally previews, asks for an exact terminal phrase, then adds/removes slugs from `public_rotunda.omit_works`, backs up and atomically replaces only `rotunda.json` (`scripts/deletor.py:542-607,991-1035`). The frontend rotunda uses that omission policy, so hiding removes discovery there, but search/direct reader links remain available. It neither changes tags, work `public`, R2 paths, nor other catalogs.

### Delete

Main builds a plan before mutation. The plan removes matching slug entries from `fetch.json`, `rotunda.json`, search and global tags, and schedules the repository work manifest for deletion (`scripts/deletor.py:338-368`). It prints the plan and asks for `DELETE N` in the terminal. `apply_plan()` backs up every affected path, validates JSON, atomically writes catalogs, unlinks manifests, regenerates search through an argument-list subprocess (no shell concatenation), validates referential removal, and restores backups on exception (`scripts/deletor.py:385-455`). It does not delete CDN objects, thumbnail cache, CBZ/ZIP, details, item, pages, or ingestion source. There is no remote partial-failure behavior or remote recovery.

## Regression and semantics decision

The operational engine was not dropped; current and legacy share it. The UI was replaced without moving confirmation/status into Tk, creating the desktop-launch failure. Separately, expectations expanded from “remove local catalog” to “delete R2 work,” a feature absent in both inspected files. Finally, hide semantics are narrower than “unavailable from public discovery”: rotunda omission does not exclude search or prevent direct resolution.

Adopt `visibility: public|hidden|unpublished` in **private canonical ingestion/admin metadata**. Generate public catalogs using only `public`; never emit hidden/unpublished entries. Maintain `omit_works` temporarily as a rotunda compatibility projection. Direct static lookup must resolve only a public manifest release, so hidden works fail closed without deleting media. Unhide republishes projections without re-uploading media.

Define delete separately: remote purge (if requested) targets exactly the allowlisted `works/<slug>/` prefix and may remove pages, item/details/tags/thumb and archives beneath it; an audit tombstone with slug, timestamp, actor, enumerated keys/checksums, and outcome remains in a private audit store. Local catalog removal happens **only after** remote success, unless the operator explicitly selects catalog-only removal.

## Safest incremental unification

1. Preserve current Tk/search/thumbnail/add-tag code and shared local transaction code; do not copy the legacy file wholesale.
2. Move confirmation into Tk and return a structured, already-confirmed action. Show title, slug, canonical reader URL, current visibility, and exact local/remote target. Keep CLI confirmation for CLI mode.
3. Add tests for no selection, cancel, malformed/Unicode slugs, missing/malformed tags, already-hidden/visible, tag preservation, atomic rollback, and GUI action dispatch using controller functions independent of Tk.
4. Introduce a `WorkTarget` resolver. Validate slug as a single logical segment, derive remote prefix from configured storage-map/ingestion data (not title), require normalized prefix matching `^works/[^/]+/$`, and reject empty, `/`, `.`, `..`, root, control characters, or prefix mismatch.
5. Restore/verify hide and unhide first using canonical visibility metadata plus generated projections; leave media untouched. Refresh the GUI only after successful commit.
6. Define a pluggable R2 client and mock it. Do not use shell strings. If rclone is selected, call an argv list with `shell=False`; preferably use a typed S3-compatible client supporting paginated list and batched delete. Credentials come from environment/profile and never logs.
7. Implement remote delete preview: enumerate the exact prefix, show object count/bytes/representative keys, and save the immutable plan. Explicit typed confirmation must match slug and prefix. Revalidate prefix immediately before execution.
8. Delete in bounded batches; report individual failures. On any partial failure, do not remove local/public metadata. Permit retry from the saved plan. Only after confirmed full success execute the existing local transaction and evict local thumbnail cache.
9. Add a redacted JSONL audit journal and run remote operations off the Tk main thread with cancellable progress (cancellation stops future batches, never claims rollback of completed deletes).

Tests must use a fake client or dedicated non-production prefix and cover authentication failure, missing objects (idempotent success policy), pagination, partial batches, network interruption, canceled confirmation, wrong/root prefix, Unicode/spaces, successful hide/unhide/delete, public/private separation, refresh ordering, and tag preservation. Production destructive tests are forbidden.

## Direct answer

Current `deletor.py` retains the newer interface because its sole major change from the legacy file is replacing curses with Tkinter and adding thumbnail/tag functions. It appears to lose working actions because those Tk buttons close the window while the actual exact confirmation and shared mutation engine still run in the terminal; desktop launches cannot see/respond reliably. It also never gained remote R2 deletion—neither named implementation has it. The minimal safe plan is therefore: preserve the Tk/tag code and shared backup transaction, move confirmations and status into a testable GUI controller, canonicalize hide as catalog exclusion, then add a mocked/previewed/strict-prefix remote deletion backend whose full success gates the existing local catalog transaction. Do not claim or perform R2 deletion until bucket semantics and a tested backend are explicitly configured.
