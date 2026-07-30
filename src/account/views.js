import { completePasswordReset, continueWithGoogle, requestPasswordReset, signInWithEmail, signOut, signUpWithEmail } from "../auth/session.js";
import { accountPresentation, accountSubnav } from "./navigation.js";
import { listBookmarks, readerUrl, removeBookmark } from "./data.js";
import { navigate, safeNext } from "../router/router.js";
import { getIdentityGeneration, isCurrentIdentity } from "../auth/session.js";
import { normalizeAuthError } from "../auth/errors.js";

const escape = value => String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
const authRedirect = path => new URL(path, window.location.origin).href;
function shell(title, body, active) {
    return `<main class="account-page"><a data-route class="account-brand" href="/">Doku-Doujin</a>${active ? accountSubnav(active) : ""}<section class="account-panel"><h1 tabindex="-1">${title}</h1>${body}</section></main>`;
}
function providers(user) {
    const values = new Set((user.identities || []).map(identity => identity.provider));
    if (user.app_metadata?.provider) values.add(user.app_metadata.provider);
    return [...values].map(value => value === "email" ? "Email and password" : value[0]?.toUpperCase() + value.slice(1)).join(", ") || "Not available";
}
export function loadingView(root) { root.innerHTML = shell("Loading account", `<p role="status">Restoring your secure session…</p>`); }
export function notFoundView(root, account = false) { root.innerHTML = shell("Page not found", `<p>${account ? "That account page does not exist." : "That page does not exist."}</p><p><a data-route href="/">Return home</a></p>`); }
export function loginView(root, mode = "login") {
    const next = safeNext(new URLSearchParams(location.search).get("next"));
    const config = {
        login: ["Log in", "Log in", "No account?", "/signup", "Sign up"],
        signup: ["Create account", "Sign up", "Already registered?", "/login", "Log in"],
        "forgot-password": ["Reset password", "Send reset email", "Remembered it?", "/login", "Log in"],
        "reset-password": ["Choose a new password", "Update password", "", "/login", "Log in"]
    }[mode];
    const email = mode !== "reset-password" ? `<label>Email address<input name="email" type="email" autocomplete="email" required></label>` : "";
    const password = !["forgot-password"].includes(mode) ? `<label>${mode === "reset-password" ? "New password" : "Password"}<input name="password" type="password" autocomplete="${mode === "login" ? "current-password" : "new-password"}" minlength="8" required></label>` : "";
    root.innerHTML = shell(config[0], `<form class="auth-form">${email}${password}<button class="account-primary" type="submit">${config[1]}</button><p class="form-status" role="status" aria-live="polite"></p></form>${["login", "signup"].includes(mode) ? '<div class="auth-divider"><span>or</span></div><button class="google-button" type="button">Continue with Google</button>' : ""}${mode === "login" ? '<p><a data-route href="/forgot-password">Forgot password?</a></p>' : ""}${config[2] ? `<p>${config[2]} <a data-route href="${config[3]}?next=${encodeURIComponent(next)}">${config[4]}</a></p>` : ""}`);
    const form = root.querySelector("form"), status = root.querySelector(".form-status"), submit = form.querySelector("button");
    form.addEventListener("submit", async event => {
        event.preventDefault(); submit.disabled = true; status.textContent = "Working…";
        const values = new FormData(form);
        try {
            if (mode === "login") { await signInWithEmail(values.get("email"), values.get("password")); navigate(next, { replace: true }); }
            if (mode === "signup") { const data = await signUpWithEmail(values.get("email"), values.get("password"), authRedirect(`/login?next=${encodeURIComponent(next)}`)); status.textContent = data.session ? "Account created." : "Check your email to confirm your account, then log in."; if (data.session) navigate(next, { replace: true }); }
            if (mode === "forgot-password") { await requestPasswordReset(values.get("email"), authRedirect("/reset-password")); status.textContent = "If an account can receive mail, reset instructions have been sent."; }
            if (mode === "reset-password") { await completePasswordReset(values.get("password")); status.textContent = "Password updated."; navigate("/account/profile", { replace: true }); }
        } catch { status.textContent = "We could not complete that request. Check your details and try again."; } finally { submit.disabled = false; }
    });
    const callbackError = new URLSearchParams(location.search).get("error_description");
    if (callbackError) status.textContent = normalizeAuthError({ message: callbackError, code: new URLSearchParams(location.search).get("error") }, "google-callback").userMessage;
    root.querySelector(".google-button")?.addEventListener("click", async event => { event.currentTarget.disabled = true; status.textContent = "Opening Google…"; try { await continueWithGoogle(next); } catch (error) { status.textContent = error.authDiagnostic?.userMessage || normalizeAuthError(error, "google-sign-in").userMessage; event.currentTarget.disabled = false; } });
}
export function profileView(root, user) {
    const metadata = user.user_metadata || {};
    const presentation = accountPresentation(user);
    const avatar = presentation.avatar ? `<img class="account-avatar" src="${escape(presentation.avatar)}" alt="">` : `<span class="account-avatar account-avatar-fallback" aria-hidden="true">${escape(presentation.fallback)}</span>`;
    root.innerHTML = shell("Your profile", `<div class="profile-summary">${avatar}<div><h2>${escape(presentation.name)}</h2><p>${escape(presentation.email)}</p></div></div><dl><dt>Account created</dt><dd>${escape(user.created_at ? new Date(user.created_at).toLocaleDateString() : "Unavailable")}</dd><dt>Authentication providers</dt><dd>${escape(providers(user))}</dd></dl><div class="account-actions"><a data-route href="/account/bookmarks">View bookmarks</a><a data-route href="/account/settings">Open settings</a><button class="signout-button">Sign out</button><p class="signout-status" role="status"></p></div>`, "profile");
    bindSignOut(root);
}
export async function bookmarksView(root, user) {
    const identityGeneration = getIdentityGeneration();
    root.innerHTML = shell("Your bookmarks", `<p class="bookmark-status" role="status" aria-live="polite">Loading bookmarks…</p><div class="bookmark-list"></div>`, "bookmarks");
    const status = root.querySelector(".bookmark-status"), list = root.querySelector(".bookmark-list");
    async function load() {
        status.textContent = "Loading bookmarks…"; list.replaceChildren();
        try {
            const rows = await listBookmarks(user.id);
            if (!isCurrentIdentity(user.id, identityGeneration)) return;
            if (!rows.length) { status.textContent = "You have no bookmarks yet."; return; }
            status.textContent = `${rows.length} bookmark${rows.length === 1 ? "" : "s"}.`;
            rows.forEach(row => {
                const item = document.createElement("article"); item.className = "bookmark-card";
                const work = row.work;
                item.innerHTML = `${work?.thumb && /^https:\/\//.test(work.thumb) ? `<img src="${escape(work.thumb)}" alt="">` : ""}<div><h2>${escape(work?.display || "Work no longer available")}</h2><p>Saved ${escape(new Date(row.created_at).toLocaleDateString())}</p>${work ? `<a href="${readerUrl(work)}">Read using the current reader</a>` : "<p>Metadata could not be resolved.</p>"}</div><button type="button">Remove bookmark</button>`;
                item.querySelector("button").addEventListener("click", async event => { event.currentTarget.disabled = true; try { await removeBookmark(user.id, row.work_id); item.remove(); status.textContent = "Bookmark removed."; } catch { event.currentTarget.disabled = false; status.textContent = "Bookmark could not be removed. Try again."; } });
                list.append(item);
            });
        } catch { if (!isCurrentIdentity(user.id, identityGeneration)) return; status.innerHTML = `Bookmarks could not be loaded. <button type="button">Retry</button>`; status.querySelector("button").addEventListener("click", load); }
    }
    await load();
}
export function settingsView(root, user) {
    root.innerHTML = shell("Account settings", `<section><h2>Account</h2><p>${escape(user.email || "Email unavailable")} · ${escape(providers(user))}</p><button class="signout-button">Sign out</button><p class="signout-status" role="status"></p></section><section><h2>Content Preferences</h2><p class="preference-notice" role="status">Preferred and excluded tags are not editable yet. The catalog does not provide a reviewed user-facing tag vocabulary, so exposing internal tags would be unsafe and misleading.</p><fieldset disabled><legend>Preferred tags</legend><input aria-label="Preferred tags unavailable" placeholder="Coming after tag vocabulary review"></fieldset><fieldset disabled><legend>Excluded tags</legend><input aria-label="Excluded tags unavailable" placeholder="Coming after tag vocabulary review"></fieldset></section>`, "settings");
    bindSignOut(root);
}

function bindSignOut(root) {
    const button = root.querySelector(".signout-button"), status = root.querySelector(".signout-status");
    button?.addEventListener("click", async () => { button.disabled = true; if (status) status.textContent = "Signing out…"; try { await signOut(); navigate("/", { replace: true }); } catch { button.disabled = false; if (status) status.textContent = "Sign out did not finish. Your account is still active; please try again."; } });
}
