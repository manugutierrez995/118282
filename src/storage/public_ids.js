import fetchData from "../data/fetch.json";
import idData from "../data/ID.json";

const MIN_PUBLIC_ID = 1000000;
const MAX_PUBLIC_ID = 9999999;
const DEFAULT_START_ID = 1199999;
const DEFAULT_STEP = 23;

function normalizeId(value) {
    if (value === null || value === undefined) return "";
    return String(value).trim();
}

function isValidPublicId(value) {
    return /^\d{7}$/.test(value) && Number(value) >= MIN_PUBLIC_ID && Number(value) <= MAX_PUBLIC_ID;
}

const configuredBySlug = new Map();
const idToSlug = new Map();
const usedIds = new Set();

for (const entry of idData.works || []) {
    const slug = String(entry?.slug || "").trim();
    const id = normalizeId(entry?.id);
    if (!slug) continue;

    configuredBySlug.set(slug, entry);

    if (!id) continue;
    if (!isValidPublicId(id)) {
        console.warn(`Ignoring invalid public ID ${id} for ${slug}`);
        continue;
    }
    if (idToSlug.has(id) && idToSlug.get(id) !== slug) {
        console.warn(`Ignoring duplicate public ID ${id} for ${slug}`);
        continue;
    }

    idToSlug.set(id, slug);
    usedIds.add(id);
}

const startId = Number(idData.settings?.start_id ?? DEFAULT_START_ID);
const step = Number(idData.settings?.step ?? DEFAULT_STEP);
let candidate = Number.isInteger(startId) && startId >= MIN_PUBLIC_ID && startId <= MAX_PUBLIC_ID
    ? startId
    : DEFAULT_START_ID;
const allocationStep = Number.isInteger(step) && step > 0 ? step : DEFAULT_STEP;

function allocateDefaultId() {
    while (candidate >= MIN_PUBLIC_ID) {
        const id = String(candidate).padStart(7, "0");
        candidate -= allocationStep;
        if (!usedIds.has(id)) {
            usedIds.add(id);
            return id;
        }
    }
    return null;
}

const slugToId = new Map();

for (const work of fetchData.works || []) {
    const slug = String(work?.slug || "").trim();
    if (!slug) continue;

    const configured = configuredBySlug.get(slug);
    const configuredId = normalizeId(configured?.id);
    let id = null;

    if (configuredId && isValidPublicId(configuredId) && idToSlug.get(configuredId) === slug) {
        id = configuredId;
    } else {
        id = allocateDefaultId();
        if (id) idToSlug.set(id, slug);
    }

    if (id) slugToId.set(slug, id);
}

export function publicIdForSlug(slug) {
    return slugToId.get(String(slug)) || null;
}

export function slugForPublicId(id) {
    const normalized = normalizeId(id);
    if (!isValidPublicId(normalized)) return null;
    return idToSlug.get(normalized) || null;
}

export function publicWorkPath(slug) {
    const id = publicIdForSlug(slug);
    return id ? `/${id}` : `/${encodeURIComponent(String(slug))}`;
}
