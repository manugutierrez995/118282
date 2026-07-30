import { inventory, placements } from "./config.js";
import { resolvePlacement, isCompatible } from "./registry.js";
import { appendExternalScript, copyScript } from "./script-loader.js";
import { createFallback } from "./fallback.js";

const active = new WeakMap();
const VISUAL_ELEMENTS = "iframe, img, video, canvas, object, embed";
const NON_CREATIVES = new Set(["SCRIPT", "STYLE", "LINK", "META", "NOSCRIPT", "TEMPLATE", "INS"]);
const ignored = node => node?.nodeType === 1 && (node.matches?.('[data-ad-verification-ui="true"], [data-ad-fallback="true"], [data-ad-measurement="true"]') || node.closest?.('[data-ad-verification-ui="true"], [data-ad-fallback="true"], [data-ad-measurement="true"]'));

const renderedBox = node => {
  const box = node.getBoundingClientRect?.();
  return box && { width: Math.max(0, box.width || 0), height: Math.max(0, box.height || 0) };
};

function visiblyStyled(node) {
  for (let current = node; current?.nodeType === 1; current = current.parentElement) {
    const style = globalThis.getComputedStyle?.(current);
    if (style && (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse" || Number.parseFloat(style.opacity) <= 0)) return false;
  }
  return true;
}

/**
 * Find provider-created rendered content. Cross-origin frames are deliberately
 * judged only by their element rectangle; their documents are never inspected.
 */
export function findVisibleProviderCreative(host, originalIns, baselineNodes = new Set(), policy = placements.global.fillDetection || {}) {
  if (!host) return null;
  const minimumWidth = policy.minimumVisibleWidth ?? 40;
  const minimumHeight = policy.minimumVisibleHeight ?? 20;
  const minimumArea = policy.minimumVisibleArea ?? 800;
  const nodes = [...host.querySelectorAll("*")];
  for (const node of nodes) {
    if (node === host || node === originalIns || baselineNodes.has(node) || ignored(node) || NON_CREATIVES.has(node.tagName) || node.isConnected === false) continue;
    // A wrapper is not evidence when all it does is inherit the site's reserved
    // slot. New leaf wrappers may, however, be provider-rendered visual nodes.
    if (!node.matches?.(VISUAL_ELEMENTS) && node.children?.length) continue;
    if (!visiblyStyled(node)) continue;
    if (node.tagName === "IMG" && ((node.complete === false) || (typeof node.naturalWidth === "number" && node.naturalWidth <= 0) || (typeof node.naturalHeight === "number" && node.naturalHeight <= 0))) continue;
    const box = renderedBox(node);
    if (!box || box.width < minimumWidth || box.height < minimumHeight || box.width * box.height < minimumArea) continue;
    return { node, box, kind: node.tagName.toLowerCase() };
  }
  return null;
}

/** Inspect activity and visible content independently. */
export function inspectProviderSlot(host, originalIns, baselineNodes = new Set(), policy = placements.global.fillDetection || {}) {
  const providerNodes = [...host.querySelectorAll("*")].filter(node => node !== originalIns && !baselineNodes.has(node) && !ignored(node) && !NON_CREATIVES.has(node.tagName));
  const creative = findVisibleProviderCreative(host, originalIns, baselineNodes, policy);
  const replaced = Boolean(originalIns && !originalIns.isConnected);
  return { filled: Boolean(creative), claimed: Boolean(creative || providerNodes.length || replaced), creative, replaced };
}

const afterLayout = callback => {
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => requestAnimationFrame(callback));
  else setTimeout(callback, 0);
};

export function renderAdPlacement(container, placementId, options = {}) {
  if (!container) return () => {};
  active.get(container)?.();
  const entry = resolvePlacement(placementId);
  const detection = placements.global.fillDetection || {};
  const verification = placements.verification || {};
  let disposed = false, timeout, graceTimeout, lateTimeout, mutation, resize, intersection;
  let state = "configured", claimed = false, filled = false, originalIns = null;
  let baselineNodes = new Set();
  const host = document.createElement("div");
  host.className = "doku-ad-provider-host";
  host.dataset.adProviderOwned = "true";

  const clearFallbackTimers = () => { clearTimeout(timeout); clearTimeout(graceTimeout); };
  const log = (next, reason) => {
    if (!verification.logToConsole || !import.meta.env?.DEV) return;
    console.info(`[ads] ${placementId}: ${next}${reason ? `, ${reason}` : ""}`);
  };
  const setState = (next, reason = "") => {
    if (filled && next !== "filled") return;
    if (state === next && (container.dataset.adReason || "") === reason) return;
    state = next;
    if (next === "filled") filled = true;
    if (verification.exposeDebugAttributes) {
      container.dataset.adPlacement = placementId;
      container.dataset.adState = state;
      if (entry) container.dataset.adProvider = entry.ad.provider;
      if (reason) container.dataset.adReason = reason; else delete container.dataset.adReason;
    }
    log(next, reason);
  };
  const stopObservers = () => { mutation?.disconnect(); resize?.disconnect(); };
  const markFilled = () => {
    if (disposed || filled) return;
    clearFallbackTimers(); clearTimeout(lateTimeout);
    container.querySelector(':scope > [data-ad-fallback="true"]')?.remove();
    setState("filled");
    stopObservers();
  };
  const markClaimed = () => {
    if (disposed || filled) return;
    claimed = true;
    setState("provider-claimed");
  };
  const inspect = () => {
    if (disposed || filled) return { filled };
    const result = inspectProviderSlot(host, originalIns, baselineNodes, detection);
    if (result.filled) markFilled(); else if (result.claimed) markClaimed();
    return result;
  };
  const collapse = reason => { if (filled) return; clearFallbackTimers(); stopObservers(); host.remove(); container.hidden = true; setState("collapsed", reason); };
  const showFallback = reason => {
    if (disposed || filled || state === "fallback" || state === "collapsed") return;
    if (inspect().filled) return;
    if (!entry || ["interstitial", "popunder"].includes(entry.ad.type) || entry.placement.fallback === "none") return collapse(reason);
    const fallback = createFallback(entry.ad, entry.placement.location === "reader");
    fallback.dataset.adFallback = "true";
    host.after(fallback); container.hidden = false;
    setState("genuinely-empty", reason);
    setState("fallback", reason);
    // Keep the existing observer briefly so an unusually late real creative wins.
    lateTimeout = setTimeout(stopObservers, detection.lateFillObservationMs ?? 10000);
  };
  const finalFallback = reason => {
    if (disposed || filled || state === "fallback" || state === "collapsed") return;
    if (inspect().filled) return;
    afterLayout(() => { if (!disposed && !filled && !inspect().filled) showFallback(reason); });
  };
  const onTimeout = () => {
    if (disposed || filled) return;
    inspect();
    if (filled) return;
    if (claimed) {
      setState("provider-claimed", "awaiting provider creative");
      graceTimeout = setTimeout(() => finalFallback("no visible creative"), detection.claimedGracePeriodMs ?? 5000);
    } else finalFallback("no visible creative");
  };

  container.replaceChildren(host);
  if (!entry || !inventory.enabled || !placements.enabled || !placements.global.enabled || !entry.placement.enabled || !entry.ad.enabled) { finalFallback("configuration disabled"); return () => {}; }
  if (!isCompatible(entry, options.width)) { collapse("incompatible device"); return () => {}; }
  container.hidden = false; container.classList.add("doku-ad-placement");
  if (entry.ad.size?.width) { container.style.setProperty("--ad-width", `${entry.ad.size.width}px`); container.style.setProperty("--ad-height", `${entry.ad.size.height}px`); }
  setState("mounting");

  const load = () => {
    if (disposed) return;
    setState("loading");
    try {
      const template = document.createElement("template"); template.innerHTML = entry.ad.snippet;
      const external = [], inline = [];
      for (const source of [...template.content.childNodes]) {
        if (source.nodeName === "SCRIPT") (source.getAttribute("src") ? external : inline).push(source);
        else { const node = source.cloneNode(true); host.appendChild(node); if (!originalIns && node.nodeName === "INS") originalIns = node; }
      }
      // Everything supplied by our configuration is baseline, including a
      // reserved-size ins/wrapper. Only later provider output can prove fill.
      baselineNodes = new Set(host.querySelectorAll("*"));
      mutation = new MutationObserver(records => {
        if (filled) return;
        const meaningful = records.some(record => !ignored(record.target) && (record.type === "attributes" || [...record.addedNodes].some(node => !ignored(node))));
        if (meaningful && detection.providerMutationMeansClaimedOnly !== false) markClaimed();
        inspect();
      });
      mutation.observe(host, { childList: true, subtree: true, attributes: true, characterData: true });
      if ("ResizeObserver" in globalThis) { resize = new ResizeObserver(inspect); resize.observe(host); }
      for (const source of external) appendExternalScript(source, host).promise.catch(() => { if (!claimed && !filled) finalFallback("provider unavailable"); });
      if (originalIns && !originalIns.isConnected) throw new Error("provider ins was not connected");
      for (const source of inline) host.appendChild(copyScript(source));
      timeout = setTimeout(onTimeout, detection.timeoutMs ?? 10000);
      inspect();
    } catch (error) { finalFallback(`invalid provider configuration: ${error.message}`); }
  };
  if (options.lazy && "IntersectionObserver" in globalThis) { intersection = new IntersectionObserver(rows => { if (rows.some(row => row.isIntersecting)) { intersection.disconnect(); load(); } }, { rootMargin: "400px" }); intersection.observe(container); } else queueMicrotask(load);
  const cleanup = () => { disposed = true; clearFallbackTimers(); clearTimeout(lateTimeout); stopObservers(); intersection?.disconnect(); container.replaceChildren(); container.hidden = true; active.delete(container); };
  active.set(container, cleanup); return cleanup;
}

export function insertHeadMarkup(doc = document) {
  for (const id of placements.global.headMarkup || []) {
    const item = inventory.headMarkup[id]; if (!item?.enabled) continue;
    const template = doc.createElement("template"); template.innerHTML = item.snippet;
    for (const node of template.content.children) if (node.tagName === "META" && ![...doc.head.querySelectorAll("meta")].some(current => current.getAttribute("http-equiv") === node.getAttribute("http-equiv") && current.getAttribute("content") === node.getAttribute("content"))) doc.head.append(node.cloneNode(true));
  }
}
