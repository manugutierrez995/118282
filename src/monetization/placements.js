import manifest from "../data/monetization/placements.json" with { type: "json" };
import { validatePlacementManifest } from "./validation.js";

const validation = validatePlacementManifest(manifest);
if (!validation.valid) console.warn("Monetization manifest disabled:", validation.errors);

export const monetizationConfig = Object.freeze({ ...manifest.settings, enabled: validation.valid && manifest.settings.enabled });
export function viewportCategory(width = globalThis.innerWidth || 1024) { return width < 600 ? "mobile" : width < 1100 ? "tablet" : "desktop"; }
export function getPlacement(name) { return validation.valid ? manifest.placements[name] || null : null; }
export function placementEligible(name, width) {
    const placement = getPlacement(name);
    if (!monetizationConfig.enabled || !placement?.enabled) return false;
    return placement[viewportCategory(width)] !== "hide";
}
export { manifest as placementManifest };
