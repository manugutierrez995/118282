import manifest from "../data/monetization/placements.json" with { type: "json" };
export const placementManifest = manifest;
export const monetizationConfig = Object.freeze({ enabled: manifest.enabled && manifest.global.enabled, providerTimeoutMs: manifest.global.fillTimeoutMs, developmentVisualization: manifest.verification.enabled });
export function viewportCategory(width = globalThis.innerWidth || 1024) { return width < 600 ? "mobile" : width < 1100 ? "tablet" : "desktop"; }
export function getPlacement(name) { return manifest.placements[name] || null; }
export function placementEligible(name, width) { const p=getPlacement(name); return Boolean(monetizationConfig.enabled && p?.enabled && (!p.devices || p.devices.includes(viewportCategory(width)))); }
export function deterministicValue(minimum, maximum, seed = 0) { const range = maximum - minimum + 1; return minimum + (Math.abs(seed) % Math.max(1, range)); }
export function readerBreaks(pageCount, config = getPlacement("reader_between_pages")) {
  if (!config?.enabled) return [];
  const every = config.frequency.mode === "fixed" ? config.frequency.everyPages : deterministicValue(config.frequency.minimumPages, config.frequency.maximumPages, pageCount);
  const count = config.adsPerBreak.mode === "fixed" ? config.adsPerBreak.count : deterministicValue(config.adsPerBreak.minimum, config.adsPerBreak.maximum, pageCount + 1);
  const breaks=[]; for(let page=every; page <= pageCount && breaks.length < config.maximumAdsPerChapter; page += every) { if(page < config.minimumPageBeforeFirstAd || (page===pageCount && !config.trailingAd)) continue; breaks.push({ afterPage:page, count }); } return breaks;
}
