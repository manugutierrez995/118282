import { getAuthState, getIdentityGeneration, isCurrentIdentity, subscribeAuth } from "../auth/session.js";
import { loadPreferences, removePreference, resetPreferences, setPreference } from "./data.js";
import { normalizeTag } from "../utils/tag.js";

const listeners = new Set();
let state = { status: "loading", userId: null, generation: 0, preferred: new Set(), excluded: new Set(), error: null, revision: 0 };
let readyPromise = Promise.resolve();
const snapshot = () => Object.freeze({ ...state, preferred: new Set(state.preferred), excluded: new Set(state.excluded) });
function publish(next) { state = { ...state, ...next, revision: state.revision + 1 }; listeners.forEach(fn => fn(snapshot())); }
function rowsState(rows) { const preferred = new Set(), excluded = new Set(); for (const row of rows) (row.preference_type === "preferred" ? preferred : excluded).add(normalizeTag(row.tag_key)); return { preferred, excluded }; }
async function activate(auth) {
    const user = auth.user?.is_anonymous ? null : auth.user;
    const generation = getIdentityGeneration();
    publish({ status: user ? "loading" : "ready", userId: user?.id || null, generation, preferred: new Set(), excluded: new Set(), error: null });
    if (!user) return;
    try { const rows = await loadPreferences(); if (isCurrentIdentity(user.id, generation)) publish({ status: "ready", ...rowsState(rows) }); }
    catch (error) { if (isCurrentIdentity(user.id, generation)) publish({ status: "error", error }); }
}
subscribeAuth((auth, detail) => { if (detail.identityChanged || (auth.status !== "loading" && !state.userId && state.status === "loading")) readyPromise = activate(auth); });
export const personalizationStore = {
    get: snapshot,
    subscribe(listener) { listeners.add(listener); listener(snapshot()); return () => listeners.delete(listener); },
    async ready() { await readyPromise; return snapshot(); },
    retry() { readyPromise = activate(getAuthState()); return readyPromise; },
    async set(tag, type) { const before = snapshot(), owner = state.userId, generation = state.generation; const preferred = new Set(state.preferred), excluded = new Set(state.excluded); preferred.delete(tag); excluded.delete(tag); (type === "preferred" ? preferred : excluded).add(tag); publish({ preferred, excluded, error: null }); try { await setPreference(tag, type); } catch (error) { if (isCurrentIdentity(owner, generation)) publish({ preferred: before.preferred, excluded: before.excluded, error }); throw error; } },
    async remove(tag) { const before = snapshot(), owner = state.userId, generation = state.generation; const preferred = new Set(state.preferred), excluded = new Set(state.excluded); preferred.delete(tag); excluded.delete(tag); publish({ preferred, excluded }); try { await removePreference(tag); } catch (error) { if (isCurrentIdentity(owner, generation)) publish({ preferred: before.preferred, excluded: before.excluded, error }); throw error; } },
    async reset() { const before = snapshot(), owner = state.userId, generation = state.generation; publish({ preferred: new Set(), excluded: new Set() }); try { await resetPreferences(); } catch (error) { if (isCurrentIdentity(owner, generation)) publish({ preferred: before.preferred, excluded: before.excluded, error }); throw error; } }
};
