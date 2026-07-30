import assert from "node:assert/strict";
import test from "node:test";
import { inspectProviderSlot } from "../src/monetization/renderer.js";

const policy = { minimumVisibleWidth: 40, minimumVisibleHeight: 20, minimumVisibleArea: 800 };
globalThis.getComputedStyle = node => node.style || { display: "block", visibility: "visible", opacity: "1" };
function element(tag, width = 0, height = 0, extra = {}) {
  return {
    nodeType: 1, tagName: tag.toUpperCase(), nodeName: tag.toUpperCase(), isConnected: true,
    children: [], parentElement: null, style: { display: "block", visibility: "visible", opacity: "1" },
    getBoundingClientRect: () => ({ width, height, left: 0, top: 0, right: width, bottom: height }),
    matches: selector => selector === "iframe, img, video, canvas, object, embed" && ["IFRAME","IMG","VIDEO","CANVAS","OBJECT","EMBED"].includes(tag.toUpperCase()),
    closest: () => null, ...extra
  };
}
function inspect(nodes, original = null, baseline = new Set()) {
  const host = element("div", 300, 250);
  host.querySelectorAll = () => nodes;
  for (const node of nodes) if (!node.parentElement) node.parentElement = host;
  return inspectProviderSlot(host, original, baseline, policy);
}

test("provider placeholders claim without filling", () => {
  for (const node of [element("div"), element("iframe", 0, 250), element("iframe", 300, 0), element("img", 0, 0, { complete:true, naturalWidth:300, naturalHeight:250 })]) {
    const result = inspect([node]); assert.equal(result.claimed, true); assert.equal(result.filled, false);
  }
});

test("scripts, styles, and the original reserved wrapper are not fill evidence", () => {
  assert.deepEqual(inspect([element("script"), element("style")]), { filled:false, claimed:false, creative:null, replaced:false });
  const reserved = element("div", 300, 250);
  const result = inspect([reserved], null, new Set([reserved]));
  assert.equal(result.claimed, false); assert.equal(result.filled, false);
});

test("meaningfully rendered provider frames and visuals fill", () => {
  for (const node of [element("iframe", 300, 250), element("canvas", 40, 20), element("img", 300, 250, { complete:true, naturalWidth:300, naturalHeight:250 })]) {
    const result = inspect([node]); assert.equal(result.claimed, true); assert.equal(result.filled, true);
  }
});

test("below-threshold, failed, and hidden creatives do not fill", () => {
  const hidden = element("iframe", 300, 250); hidden.style.display = "none";
  const failedImage = element("img", 300, 250, { complete:true, naturalWidth:0, naturalHeight:0 });
  for (const node of [element("canvas", 39, 20), element("canvas", 40, 19), hidden, failedImage]) assert.equal(inspect([node]).filled, false);
});
