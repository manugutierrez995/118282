import { normalize } from "../utils/normalize.js";
import tagCatalog from "../data/tags.json";
import { getLocalProfileState, subscribeLocalProfiles } from "../local-profile/store.js";
import { personalizeWorks } from "../local-profile/personalization.js";
import { renderAdRegion } from "../monetization/components/ad-region.js";

const SEARCH_INDEX_URL = "/data/search.index.json";
let searchIndexPromise = null;

function loadSearchIndex() {
    if (!searchIndexPromise) {
        searchIndexPromise = fetch(SEARCH_INDEX_URL, {
            cache: "no-store",
        })
            .then(response => {
                if (!response.ok) throw new Error(`Search index failed: ${response.status}`);
                return response.json();
            })
            .then(data => data.entries || []);
    }

    return searchIndexPromise;
}

function hide(results) {
    results.hidden = true;
    results.innerHTML = "";
}

function emitOpen(entry) {
    window.dispatchEvent(new CustomEvent("open-reader", {
        detail: entry
    }));
}

function renderResults(container, matches) {
    container.hidden = matches.length === 0;
    const nodes = matches.map((entry, index) => {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "search-result";
        el.setAttribute("role", "option");
        el.textContent = entry.display;
        el.dataset.resultIndex = String(index);
        return el;
    });
    if (matches.length > 6) {
        const sponsored = document.createElement("div");
        sponsored.className = "search-sponsored-region";
        sponsored.setAttribute("role", "group");
        sponsored.setAttribute("aria-label", "Sponsored or site promotion");
        nodes.splice(6, 0, sponsored);
    }
    container.replaceChildren(...nodes);
    const sponsored = container.querySelector(".search-sponsored-region");
    return sponsored ? renderAdRegion({ placement: "search_after_6", mount: sponsored }) : null;
}

export function personalizeSearchResults(entries, profile, maximum = 12, catalog = tagCatalog) {
    return personalizeWorks(entries, profile, catalog, maximum);
}

export class Search {
    static async start(options = {}) {
        const mount = options instanceof Element
            ? options
            : options.mount || document.querySelector(".landing-search");
        if (!mount) return;

        const context = options instanceof Element ? "landing" : options.context || "landing";
        const controller = new AbortController();
        const { signal } = controller;
        let hideTimer = null;

        mount.innerHTML = `
            <div class="search-box">
                <span class="search-icon" aria-hidden="true">⌕</span>
                <input class="search-input" type="search" placeholder="Search Doku-Doujin…" aria-label="Search Doku-Doujin" autocomplete="off" />
                <div class="search-results" role="listbox" hidden></div>
            </div>
        `;

        const input = mount.querySelector(".search-input");
        const results = mount.querySelector(".search-results");

        let activeMatches = [];
        let activeAdCleanup = null;
        let activeIndex = -1;
        let lastQuery = "";

        const announceState = () => mount.dispatchEvent(new CustomEvent("search-state-change", {
            bubbles: true,
            detail: { open: !results.hidden, focused: document.activeElement === input }
        }));
        const close = () => {
            hide(results);
            activeIndex = -1;
            announceState();
        };

        input.addEventListener("focus", () => {
            loadSearchIndex().catch(error => console.warn("search index failed", error));
        }, { once: true, signal });

        input.addEventListener("blur", () => {
            clearTimeout(hideTimer);
            hideTimer = setTimeout(close, 250);
            announceState();
        }, { signal });

        function openResult(result) {
            const entry = activeMatches[Number(result.dataset.resultIndex)];
            if (!entry) return;

            clearTimeout(hideTimer);
            close();
            input.value = "";
            emitOpen(entry);
        }

        // Pointerdown fires before another layer or focus change can swallow the click.
        results.addEventListener("pointerdown", event => {
            if (!(event.target instanceof Element)) return;

            const result = event.target.closest(".search-result");
            if (!result) return;

            event.preventDefault();
            event.stopPropagation();
            openResult(result);
        }, { signal });

        // Preserve keyboard-generated and synthetic clicks.
        results.addEventListener("click", event => {
            if (!(event.target instanceof Element)) return;

            const result = event.target.closest(".search-result");
            if (!result || event.detail !== 0) return;

            openResult(result);
        }, { signal });

        results.addEventListener("pointerenter", () => {
            clearTimeout(hideTimer);
        }, { signal });

        // -----------------------------
        // INPUT SEARCH
        // -----------------------------
        input.addEventListener("input", async () => {
            const query = input.value;
            const q = normalize(query);
            const tokens = q.split(" ").filter(Boolean);

            if (!tokens.length) {
                activeMatches = [];
                close();
                return;
            }

            const index = await loadSearchIndex();

            if (query !== input.value) return;

            activeMatches = [];
            for (const entry of index) {
                if (tokens.every(token => entry.normalized?.includes(token))) {
                    activeMatches.push(entry);
                }
            }
            activeMatches = personalizeSearchResults(activeMatches, getLocalProfileState().status === "ready" ? getLocalProfileState().profile : null);
            lastQuery = query;

            activeAdCleanup?.();
            activeAdCleanup = renderResults(results, activeMatches);
            activeIndex = -1;
            clearTimeout(hideTimer);
            announceState();
        }, { signal });

        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                input.value = "";
                close();
                input.blur();
            } else if ((event.key === "ArrowDown" || event.key === "ArrowUp") && activeMatches.length) {
                event.preventDefault();
                activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + activeMatches.length) % activeMatches.length;
                results.querySelectorAll(".search-result").forEach((result, index) => {
                    result.classList.toggle("is-active", index === activeIndex);
                });
            } else if (event.key === "Enter" && activeIndex >= 0) {
                event.preventDefault();
                openResult(results.querySelector(`[data-result-index="${activeIndex}"]`));
            }
        }, { signal });

        mount.dataset.searchContext = context;
        const unsubscribe = subscribeLocalProfiles(() => { if (lastQuery && input.value === lastQuery) input.dispatchEvent(new Event("input")); });
        return () => {
            activeAdCleanup?.();
            unsubscribe();
            controller.abort();
            clearTimeout(hideTimer);
            mount.replaceChildren();
        };
    }
}
