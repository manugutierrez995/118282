import { insertHeadMarkup, renderAdPlacement } from "./renderer.js";
let initialized = false;
export function initializeGlobalMonetization() {
  if (initialized || typeof document === "undefined") return () => {}; initialized = true; insertHeadMarkup();
  const cleanups = [], root = document.createElement("div"); root.className = "doku-global-formats"; document.body.append(root);
  for (const id of ["desktop_full_page_interstitial", "mobile_full_page_interstitial", "global_popunder"]) { const mount=document.createElement("div"); mount.hidden=true; root.append(mount); cleanups.push(renderAdPlacement(mount,id)); }
  const attachTop = () => { const header=document.querySelector(".landing-header,.reader-home-bar"); if (!header || document.querySelector('[data-placement="global_top_banner"]')) return; const mount=document.createElement("aside"); mount.className="global-top-ad"; header.after(mount); cleanups.push(renderAdPlacement(mount,"global_top_banner")); };
  attachTop(); const observer=new MutationObserver(attachTop); observer.observe(document.getElementById("reader-container") || document.body,{childList:true,subtree:true});
  return () => { observer.disconnect(); cleanups.forEach(fn=>fn()); root.remove(); initialized=false; };
}
