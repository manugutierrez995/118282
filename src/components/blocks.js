import blocksData from "../data/blocks.json";

const IMAGE_PATTERN = /\.(avif|bmp|gif|jpe?g|png|svg|webp)(\?.*)?$/i;
const HTML_PATTERN = /\.html?(\?.*)?$/i;
const PLACEMENTS = ["left", "center", "right"];
const activeSessions = new WeakMap();
const SAFETY_BACKGROUND = "#000000";

function isValidBackground(value) {
    if (typeof value !== "string" || !value.trim()) return false;
    const color = value.trim();
    if (typeof CSS !== "undefined" && typeof CSS.supports === "function") {
        return CSS.supports("color", color);
    }

    // Keep non-browser test environments safe without treating arbitrary CSS as a color.
    return /^(#(?:[\da-f]{3}|[\da-f]{4}|[\da-f]{6}|[\da-f]{8})|(?:rgb|hsl)a?\([^()]+\)|transparent|currentcolor)$/i.test(color);
}

export function resolveBlockBackground(item, defaults) {
    if (isValidBackground(item?.background)) return item.background.trim();
    if (isValidBackground(defaults?.background)) return defaults.background.trim();
    return SAFETY_BACKGROUND;
}

async function loadText(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.text();
}

function normalizeBlock(item) {
    if (typeof item !== "string") return item || null;

    const value = item.trim();
    if (value.startsWith("<")) return { embed: value };
    if (IMAGE_PATTERN.test(value)) return { image: value };
    if (HTML_PATTERN.test(value)) return { html: value };
    return { text: value };
}

function isEnabled(item, page) {
    const block = normalizeBlock(item);
    if (!block) return false;
    if (block.enabled === false || block.active === false || block.disabled === true) return false;
    const excluded = block.excludePages || block.exclude_pages || block.exclude || block.hiddenOn || block.hidden_on;
    if (Array.isArray(excluded) && excluded.includes(page)) return false;
    const pages = block.pages || block.includePages || block.include_pages || block.onlyPages || block.only_pages;
    if (Array.isArray(pages) && pages.length && !pages.includes(page)) return false;
    if (page === "reader" && (block.reader === false || block.readerEnabled === false || block.reader_enabled === false)) return false;
    return true;
}

function block(className, item = {}, background = SAFETY_BACKGROUND) {
    const element = document.createElement("section");
    element.className = ["site-block", className, item.className || item.class || ""].filter(Boolean).join(" ");
    element.style.backgroundColor = background;
    if (item.sticky) element.classList.add("site-block-sticky");
    return element;
}

function appendHtml(target, html) {
    const template = document.createElement("template");
    template.innerHTML = html;

    for (const script of template.content.querySelectorAll("script")) {
        const replacement = document.createElement("script");
        for (const attribute of script.attributes) {
            replacement.setAttribute(attribute.name, attribute.value);
        }
        replacement.textContent = script.textContent;
        script.replaceWith(replacement);
    }

    target.appendChild(template.content.cloneNode(true));
}

function imageBlock(item, background) {
    const element = block("image-block", item, background);
    const image = document.createElement("img");
    image.className = "block-image";
    image.src = item.image || item.src || item.url;
    image.alt = item.alt || item.title || "";
    image.loading = item.loading || "lazy";
    image.decoding = "async";
    if (item.width) image.width = item.width;
    if (item.height) image.height = item.height;

    if (item.href || item.link) {
        const link = document.createElement("a");
        link.href = item.href || item.link;
        link.target = item.target || "_blank";
        link.rel = item.rel || "noopener noreferrer";
        link.appendChild(image);
        element.appendChild(link);
    } else {
        element.appendChild(image);
    }

    return element;
}

function textBlock(item, background) {
    const element = block("text-block", item, background);
    if (item.title) {
        const title = document.createElement("h3");
        title.textContent = item.title;
        element.appendChild(title);
    }

    const body = item.body || item.text || item.content;
    if (body) {
        const paragraph = document.createElement("p");
        paragraph.textContent = body;
        element.appendChild(paragraph);
    }

    return element;
}

async function renderBlock(target, rawItem, defaults) {
    const item = normalizeBlock(rawItem);
    if (!item) return;
    const background = resolveBlockBackground(item, defaults);

    try {
        if (item.type === "rail-ad") {
            const element = block("rail-ad-block", item, background);
            const frame = document.createElement("div");
            frame.className = "rail-ad-frame";
            frame.style.backgroundColor = background;
            const iframe = document.createElement("iframe");
            iframe.className = "block-iframe rail-ad-iframe";
            iframe.src = item.src;
            iframe.title = item.title || "Sponsored content";
            iframe.width = item.width || 160;
            iframe.height = item.height || 600;
            iframe.loading = "lazy";
            iframe.scrolling = "no";
            iframe.setAttribute("frameborder", "0");
            iframe.setAttribute("marginwidth", "0");
            iframe.setAttribute("marginheight", "0");
            iframe.style.border = "0";
            iframe.style.backgroundColor = background;
            frame.appendChild(iframe);
            element.appendChild(frame);
            target.appendChild(element);
        } else if (item.html) {
            const element = block("html-block", item, background);
            appendHtml(element, await loadText(item.html));
            target.appendChild(element);
        } else if (item.image || item.src || IMAGE_PATTERN.test(item.url || "")) {
            target.appendChild(imageBlock(item, background));
        } else if (item.embed || item.code) {
            const element = block("embed-block", item, background);
            appendHtml(element, item.embed || item.code);
            target.appendChild(element);
        } else if (item.iframe || item.page) {
            const element = block("iframe-block", item, background);
            const iframe = document.createElement("iframe");
            iframe.className = "block-iframe";
            iframe.src = item.iframe || item.page;
            iframe.title = item.title || "Embedded content";
            iframe.loading = "lazy";
            iframe.scrolling = "no";
            iframe.style.border = "0";
            iframe.style.backgroundColor = background;
            if (item.width) iframe.width = item.width;
            if (item.height) iframe.height = item.height;
            element.appendChild(iframe);
            target.appendChild(element);
        } else if (item.title || item.body || item.text || item.content) {
            target.appendChild(textBlock(item, background));
        }
    } catch (error) {
        console.warn("Block failed:", item, error);
    }
}

async function buildBlock(rawItem, defaults) {
    const fragment = document.createDocumentFragment();
    await renderBlock(fragment, rawItem, defaults);
    return fragment;
}

async function renderBlocks(target, items = [], page = "landing", defaults) {
    if (!target) return;
    activeSessions.get(target)?.();
    const filtered = items.filter(item => isEnabled(item, page));
    const rendered = await Promise.all(filtered.map(item => buildBlock(item, defaults)));
    target.replaceChildren(...rendered);
    const cleanup = () => target.replaceChildren();
    activeSessions.set(target, cleanup);
    return cleanup;
}

export function createLandingBlockShell(root) {
    root.innerHTML = `
        <div id="blocks-shell" class="blocks-shell">
            <aside class="blocks-side"><div id="blocks-left" class="blocks-column"></div></aside>
            <main class="blocks-main"><div id="blocks-center" class="blocks-column"></div><div id="blocks-reader"></div></main>
            <aside class="blocks-side"><div id="blocks-right" class="blocks-column"></div></aside>
        </div>
    `;
}

function optionContainer(options, name, fallbackSelector) {
    if (Object.prototype.hasOwnProperty.call(options, name)) {
        const value = options[name];
        if (value === null) return null;
        if (typeof value === "string") return document.querySelector(value);
        return value;
    }
    if (!fallbackSelector) return null;
    return document.querySelector(fallbackSelector);
}

function itemsForPlacement(config, placement) {
    const raw = config?.[placement];
    if (!Array.isArray(raw)) return [];
    return raw.slice().sort((a, b) => (normalizeBlock(a)?.order ?? 0) - (normalizeBlock(b)?.order ?? 0));
}

export async function renderBlocksIntoContainers(options = {}) {
    const page = options.page || "landing";
    const config = options.blocksData || blocksData || {};
    const containers = {
        left: optionContainer(options, "left", "#blocks-left"),
        center: optionContainer(options, "center", "#blocks-center"),
        right: optionContainer(options, "right", "#blocks-right")
    };

    const cleanups = await Promise.all(PLACEMENTS.map(placement => renderBlocks(
        containers[placement],
        itemsForPlacement(config, placement),
        page,
        config.defaults
    )));
    return () => cleanups.forEach(cleanup => cleanup?.());
}

export class Blocks {
    static async start(options = {}) {
        if (Object.keys(options).length === 0) {
            const root = document.getElementById("blocks-root");
            if (!root) return;
            createLandingBlockShell(root);
            return renderBlocksIntoContainers({ page: "landing" });
        }

        return renderBlocksIntoContainers(options);
    }
}
