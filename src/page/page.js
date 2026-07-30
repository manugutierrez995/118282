import { Landing } from "./landing.js";
import { Reader } from "./reader.js";
import { getAuthState, subscribeAuth } from "../auth/session.js";
import { startRouter, navigate, safeNext } from "../router/router.js";
import { bookmarksView, loadingView, loginView, notFoundView, profileView, settingsView } from "../account/views.js";

let currentRoute, generation = 0, viewCleanup;
const root = () => document.getElementById("reader-container");
const focusHeading = () => requestAnimationFrame(() => root()?.querySelector("h1")?.focus());
async function render(route) {
    const renderId = ++generation;
    viewCleanup?.(); viewCleanup = null;
    document.body.classList.remove("reader-active");
    if (route.kind === "redirect") return navigate(route.to, { replace: true });
    if (route.kind === "legacy-reader") { const p = new URLSearchParams(location.search); return Reader.start(p.get("work"), p.get("chapter")); }
    if (route.kind === "home") return Landing.start();
    if (route.kind === "account-not-found" || route.kind === "not-found") { notFoundView(root(), route.kind === "account-not-found"); focusHeading(); return; }
    const state = getAuthState();
    if (route.private && state.status === "loading") return loadingView(root());
    if (route.private && state.status !== "authenticated") {
        const callback = new URLSearchParams(location.search);
        const error = callback.get("error"), description = callback.get("error_description");
        const failure = description ? `&error=${encodeURIComponent(error || "oauth_error")}&error_description=${encodeURIComponent(description)}` : "";
        return navigate(`/login?next=${encodeURIComponent(safeNext(location.pathname + location.search + location.hash))}${failure}`, { replace: true });
    }
    if (["login", "signup", "forgot-password", "reset-password"].includes(route.kind)) {
        if (state.status === "authenticated" && route.kind !== "reset-password") return navigate(safeNext(new URLSearchParams(location.search).get("next")), { replace: true });
        loginView(root(), route.kind); focusHeading(); return;
    }
    if (route.kind === "account-profile") profileView(root(), state.user);
    if (route.kind === "account-bookmarks") await bookmarksView(root(), state.user);
    if (route.kind === "account-settings") viewCleanup = settingsView(root(), state.user);
    if (renderId === generation) focusHeading();
}
const rerender = () => currentRoute && render(currentRoute);
export class Page {
    static async start() {
        subscribeAuth((_state, detail) => { if (detail.identityChanged) rerender(); });
        startRouter(route => { currentRoute = route; return render(route); });
    }
}
