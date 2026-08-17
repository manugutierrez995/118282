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

export function workUrl(slug, chapter = null) {
    const path = `/work/${encodeURIComponent(slug)}`;
    return chapter ? `${path}?chapter=${encodeURIComponent(chapter)}` : path;
}

function parseWorkPath(pathname, search = "") {
    if (!pathname.startsWith("/work/")) return null;
    const encodedSlug = pathname.slice("/work/".length);
    if (!encodedSlug || encodedSlug.includes("/")) return { kind: "not-found", pathname };
    try {
        const work = decodeURIComponent(encodedSlug);
        if (!work) return { kind: "not-found", pathname };
        return { kind: "work", work, chapter: new URLSearchParams(search || "").get("chapter"), pathname };
    } catch {
        return { kind: "not-found", pathname };
    }
}

export function resolveRoute(locationLike) {
    const pathname = locationLike.pathname || "/";
    // The deployed reader contract is query-based, including on the root path.
    const params = new URLSearchParams(locationLike.search || "");
    if (params.get("work") && params.get("chapter")) return { kind: "legacy-reader", work: params.get("work"), chapter: params.get("chapter"), pathname };
    const workRoute = parseWorkPath(pathname, locationLike.search || "");
    if (workRoute) return workRoute;
    if (pathname === "/account") return { kind: "redirect", to: "/account/profile" };
    if (LEGACY_PROFILE_ROUTES.has(pathname)) return { kind: "redirect", to: "/profiles?from=legacy-account" };
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
    const next = new URL(url, window.location.href);
    const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const target = `${next.pathname}${next.search}${next.hash}`;
    if (target !== current) history[replace ? "replaceState" : "pushState"]({}, "", target);
    handler?.();
}
