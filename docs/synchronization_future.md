# Future optional synchronization

Synchronization is optional and must never become a startup prerequisite. A static browser must not contain R2 write secrets or rely on unguessable object keys. Any future profile snapshot service requires a trusted authorization/signing boundary, explicit opt-in, conflict rules, encryption and deletion/export controls. Until that exists, export files are the honest portable format and IndexedDB updates are immediate and local.
