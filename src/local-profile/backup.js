import { createProfileRecord, validateProfileRecord } from "./schema.js";
export function serializeProfile(profile) { return JSON.stringify(validateProfileRecord(profile), null, 2); }
export function parseProfileBackup(text) {
    let value; try { value = JSON.parse(text); } catch { throw new Error("Backup is not valid JSON."); }
    return validateProfileRecord(value);
}
export function backupFilename(profile, date = new Date()) {
    const safe = String(profile.displayName || "profile").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "profile";
    return `doku-profile-${safe}-${date.toISOString().slice(0, 10)}.json`;
}
export function cloneImportedProfile(profile) { return createProfileRecord(validateProfileRecord(profile), { newId: true }); }
