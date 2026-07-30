import { publicAdContext } from "./validation.js";

const initialized = new WeakSet();
export async function requestWithTimeout(provider, context, timeoutMs, signal) {
    let timer;
    try {
        if (!initialized.has(provider)) { await provider.initialize?.(); initialized.add(provider); }
        return await Promise.race([
            provider.request(context, signal),
            new Promise(resolve => { timer = setTimeout(() => resolve({ state: "timeout" }), timeoutMs); })
        ]);
    } catch (error) { return { state: "error", error }; }
    finally { clearTimeout(timer); }
}

export class MonetizationController {
    constructor({ providers = [], timeoutMs = 800 } = {}) { this.providers = providers; this.timeoutMs = timeoutMs; this.generation = 0; this.abortController = null; }
    async request(context) {
        const generation = ++this.generation;
        this.abortController?.abort();
        this.abortController = new AbortController();
        const safeContext = publicAdContext(context);
        const attempts = [];
        for (const provider of this.providers) {
            if (!provider.supports?.(safeContext)) continue;
            const result = await requestWithTimeout(provider, safeContext, context.timeoutMs || this.timeoutMs, this.abortController.signal);
            attempts.push({ provider: provider.id, state: result?.state || "invalid" });
            if (generation !== this.generation) return { state: "stale", attempts };
            if (result?.state === "filled") return { ...result, provider: provider.id, attempts, generation };
        }
        return { state: "no-fill", attempts, generation };
    }
    destroy() { this.generation += 1; this.abortController?.abort(); this.providers.forEach(provider => provider.destroy?.()); }
}
