const BEHAVIORS = new Set(["show", "show-inline", "hide"]);

export function validatePlacementManifest(manifest) {
    const errors = [];
    if (!manifest || manifest.version !== 1 || typeof manifest.placements !== "object") return { valid: false, errors: ["Unsupported or missing placement manifest."] };
    for (const [name, placement] of Object.entries(manifest.placements)) {
        if (!/^[a-z][a-z0-9_]+$/.test(name)) errors.push(`${name}: invalid name`);
        if (typeof placement.enabled !== "boolean") errors.push(`${name}: enabled must be boolean`);
        if (!Array.isArray(placement.allowedFormats) || !placement.allowedFormats.length) errors.push(`${name}: allowedFormats is required`);
        if (!Number.isInteger(placement.maxItems) || placement.maxItems < 1) errors.push(`${name}: maxItems must be positive`);
        for (const viewport of ["desktop", "tablet", "mobile"]) if (!BEHAVIORS.has(placement[viewport])) errors.push(`${name}: invalid ${viewport} behavior`);
        if (placement.minWidth > placement.maxWidth || placement.minHeight > placement.maxHeight) errors.push(`${name}: invalid dimensions`);
        if (typeof placement.collapseWhenEmpty !== "boolean") errors.push(`${name}: collapseWhenEmpty must be boolean`);
    }
    return { valid: errors.length === 0, errors };
}

export function publicAdContext(context = {}) {
    return Object.fromEntries(["placement", "pageType", "viewport", "publicCategory", "format"].filter(key => typeof context[key] === "string").map(key => [key, context[key]]));
}
