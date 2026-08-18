const KNOWN = new Set(["/", "/profiles", "/profiles/new", "/account/profile", "/account/bookmarks", "/account/settings"]);
const LEGACY_PROFILE_ROUTES = new Set(["/login", "/signup", "/forgot-password", "/reset-password"]);
export const PRIVATE_ROUTES = new Set(["/account/profile", "/account/bookmarks", "/account/settings"]);

export function safeNext(value, fallback = "/account/profile") {
    if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u001f]/.test(value)) return fallback;
    try {
        const url = new URL(value, "https://doku.invalid");
        if (url.origin !== "https://doku.invalid" || !PRIVATE_ROUTES.has(url.pathname)) return fallback;
        return `${url.pathname}${url.search}${url.hash}`;
    } catch { return fallback; }
}

function parsePublicWorkIdPath(pathname) {
    const match = /^\/(\d{7})$/.exec(pathname);
    if (!match) return null;
    return { kind: "work-id", id: match[1], pathname };
}

function parseWorkSlugPath(pathname) {
    if (!pathname.startsWith("/") || pathname === "/") return null;

    const encodedSlug = pathname.slice(1);
    if (!encodedSlug || encodedSlug.includes("/")) return null;

    try {
        const work = decodeURIComponent(encodedSlug);
        if (!work) return null;
        return { kind: "work-slug", work, pathname };
    } catch {
        return { kind: "not-found", pathname };
    }
}

export function resolveRoute(locationLike) {
    const pathname = locationLike.pathname || "/";
    // The deployed reader contract is query-based, including on the root path.
    const params = new URLSearchParams(locationLike.search || "");
    if (params.get("work") && params.get("chapter")) return { kind: "legacy-reader", pathname };
    if (pathname === "/account") return { kind: "redirect", to: "/account/profile" };
    if (LEGACY_PROFILE_ROUTES.has(pathname)) return { kind: "redirect", to: "/profiles?from=legacy-account" };
    if (KNOWN.has(pathname)) return { kind: pathname === "/" ? "home" : pathname.slice(1).replaceAll("/", "-"), pathname, private: PRIVATE_ROUTES.has(pathname) };
    if (pathname.startsWith("/account/")) return { kind: "account-not-found", pathname };

    const publicIdRoute = parsePublicWorkIdPath(pathname);
    if (publicIdRoute) return publicIdRoute;

    const workRoute = parseWorkSlugPath(pathname);
    if (workRoute) return workRoute;

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
