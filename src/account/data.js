import catalog from "../data/fetch.json";
import { getSupabase } from "../auth/supabase.js";

const manifests = import.meta.glob("../data/works/*.json", { eager: true, import: "default" });
const works = Array.isArray(catalog) ? catalog : catalog.works || [];
const byId = new Map();
for (const work of works) {
    const manifest = manifests[`../data/${work.manifest}`];
    const id = manifest?.parent_work_id;
    if (id !== undefined && id !== null) byId.set(String(id), { ...work, manifestData: manifest });
}
const run = async promise => { const { data, error } = await promise; if (error) throw error; return data; };

export async function listBookmarks(userId) {
    const db = await getSupabase();
    if (!db || !userId) throw new Error("Bookmarks are unavailable.");
    const rows = await run(db.from("bookmarks").select("work_id,created_at").eq("user_id", userId).order("created_at", { ascending: false }));
    return rows.map(row => ({ ...row, work: byId.get(String(row.work_id)) || null }));
}
export async function removeBookmark(userId, workId) {
    const db = await getSupabase();
    if (!db || !userId) throw new Error("Bookmarks are unavailable.");
    await run(db.from("bookmarks").delete().eq("user_id", userId).eq("work_id", String(workId)));
}
export function readerUrl(work) {
    const chapter = work?.manifestData?.chapters?.[0] || "chapter_1";
    return `/?source=${encodeURIComponent(work.source || "e")}&work=${encodeURIComponent(work.slug)}&chapter=${encodeURIComponent(chapter)}`;
}

