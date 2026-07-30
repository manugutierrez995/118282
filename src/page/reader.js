import { Storage } from "../storage/storage.js";
import { resolveManifest } from "../storage/manifest_resolver.js";
import { loadWork } from "../storage/work_manifest.js";
import { Blocks } from "../components/blocks.js";
import { Search } from "../components/search.js";
import { mountDiscussion } from "../discussion/discussion.js";
import { mountAccountNavigation } from "../account/navigation.js";
import { renderAdRegion } from "../monetization/components/ad-region.js";

// At most WINDOW_BEFORE + the active page + WINDOW_AFTER images are retained.
// Keep these deliberately conservative for Safari's decoded-image memory budget.
const WINDOW_BEFORE = 10;
const WINDOW_AFTER = 10;
const PRIORITY_PAGES = 3;
const ESTIMATED_ASPECT_RATIO = 2 / 3;

let currentReader = null;
let renderGeneration = 0;

async function getChapterList(workSlug) {
    const work = await loadWork(workSlug);
    return work?.chapters || [];
}

function openChapter(source, work, chapter) {
    window.dispatchEvent(new CustomEvent("open-reader", {
        detail: { source, work, chapter }
    }));
}

function chapterLabel(chapter) {
    return String(chapter)
        .replaceAll("_", " ")
        .replaceAll("/", " / ");
}

function setResponsiveButtonLabel(button, full, compact, accessibleLabel = full) {
    button.setAttribute("aria-label", accessibleLabel);
    const fullLabel = document.createElement("span");
    fullLabel.className = "reader-button-label-full";
    fullLabel.textContent = full;
    const compactLabel = document.createElement("span");
    compactLabel.className = "reader-button-label-compact";
    compactLabel.setAttribute("aria-hidden", "true");
    compactLabel.textContent = compact;
    button.append(fullLabel, compactLabel);
}

function buildReaderNavBar(source, work, chapter, chapters, options = {}) {
    const currentIndex = chapters.indexOf(chapter);

    const homeBar = document.createElement("div");
    homeBar.className = ["reader-home-bar", options.className].filter(Boolean).join(" ");

    const homeButton = document.createElement("button");
    homeButton.className = "reader-home-button";
    homeButton.type = "button";
    setResponsiveButtonLabel(homeButton, "Home", "⌂");
    homeButton.addEventListener("click", () => {
        document.body.classList.remove("reader-active");
        window.location.href = "/";
    });

    const prevButton = document.createElement("button");
    prevButton.className = "reader-home-button";
    prevButton.type = "button";
    setResponsiveButtonLabel(prevButton, "← Previous", "← Prev", "Previous chapter");
    prevButton.disabled = currentIndex <= 0;
    prevButton.addEventListener("click", () => {
        if (currentIndex > 0) {
            openChapter(source, work, chapters[currentIndex - 1]);
        }
    });

    const select = document.createElement("select");
    select.className = "reader-chapter-select";

    for (const item of chapters) {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = chapterLabel(item);
        option.selected = item === chapter;
        select.appendChild(option);
    }

    select.addEventListener("change", () => {
        openChapter(source, work, select.value);
    });

    const nextButton = document.createElement("button");
    nextButton.className = "reader-home-button";
    nextButton.type = "button";
    setResponsiveButtonLabel(nextButton, "Next →", "Next →", "Next chapter");
    nextButton.disabled = currentIndex < 0 || currentIndex >= chapters.length - 1;
    nextButton.addEventListener("click", () => {
        if (currentIndex >= 0 && currentIndex < chapters.length - 1) {
            openChapter(source, work, chapters[currentIndex + 1]);
        }
    });

    const lastButton = document.createElement("button");
    lastButton.className = "reader-home-button";
    lastButton.type = "button";
    setResponsiveButtonLabel(lastButton, "Last", "Last", "Last chapter");
    lastButton.disabled = chapters.length === 0 || currentIndex === chapters.length - 1;
    lastButton.addEventListener("click", () => {
        if (chapters.length > 0) {
            openChapter(source, work, chapters[chapters.length - 1]);
        }
    });

    const leftGroup = document.createElement("div");
    leftGroup.className = "reader-bar-left";

    const searchMount = options.search === false ? null : document.createElement("div");
    if (searchMount) searchMount.className = "reader-search";

    const middleGroup = document.createElement("div");
    middleGroup.className = "reader-bar-middle";

    const rightGroup = document.createElement("div");
    rightGroup.className = "reader-bar-right";

    leftGroup.appendChild(homeButton);
    if (searchMount) leftGroup.appendChild(searchMount);

    middleGroup.appendChild(prevButton);
    middleGroup.appendChild(select);
    middleGroup.appendChild(nextButton);

    const accountMount = document.createElement("nav");
    accountMount.setAttribute("aria-label", "Account controls");
    const cleanupAccount = mountAccountNavigation(accountMount, { compact: true });
    options.session?.cleanups?.push(cleanupAccount);
    rightGroup.append(lastButton, accountMount);

    homeBar.appendChild(leftGroup);
    homeBar.appendChild(middleGroup);
    homeBar.appendChild(rightGroup);

    return { homeBar, searchMount };
}

