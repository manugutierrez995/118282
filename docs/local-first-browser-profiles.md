# Local-first browser profiles

## Why this replaced Supabase

Doku-Doujin no longer requires remote authentication or a remote database for personal state. A **local profile** is a convenience container, not secure authentication: it is stored in this browser, does not automatically follow a reader to another device, and cannot be recovered after browser data is cleared unless the reader exported a backup.

## Data and storage

IndexedDB database `doku-local-profiles`, schema version 1, contains `profiles` (keyed by random `profileId`) and `meta` (the selected profile ID). Records contain display name, optional avatar reference/data, preferred and excluded tag keys, minimal bookmark references, settings, archived local comments, and timestamps. They never contain passwords, email ownership, cached images, manifests, or catalog data. Schema upgrades must validate and migrate records transactionally; a future repair tool may export valid records, discard corrupt records only with consent, and garbage-collect orphaned cache entries.

Memory holds the selected record and a generation counter. Switching clears the prior in-memory profile before the new IndexedDB read; stale generations cannot publish. IndexedDB is authoritative. Cookies and localStorage are not used for profile records.

## Preferences, bookmarks, and discussion

Exclusions are applied before Search limits and remove matching works from Search and Rotunda. Preferred tags provide stable secondary prominence. Exclusion wins. Bookmarks remain visible and readable even when excluded and resolve current public catalog metadata when rendered. Public posting is disabled and described honestly as read-only; this milestone does not pretend local text is globally visible.

## Backup and restore

Export downloads one versioned JSON profile without public assets. Import parses, validates, normalizes tags, sanitizes text, deduplicates bookmarks, previews counts, and creates a new identity by default. Overwriting requires an explicit future/administrative flow rather than accidental replacement. Export before clearing browser data or use it to move state to another browser.

## Failure and privacy

The public Rotunda and Search start independently. Missing, delayed, or failed IndexedDB falls open to global public behavior; it must never replace public candidates with an empty list. A storage error is shown outside content, with retry via reopening the profile chooser. Failed writes keep the last successfully stored in-memory record and report that the change was not saved. Profile IDs, names, preferences, bookmarks, and notes are not sent to analytics, logs, URLs, or public files.

## R2 and synchronization boundary

R2 remains a distributor for operator-managed public works, pages, thumbnails, manifests, catalogs, and archives. Browser JavaScript cannot securely hold general R2 write credentials: embedded credentials can be extracted and abused, and an obscure object name or random profile ID is not authorization. Private object access needs a trusted signing/authorization layer. Therefore this static application performs no private R2 writes and generates no long-lived presigned URLs.

Public catalogs may continue receiving nightly static ingestion/deployment updates. Private profiles update immediately in IndexedDB. There is no fake nightly profile synchronization. Future opt-in synchronization could transfer authenticated or encrypted snapshots, but only across a separately designed trusted server boundary.

## Tests and manual verification

Automated tests cover schema normalization, bookmark deduplication, backup validation/version rejection, import cloning, route redirects, account-menu language, Search ordering, Rotunda fail-open behavior, read-only discussion, and scans for forbidden runtime dependencies. Run `npm test`, `npm run build`, and the Python test suite.

Manual browser checklist: create A; edit it; prefer/exclude tags; bookmark and reload; verify Search/Rotunda and excluded-bookmark access; export. Create B and verify isolation; switch back. Import A in another browser profile. In developer tools, block IndexedDB and verify public Search/Rotunda remain, profile warning is visible, and retry is possible.

## Limitations

There is no authentication, password, automatic recovery, automatic cross-device synchronization, global posting, or background private upload. Offline public reading is limited to assets already held by the browser; broader service-worker caching is future work.
