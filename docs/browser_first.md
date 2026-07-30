# Browser-first architecture

The browser is the host for personal state; the server primarily distributes public content. Every network request must justify its cost. Personal features should first ask whether IndexedDB can provide immediate, offline, exportable behavior. Cloud outages must not make the loaded site useless.

Storage hierarchy: (1) disposable memory page state; (2) authoritative IndexedDB profiles, bookmarks, preferences, progress, collections and notes; (3) replaceable Cache Storage public images, catalogs, manifests, fonts and UI assets; (4) human-controlled export files; (5) future optional cloud synchronization. Cookies, if introduced, stay tiny and may only bootstrap theme, language, feature flags, or a selected profile ID—not a profile.

Feature reviews ask: can it work offline, survive cloud failure, synchronize later, export/import, and migrate locally? A network-dependent answer should trigger redesign.