function buildReaderTopBar(source, work, chapter, chapters) {
    return buildReaderNavBar(source, work, chapter, chapters);
}



function installReaderChromeAutohide(bar, session) {
    let hideTimer = null;

    function showThenHide() {
        bar.classList.remove("reader-nav-hidden");

        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => {
            const searchOpen = Boolean(bar.querySelector(".search-results:not([hidden])"));
            const focusInside = bar.contains(document.activeElement);
            if (document.body.classList.contains("reader-active") && !bar.matches(":hover") && !focusInside && !searchOpen) {
                bar.classList.add("reader-nav-hidden");
            }
        }, 1400);
    }

    window.addEventListener("scroll", showThenHide, { passive: true });
    session.cleanups.push(() => {
        clearTimeout(hideTimer);
        window.removeEventListener("scroll", showThenHide);
    });

    bar.addEventListener("mouseenter", showThenHide);
    bar.addEventListener("focusin", showThenHide);
    bar.addEventListener("focusout", showThenHide);
    bar.addEventListener("search-state-change", showThenHide);
    session.cleanups.push(() => {
        bar.removeEventListener("mouseenter", showThenHide);
        bar.removeEventListener("focusin", showThenHide);
        bar.removeEventListener("focusout", showThenHide);
        bar.removeEventListener("search-state-change", showThenHide);
    });

    showThenHide();
}

