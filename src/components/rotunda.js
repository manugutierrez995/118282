import { Storage } from "../storage/storage.js";
import { resolveManifest } from "../storage/manifest_resolver.js";
import { loadWork } from "../storage/work_manifest.js";
import rotunda from "../data/rotunda.json";
import tagCatalog from "../data/tags.json";
import { visibilityPolicyStore } from "./visibility_policy.js";
import { filterRotundaCandidates } from "../utils/tag.js";
import storage from "../data/storage.json";
import { ROTUNDA_MAX_MOUNTED, rotundaWindow } from "./rotunda_window.js";
import "../styles/rotunda.css";
import { getLocalProfileState, subscribeLocalProfiles } from "../local-profile/store.js";
import { navigate, workUrl } from "../router/router.js";
import { personalizeWorks } from "../local-profile/personalization.js";

export function personalizeRotundaCandidates(works, profile, catalog = tagCatalog) {
    return personalizeWorks(works, profile, catalog);
}

const ROTUNDA_METADATA_CACHE_MAX = 40;
const ROTUNDA_THUMBNAIL_CACHE_MAX = 40;
const ROTUNDA_REQUEST_CONCURRENCY = 4;
const ROTUNDA_SWIPE_THRESHOLD = 42;

function warnDev(message, error) {
    if (!import.meta.env.DEV) return;
    if (error) console.warn(message, error);
    else console.warn(message);
}

function uniqueUrls(urls) {
    return [...new Set(urls.filter(Boolean))];
}

function humanizeChapterPart(part) {
    const value = String(part || "").replace(/_/g, " ").trim();
    if (!value) return "";
    if (/^oneshot$/i.test(value)) return "Oneshot";
    return value.replace(/\b(volume|vol|chapter|ch)\s*([\d.]+)\b/gi, (_, kind, number) =>
        `${/^v/i.test(kind) ? "Volume" : "Chapter"} ${number}`
    ).replace(/\b\w/g, letter => letter.toUpperCase());
}

/** Turn storage chapter identifiers into UI copy without inventing a volume. */
export function formatChapterLabel(chapter, displayLabel) {
    if (displayLabel) return String(displayLabel);
    if (!chapter) return "";
    return String(chapter).split("/").filter(Boolean).map(humanizeChapterPart).filter(Boolean).join(" · ");
}

class LruCache {
    constructor(maximum) {
        this.maximum = maximum;
        this.values = new Map();
    }

    get(key) {
        if (!this.values.has(key)) return undefined;
        const value = this.values.get(key);
        this.values.delete(key);
        this.values.set(key, value);
        return value;
    }

    set(key, value) {
        this.values.delete(key);
        this.values.set(key, value);
        while (this.values.size > this.maximum) {
            this.values.delete(this.values.keys().next().value);
        }
        return value;
    }

    delete(key) { this.values.delete(key); }
    clear() { this.values.clear(); }
    get size() { return this.values.size; }
}

function openReader(card) {
    navigate(workUrl(card.slug));
}

function initialCard(work, sources, defaultSource) {
    const source = work.source || defaultSource;
    if (!sources[source]) {
        warnDev(`Rotunda: "${work.slug}" has an unknown source.`);
        return null;
    }
    const sourceThumb = `${Storage.work(source, work.slug)}/thumb.webp`;
    return {
        title: work.display || work.slug,
        slug: work.slug,
        source,
        chapter: work.chapters?.[0] || null,
        imageCandidates: uniqueUrls([work.thumb, sourceThumb])
    };
}

function isTypingTarget(target) {
    if (!(target instanceof Element)) return false;
    const tagName = target.tagName.toLowerCase();
    return tagName === "input" || tagName === "textarea" || tagName === "select" ||
        target.isContentEditable || Boolean(target.closest("[contenteditable='true']"));
}

export class Rotunda {
    static cleanup = null;

