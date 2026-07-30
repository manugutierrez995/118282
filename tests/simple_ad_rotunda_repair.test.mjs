import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = path => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("Rotunda is the sole principal child of a dedicated full-width centered row", async () => {
  const [landing, css] = await Promise.all([read("src/page/landing.js"), read("src/monetization/styles/ad-slots.css")]);
  const row = landing.match(/<section class="rotunda-layer rotunda-row">([\s\S]*?)<\/section>/)?.[1] || "";
  assert.match(row, /landing-rotunda rotunda-container/);
  assert.doesNotMatch(row, /ad|aside|fallback/i);
  assert.match(css, /\.rotunda-row\{[^}]*display:flex[^}]*width:100%[^}]*justify-content:center[^}]*align-items:center/);
  assert.doesNotMatch(css, /landing-rotunda-frame|landing-ad-rail/);
});

test("inline renderer creates one stable connected host and contains no fill heuristics", async () => {
  const renderer = await read("src/monetization/renderer.js");
  assert.match(renderer, /if \(active\.has\(container\)\) return active\.get\(container\)/);
  assert.match(renderer, /host\.className = "ad-provider-host"/);
  assert.match(renderer, /container\.appendChild\(host\)[\s\S]*host\.isConnected/);
  assert.match(renderer, /appendExternalScript\(source, document\.head\)/);
  assert.match(renderer, /host\.appendChild\(copyScript\(source\)\)/);
  assert.doesNotMatch(renderer, /MutationObserver|ResizeObserver|getBoundingClientRect|provider timeout|no measurable creative|setTimeout/);
  assert.doesNotMatch(renderer, /doku-ad-verification|data-ad-state/);
  const cleanup = renderer.match(/const cleanup =[^;]+;/)?.[0] || "";
  assert.doesNotMatch(cleanup, /replaceChildren|remove|hidden/);
});

test("Reader breaks are deterministic stable non-page items", async () => {
  const reader = await read("src/page/reader.js");
  assert.match(reader, /adSlot\.dataset\.adBreakId = `\$\{readerIdentity\}:break-\$\{index \+ 1\}-\$\{adIndex\}`/);
  assert.match(reader, /createVirtualReader\(wrapper, manifest, session, `\$\{work\}:\$\{chapter\}`\)/);
  assert.doesNotMatch(reader, /reader_between_pages[\s\S]{0,100}lazy:\s*true/);
});

test("interstitial root is body-level and device-specific", async () => {
  const global = await read("src/monetization/global.js");
  assert.match(global, /root\.id = "doku-interstitial-root"/);
  assert.match(global, /document\.body\.append\(root\)/);
  assert.match(global, /innerWidth < 600 \? "mobile_full_page_interstitial" : "desktop_full_page_interstitial"/);
  assert.doesNotMatch(global, /\["desktop_full_page_interstitial", "mobile_full_page_interstitial"/);
});

test("site CSS does not style provider descendants or clip creatives", async () => {
  const css = await read("src/monetization/styles/ad-slots.css");
  assert.match(css, /\.ad-placement\{[^}]*background:#000/);
  assert.doesNotMatch(css, /\.ad-(?:placement|provider-host)\s+(?:iframe|ins|div|\*)/);
  assert.doesNotMatch(css, /\.ad-(?:placement|provider-host)\{[^}]*overflow:hidden/);
});
