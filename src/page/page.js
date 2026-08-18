import { Landing } from "./landing.js";
import { Reader } from "./reader.js";
import { loadWork, workSource } from "../storage/work_manifest.js";
import { publicWorkPath, slugForPublicId } from "../storage/public_ids.js";
import { getLocalProfileState, subscribeLocalProfiles } from "../local-profile/store.js";
import { resolveRoute, startRouter, navigate } from "../router/router.js";
import { bookmarksView, notFoundView, profileView, profilesView, settingsView } from "../account/views.js";

let currentRoute, generation = 0;
let readerUrlSyncInstalled = false;
const root = () => document.getElementById("reader-container");
const focus = () => requestAnimationFrame(() => root()?.querySelector("h1")?.focus());

function showNotFound(account = false) {
    notFoundView(root(), account);
    return focus();
}

function syncOpenedWorkUrl(entry) {
    const work = entry?.work || entry?.slug || entry?.work_slug;
    if (!work) return;

    const nextPath = publicWorkPath(work);
    const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;

    // Work URLs are work-level for now, so chapter changes inside the same
    // work do not create duplicate history entries.
    if (currentPath !== nextPath) {
        history.pushState({}, "", nextPath);
    }

    // Keep Page's logical route aligned with the address bar without invoking
    // the router renderer. The existing open-reader listener owns the reader
    // render, so rerendering here would wipe/rebuild the landing shell.
    currentRoute = resolveRoute(window.location);
}

async function openCatalogWork(workSlug, id) {
    const work = await loadWork(workSlug);
    if (id !== generation) return;
    if (!work) return showNotFound();

    const chapters = work.chapters || [];
    if (!chapters.length) return showNotFound();

    // Build the exact same landing shell used by a normal homepage visit,
    // then hand the resolved work to the existing open-reader pipeline.
    await Landing.start();
    if (id !== generation) return;

    window.dispatchEvent(new CustomEvent("open-reader", {
        detail: {
            source: workSource(work),
            work: work.slug || workSlug,
            chapter: chapters[0]
        }
    }));
}

async function openWorkIdRoute(route, id) {
    const workSlug = slugForPublicId(route.id);
    if (!workSlug) return showNotFound();
    return openCatalogWork(workSlug, id);
}

async function openWorkSlugRoute(route, id) {
    return openCatalogWork(route.work, id);
}

async function render(route) {
    const id = ++generation;
    document.body.classList.remove("reader-active");

    if (route.kind === "redirect") return navigate(route.to, { replace: true });

    if (route.kind === "legacy-reader") {
        const p = new URLSearchParams(location.search);
        return Reader.start(p.get("work"), p.get("chapter"));
    }

    if (route.kind === "work-id") return openWorkIdRoute(route, id);
    if (route.kind === "work-slug") return openWorkSlugRoute(route, id);
    if (route.kind === "home") return Landing.start();
    if (route.kind === "account-not-found" || route.kind === "not-found") return showNotFound(route.kind === "account-not-found");

    const state = getLocalProfileState();
    if (route.kind === "profiles" || route.kind === "profiles-new") profilesView(root(), state, route.kind === "profiles-new");
    else if (!state.profile) return navigate("/profiles", { replace: true });
    else if (route.kind === "account-profile") profileView(root(), state.profile);
    else if (route.kind === "account-bookmarks") await bookmarksView(root(), state.profile);
    else if (route.kind === "account-settings") settingsView(root(), state.profile);

    if (id === generation) focus();
}

export class Page {
    static async start() {
        if (!readerUrlSyncInstalled) {
            readerUrlSyncInstalled = true;
            window.addEventListener("open-reader", event => syncOpenedWorkUrl(event.detail));
        }

        subscribeLocalProfiles(() => currentRoute && render(currentRoute));
        startRouter(route => {
            currentRoute = route;
            return render(route);
        });
    }
}
