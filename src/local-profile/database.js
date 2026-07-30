export const DATABASE_NAME = "doku-local-profiles";
export const DATABASE_VERSION = 1;
export const PROFILE_STORE = "profiles";
export const META_STORE = "meta";

let connection;
export function openProfileDatabase(indexedDB = globalThis.indexedDB) {
    if (!indexedDB) return Promise.reject(new Error("IndexedDB is unavailable."));
    if (connection) return connection;
    connection = new Promise((resolve, reject) => {
        const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(PROFILE_STORE)) db.createObjectStore(PROFILE_STORE, { keyPath: "profileId" });
            if (!db.objectStoreNames.contains(META_STORE)) db.createObjectStore(META_STORE);
        };
        request.onsuccess = () => { request.result.onversionchange = () => request.result.close(); resolve(request.result); };
        request.onerror = () => reject(request.error || new Error("IndexedDB could not be opened."));
        request.onblocked = () => reject(new Error("IndexedDB upgrade was blocked."));
    });
    connection.catch(() => { connection = null; });
    return connection;
}

export async function transact(storeName, mode, operation) {
    const db = await openProfileDatabase();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(storeName, mode), store = transaction.objectStore(storeName);
        let request;
        try { request = operation(store); } catch (error) { reject(error); return; }
        transaction.oncomplete = () => resolve(request?.result);
        transaction.onerror = () => reject(transaction.error || request?.error || new Error("Local profile transaction failed."));
        transaction.onabort = transaction.onerror;
    });
}
export const resetDatabaseConnection = () => { connection = null; };
