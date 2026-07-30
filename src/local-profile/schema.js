export const PROFILE_SCHEMA_VERSION = 1;

export function normalizeTags(values) {
    return [...new Set((Array.isArray(values) ? values : []).map(value => String(value).trim().toLowerCase().replace(/\s+/g, "-")).filter(Boolean))].sort();
}
export function normalizeBookmarks(values) {
    const seen = new Set();
    return (Array.isArray(values) ? values : []).filter(value => value && typeof value === "object").map(value => ({
        workId: String(value.workId ?? value.work_id ?? "").trim(),
        chapter: value.chapter == null ? null : String(value.chapter),
        createdAt: validDate(value.createdAt ?? value.created_at) || new Date().toISOString()
    })).filter(value => value.workId && !seen.has(value.workId) && seen.add(value.workId));
}
const validDate = value => typeof value === "string" && !Number.isNaN(Date.parse(value)) ? new Date(value).toISOString() : null;
const cleanText = (value, maximum) => String(value ?? "").replace(/[<>\u0000-\u001f]/g, "").trim().slice(0, maximum);

export function createProfileRecord(input = {}, { newId = false } = {}) {
    const now = new Date().toISOString();
    const id = !newId && typeof input.profileId === "string" && /^[a-zA-Z0-9-]{8,100}$/.test(input.profileId)
        ? input.profileId : globalThis.crypto?.randomUUID?.() || `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return {
        version: PROFILE_SCHEMA_VERSION, profileId: id,
        displayName: cleanText(input.displayName || "Local reader", 80),
        avatar: typeof input.avatar === "string" ? cleanText(input.avatar, 500) || null : null,
        preferredTags: normalizeTags(input.preferredTags), excludedTags: normalizeTags(input.excludedTags),
        bookmarks: normalizeBookmarks(input.bookmarks),
        settings: input.settings && typeof input.settings === "object" && !Array.isArray(input.settings) ? { ...input.settings } : {},
        archivedComments: Array.isArray(input.archivedComments) ? input.archivedComments.map(value => ({
            workId: cleanText(value?.workId, 200), body: cleanText(value?.body, 4000), createdAt: validDate(value?.createdAt) || now
        })).filter(value => value.workId && value.body) : [],
        createdAt: validDate(input.createdAt) || now, updatedAt: validDate(input.updatedAt) || now
    };
}

export function validateProfileRecord(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Backup must contain a profile object.");
    if (value.version !== PROFILE_SCHEMA_VERSION) throw new Error(`Unsupported profile schema version: ${value.version}.`);
    if (typeof value.displayName !== "string" || !value.displayName.trim()) throw new Error("Profile display name is required.");
    return createProfileRecord(value);
}
