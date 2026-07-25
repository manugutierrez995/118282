import { Rotunda } from "../components/rotunda.js";
import { Search } from "../components/search.js";
import { Blocks } from "../components/blocks.js";
import { mountLandingAds } from "../components/landing_ads.js";
async function startHeaderTicker() {
    const ticker = document.getElementById("header-ticker-track");
    if (!ticker) return;

    try {
        const response = await fetch("/header-ticker.json");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const rows = Array.isArray(data.rows) ? data.rows : [];
        const hero = Array.isArray(data.hero) ? data.hero : [];

        ticker.replaceChildren();

        for (let i = 0; i < 3; i++) {
            const rowData = rows[i] || {};
            const items = Array.isArray(rowData.items) ? rowData.items : [""];
            const line = items.filter(Boolean).join("     ✦     ");

            const row = document.createElement("div");
            row.className = `header-ticker-row header-ticker-row-${i + 1}`;
            row.style.setProperty("--ticker-speed", rowData.speed || `${26 + i * 10}s`);
            row.textContent = `${line}     ✦     ${line}`;
            ticker.appendChild(row);
        }

        const heroBox = document.createElement("div");
        heroBox.className = "header-ticker-hero";
        heroBox.textContent = hero[0] || "";
        ticker.appendChild(heroBox);

        let heroIndex = 0;
        window.setInterval(() => {
            if (!hero.length) return;
            heroIndex = (heroIndex + 1) % hero.length;
            heroBox.textContent = hero[heroIndex];
        }, 4200);
    } catch (error) {
        console.warn("header ticker failed", error);
        ticker.textContent = "";
    }
}

async function safeStart(name, fn) {
    try {
        await fn();
    } catch (e) {
        console.warn(`${name} failed`, e);
    }
}

export class Landing {
    static async start() {
        const container = document.getElementById("reader-container");
        if (!container) return;

        document.body.classList.remove("reader-active");

        container.innerHTML = `
        <div class="app-root landing-page">
            <header class="landing-header" aria-label="Doku-Doujin site header">
                <div class="landing-identity">
                    <span class="landing-accession">Digital archive · No. 564578634</span>
                    <a class="landing-brand" href="/" aria-label="Doku-Doujin home">Doku—Doujin</a>
                </div>
                <div class="landing-search" aria-label="Site search"></div>
            </header>

            <main class="landing-exhibition">
                <aside class="exhibition-rail exhibition-rail--left" aria-label="Left exhibition rail">
                    <p class="exhibition-rail__label">From the archive</p>
                    <div id="blocks-left" class="blocks-column"></div>
                    <div data-ad-rail="left"></div>
                </aside>
                <div class="exhibition-center">
                    <section class="rotunda-layer" aria-label="Archive rotunda"><div class="landing-rotunda"></div></section>
                    <section class="ticker-layer" aria-label="Doku-Doujin updates">
                        <div class="header-ticker"><div class="header-ticker-track" id="header-ticker-track"></div></div>
                    </section>
                    <div class="exhibition-inline-ad" data-ad-inline></div>
                    <section id="blocks-center" class="blocks-column exhibition-notes"></section>
                </div>
                <aside class="exhibition-rail exhibition-rail--right" aria-label="Right exhibition rail">
                    <p class="exhibition-rail__label">Rotating exhibit</p>
                    <div id="blocks-right" class="blocks-column"></div>
                    <div data-ad-rail="right"></div>
                </aside>
            </main>
        </div>
        `;

        await Promise.all([
            safeStart("search", Search.start),
            safeStart("rotunda", Rotunda.start),
            safeStart("blocks", () => Blocks.start({ page: "landing" })),
            safeStart("header ticker", startHeaderTicker)
        ]);
        // Advertising is progressive enhancement and never gates the archive UI.
        void mountLandingAds(container.querySelector(".landing-exhibition"));
    }
}
