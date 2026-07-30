import { Rotunda } from "../components/rotunda.js";
import { Search } from "../components/search.js";
import { Blocks } from "../components/blocks.js";
import { mountAccountNavigation } from "../account/navigation.js";
import { renderAdRegion } from "../monetization/components/ad-region.js";
let accountCleanup;
let adCleanups = [];
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
        <div class="app-root">
            <header class="landing-header" aria-label="Doku-Doujin site header">
                <a class="landing-brand" href="/" aria-label="Doku-Doujin home">Doku-Doujin</a>
                <div class="landing-search" aria-label="Site search"></div>
                <nav class="landing-account" aria-label="Account controls"></nav>
            </header>

            <section class="rotunda-layer landing-rotunda-frame" data-rotunda-full-row="true">
                <div class="landing-rotunda"></div>
            </section>

            <div class="landing-below-rotunda-ad"></div>

            <section class="ticker-layer" aria-label="Doku-Doujin updates">
                <div class="header-ticker">
                    <div class="header-ticker-track" id="header-ticker-track"></div>
                </div>
            </section>

            <section id="blocks-root"></section>
        </div>
        `;

        accountCleanup?.();
        adCleanups.splice(0).forEach(cleanup => cleanup());
        accountCleanup = mountAccountNavigation(container.querySelector(".landing-account"));
        adCleanups.push(
            renderAdRegion({ placement: "landing_top_leaderboard", mount: container.querySelector(".landing-below-rotunda-ad") })
        );

        await Promise.all([
            safeStart("search", Search.start),
            safeStart("rotunda", Rotunda.start),
            safeStart("blocks", Blocks.start),
            safeStart("header ticker", startHeaderTicker)
        ]);
    }
}