    static async start() {
        Rotunda.cleanup?.();

        const container = document.querySelector(".landing-rotunda");
        if (!container) return;

        const environment = storage.active;
        const sources = storage[environment]?.sources ?? {};
        const rawWorks = rotunda.works ?? [];
        let publicWorks;
        try { publicWorks = filterRotundaCandidates(rawWorks, await visibilityPolicyStore.refresh(), tagCatalog); }
        catch (error) { warnDev("Visibility refresh failed; keeping the public Rotunda.", error); publicWorks = filterRotundaCandidates(rawWorks, visibilityPolicyStore.get(), tagCatalog); }
        let works = personalizeRotundaCandidates(publicWorks, getLocalProfileState().status === "ready" ? getLocalProfileState().profile : null);
        const defaultSource = rotunda.default?.source || "e";
        const metadataCache = new LruCache(ROTUNDA_METADATA_CACHE_MAX);
        const thumbnailCache = new LruCache(ROTUNDA_THUMBNAIL_CACHE_MAX);
        const mounted = new Map();
        let absoluteActiveIndex = 0;
        let generation = 0;
        let renderController = null;
        let destroyed = false;
        let hovered = false;
        let touchStart = null;
        let touchMoved = false;
        const thumbnailStats = { started: 0, reused: 0, prevented: 0, stale: 0 };

        const viewport = document.createElement("div");
        viewport.className = "rotunda-scroll-viewport";
        const track = document.createElement("div");
        track.className = "rotunda-track";
        const status = document.createElement("div");
        status.className = "rotunda-status";
        status.setAttribute("aria-live", "polite");
        status.setAttribute("aria-atomic", "true");
        const caption = document.createElement("div");
        caption.className = "rotunda-active-caption";
        const titleViewport = document.createElement("div");
        titleViewport.className = "rotunda-title-viewport";
        const titleTrack = document.createElement("span");
        titleTrack.className = "rotunda-title-track";
        titleViewport.append(titleTrack);
        caption.append(titleViewport);
        viewport.append(track, caption, status);
        container.replaceChildren(viewport);

        function renderEmptyState(message = "No rotunda works available.") {
            track.replaceChildren();
            mounted.clear();
            updateCaption(null);
            status.textContent = message;
            const empty = document.createElement("p");
            empty.className = "rotunda-empty-state";
            empty.textContent = message;
            track.append(empty);
        }

        let captionMeasureFrame = 0;
        function measureCaption() {
            cancelAnimationFrame(captionMeasureFrame);
            titleTrack.classList.remove("is-overflowing");
            titleTrack.style.removeProperty("--ticker-distance");
            titleTrack.style.removeProperty("--ticker-duration");
            captionMeasureFrame = requestAnimationFrame(() => {
                captionMeasureFrame = 0;
                if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
                const overflow = titleTrack.scrollWidth - titleViewport.clientWidth;
                if (overflow > 1) {
                    titleTrack.style.setProperty("--ticker-distance", `${overflow}px`);
                    titleTrack.style.setProperty("--ticker-duration", `${Math.max(9, overflow / 22 + 5)}s`);
                    titleTrack.classList.add("is-overflowing");
                }
            });
        }

        let captionKey = null;
        function updateCaption(card) {
            const nextKey = `${card?.slug || ""}\u0000${card?.title || ""}`;
            if (captionKey === nextKey) return;
            captionKey = nextKey;
            titleTrack.classList.remove("is-overflowing");
            titleTrack.textContent = card?.title || "";
            titleTrack.title = card?.title || "";
            titleTrack.setAttribute("aria-label", card?.title || "");
            caption.setAttribute("aria-label", card?.title || "");
            measureCaption();
        }

        function clearImage(record, reason = "eviction") {
            if (import.meta.env.DEV && reason === "position" && record.loadedUrl) {
                console.warn("Rotunda retained thumbnail was cleared during a position-only update.", record.card?.slug);
            }
            record.imageAbort?.abort();
            record.imageAbort = null;
            record.img.onload = null;
            record.img.onerror = null;
            record.img.removeAttribute("src");
            record.button.style.removeProperty("--rotunda-reflection-image");
            record.loadedUrl = null;
            record.pendingUrl = null;
            record.thumbnailKey = null;
        }

        function unmount(record) {
            clearImage(record);
            record.button.onclick = null;
            record.button.remove();
        }

        function imageReady(url, signal) {
            return new Promise((resolve, reject) => {
                const image = new Image();
                image.decoding = "async";
                let settled = false;
                const finish = callback => { if (!settled) { settled = true; callback(url); } };
                image.onload = () => {
                    if (typeof image.decode === "function") image.decode().then(() => finish(resolve), () => finish(resolve));
                    else finish(resolve);
                };
                image.onerror = () => finish(() => reject(new Error(`Thumbnail failed: ${url}`)));
                signal.addEventListener("abort", () => finish(() => reject(new DOMException("Aborted", "AbortError"))), { once: true });
                image.src = url;
                if (image.complete && image.naturalWidth) finish(resolve);
            });
        }

        async function firstPageUrl(card, signal) {
            if (!card.chapter) return null;
            const key = Storage.manifest(card.source, card.slug, card.chapter);
            let promise = thumbnailCache.get(key);
            if (!promise) {
                promise = fetch(key, { signal }).then(response => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    return response.json();
                }).then(json => {
                    const manifest = resolveManifest(json, card.source, card.slug, card.chapter);
                    return `${manifest.base_url}/${String(1).padStart(manifest.padding ?? 3, "0")}.${manifest.extension || "webp"}`;
                }).catch(error => {
                    if (thumbnailCache.get(key) === promise) thumbnailCache.delete(key);
                    throw error;
                });
                thumbnailCache.set(key, promise);
            }
            return promise;
        }

