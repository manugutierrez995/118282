const RULES = [
    [/provider.*(disabled|not enabled)|unsupported provider/i, "Google sign-in is not enabled for this site. An administrator must enable it before you can continue.", "provider_disabled"],
    [/supabase.*not configured|publishable.*key|project url/i, "Accounts are not configured for this site yet.", "supabase_not_configured"],
    [/redirect.*(not allowed|rejected)|url.*allow/i, "Google could not return to this page because the return address is not approved.", "redirect_rejected"],
    [/callback|redirect_uri_mismatch/i, "Google and this site's sign-in callback do not match. An administrator must correct the Google client settings.", "callback_mismatch"],
    [/client[_ ]?(id|secret)|oauth client|invalid_client/i, "The site's Google sign-in credentials need administrator attention.", "client_configuration"],
    [/link.*(disabled|not enabled|manual)|identity.*link/i, "This anonymous account cannot be upgraded until identity linking is enabled by an administrator.", "identity_linking"],
    [/network|fetch|offline|timeout/i, "The sign-in service could not be reached. Check your connection and try again.", "network"],
    [/popup|cancel|interrupted|closed/i, "Google sign-in was interrupted before it finished. Please try again.", "interrupted"]
];

export function normalizeAuthError(error, operation = "authentication") {
    const raw = String(error?.message || error?.error_description || error || "Unknown provider failure").replace(/[\r\n]+/g, " ").slice(0, 300);
    const match = RULES.find(([pattern]) => pattern.test(`${error?.code || ""} ${error?.name || ""} ${raw}`));
    return {
        operation,
        code: match?.[2] || String(error?.code || "provider_failure").slice(0, 80),
        name: String(error?.name || "AuthError").slice(0, 80),
        message: raw,
        userMessage: match?.[1] || "Google sign-in could not be completed. Please try again or use email and password."
    };
}

export function reportAuthError(error, context = {}) {
    const normalized = normalizeAuthError(error, context.operation);
    console.error("Account authentication failed", {
        operation: normalized.operation,
        name: normalized.name,
        code: normalized.code,
        message: normalized.message,
        origin: globalThis.location?.origin || "unavailable",
        returnPath: context.returnPath,
        accountState: context.accountState
    });
    return normalized;
}
