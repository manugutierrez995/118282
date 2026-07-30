import { inventory, placements } from "./config.js";
export function resolvePlacement(id) {
  const placement = placements.placements[id];
  const ad = placement && inventory.ads[placement.adId];
  return placement && ad ? { id, placement, adId: placement.adId, ad } : null;
}
export function deviceCategory(width = globalThis.innerWidth || 1024) { return width < 600 ? "mobile" : width < 1100 ? "tablet" : "desktop"; }
export function isCompatible(entry, width) {
  const device = deviceCategory(width);
  return (!entry.placement.devices || entry.placement.devices.includes(device)) && (!entry.ad.devices || entry.ad.devices.includes(device));
}