        function setThumbnail(record, card) {
            const thumbnailKey = card.imageCandidates.join("\u0000");
            if (record.cardSlug === card.slug && record.thumbnailKey === thumbnailKey && (record.loadedUrl || record.pendingUrl)) {
                thumbnailStats.reused += 1;
                thumbnailStats.prevented += 1;
                return;
            }
            clearImage(record, "reassignment");
            const controller = new AbortController();
            record.imageAbort = controller;
            const assignment = ++record.assignmentGeneration;
            record.cardSlug = card.slug;
            record.thumbnailKey = thumbnailKey;
            record.pendingUrl = card.imageCandidates[0] || "fallback";
            record.button.classList.remove("is-thumbnail-ready", "is-thumbnail-failed");
            record.button.classList.add("is-thumbnail-loading");
            thumbnailStats.started += 1;
            (async () => {
                const candidates = [...card.imageCandidates];
                let applied = null;
                for (const url of candidates) {
                    try { applied = await imageReady(url, controller.signal); break; } catch (error) { if (error.name === "AbortError") return; }
                }
                if (!applied) {
                    try {
                        const fallback = await firstPageUrl(card, controller.signal);
                        if (fallback) applied = await imageReady(fallback, controller.signal);
                    } catch (error) { if (error.name === "AbortError") return; }
                }
                if (destroyed || controller.signal.aborted || record.assignmentGeneration !== assignment || record.cardSlug !== card.slug || record.thumbnailKey !== thumbnailKey) {
                    thumbnailStats.stale += 1;
                    return;
                }
                record.pendingUrl = null;
                record.button.classList.remove("is-thumbnail-loading");
                if (!applied) {
                    record.button.classList.add("is-thumbnail-failed");
                    return;
                }
                record.img.src = applied;
                record.button.style.setProperty("--rotunda-reflection-image", `url("${applied}")`);
                record.loadedUrl = applied;
                record.button.classList.add("is-thumbnail-ready");
            })();
        }

