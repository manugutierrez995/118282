import { renderAdRegion } from "../monetization/components/ad-region.js";

let adCleanup;
export class Footer {
    static start() {
        const footer = document.getElementById("footer");
        if (!footer) return;

        footer.replaceChildren();
        footer.classList.add("site-footer");

        const brand = document.createElement("div");
        brand.className = "site-footer-brand";
        brand.textContent = "Doku-Doujin";

        const top = document.createElement("button");
        top.className = "site-footer-top";
        top.type = "button";
        top.textContent = "Back to top";
        top.addEventListener("click", () => {
            const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
        });

        const promotion = document.createElement("aside");
        promotion.className = "footer-ad-region";
        promotion.setAttribute("aria-label", "Sponsored and site promotions");
        footer.append(brand, promotion, top);
        adCleanup?.();
        adCleanup = renderAdRegion({ placement: "global_footer_banner", mount: promotion });
    }
}
