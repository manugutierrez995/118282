import { getPlacement, monetizationConfig, placementEligible, viewportCategory } from "../placements.js";
import { MonetizationController } from "../controller.js";
import { houseProvider } from "../providers/house.js";
import { memeProvider } from "../providers/meme.js";

const sessions = new WeakMap();
function creativeNode(result, placementName) {
    const creative = result.creative;
    const element = creative.destination ? document.createElement("a") : document.createElement("div");
    element.className = `ad-creative ${result.fallback ? "ad-creative-meme" : "ad-creative-house"}`;
    if (creative.destination) element.href = creative.destination;
    element.setAttribute("aria-label", creative.accessibleLabel);
    const image = document.createElement("img"); image.src = creative.image; image.alt = ""; image.loading = "lazy"; image.decoding = "async";
    const copy = document.createElement("span"); copy.className = "ad-creative-copy";
    const label = document.createElement("small"); label.textContent = result.fallback ? "Site intermission" : "House promotion";
    const title = document.createElement("strong"); title.textContent = creative.title;
    const body = document.createElement("span"); body.textContent = creative.body || "";
    copy.append(label, title, body); element.append(image, copy); element.dataset.placement = placementName; return element;
}

export function renderAdRegion({ placement: name, mount, width = globalThis.innerWidth, development = monetizationConfig.developmentVisualization } = {}) {
    if (!mount) return () => {};
    sessions.get(mount)?.(); mount.replaceChildren();
    const placement = getPlacement(name);
    if (!placement || !placementEligible(name, width)) { mount.hidden = true; return () => {}; }
    mount.hidden = false; mount.className = `ad-region ad-region-${placement.layout}`; mount.dataset.placement = name; mount.dataset.state = "waiting";
    const format = placement.allowedFormats[0];
    const controller = new MonetizationController({ providers: placement.fallback === "collapse" ? [houseProvider] : [houseProvider, memeProvider], timeoutMs: monetizationConfig.providerTimeoutMs });
    let disposed = false, observer;
    const load = async () => {
        mount.dataset.state = "loading";
        const result = await controller.request({ placement: name, pageType: placement.pageType, viewport: viewportCategory(width), format });
        if (disposed || result.state === "stale") return;
        mount.replaceChildren(); mount.dataset.state = result.state === "filled" ? (result.fallback ? "fallback" : "filled") : "empty";
        if (result.state === "filled") mount.appendChild(creativeNode(result, name)); else if (placement.collapseWhenEmpty) mount.hidden = true;
        if (development) { const debug = document.createElement("pre"); debug.className = "ad-debug"; debug.textContent = `${name}\nstate: ${mount.dataset.state}\nformat: ${format}\nattempts: ${result.attempts?.map(a => `${a.provider}:${a.state}`).join(" → ") || "none"}\nwinner: ${result.provider || "none"}\nfallback: ${result.fallback ? "yes" : "no"}\nsize: ${mount.clientWidth} × ${mount.clientHeight}\ntimeout: ${result.attempts?.some(a => a.state === "timeout") ? "yes" : "no"}`; mount.appendChild(debug); }
    };
    if ("IntersectionObserver" in globalThis && placement.lazyThreshold !== "0px") { observer = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { observer.disconnect(); load(); } }, { rootMargin: placement.lazyThreshold }); observer.observe(mount); } else queueMicrotask(load);
    const cleanup = () => { disposed = true; observer?.disconnect(); controller.destroy(); mount.replaceChildren(); mount.hidden = true; sessions.delete(mount); };
    sessions.set(mount, cleanup); return cleanup;
}