function createVirtualReader(wrapper, manifest, session) {
    const pages = [];
    let activePage = 0;
    let windowStart = 0;
    let windowEnd = Math.min(manifest.pages - 1, WINDOW_AFTER);
    let observer = null;
    let scrollFrame = null;
    const intersecting = new Map();

    const pageUrl = index =>
        `${manifest.base_url}/${String(index + 1).padStart(manifest.padding, "0")}.${manifest.extension}`;

    function adjustKnownRatio(page, img) {
        if (!img.naturalWidth || !img.naturalHeight) return;
        const oldHeight = page.element.getBoundingClientRect().height;
        const top = page.element.getBoundingClientRect().top;
        page.ratio = img.naturalWidth / img.naturalHeight;
        page.element.style.aspectRatio = String(page.ratio);
        const newHeight = page.element.getBoundingClientRect().height;

        // Scroll anchoring is inconsistent on iOS. Explicitly compensate when a
        // corrected estimate belongs entirely above the viewport.
        if (top + oldHeight <= 0 && newHeight !== oldHeight) {
            window.scrollBy(0, newHeight - oldHeight);
        }
    }

    function unload(page) {
        if (!page.image) return;
        page.image.onload = null;
        page.image.onerror = null;
        page.image.removeAttribute("src");
        page.image.remove();
        page.image = null;
        page.element.classList.remove("reader-page-loaded");
    }

    function load(page) {
        if (page.image || page.failed || session.disposed) return;
        const img = document.createElement("img");
        page.image = img;
        img.className = "reader-page-image";
        img.alt = `Page ${page.index + 1}`;
        img.decoding = "async";
        img.loading = page.index < PRIORITY_PAGES ? "eager" : "lazy";
        if (page.index < PRIORITY_PAGES) img.fetchPriority = "high";

        img.onload = () => {
            if (session.disposed || page.image !== img) return;
            adjustKnownRatio(page, img);
            page.element.classList.add("reader-page-loaded");
            page.element.classList.remove("reader-page-error");
        };
        img.onerror = () => {
            if (session.disposed || page.image !== img) return;
            unload(page);
            page.failed = true;
            page.element.classList.add("reader-page-error");
            page.error.hidden = false;
        };
        page.element.insertBefore(img, page.error);
        img.src = page.url;
    }

    function updateWindow(nextActive) {
        activePage = Math.max(0, Math.min(manifest.pages - 1, nextActive));
        windowStart = Math.max(0, activePage - WINDOW_BEFORE);
        windowEnd = Math.min(manifest.pages - 1, activePage + WINDOW_AFTER);
        for (let index = 0; index < pages.length; index += 1) {
            if (index >= windowStart && index <= windowEnd) load(pages[index]);
            else unload(pages[index]);
        }
    }

    for (let index = 0; index < manifest.pages; index += 1) {
        const element = document.createElement("div");
        element.className = "reader-page";
        element.dataset.page = String(index + 1);
        element.style.aspectRatio = String(ESTIMATED_ASPECT_RATIO);

        const error = document.createElement("button");
        error.type = "button";
        error.className = "reader-page-retry";
        error.textContent = `Page ${index + 1} failed to load — tap to retry`;
        error.hidden = true;
        const page = { index, element, error, image: null, failed: false, ratio: null, url: pageUrl(index) };
        const retry = () => {
            if (session.disposed) return;
            page.failed = false;
            error.hidden = true;
            element.classList.remove("reader-page-error");
            load(page);
        };
        page.retry = retry;
        error.addEventListener("click", retry);
        element.appendChild(error);
        wrapper.appendChild(element);
        pages.push(page);
    }

    if ("IntersectionObserver" in window) {
        observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) intersecting.set(entry.target, entry);
                else intersecting.delete(entry.target);
            });
            // Measure only the handful of pages intersecting the expanded
            // viewport, never the entire chapter.
            const visible = [...intersecting.keys()]
                .map(element => ({ element, top: element.getBoundingClientRect().top }))
                .sort((a, b) => Math.abs(a.top) - Math.abs(b.top));
            if (visible.length) updateWindow(Number(visible[0].element.dataset.page) - 1);
        }, { rootMargin: "50% 0px 50% 0px", threshold: 0 });
        pages.forEach(page => observer.observe(page.element));
    } else {
        const findActive = () => {
            scrollFrame = null;
            const point = document.elementFromPoint(window.innerWidth / 2, Math.min(window.innerHeight / 2, window.innerHeight - 1));
            const page = point?.closest?.(".reader-page");
            if (page && wrapper.contains(page)) updateWindow(Number(page.dataset.page) - 1);
        };
        const onScroll = () => {
            if (scrollFrame === null) scrollFrame = requestAnimationFrame(findActive);
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        session.cleanups.push(() => window.removeEventListener("scroll", onScroll));
    }

    updateWindow(0);
    session.cleanups.push(() => {
        observer?.disconnect();
        intersecting.clear();
        if (scrollFrame !== null) cancelAnimationFrame(scrollFrame);
        pages.forEach(page => {
            page.error.removeEventListener("click", page.retry);
            unload(page);
        });
        pages.length = 0;
    });

    session.diagnostics = () => ({
        totalPages: manifest.pages,
        loadedImages: pages.reduce((count, page) => count + Number(Boolean(page.image)), 0),
        activePage: activePage + 1,
        virtualWindow: { start: windowStart + 1, end: windowEnd + 1 }
    });
}

function ensureReaderBlockLayout(container) {
    let layout = container.querySelector(":scope > .reader-block-layout");
    if (!layout) {
        container.replaceChildren();
        layout = document.createElement("div");
        layout.className = "reader-block-layout";

        const leftAside = document.createElement("aside");
        leftAside.className = "reader-block-side reader-block-side-left";
        const leftBlocks = document.createElement("div");
        leftBlocks.className = "reader-blocks-left blocks-column";
        leftAside.appendChild(leftBlocks);

        const content = document.createElement("main");
        content.className = "reader-content-area";

        const rightAside = document.createElement("aside");
        rightAside.className = "reader-block-side reader-block-side-right";
        const rightBlocks = document.createElement("div");
        rightBlocks.className = "reader-blocks-right blocks-column";
        rightAside.appendChild(rightBlocks);

        layout.appendChild(leftAside);
        layout.appendChild(content);
        layout.appendChild(rightAside);
        container.appendChild(layout);
    }

    return {
        layout,
        content: layout.querySelector(".reader-content-area"),
        left: layout.querySelector(".reader-blocks-left"),
        right: layout.querySelector(".reader-blocks-right")
    };
}

async function startReaderBlocks(layoutParts) {
    await Blocks.start({
        page: "reader",
        left: layoutParts.left,
        center: null,
        right: layoutParts.right
    });
}

