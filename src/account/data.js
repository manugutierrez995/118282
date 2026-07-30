import catalog from "../data/fetch.json";
import { getLocalProfileState, saveActiveProfile } from "../local-profile/store.js";
const manifests=import.meta.glob("../data/works/*.json",{eager:true,import:"default"}), works=Array.isArray(catalog)?catalog:catalog.works||[], byId=new Map();
for(const work of works){const manifest=manifests[`../data/${work.manifest}`],id=manifest?.parent_work_id;if(id!=null)byId.set(String(id),{...work,manifestData:manifest});byId.set(String(work.slug),{...work,manifestData:manifest});}
export async function listBookmarks(){return (getLocalProfileState().profile?.bookmarks||[]).map(row=>({...row,work:byId.get(String(row.workId))||null})).sort((a,b)=>b.createdAt.localeCompare(a.createdAt));}
export async function removeBookmark(_profileId,workId){const profile=getLocalProfileState().profile;if(!profile)throw new Error('Choose a local profile.');await saveActiveProfile({bookmarks:profile.bookmarks.filter(row=>row.workId!==String(workId))});}
export function readerUrl(work){const chapter=work?.manifestData?.chapters?.[0]||'chapter_1';return `/?source=${encodeURIComponent(work.source||'e')}&work=${encodeURIComponent(work.slug)}&chapter=${encodeURIComponent(chapter)}`;}
