import { inventory, placements } from "./config.js";
import { resolvePlacement, isCompatible } from "./registry.js";
import { appendExternalScript, copyScript } from "./script-loader.js";
import { createFallback, sizeLabel } from "./fallback.js";

const active = new WeakMap();
const TERMINAL = new Set(["filled", "fallback", "collapsed"]);
const MEDIA = "iframe, img, video, canvas, object, embed";
const ignored = node => node?.nodeType === 1 && (node.matches?.('[data-ad-verification-ui="true"], [data-ad-fallback="true"]') || node.closest?.('[data-ad-verification-ui="true"], [data-ad-fallback="true"]'));

function label(entry, state, reason) {
  const node = document.createElement("output");
  node.className = "doku-ad-verification";
  node.dataset.adVerificationUi = "true";
  const bits = [entry.id, entry.adId, sizeLabel(entry.ad.size), entry.ad.provider];
  if (placements.verification.showProviderState) bits.push(`state: ${state}`);
  if (reason && placements.verification.showFallbackReason) bits.push(`reason: ${reason}`);
  node.textContent = bits.join(" · ");
  return node;
}

const dimensions = node => { const box = node.getBoundingClientRect?.(); return Boolean(box && (box.width > 0 || box.height > 0)); };

/** Inspect the complete provider-owned subtree without reading iframe documents. */
export function inspectProviderSlot(host, originalIns) {
  const nodes = [...host.querySelectorAll("*")].filter(node => !ignored(node) && node.tagName !== "SCRIPT" && node !== originalIns);
  const iframe = nodes.find(node => node.tagName === "IFRAME");
  const media = nodes.find(node => node.matches?.(MEDIA) && (node.tagName === "IFRAME" || dimensions(node)));
  const providerChildren = originalIns && originalIns.isConnected
    ? [...originalIns.children].filter(node => !ignored(node)) : [];
  const replaced = Boolean(originalIns && !originalIns.isConnected);
  const measurable = nodes.some(dimensions);
  const filled = Boolean(iframe || media || providerChildren.length || replaced || measurable);
  return { filled, claimed: filled || nodes.length > 0, iframe: Boolean(iframe), replaced };
}

