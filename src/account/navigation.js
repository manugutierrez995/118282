import { signOut, subscribeAuth } from "../auth/session.js";
import { navigate } from "../router/router.js";

const escape = value => String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
export function accountPresentation(user) {
    const metadata = user?.user_metadata || {};
    const name = metadata.full_name || metadata.name || "Doku-Doujin member";
    const avatar = metadata.avatar_url || metadata.picture || "";
    return { name, email: user?.email || "Email unavailable", avatar: /^https:\/\/[^\s]+$/i.test(avatar) ? avatar : "", fallback: String(name || user?.id || "M").trim()[0]?.toUpperCase() || "M" };
}
export function accountMenuMarkup(user, menuId = "account-menu") {
    const profile = accountPresentation(user);
    const face = profile.avatar ? `<img src="${escape(profile.avatar)}" alt="">` : `<span aria-hidden="true">${escape(profile.fallback)}</span>`;
    return `<button type="button" class="account-menu-trigger" aria-label="Open account menu for ${escape(profile.name)}" aria-expanded="false" aria-controls="${menuId}">${face}</button><div class="account-menu" id="${menuId}" hidden><div class="account-menu-identity"><strong>${escape(profile.name)}</strong><span>${escape(profile.email)}</span></div><a data-route href="/account/profile">Profile</a><a data-route href="/account/bookmarks">Bookmarks</a><a data-route href="/account/settings">Settings</a><button type="button" class="account-menu-signout">Sign out</button><p class="account-menu-status" role="status" aria-live="polite"></p></div>`;
}
export function mountAccountNavigation(root, { compact = false } = {}) {
    if (!root) return () => {};
    let cleanupMenu = () => {};
    root.className = `account-controls${compact ? " account-controls-compact" : ""}`;
    const unsubscribe = subscribeAuth(state => {
        cleanupMenu(); cleanupMenu = () => {};
        root.setAttribute("aria-busy", String(state.status === "loading"));
        if (state.status === "loading") { root.innerHTML = `<span class="account-control-placeholder" aria-label="Loading account"></span>`; return; }
        if (state.status !== "authenticated") { root.innerHTML = `<a data-route class="account-login-link" href="/login">Log in</a>`; return; }
        const menuId = `account-menu-${Math.random().toString(36).slice(2)}`;
        root.innerHTML = accountMenuMarkup(state.user, menuId);
        const trigger = root.querySelector(".account-menu-trigger"), menu = root.querySelector(".account-menu"), signout = root.querySelector(".account-menu-signout"), status = root.querySelector(".account-menu-status");
        const close = ({ focus = false } = {}) => { menu.hidden = true; trigger.setAttribute("aria-expanded", "false"); if (focus) trigger.focus(); };
        const open = () => { menu.hidden = false; trigger.setAttribute("aria-expanded", "true"); menu.querySelector("a,button")?.focus(); };
        const outside = event => { if (!root.contains(event.target)) close(); };
        const keydown = event => { if (event.key === "Escape" && !menu.hidden) { event.preventDefault(); close({ focus: true }); } };
        trigger.addEventListener("click", () => menu.hidden ? open() : close()); document.addEventListener("pointerdown", outside); document.addEventListener("keydown", keydown);
        signout.addEventListener("click", async () => { signout.disabled = true; status.textContent = "Signing out…"; try { await signOut(); close(); navigate("/", { replace: true }); } catch { signout.disabled = false; status.textContent = "Sign out did not finish. Your account is still active; please try again."; } });
        cleanupMenu = () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", keydown); };
    });
    return () => { cleanupMenu(); unsubscribe(); root.replaceChildren(); };
}
export function accountSubnav(active) {
    return `<nav class="account-subnav" aria-label="Account"><a data-route href="/account/profile"${active === "profile" ? ' aria-current="page"' : ""}>Profile</a><a data-route href="/account/bookmarks"${active === "bookmarks" ? ' aria-current="page"' : ""}>Bookmarks</a><a data-route href="/account/settings"${active === "settings" ? ' aria-current="page"' : ""}>Settings</a></nav>`;
}
