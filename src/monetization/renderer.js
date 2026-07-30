import { inventory, placements } from "./config.js";
import { resolvePlacement, isCompatible } from "./registry.js";
import { appendExternalScript, copyScript } from "./script-loader.js";
import { createFallback, sizeLabel } from "./fallback.js";
const active = new WeakMap();
const terminal = new Set(["filled", "fallback", "collapsed"]);
function label(entry, state, reason) {
  const node = document.createElement("output"); node.className = "doku-ad-verification";
  const bits = [entry.id, entry.adId, sizeLabel(entry.ad.size), entry.ad.provider];
  if (placements.verification.showProviderState) bits.push(`state: ${state}`);
  if (reason && placements.verification.showFallbackReason) bits.push(`reason: ${reason}`);
  node.textContent = bits.join(" · "); return node;
}
function measurable(root) {
  return [...root.querySelectorAll("iframe, video, img, canvas, object, embed")].some(node => node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0);
}
export function renderAdPlacement(container, placementId, options = {}) {
  if (!container) return () => {};
  active.get(container)?.();
  const entry = resolvePlacement(placementId);
  let disposed = false, timeout, mutation, resize, intersection;
  const setState = (state, reason = "") => {
    container.dataset.state = state; container.dataset.reason = reason;
    container.querySelector(":scope > .doku-ad-verification")?.remove();
    if (placements.verification.enabled && placements.verification.showPlacementLabels && entry && !["interstitial", "popunder"].includes(entry.ad.type)) container.prepend(label(entry, state, reason));
  };
  const collapse = reason => { container.replaceChildren(); container.hidden = true; setState("collapsed", reason); };
  const fallback = reason => {
    if (disposed || terminal.has(container.dataset.state)) return;
    if (!entry || ["interstitial", "popunder"].includes(entry.ad.type) || entry.placement.fallback === "none") return collapse(reason);
    container.replaceChildren(createFallback(entry.ad, entry.placement.location === "reader")); container.hidden = false; setState("fallback", reason);
  };
  if (!entry || !inventory.enabled || !placements.enabled || !placements.global.enabled || !entry.placement.enabled || !entry.ad.enabled) { fallback("configuration disabled"); return () => {}; }
  if (!isCompatible(entry, options.width)) { collapse("incompatible device"); return () => {}; }
  container.hidden = false; container.classList.add("doku-ad-placement"); container.dataset.placement = placementId; container.dataset.adId = entry.adId;
  if (entry.ad.size?.width) { container.style.setProperty("--ad-width", `${entry.ad.size.width}px`); container.style.setProperty("--ad-height", `${entry.ad.size.height}px`); }
  setState("waiting");
  const load = () => {
    if (disposed) return; setState("loading");
    try {
      const template = document.createElement("template"); template.innerHTML = entry.ad.snippet;
      for (const source of [...template.content.childNodes]) {
        if (source.nodeName === "SCRIPT") {
          if (source.getAttribute("src")) appendExternalScript(source, container).promise.catch(() => fallback("provider blocked or errored"));
          else container.appendChild(copyScript(source));
        } else container.appendChild(source.cloneNode(true));
      }
      const inspect = () => { if (measurable(container)) { clearTimeout(timeout); setState("filled"); mutation?.disconnect(); resize?.disconnect(); } };
      mutation = new MutationObserver(inspect); mutation.observe(container, { childList: true, subtree: true, attributes: true });
      if ("ResizeObserver" in globalThis) { resize = new ResizeObserver(inspect); resize.observe(container); }
      timeout = setTimeout(() => fallback("provider timeout: no measurable creative"), placements.global.fillTimeoutMs || 3000);
      inspect();
    } catch (error) { fallback(`invalid snippet: ${error.message}`); }
  };
  if (options.lazy && "IntersectionObserver" in globalThis) { intersection = new IntersectionObserver(rows => { if (rows.some(row => row.isIntersecting)) { intersection.disconnect(); load(); } }, { rootMargin: "400px" }); intersection.observe(container); } else queueMicrotask(load);
  const cleanup = () => { disposed = true; clearTimeout(timeout); mutation?.disconnect(); resize?.disconnect(); intersection?.disconnect(); container.replaceChildren(); container.hidden = true; active.delete(container); };
  active.set(container, cleanup); return cleanup;
}
export function insertHeadMarkup(doc = document) {
  for (const id of placements.global.headMarkup || []) {
    const item = inventory.headMarkup[id]; if (!item?.enabled) continue;
    const template = doc.createElement("template"); template.innerHTML = item.snippet;
    for (const node of template.content.children) {
      if (node.tagName === "META" && ![...doc.head.querySelectorAll("meta")].some(current => current.getAttribute("http-equiv") === node.getAttribute("http-equiv") && current.getAttribute("content") === node.getAttribute("content"))) doc.head.append(node.cloneNode(true));
    }
  }
}
