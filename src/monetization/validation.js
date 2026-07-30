export function validatePlacementManifest(manifest) {
  const errors=[];
  if (!manifest || manifest.version !== 1 || typeof manifest.placements !== "object") return {valid:false,errors:["Unsupported or missing placement manifest."]};
  if (typeof manifest.enabled !== "boolean" || typeof manifest.global?.enabled !== "boolean") errors.push("Global enabled flags are required.");
  for(const [id,p] of Object.entries(manifest.placements)){if(!/^[a-z][a-z0-9_]+$/.test(id))errors.push(`${id}: invalid name`);if(typeof p.enabled!=="boolean")errors.push(`${id}: enabled must be boolean`);if(typeof p.adId!=="string")errors.push(`${id}: adId is required`)}
  return {valid:!errors.length,errors};
}
export function publicAdContext(context={}) { return Object.fromEntries(["placement","pageType","viewport","publicCategory","format"].filter(key=>typeof context[key]==="string").map(key=>[key,context[key]])); }