        function updateRecord(record, card, entry) {
            record.card = card;
            record.button.dataset.logicalIndex = String(entry.index);
            record.button.dataset.rotundaPosition = entry.visible ? String(entry.distance) : "buffered";
            record.button.dataset.rotundaDistance = String(Math.abs(entry.distance));
            record.button.classList.toggle("is-active", entry.distance === 0);
            record.button.setAttribute("aria-current", entry.distance === 0 ? "true" : "false");
            record.button.setAttribute("aria-hidden", entry.visible ? "false" : "true");
            record.button.tabIndex = entry.visible && Math.abs(entry.distance) <= 2 ? 0 : -1;
            const chapterText = formatChapterLabel(card.chapter, card.chapterDisplay);
            record.button.setAttribute("aria-label", card.chapter ? `Open ${card.title}, ${chapterText}` : card.title);
            record.img.alt = card.title;
            setThumbnail(record, card);
            if (entry.distance === 0) updateCaption(card);
        }

        function mount(entry, card) {
            const button = document.createElement("button");
            button.className = "rotunda-card";
            button.type = "button";
            const frame = document.createElement("div");
            frame.className = "rotunda-cover-frame";
            const img = document.createElement("img");
            img.className = "rotunda-cover";
            frame.append(img);
            button.append(frame);
            const record = { button, img, card: null, cardSlug: null, imageAbort: null, thumbnailKey: null, loadedUrl: null, pendingUrl: null, assignmentGeneration: 0 };
            button.onclick = () => {
                if (!touchMoved && record.card?.chapter) openReader(record.card);
            };
            updateRecord(record, card, entry);
            track.append(button);
            return record;
        }

        function diagnostics(entries = rotundaWindow(absoluteActiveIndex, works.length)) {
            const records = [...mounted.values()];
            return {
                totalLogicalWorks: works.length,
                totalCandidateWorks: rawWorks.length,
                activeLogicalIndex: works.length ? ((absoluteActiveIndex % works.length) + works.length) % works.length : 0,
                absoluteActiveIndex,
                mountedDomCardCount: track.querySelectorAll(".rotunda-card").length,
                loadedImageCount: records.filter(record => record.img.hasAttribute("src")).length,
                readyThumbnailCount: records.filter(record => record.button.classList.contains("is-thumbnail-ready")).length,
                loadingThumbnailCount: records.filter(record => record.button.classList.contains("is-thumbnail-loading")).length,
                failedThumbnailCount: records.filter(record => record.button.classList.contains("is-thumbnail-failed")).length,
                thumbnailAssignmentsStarted: thumbnailStats.started,
                thumbnailAssignmentsReused: thumbnailStats.reused,
                unnecessaryReloadsPrevented: thumbnailStats.prevented,
                staleThumbnailCompletionsDiscarded: thumbnailStats.stale,
                visibleIndices: entries.filter(entry => entry.visible).map(entry => entry.index),
                bufferedIndices: entries.filter(entry => !entry.visible).map(entry => entry.index),
                metadataCacheSize: metadataCache.size,
                thumbnailCacheSize: thumbnailCache.size,
                renderGeneration: generation
            };
        }

        function assertBounds(entries) {
            if (!import.meta.env.DEV) return;
            const info = diagnostics(entries);
            const visible = entries.filter(entry => entry.visible).map(entry => entry.index);
            if (info.mountedDomCardCount > ROTUNDA_MAX_MOUNTED) console.warn("Rotunda mounted-card limit exceeded.", info);
            if (info.loadedImageCount > ROTUNDA_MAX_MOUNTED) console.warn("Rotunda loaded-image limit exceeded.", info);
            if (new Set(visible).size !== visible.length) console.warn("Rotunda has duplicate visible logical works.", info);
            if (track.querySelectorAll('[aria-current="true"]').length > 1) console.warn("Rotunda has multiple active cards.", info);
        }