export function renderAdPlacement(container, placementId, options = {}) {
  if (!container) return () => {};
  active.get(container)?.();
  const entry = resolvePlacement(placementId);
  const detection = placements.global.fillDetection || {};
  let disposed = false, timeout, graceTimeout, mutation, resize, intersection;
  let state = "configured", claimed = false, filled = false, originalIns = null;
  const host = document.createElement("div");
  host.className = "doku-ad-provider-host";
  host.dataset.adProviderOwned = "true";

  const clearTimers = () => { clearTimeout(timeout); clearTimeout(graceTimeout); };
  const setState = (next, reason = "") => {
    if (filled && next !== "filled") return;
    state = next; if (next === "filled") filled = true;
    container.dataset.state = state; container.dataset.reason = reason;
    container.querySelector(":scope > .doku-ad-verification")?.remove();
    if (placements.verification.enabled && placements.verification.showPlacementLabels && entry && !["interstitial", "popunder"].includes(entry.ad.type)) container.prepend(label(entry, state, reason));
  };
  const markFilled = () => {
    if (disposed || filled) return;
    clearTimers(); setState("filled"); mutation?.disconnect(); resize?.disconnect();
  };
  const markClaimed = () => {
    if (disposed || filled || claimed) return;
    claimed = true; setState("provider-claimed");
  };
  const inspect = () => {
    if (disposed || filled) return { filled };
    const result = inspectProviderSlot(host, originalIns);
    if (result.filled) markFilled(); else if (result.claimed) markClaimed();
    return result;
  };
  const collapse = reason => { if (filled) return; clearTimers(); host.remove(); container.hidden = true; setState("collapsed", reason); };
  const finalFallback = reason => {
    if (disposed || filled || TERMINAL.has(state)) return;
    const final = inspect();
    if (filled || claimed || final.filled || final.claimed) return;
    if (!entry || ["interstitial", "popunder"].includes(entry.ad.type) || entry.placement.fallback === "none") return collapse(reason);
    const fallback = createFallback(entry.ad, entry.placement.location === "reader");
    fallback.dataset.adFallback = "true";
    host.after(fallback); container.hidden = false;
    setState(/blocked|error|invalid/i.test(reason) ? "failed" : "genuinely-empty", reason);
    setState("fallback", reason);
  };
  const onTimeout = () => {
    if (disposed || filled) return;
    inspect();
    if (filled) return;
    if (claimed) {
      setState("provider-claimed", "awaiting provider creative");
      graceTimeout = setTimeout(() => { inspect(); if (!filled && !claimed) finalFallback("provider timeout: slot genuinely empty"); }, detection.claimedGracePeriodMs || 5000);
      return;
    }
    finalFallback("provider timeout: slot genuinely empty");
  };

  container.replaceChildren(host);
  if (!entry || !inventory.enabled || !placements.enabled || !placements.global.enabled || !entry.placement.enabled || !entry.ad.enabled) { finalFallback("configuration disabled"); return () => {}; }
  if (!isCompatible(entry, options.width)) { collapse("incompatible device"); return () => {}; }
  container.hidden = false; container.classList.add("doku-ad-placement"); container.dataset.placement = placementId; container.dataset.adId = entry.adId;
  if (entry.ad.size?.width) { container.style.setProperty("--ad-width", `${entry.ad.size.width}px`); container.style.setProperty("--ad-height", `${entry.ad.size.height}px`); }
  setState("mounting");

  const load = () => {
    if (disposed) return;
    setState("provider-loading");
    try {
      const template = document.createElement("template"); template.innerHTML = entry.ad.snippet;
      const external = [], inline = [];
      for (const source of [...template.content.childNodes]) {
        if (source.nodeName === "SCRIPT") (source.getAttribute("src") ? external : inline).push(source);
        else { const node = source.cloneNode(true); host.appendChild(node); if (!originalIns && node.nodeName === "INS") originalIns = node; }
      }
      mutation = new MutationObserver(records => {
        if (filled) return;
        const meaningful = records.some(record => !ignored(record.target) && [...record.addedNodes].some(node => !ignored(node)) || (record.type === "attributes" && record.target === originalIns));
        if (meaningful && detection.acceptProviderMutationAsClaimed !== false) markClaimed();
        inspect();
      });
      mutation.observe(host, { childList: true, subtree: true, attributes: true, characterData: true });
      if ("ResizeObserver" in globalThis) { resize = new ResizeObserver(inspect); resize.observe(host); }
      for (const source of external) appendExternalScript(source, host).promise.catch(() => { if (!claimed && !filled) finalFallback("provider blocked or errored"); });
      // Each mounted placement executes its own serve call after its fresh ins is connected.
      if (originalIns && !originalIns.isConnected) throw new Error("provider ins was not connected");
      for (const source of inline) host.appendChild(copyScript(source));
      timeout = setTimeout(onTimeout, detection.timeoutMs || 10000);
      inspect();
    } catch (error) { finalFallback(`invalid snippet: ${error.message}`); }
  };
  if (options.lazy && "IntersectionObserver" in globalThis) { intersection = new IntersectionObserver(rows => { if (rows.some(row => row.isIntersecting)) { intersection.disconnect(); load(); } }, { rootMargin: "400px" }); intersection.observe(container); } else queueMicrotask(load);
  const cleanup = () => { disposed = true; clearTimers(); mutation?.disconnect(); resize?.disconnect(); intersection?.disconnect(); container.replaceChildren(); container.hidden = true; active.delete(container); };
  active.set(container, cleanup); return cleanup;
}

export function insertHeadMarkup(doc = document) {
  for (const id of placements.global.headMarkup || []) {
    const item = inventory.headMarkup[id]; if (!item?.enabled) continue;
    const template = doc.createElement("template"); template.innerHTML = item.snippet;
    for (const node of template.content.children) if (node.tagName === "META" && ![...doc.head.querySelectorAll("meta")].some(current => current.getAttribute("http-equiv") === node.getAttribute("http-equiv") && current.getAttribute("content") === node.getAttribute("content"))) doc.head.append(node.cloneNode(true));
  }
}
