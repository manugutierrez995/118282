import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { validatePlacementManifest, publicAdContext } from "../src/monetization/validation.js";
import { MonetizationController } from "../src/monetization/controller.js";
import { placementEligible, placementManifest, viewportCategory } from "../src/monetization/placements.js";
import { houseProvider } from "../src/monetization/providers/house.js";
import { memeProvider } from "../src/monetization/providers/meme.js";

const context = { placement: "reader_chapter_end", pageType: "reader", viewport: "desktop", format: "leaderboard" };
const provider = (id, result, delay = 0) => ({ id, initialize() { this.initialized = (this.initialized || 0) + 1; }, supports: () => true, request: () => new Promise((resolve, reject) => setTimeout(() => result instanceof Error ? reject(result) : resolve(result), delay)), destroy() {} });

test("checked-in placement manifest is valid and malformed manifests fail safely", () => {
    assert.deepEqual(validatePlacementManifest(placementManifest), { valid: true, errors: [] });
    assert.equal(validatePlacementManifest({ version: 2 }).valid, false);
});

test("unknown, disabled, and responsive placements are ineligible", () => {
    assert.equal(placementEligible("unknown", 1920), false);
    assert.equal(placementEligible("profile_footer", 1920), false);
    assert.equal(placementEligible("mobile_full_page_interstitial", 1920), false);
    assert.equal(placementEligible("desktop_full_page_interstitial", 1440), true);
    assert.deepEqual([viewportCategory(320), viewportCategory(768), viewportCategory(1280)], ["mobile", "tablet", "desktop"]);
});

test("house fills through the provider contract and meme is a functional fallback", async () => {
    const house = await new MonetizationController({ providers: [houseProvider, memeProvider] }).request(context);
    assert.equal(house.provider, "house");
    assert.equal(house.state, "filled");
    const meme = await new MonetizationController({ providers: [memeProvider] }).request({ ...context, placement: "unclaimed" });
    assert.equal(meme.provider, "meme"); assert.equal(meme.fallback, true);
});

test("waterfall progresses through no-fill and error, then stops after one winner", async () => {
    const noFill = provider("primary", { state: "no-fill" });
    const broken = provider("secondary", new Error("blocked"));
    const winner = provider("house-test", { state: "filled", creative: { id: "one" } });
    const never = provider("never", { state: "filled" });
    const result = await new MonetizationController({ providers: [noFill, broken, winner, never] }).request(context);
    assert.equal(result.provider, "house-test");
    assert.deepEqual(result.attempts.map(item => item.state), ["no-fill", "error", "filled"]);
    assert.equal(never.initialized, undefined);
});

test("timeouts progress, complete no-fill collapses, and providers initialize lazily once", async () => {
    const slow = provider("slow", { state: "filled" }, 40);
    const empty = provider("empty", { state: "no-fill" });
    const controller = new MonetizationController({ providers: [slow, empty], timeoutMs: 5 });
    const result = await controller.request(context);
    assert.equal(result.state, "no-fill"); assert.equal(result.attempts[0].state, "timeout");
    await controller.request(context); assert.equal(slow.initialized, 1); assert.equal(empty.initialized, 1);
});

test("a newer generation rejects stale results and destroy cleans up", async () => {
    const changing = provider("changing", { state: "filled" }, 20);
    const controller = new MonetizationController({ providers: [changing], timeoutMs: 100 });
    const first = controller.request(context);
    const second = controller.request(context);
    assert.equal((await first).state, "stale"); assert.equal((await second).state, "filled");
    controller.destroy();
});

test("only public non-personal context crosses the privacy boundary", () => {
    assert.deepEqual(publicAdContext({ ...context, profileId: "secret", displayName: "secret", bookmarks: [1], preferredTags: [2], readingHistory: [3], localNotes: "secret", backup: true }), context);
});

test("page integrations remain placement-only and core content precedes optional regions", async () => {
    const [landing, search, reader, footer, component] = await Promise.all(["landing", "../components/search", "reader", "../components/footer", "../monetization/components/ad-region"].map(path => readFile(new URL(`../src/page/${path}.js`, import.meta.url), "utf8").catch(() => readFile(new URL(`../src/${path}.js`, import.meta.url), "utf8"))));
    assert.match(landing, /landing_top_leaderboard/); assert.match(search, /nodes\.splice\(6/); assert.match(reader, /createVirtualReader[\s\S]+reader_between_pages[\s\S]+reader-bottom-bar/);
    for (const page of [landing, search, reader, footer]) assert.doesNotMatch(page, /https?:\/\/|accountId|provider\.request/);
    assert.match(await readFile(new URL("../src/monetization/renderer.js", import.meta.url), "utf8"), /IntersectionObserver/);
});

test("verification is configured centrally and page markup has no provider snippets", async () => {
    const [manifestText, renderer, index] = await Promise.all([readFile(new URL("../src/data/monetization/placements.json", import.meta.url), "utf8"), readFile(new URL("../src/monetization/renderer.js", import.meta.url), "utf8"), readFile(new URL("../index.html", import.meta.url), "utf8")]);
    assert.match(manifestText, /"verification"[\s\S]+"enabled": true/); assert.doesNotMatch(renderer, /className = "doku-ad-verification"/); assert.match(renderer, /dataset\.adState/); assert.doesNotMatch(index, /exoclick|juicyads|adserver/i);
});