        async function resolveEntry(entry, localGeneration, signal) {
            const work = works[entry.index];
            const cached = metadataCache.get(work.slug);
            if (cached) return cached;
            const base = initialCard(work, sources, defaultSource);
            if (!base) return null;
            try {
                const resolved = await loadWork(work.slug, rotunda, { signal, cache: false });
                if (signal.aborted || localGeneration !== generation) return null;
                const source = resolved?.source || base.source;
                const chapter = resolved?.chapters?.[0];
                if (!sources[source] || !chapter) return { ...base, chapter: null };
                const card = {
                    ...base,
                    title: resolved.display || base.title,
                    source,
                    chapter,
                    chapterDisplay: resolved.chapter_labels?.[chapter] || resolved.chapterLabels?.[chapter],
                    imageCandidates: uniqueUrls([work.thumb, resolved.thumb, `${Storage.work(source, work.slug)}/thumb.webp`])
                };
                metadataCache.set(work.slug, card);
                return card;
            } catch (error) {
                if (error.name !== "AbortError") warnDev(`Rotunda: failed to load "${work.slug}".`, error);
                return null;
            }
        }

        function render() {
            if (!works.length) {
                generation += 1;
                renderController?.abort();
                for (const record of mounted.values()) unmount(record);
                mounted.clear();
                renderEmptyState(rawWorks.length ? "No rotunda works match the current visibility policy." : "No rotunda works available.");
                return;
            }
            generation += 1;
            const localGeneration = generation;
            renderController?.abort();
            renderController = new AbortController();
            const signal = renderController.signal;
            const entries = rotundaWindow(absoluteActiveIndex, works.length);
            const wanted = new Set(entries.map(entry => entry.index));
            for (const [index, record] of mounted) {
                if (!wanted.has(index)) {
                    unmount(record);
                    mounted.delete(index);
                }
            }
            for (const entry of entries) {
                const base = metadataCache.get(works[entry.index].slug) || initialCard(works[entry.index], sources, defaultSource);
                if (!base) continue;
                const existing = mounted.get(entry.index);
                if (existing) updateRecord(existing, base, entry);
                else mounted.set(entry.index, mount(entry, base));
            }
            const activeEntry = entries.find(entry => entry.distance === 0);
            if (activeEntry) status.textContent = `${works[activeEntry.index].display || works[activeEntry.index].slug}. Work ${activeEntry.index + 1} of ${works.length}.`;
            else status.textContent = "No works available.";
            assertBounds(entries);

            const prioritizedEntries = [...entries].sort((a, b) => Math.abs(a.distance) - Math.abs(b.distance));
            let cursor = 0;
            const worker = async () => {
                while (!signal.aborted && cursor < prioritizedEntries.length) {
                    const entry = prioritizedEntries[cursor++];
                    const card = await resolveEntry(entry, localGeneration, signal);
                    if (!card || signal.aborted || localGeneration !== generation) continue;
                    const record = mounted.get(entry.index);
                    if (record) updateRecord(record, card, entry);
                    if (entry.distance === 0) status.textContent = `${card.title}. Work ${entry.index + 1} of ${works.length}.`;
                }
                assertBounds(entries);
            };
            for (let i = 0; i < Math.min(ROTUNDA_REQUEST_CONCURRENCY, prioritizedEntries.length); i += 1) worker();
        }

        const moveBy = direction => {
            if (!works.length) return;
            absoluteActiveIndex += direction;
            render();
        };
        const keydown = event => {
            if (!hovered || isTypingTarget(event.target)) return;
            const direction = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
            if (!direction) return;
            event.preventDefault();
            moveBy(direction);
        };
        const pointerEnter = () => { hovered = true; };
        const pointerLeave = () => { hovered = false; };
        const pointerDown = event => {
            if (event.pointerType !== "mouse") touchStart = [event.clientX, event.clientY];
            touchMoved = false;
        };
        const pointerUp = event => {
            if (!touchStart) return;
            const [x, y] = touchStart;
            touchStart = null;
            const dx = event.clientX - x;
            const dy = event.clientY - y;
            if (Math.abs(dx) < ROTUNDA_SWIPE_THRESHOLD || Math.abs(dx) < Math.abs(dy)) return;
            touchMoved = true;
            moveBy(dx < 0 ? 1 : -1);
            window.setTimeout(() => { touchMoved = false; }, 0);
        };

