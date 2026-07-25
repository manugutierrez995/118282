import type { AdNetworkAdapter } from "./registry.js";
import type { AdUnit, CandidateResult } from "../specification/types.js";

function numeric(unit: AdUnit, key: string, fallback: number): number {
  const value = Number(unit[key] ?? fallback);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export function iframeDocument(markup: string, headMarkup = ""): string {
  return `<!doctype html><html><head><meta charset="utf-8"><base target="_blank">${headMarkup}</head><body>${markup}</body></html>`;
}

export const externalTagAdapter: AdNetworkAdapter = {
  id: "external-tag",
  async mount(unit, container, ctx, signal) {
    if (signal.aborted) throw new DOMException("aborted", "AbortError");
    const iframe = document.createElement("iframe");
    iframe.setAttribute("sandbox", "allow-scripts allow-popups allow-popups-to-escape-sandbox");
    iframe.setAttribute("referrerpolicy", "no-referrer-when-downgrade");
    iframe.style.border = "0";
    iframe.width = String(unit.width ?? "100%");
    iframe.height = String(unit.height ?? 90);
    container.appendChild(iframe);

    const network = ctx.manifest.networks[unit.network];
    const success = String(unit.external_success_message ?? network?.loader?.success_message ?? "");
    const fail = String(unit.external_failure_message ?? network?.loader?.failure_message ?? "");
    const assumeFilled = String(unit.assume_filled_on_mount ?? "false") === "true";
    const graceMs = numeric(unit, "mount_grace_ms", 750);

    return await new Promise<CandidateResult>((resolve, reject) => {
      let settled = false;
      let graceTimer: number | undefined;
      const cleanup = () => {
        window.removeEventListener("message", onMessage);
        iframe.removeEventListener("load", onLoad);
        signal.removeEventListener("abort", onAbort);
        if (graceTimer) window.clearTimeout(graceTimer);
      };
      const finish = (result: CandidateResult) => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(result);
      };
      const onAbort = () => {
        if (settled) return;
        settled = true;
        cleanup();
        iframe.remove();
        reject(new DOMException("aborted", "AbortError"));
      };
      const onLoad = () => {
        if (!assumeFilled) return;
        graceTimer = window.setTimeout(() => finish({ outcome: "filled", renderedAt: Date.now() }), graceMs);
      };
      const onMessage = (e: MessageEvent) => {
        if (e.source !== iframe.contentWindow) return;
        if (success && e.data === success) finish({ outcome: "filled", renderedAt: Date.now() });
        if (fail && e.data === fail) finish({ outcome: "no-fill", reason: "external failure message" });
      };
      signal.addEventListener("abort", onAbort, { once: true });
      iframe.addEventListener("load", onLoad);
      window.addEventListener("message", onMessage);
      iframe.srcdoc = iframeDocument(String(unit.markup ?? unit.html ?? ""), String(unit.head_markup ?? ""));
      if (!success && !fail && !assumeFilled) finish({ outcome: "unknown", reason: "external tag has no reliable fill signal", renderedAt: Date.now() });
    });
  },
  async destroy(_unit, container) {
    container.querySelectorAll("iframe").forEach((iframe) => iframe.remove());
    container.textContent = "";
  }
};
