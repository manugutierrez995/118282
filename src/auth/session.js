import { getSupabase } from "./supabase.js";

const listeners = new Set();
let state = Object.freeze({ status: "loading", session: null, user: null, error: null });
let initialization;
let subscription;

function durableStatus(user) {
    return user?.is_anonymous ? "anonymous" : user ? "authenticated" : "signed-out";
}
function publish(session, error = null) {
    const next = Object.freeze({ status: error ? "error" : durableStatus(session?.user), session: session || null, user: session?.user || null, error });
    const identityChanged = state.user?.id !== next.user?.id;
    state = next;
    listeners.forEach(listener => listener(state, { identityChanged }));
}
export const getAuthState = () => state;
export function subscribeAuth(listener) {
    listeners.add(listener);
    listener(state, { identityChanged: false });
    return () => listeners.delete(listener);
}
export function initializeAuth() {
    if (initialization) return initialization;
    initialization = (async () => {
        try {
            const client = await getSupabase();
            if (!client) { publish(null); return state; }
            const { data, error } = await client.auth.getSession();
            if (error) throw error;
            publish(data.session);
            const result = client.auth.onAuthStateChange((_event, session) => publish(session));
            subscription = result.data.subscription;
        } catch (error) { publish(null, error); }
        return state;
    })();
    return initialization;
}
export function disposeAuth() {
    subscription?.unsubscribe(); subscription = null; initialization = null;
}
async function authCall(method, ...args) {
    const client = await getSupabase();
    if (!client) throw new Error("Accounts are unavailable because Supabase is not configured.");
    const result = await client.auth[method](...args);
    if (result.error) throw result.error;
    return result.data;
}
export const signUpWithEmail = (email, password, redirectTo) => authCall("signUp", { email, password, options: { emailRedirectTo: redirectTo } });
export const signInWithEmail = (email, password) => authCall("signInWithPassword", { email, password });
export const requestPasswordReset = (email, redirectTo) => authCall("resetPasswordForEmail", email, { redirectTo });
export const completePasswordReset = password => authCall("updateUser", { password });
export const signOut = () => authCall("signOut");
export async function ensureAnonymousSession() {
    if (state.session) return state.session;
    const data = await authCall("signInAnonymously");
    return data.session;
}
export async function continueWithGoogle(redirectTo) {
    const client = await getSupabase();
    if (!client) throw new Error("Accounts are unavailable because Supabase is not configured.");
    let safeRedirect = new URL("/", window.location.origin).href;
    try {
        const candidate = new URL(redirectTo || `${window.location.pathname}${window.location.search}`, window.location.origin);
        if (candidate.origin === window.location.origin && !candidate.username && !candidate.password) safeRedirect = candidate.href;
    } catch { /* retain the fixed same-origin fallback */ }
    const options = { provider: "google", options: { scopes: "openid email profile", redirectTo: safeRedirect } };
    const result = state.user?.is_anonymous ? await client.auth.linkIdentity(options) : await client.auth.signInWithOAuth(options);
    if (result.error) throw result.error;
    return result.data;
}

if (import.meta.hot) import.meta.hot.dispose(disposeAuth);