        for (const [direction, label, glyph] of [[-1, "Show previous rotunda work", "‹"], [1, "Show next rotunda work", "›"]]) {
            const arrow = document.createElement("button");
            arrow.className = `rotunda-control-zone rotunda-control-zone-${direction < 0 ? "left" : "right"}`;
            arrow.type = "button";
            arrow.setAttribute("aria-label", label);
            const arrowGlyph = document.createElement("span");
            arrowGlyph.className = "rotunda-control-glyph";
            arrowGlyph.setAttribute("aria-hidden", "true");
            arrowGlyph.textContent = glyph;
            arrow.append(arrowGlyph);
            arrow.onclick = event => {
                event.preventDefault();
                event.stopPropagation();
                touchStart = null;
                touchMoved = false;
                moveBy(direction);
            };
            container.append(arrow);
        }
        container.addEventListener("pointerenter", pointerEnter);
        container.addEventListener("pointerleave", pointerLeave);
        viewport.addEventListener("pointerdown", pointerDown);
        viewport.addEventListener("pointerup", pointerUp);
        window.addEventListener("keydown", keydown);

        let lastCaptionWidth = titleViewport.clientWidth;
        let resizeTimer = 0;
        const resizeCaption = () => {
            clearTimeout(resizeTimer);
            resizeTimer = window.setTimeout(() => {
                const width = titleViewport.clientWidth;
                if (Math.abs(width - lastCaptionWidth) > 2) {
                    lastCaptionWidth = width;
                    measureCaption();
                }
            }, 160);
        };
        window.addEventListener("resize", resizeCaption, { passive: true });

        const policyChange = event => {
            publicWorks = filterRotundaCandidates(rawWorks, event.detail || visibilityPolicyStore.get(), tagCatalog);
            works = personalizeRotundaCandidates(publicWorks, getLocalProfileState().status === "ready" ? getLocalProfileState().profile : null);
            absoluteActiveIndex = works.length ? ((absoluteActiveIndex % works.length) + works.length) % works.length : 0;
            metadataCache.clear();
            render();
        };
        visibilityPolicyStore.addEventListener("change", policyChange);
        const unsubscribeProfile = subscribeLocalProfiles(state => {
            works = personalizeRotundaCandidates(publicWorks, state.status === "ready" ? state.profile : null);
            absoluteActiveIndex = works.length ? ((absoluteActiveIndex % works.length) + works.length) % works.length : 0;
            render();
        });

        if (import.meta.env.DEV) window.__rotundaDiagnostics = diagnostics;
        Rotunda.cleanup = () => {
            if (destroyed) return;
            destroyed = true;
            generation += 1;
            renderController?.abort();
            cancelAnimationFrame(captionMeasureFrame);
            clearTimeout(resizeTimer);
            window.removeEventListener("keydown", keydown);
            window.removeEventListener("resize", resizeCaption);
            visibilityPolicyStore.removeEventListener("change", policyChange);
            unsubscribeProfile();
            container.removeEventListener("pointerenter", pointerEnter);
            container.removeEventListener("pointerleave", pointerLeave);
            viewport.removeEventListener("pointerdown", pointerDown);
            viewport.removeEventListener("pointerup", pointerUp);
            for (const record of mounted.values()) unmount(record);
            mounted.clear();
            metadataCache.clear();
            thumbnailCache.clear();
            container.replaceChildren();
            if (import.meta.env.DEV && window.__rotundaDiagnostics === diagnostics) delete window.__rotundaDiagnostics;
            Rotunda.cleanup = null;
        };
        render();
    }
}
