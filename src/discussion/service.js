import { getLocalProfileState, toggleLocalBookmark } from "../local-profile/store.js";
export async function bookmarkState(workId) { return Boolean(getLocalProfileState().profile?.bookmarks.some(item => item.workId === String(workId))); }
export async function toggleBookmark(workId) { return toggleLocalBookmark(String(workId)); }
