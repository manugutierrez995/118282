import { renderAdPlacement } from "../renderer.js";
export function renderAdRegion({ placement, mount, width, lazy = false } = {}) { return renderAdPlacement(mount, placement, { width, lazy }); }