async function renderManifestInto(root, manifestUrl, source, work, chapter) {
    if (!root || !manifestUrl) {
        console.warn("Reader: missing root or manifestUrl.");
        return;
    }

    currentReader?.dispose();
    const generation = ++renderGeneration;
    const session = {
        disposed: false,
        cleanups: [],
        diagnostics: () => null,
        dispose() {
            if (this.disposed) return;
            this.disposed = true;
            this.cleanups.splice(0).forEach(cleanup => cleanup());
        }
    };
    currentReader = session;
    document.body.classList.add("reader-active");

    let manifest;
    try {
        manifest = await fetch(manifestUrl).then(r => {
            if (!r.ok) {
                throw new Error(`Manifest failed: ${r.status}`);
            }
            return r.json();
        });
    } catch (error) {
        if (session.disposed) return;
        throw error;
    }

    if (session.disposed || generation !== renderGeneration) return;
    manifest = resolveManifest(manifest, source, work, chapter);
    let chapters;
    try {
        chapters = await getChapterList(work);
    } catch (error) {
        if (session.disposed) return;
        throw error;
    }
    if (session.disposed || generation !== renderGeneration) return;

    const wrapper = document.createElement("div");
    wrapper.className = "reader-pages";

    const { homeBar: readerBar, searchMount } = buildReaderNavBar(source, work, chapter, chapters, { session });
    wrapper.appendChild(readerBar);
    const destroySearch = await Search.start({ mount: searchMount, context: "reader" });
    if (destroySearch) session.cleanups.push(destroySearch);
    installReaderChromeAutohide(readerBar, session);

    const anchor = document.createElement("div");
    anchor.id = "chapter-start";
    wrapper.appendChild(anchor);

    createVirtualReader(wrapper, manifest, session);

    const chapterAd = document.createElement("aside");
    chapterAd.className = "reader-chapter-ad";
    chapterAd.setAttribute("aria-label", "Sponsored and site promotions");
    wrapper.appendChild(chapterAd);
    session.cleanups.push(renderAdRegion({ placement: "reader_chapter_end", mount: chapterAd }));

    const { homeBar: bottomReaderBar } = buildReaderNavBar(source, work, chapter, chapters, {
        className: "reader-bottom-bar",
        search: false,
        session
    });
    wrapper.appendChild(bottomReaderBar);

    const workManifest = await loadWork(work);
    if (session.disposed || generation !== renderGeneration) return;
    const parentWorkId = workManifest?.parent_work_id;
    if (parentWorkId !== undefined && parentWorkId !== null) {
        session.cleanups.push(mountDiscussion(wrapper, String(parentWorkId)));
    }

    const layoutParts = ensureReaderBlockLayout(root);
    layoutParts.content.replaceChildren(wrapper);
    startReaderBlocks(layoutParts).catch(error => console.warn("Reader blocks failed", error));

    const scrollTimer = setTimeout(() => {
        if (session.disposed) return;
        anchor.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }, 50);
    session.cleanups.push(() => clearTimeout(scrollTimer));
}

if (import.meta.env.DEV) {
    window.__animePlexReaderDiagnostics = () => currentReader?.diagnostics() || null;
}

export class Reader {
    static async start(work, chapter) {
        const container = document.getElementById("reader-container");

        if (!container) return;

        const source =
            new URLSearchParams(window.location.search).get("source") || "e";

        const manifestUrl = Storage.manifest(source, work, chapter);

        try {
            await renderManifestInto(container, manifestUrl, source, work, chapter);
        } catch (err) {
            console.error("Reader failed:", err);

            container.replaceChildren();
            container.innerHTML = `
                <div class="reader-error">
                    <h2>Failed to load chapter</h2>
                </div>
            `;
        }
    }
}

window.addEventListener("open-reader", async (e) => {
    const entry = e.detail;
    const root = document.getElementById("blocks-reader") || document.getElementById("blocks-root");

    if (!root) {
        console.warn("Reader: blocks-root missing. Refusing to wipe page.");
        return;
    }

    const source = entry.source || "e";
    const work = entry.work || entry.slug || entry.work_slug;
    const chapter = entry.chapter || entry.chapter_path;

    const manifestUrl =
        entry.manifest_url || Storage.manifest(source, work, chapter);

    try {
        await renderManifestInto(root, manifestUrl, source, work, chapter);
    } catch (err) {
        console.error("Reader failed:", err);

        root.innerHTML = `
            <div class="reader-error">
                <h2>Failed to load chapter</h2>
            </div>
        `;
    }
});
