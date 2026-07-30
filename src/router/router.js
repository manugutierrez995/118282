const KNOWN = new Set(["/", "/login", "/signup", "/forgot-password", "/reset-password", "/account/profile", "/account/bookmarks", "/account/settings"]);
export const PRIVATE_ROUTES = new Set(["/account/profile", "/account/bookmarks", "/account/settings"]);

export function safeNext(value, fallback = "/account/profile") {
    if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u001f]/.test(value)) return fallback;
    try {
        const url = new URL(value, "https://doku.invalid");
        if (url.origin !== "https://doku.invalid" || !PRIVATE_ROUTES.has(url.pathname)) return fallback;
        return `${url.pathname}${url.search}${url.hash}`;
    } catch { return fallback; }
}
export function resolveRoute(locationLike) {
    const pathname = locationLike.pathname || "/";
    // The deployed reader contract is query-based, including on the root path.
    const params = new URLSearchParams(locationLike.search || "");
    if (params.get("work") && params.get("chapter")) return { kind: "legacy-reader", pathname };
    if (pathname === "/account") return { kind: "redirect", to: "/account/profile" };
    if (KNOWN.has(pathname)) return { kind: pathname === "/" ? "home" : pathname.slice(1).replaceAll("/", "-"), pathname, private: PRIVATE_ROUTES.has(pathname) };
    if (pathname.startsWith("/account/")) return { kind: "account-not-found", pathname };
    return { kind: "not-found", pathname };
}
let handler;
export function startRouter(render) {
    if (handler) return;
    handler = () => render(resolveRoute(window.location));
    window.addEventListener("popstate", handler);
    document.addEventListener("click", event => {
        const anchor = event.target.closest?.("a[data-route]");
        if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || anchor.target) return;
        const url = new URL(anchor.href, window.location.href);
        if (url.origin !== window.location.origin) return;
        event.preventDefault(); navigate(`${url.pathname}${url.search}${url.hash}`);
    });
    handler();
}
export function navigate(url, { replace = false } = {}) {
    history[replace ? "replaceState" : "pushState"]({}, "", url);
    handler?.();
}
