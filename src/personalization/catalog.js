import { normalizeTags } from "../utils/tag.js";
import { normalizeTag } from "../utils/tag.js";

export const ROTUNDA_BASE_WEIGHT = 1;
export const ROTUNDA_PREFERRED_BONUS = 0.75;
export const ROTUNDA_MAX_PREFERRED_BONUS = 2;

export function selectableVocabulary(artifact) {
    const seen = new Set();
    return (artifact?.tags || []).filter(entry => {
        const key = normalizeTag(entry.tag_key);
        if (!key || key === "manifest" || entry.status !== "active" || !entry.user_selectable || seen.has(key)) return false;
        seen.add(key); return true;
    }).map(entry => ({ ...entry, tag_key: normalizeTag(entry.tag_key) }));
}
export function resolveVocabularyTag(value, artifact) {
    const normalized = normalizeTag(value);
    return selectableVocabulary(artifact).find(entry => entry.tag_key === normalized || (entry.aliases || []).some(alias => normalizeTag(alias) === normalized))?.tag_key || null;
}

export function workTags(work, catalog) {
    const slug = String(work?.slug || work?.work || "");
    return normalizeTags(catalog?.works?.[slug]?.tags || work?.tags);
}
export const excludedMatch = (work, snapshot, catalog) => workTags(work, catalog).some(tag => snapshot.excluded?.has(tag));
export const preferredMatchCount = (work, snapshot, catalog) => workTags(work, catalog).filter(tag => snapshot.preferred?.has(tag)).length;
export function rotundaWeight(work, snapshot, catalog) {
    if (excludedMatch(work, snapshot, catalog)) return 0;
    return ROTUNDA_BASE_WEIGHT + Math.min(ROTUNDA_MAX_PREFERRED_BONUS, preferredMatchCount(work, snapshot, catalog) * ROTUNDA_PREFERRED_BONUS);
}
export function rankSearchMatches(matches, snapshot, catalog, cap = 12) {
    return matches.filter(entry => !excludedMatch(entry, snapshot, catalog))
        .map((entry, index) => ({ entry, index, preferred: preferredMatchCount(entry, snapshot, catalog) }))
        .sort((a, b) => b.preferred - a.preferred || a.index - b.index).slice(0, cap).map(item => item.entry);
}
function hash(value) { let h = 2166136261; for (const char of value) { h ^= char.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
function score(seed, slug, weight) { const uniform = (hash(`${seed}:${slug}`) + 1) / 4294967297; return -Math.log(uniform) / weight; }
export function personalizedRotundaOrder(works, snapshot, catalog, seed = "public") {
    const unique = [...new Map((works || []).map(work => [work.slug, work])).values()]
        .filter(work => !excludedMatch(work, snapshot, catalog));
    const preferred = unique.filter(work => preferredMatchCount(work, snapshot, catalog));
    const neutral = unique.filter(work => !preferredMatchCount(work, snapshot, catalog));
    preferred.sort((a, b) => score(seed, a.slug, rotundaWeight(a, snapshot, catalog)) - score(seed, b.slug, rotundaWeight(b, snapshot, catalog)));
    neutral.sort((a, b) => score(seed, a.slug, 1) - score(seed, b.slug, 1));
    if (!preferred.length) return neutral;
    const output = [], neutralEvery = 3;
    while (preferred.length || neutral.length) {
        if (neutral.length && (output.length % neutralEvery === neutralEvery - 1 || !preferred.length)) output.push(neutral.shift());
        else if (preferred.length) output.push(preferred.shift());
        else output.push(neutral.shift());
    }
    return output;
}
