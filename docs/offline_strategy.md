# Offline strategy

Today, loaded pages and local profiles can be used without a profile network request. The target is cached catalog browsing/search, bookmarked works, cached chapters, profile editing, and local bookmark/preference changes. A future service worker should use versioned manifests, bounded caches, graceful reconnection, and explicit storage controls. Queued operations apply only to public refreshes or a future opt-in sync service—not direct private R2 writes.
