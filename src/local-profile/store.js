import { META_STORE, PROFILE_STORE, transact } from "./database.js";
import { createProfileRecord } from "./schema.js";

const listeners = new Set();
let state = Object.freeze({ status: "loading", profile: null, profiles: [], error: null });
let generation = 0, initialization;
const publish = patch => { state = Object.freeze({ ...state, ...patch }); listeners.forEach(fn => fn(state)); };
const all = () => transact(PROFILE_STORE, "readonly", store => store.getAll());
const selected = () => transact(META_STORE, "readonly", store => store.get("activeProfileId"));
const writeSelected = id => transact(META_STORE, "readwrite", store => id ? store.put(id, "activeProfileId") : store.delete("activeProfileId"));

export const getLocalProfileState = () => state;
export const getProfileGeneration = () => generation;
export const isCurrentProfile = (id, value) => generation === value && state.profile?.profileId === id;
export function subscribeLocalProfiles(listener) { listeners.add(listener); listener(state); return () => listeners.delete(listener); }
export async function initializeLocalProfiles({ force = false } = {}) {
    if (initialization && !force) return initialization;
    const requestGeneration = generation;
    initialization = Promise.all([all(), selected()]).then(([profiles, id]) => {
        if (requestGeneration !== generation) return state;
        const profile = profiles.find(item => item.profileId === id) || null;
        publish({ status: "ready", profiles, profile, error: null }); return state;
    }).catch(error => { if (requestGeneration === generation) publish({ status: "error", profile: null, profiles: [], error }); return state; });
    return initialization;
}
export const retryLocalProfiles = () => initializeLocalProfiles({ force: true });
export async function createLocalProfile(input) {
    const profile = createProfileRecord(input, { newId: true });
    await transact(PROFILE_STORE, "readwrite", store => store.add(profile));
    await selectLocalProfile(profile.profileId); return profile;
}
export async function selectLocalProfile(profileId) {
    const nextGeneration = ++generation;
    publish({ profile: null, status: "loading", error: null });
    const profile = await transact(PROFILE_STORE, "readonly", store => store.get(profileId));
    if (nextGeneration !== generation) return null;
    if (!profile) throw new Error("Local profile was not found.");
    await writeSelected(profileId);
    if (nextGeneration === generation) publish({ profile, status: "ready", profiles: await all(), error: null });
    return profile;
}
export async function clearActiveProfile() { generation++; await writeSelected(null); publish({ profile: null, status: "ready", error: null }); }
export async function saveActiveProfile(changes) {
    const previous = state.profile;
    if (!previous) throw new Error("Choose a local profile first.");
    const profile = createProfileRecord({ ...previous, ...changes, profileId: previous.profileId, createdAt: previous.createdAt, updatedAt: new Date().toISOString() });
    try { await transact(PROFILE_STORE, "readwrite", store => store.put(profile)); publish({ profile, profiles: state.profiles.map(p => p.profileId === profile.profileId ? profile : p), error: null }); return profile; }
    catch (error) { publish({ error }); throw error; }
}
export async function deleteLocalProfile(profileId) {
    await transact(PROFILE_STORE, "readwrite", store => store.delete(profileId));
    if (state.profile?.profileId === profileId) await clearActiveProfile();
    publish({ profiles: await all() });
}
export async function importLocalProfile(profile, { overwrite = false } = {}) {
    const record = createProfileRecord(profile, { newId: !overwrite });
    await transact(PROFILE_STORE, "readwrite", store => overwrite ? store.put(record) : store.add(record));
    return selectLocalProfile(record.profileId);
}
export async function toggleLocalBookmark(workId, chapter = null) {
    const current = state.profile; if (!current) throw new Error("Create or choose a local profile to bookmark works.");
    const found = current.bookmarks.some(item => item.workId === String(workId));
    const bookmarks = found ? current.bookmarks.filter(item => item.workId !== String(workId)) : [...current.bookmarks, { workId: String(workId), chapter, createdAt: new Date().toISOString() }];
    await saveActiveProfile({ bookmarks }); return !found;
}
