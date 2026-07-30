import { getSupabase } from "./supabase.js";
import { reportAuthError } from "./errors.js";

const listeners = new Set();
let state = Object.freeze({ status: "loading", session: null, user: null, error: null });
let initialization;
let subscription;
let identityGeneration = 0;

function durableStatus(user) {
    return user?.is_anonymous ? "anonymous" : user ? "authenticated" : "signed-out";
}
function publish(session, error = null) {
    const next = Object.freeze({ status: error ? "error" : durableStatus(session?.user), session: session || null, user: session?.user || null, error });
    const identityChanged = state.user?.id !== next.user?.id;
    if (identityChanged) identityGeneration++;
    state = next;
    listeners.forEach(listener => listener(state, { identityChanged }));
}
export const getAuthState = () => state;
export const getIdentityGeneration = () => identityGeneration;
export const isCurrentIdentity = (userId, generation) => state.user?.id === userId && identityGeneration === generation;
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
            const result = client.auth.onAuthStateChange((_event, session) => publish(session));
            subscription = result.data.subscription;
            const { data, error } = await client.auth.getSession();
            if (error) throw error;
            publish(data.session);
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
export async function signOut() {
    const data = await authCall("signOut");
    // Supabase normally publishes SIGNED_OUT. Publishing is also an immediate,
    // idempotent privacy boundary if the event is delayed.
    publish(null);
    return data;
}
export async function ensureAnonymousSession() {
    if (state.session) return state.session;
    const data = await authCall("signInAnonymously");
    return data.session;
}
export function safeOAuthReturnPath(value, fallback = "/account/profile") {
    if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u001f]/.test(value)) return fallback;
    try {
        const candidate = new URL(value, "https://account.invalid");
        const allowed = new Set(["/account/profile", "/account/bookmarks", "/account/settings"]);
        return candidate.origin === "https://account.invalid" && !candidate.username && !candidate.password && allowed.has(candidate.pathname)
            ? `${candidate.pathname}${candidate.search}${candidate.hash}` : fallback;
    } catch { return fallback; }
}
export function oauthRedirectUrl(value, origin = window.location.origin) {
    return new URL(safeOAuthReturnPath(value), origin).href;
}
export async function continueWithGoogle(returnPath = "/account/profile") {
    const client = await getSupabase();
    if (!client) throw new Error("Accounts are unavailable because Supabase is not configured.");
    const path = safeOAuthReturnPath(returnPath);
    const accountState = state.user?.is_anonymous ? "anonymous" : state.user ? "durable" : "signed-out";
    const options = { provider: "google", options: { scopes: "openid email profile", redirectTo: oauthRedirectUrl(path) } };
    try {
        let result;
        if (state.user?.is_anonymous) {
            if (import.meta.env.VITE_ENABLE_ANONYMOUS_GOOGLE_LINKING !== "true") throw Object.assign(new Error("Manual identity linking is not enabled for this deployment."), { code: "identity_linking_disabled" });
            result = await client.auth.linkIdentity(options);
        } else {
            if (state.user) await signOut();
            result = await client.auth.signInWithOAuth(options);
        }
        if (result.error) throw result.error;
        return result.data;
    } catch (error) {
        const diagnostic = reportAuthError(error, { operation: state.user?.is_anonymous ? "link-google-identity" : "google-sign-in", returnPath: path, accountState });
        error.authDiagnostic = diagnostic;
        throw error;
    }
}

if (import.meta.hot) import.meta.hot.dispose(disposeAuth);
