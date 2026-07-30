// Compatibility facade: discussion and account surfaces share one client.
export { getSupabase, isSupabaseConfigured as isDiscussionConfigured } from "../auth/supabase.js";
export { ensureAnonymousSession, continueWithGoogle } from "../auth/session.js";
import { getAuthState, initializeAuth } from "../auth/session.js";
export async function session() { await initializeAuth(); return getAuthState().session; }
