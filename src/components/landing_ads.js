const CONFIG_URL = "/ad-runner.json";
const SCRIPT_MARKER = "data-doku-landing-ad-runner";

const SLOT_GROUPS = {
    wide: [
        ["left-rail", 160, 600, "Skyscraper"],
        ["right-rail", 160, 600, "Skyscraper"]
    ],
    middle: [["banner", 728, 90, "Banner"]],
    mobile: [["mobile-intermission", 300, 250, "Mobile exhibit"]]
};

let session = null;

export function eligibleGroup(width) {
    if (width >= 1500) return "wide";
    if (width >= 768) return "middle";
    return "mobile";
}

function validConfiguration(value) {
    if (!value?.enabled || !value.siteId || !value.baseUrl) return null;
    try {
        const url = new URL(value.baseUrl);
        if (!/^https?:$/.test(url.protocol)) return null;
        return { ...value, baseUrl: url.href.replace(/\/$/, "") };
    } catch {
        return null;
    }
}

function sponsorFrame([slot, width, height, format]) {
    const frame = document.createElement("section");
    frame.className = `sponsored-exhibit sponsored-exhibit--${slot}`;
    frame.dataset.adSlotFrame = slot;
    frame.style.setProperty("--ad-width", `${width}px`);
    frame.style.setProperty("--ad-height", `${height}px`);

    const label = document.createElement("div");
    label.className = "sponsored-exhibit__label";
    label.textContent = "Sponsored";

    const host = document.createElement("div");
    host.className = "sponsored-exhibit__host";
    host.dataset.adRunnerSlot = slot;
    host.setAttribute("aria-label", `${format} advertisement`);
    frame.append(label, host);
    return frame;
}

function renderSlots(root, group) {
    for (const definition of SLOT_GROUPS[group]) {
        const frame = sponsorFrame(definition);
        const rail = definition[0] === "left-rail" ? root.querySelector("[data-ad-rail=left]")
            : definition[0] === "right-rail" ? root.querySelector("[data-ad-rail=right]")
                : root.querySelector("[data-ad-inline]");
        rail?.append(frame);
    }
}

async function readConfiguration() {
    const response = await fetch(CONFIG_URL, { cache: "no-store" });
    if (!response.ok) return null;
    return validConfiguration(await response.json());
}

export async function mountLandingAds(root = document.querySelector(".landing-exhibition")) {
    if (!root || document.body.classList.contains("reader-active")) return () => {};
    if (session?.root === root) return session.cleanup;
    session?.cleanup();

    let disposed = false;
    const cleanup = () => {
        if (disposed) return;
        disposed = true;
        window.AdRunner?.stop?.();
        root.querySelectorAll("[data-ad-slot-frame]").forEach(node => node.remove());
        document.querySelector(`script[${SCRIPT_MARKER}]`)?.remove();
        if (session?.root === root) session = null;
    };
    session = { root, cleanup };

    try {
        const config = await readConfiguration();
        if (!config || disposed || !root.isConnected) return cleanup;
        renderSlots(root, eligibleGroup(window.innerWidth));
        if (disposed) return cleanup;

        let script = document.querySelector(`script[${SCRIPT_MARKER}]`);
        if (!script) {
            script = document.createElement("script");
            script.src = `${config.baseUrl}/v1/ad-runner.min.js`;
            script.dataset.adRunnerSite = config.siteId;
            script.dataset.adRunnerBase = config.baseUrl;
            script.setAttribute(SCRIPT_MARKER, "");
            script.defer = true;
            script.addEventListener("error", cleanup, { once: true });
            document.head.append(script);
        }
    } catch {
        cleanup();
    }
    return cleanup;
}

export function cleanupLandingAds() {
    session?.cleanup();
}
