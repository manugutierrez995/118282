# Storage architecture

IndexedDB is the local database and primary persistent source for personal data. Versioned upgrades create or migrate object stores atomically. Inputs are validated and normalized at every import/write boundary. Backups provide user-controlled recovery; repair and garbage collection must never silently destroy the only copy.

Cache Storage is appropriate for replaceable public images, reader pages, thumbnails, catalog JSON, fonts, icons and manifests. Versioned public manifests should invalidate changed assets and retain byte-identical ones. Cache entries must never be confused with profile ownership or backup data.
