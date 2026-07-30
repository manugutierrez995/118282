import { subscribeAuth } from "../auth/session.js";

const icon = (href, label, glyph) => `<a data-route class="account-icon-link" href="${href}" aria-label="${label}"><span aria-hidden="true">${glyph}</span></a>`;
export function mountAccountNavigation(root, { compact = false } = {}) {
    if (!root) return () => {};
    root.className = `account-controls${compact ? " account-controls-compact" : ""}`;
    return subscribeAuth(state => {
        root.setAttribute("aria-busy", String(state.status === "loading"));
        if (state.status === "loading") { root.innerHTML = `<span class="account-control-placeholder" aria-label="Loading account"></span>`; return; }
        if (state.status === "authenticated") root.innerHTML = `${icon("/account/profile", "View profile", "●")}${icon("/account/bookmarks", "View bookmarks", "▣")}${icon("/account/settings", "Open settings", "⚙")}`;
        else root.innerHTML = `<a data-route class="account-login-link" href="/login">Log in</a>`;
    });
}
export function accountSubnav(active) {
    return `<nav class="account-subnav" aria-label="Account"><a data-route href="/account/profile"${active === "profile" ? ' aria-current="page"' : ""}>Profile</a><a data-route href="/account/bookmarks"${active === "bookmarks" ? ' aria-current="page"' : ""}>Bookmarks</a><a data-route href="/account/settings"${active === "settings" ? ' aria-current="page"' : ""}>Settings</a></nav>`;
}

