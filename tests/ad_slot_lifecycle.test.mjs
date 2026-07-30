import assert from "node:assert/strict";
import test from "node:test";
import { createSlotLifecycle } from "../src/monetization/slot-lifecycle.js";

test("a detected creative survives every delayed downgrade signal", () => {
  const creative = { tagName: "INS", providerOwned: true };
  const container = { dataset: {}, children: [creative] };
  const scheduled = [];
  const observers = ["mutation", "resize", "intersection"].map(name => ({
    name,
    disconnected: false,
    disconnect() { this.disconnected = true; }
  }));
  const lifecycle = createSlotLifecycle(container, {
    debug: false,
    setTimer(callback) { scheduled.push(callback); return callback; },
    clearTimer() {}
  });

  lifecycle.transition("requesting", "provider request started", "test provider request");
  observers.forEach(observer => lifecycle.observe(observer));
  lifecycle.fallbackTimer(() => {
    if (lifecycle.transition("failed", "provider timeout", "delayed fallback timer")) {
      lifecycle.transition("fallback", "provider timeout", "delayed fallback timer");
      container.children = [{ tagName: "DOKU-FALLBACK" }];
    }
  }, 3_000);

  // The provider inserts and displays its real creative.
  lifecycle.transition("filled", "measurable provider creative detected", "mutation observer");
  assert.ok(observers.every(observer => observer.disconnected));

  // Model already-queued and stale callbacks after the fill became terminal.
  scheduled[0]();
  lifecycle.transition("failed", "iframe temporarily measured 0x0", "resize observer");
  lifecycle.transition("fallback", "slot left viewport", "intersection observer");
  lifecycle.transition("initializing", "rotunda update requested a rerender", "renderAdPlacement");

  assert.equal(lifecycle.state, "filled");
  assert.equal(container.dataset.state, "filled");
  assert.equal(container.children.length, 1);
  assert.strictEqual(container.children[0], creative);
  assert.equal(container.children[0].providerOwned, true);
});
