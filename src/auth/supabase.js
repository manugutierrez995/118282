let clientPromise;

export const isSupabaseConfigured = () => Boolean(
    import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
);

export function getSupabase() {
    if (!isSupabaseConfigured()) return Promise.resolve(null);
    if (!clientPromise) {
        clientPromise = import("@supabase/supabase-js").then(({ createClient }) => createClient(
            import.meta.env.VITE_SUPABASE_URL,
            import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
            { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } }
        ));
    }
    return clientPromise;
}

