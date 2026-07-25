import type { Placement } from "../specification/types.js";

const ANCHOR_ALIASES: Record<string, string[]> = {
  "top-banner": ["top"], top: ["top-banner"],
  "between-content": ["between-pages-banner"], "between-pages-banner": ["between-content"],
  "left-rail": ["left-skyscraper"], "left-skyscraper": ["left-rail"],
  "right-rail": ["right-skyscraper"], "right-skyscraper": ["right-rail"],
  "mobile-sticky": ["mobile-bottom"], "mobile-bottom": ["mobile-sticky"]
};

export function resolvePlacementTarget(placement: Placement): Element | null {
  if (placement.selector) return document.querySelector(placement.selector);
  const anchors = [placement.anchor, ...(ANCHOR_ALIASES[placement.anchor] ?? [])];
  for (const anchor of anchors) {
    const node = document.querySelector(`[data-ad-runner-slot="${cssEscape(anchor)}"]`);
    if (node) return node;
  }
  return null;
}
function cssEscape(value:string){return typeof CSS!=="undefined"&&CSS.escape?CSS.escape(value):value.replace(/[^a-zA-Z0-9_-]/g,"\\$&");}
