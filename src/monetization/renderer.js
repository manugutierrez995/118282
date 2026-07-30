import { inventory, placements } from "./config.js";
import { resolvePlacement, isCompatible } from "./registry.js";
import { appendExternalScript, copyScript } from "./script-loader.js";
import { createFallback } from "./fallback.js";

// A mount is initialized at most once. After initialization this module keeps no
// lifecycle state that can reinterpret or mutate provider-owned content.
const active = new WeakMap();

function preInitializationFallback(container, entry) {
  if (!entry || ["interstitial", "popunder"].includes(entry.ad.type) || entry.placement.fallback === "none") {
    container.hidden = true;
    return;
  }
  container.replaceChildren(createFallback(entry.ad, entry.placement.location === "reader"));
  container.hidden = false;
}

export function renderAdPlacement(container, placementId, options = {}) {
  if (!container) return () => {};
  if (active.has(container)) return active.get(container);

  const entry = resolvePlacement(placementId);
  const cleanup = () => active.delete(container);
  active.set(container, cleanup);

  if (!entry || !inventory.enabled || !placements.enabled || !placements.global.enabled || !entry.placement.enabled || !entry.ad.enabled) {
    preInitializationFallback(container, entry);
    return cleanup;
  }
  if (!isCompatible(entry, options.width)) {
    container.hidden = true;
    return cleanup;
  }

  container.hidden = false;
  container.classList.add("ad-placement");
  container.dataset.adPlacement = placementId;
  container.dataset.placement = placementId;
  if (entry.ad.size?.width) {
    container.style.setProperty("--ad-width", `${entry.ad.size.width}px`);
    container.style.setProperty("--ad-height", `${entry.ad.size.height}px`);
  }

  const host = document.createElement("div");
  host.className = "ad-provider-host";
  container.appendChild(host);

  queueMicrotask(() => {
    if (!host.isConnected || !active.has(container)) return;
    try {
      const template = document.createElement("template");
      template.innerHTML = entry.ad.snippet;
      for (const source of [...template.content.childNodes]) {
        if (source.nodeName === "SCRIPT") {
          if (source.getAttribute("src")) {
            // The network loader is shared. The placement's independent inline
            // serve command below is never shared or suppressed.
            appendExternalScript(source, document.head).promise.catch(error => console.warn("Advertisement provider script failed", error));
          } else {
            host.appendChild(copyScript(source));
          }
        } else {
          host.appendChild(source.cloneNode(true));
        }
      }
      // Provider ownership begins here. Do not inspect or alter `host` again.
    } catch (error) {
      // Parsing/initialization did not complete, so provider ownership never began.
      console.warn("Advertisement initialization failed", error);
      host.remove();
      preInitializationFallback(container, entry);
    }
  });

  return cleanup;
}

export function insertHeadMarkup(doc = document) {
  for (const id of placements.global.headMarkup || []) {
    const item = inventory.headMarkup[id];
    if (!item?.enabled) continue;
    const template = doc.createElement("template");
    template.innerHTML = item.snippet;
    for (const node of template.content.children) {
      if (node.tagName === "META" && ![...doc.head.querySelectorAll("meta")].some(current => current.getAttribute("http-equiv") === node.getAttribute("http-equiv") && current.getAttribute("content") === node.getAttribute("content"))) doc.head.append(node.cloneNode(true));
    }
  }
}
