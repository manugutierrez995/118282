import inventory from "../data/monetization/ads.json" with { type: "json" };
import placements from "../data/monetization/placements.json" with { type: "json" };
export { inventory, placements };
export const monetizationEnabled = () => Boolean(inventory.enabled && placements.enabled && placements.global?.enabled);
