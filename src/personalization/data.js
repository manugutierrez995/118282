import { getSupabase } from "../auth/supabase.js";
import { getAuthState } from "../auth/session.js";
import { normalizeTag } from "../utils/tag.js";

async function clientAndUser() {
    const client = await getSupabase(), user = getAuthState().user;
    if (!client || !user || user.is_anonymous) throw new Error("Tag preferences require a signed-in account.");
    return { client, user };
}
const result = async operation => { const { data, error } = await operation; if (error) throw error; return data || []; };
export async function loadPreferences() {
    const { client, user } = await clientAndUser();
    return result(client.from("user_tag_preferences").select("tag_key,preference_type").eq("user_id", user.id));
}
export async function setPreference(tagKey, preferenceType) {
    const { client } = await clientAndUser();
    return result(client.rpc("set_user_tag_preference", { p_tag_key: normalizeTag(tagKey), p_preference_type: preferenceType }));
}
export async function removePreference(tagKey) { const { client } = await clientAndUser(); return result(client.rpc("remove_user_tag_preference", { p_tag_key: normalizeTag(tagKey) })); }
export async function resetPreferences() { const { client } = await clientAndUser(); return result(client.rpc("reset_user_tag_preferences")); }
