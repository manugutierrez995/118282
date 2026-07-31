import assert from "node:assert/strict";
import test from "node:test";
import { FullscreenOverlayController, validAdvertisementUrl } from "../src/monetization/fullscreen-overlay.js";

class Events {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, fn) { const list = this.listeners.get(type) || []; list.push(fn); this.listeners.set(type, list); }
  removeEventListener(type, fn) { this.listeners.set(type, (this.listeners.get(type) || []).filter(item => item !== fn)); }
  dispatch(type, event = {}) { for (const fn of [...(this.listeners.get(type) || [])]) fn({ type, preventDefault() {}, stopPropagation() {}, ...event }); }
}
class Element extends Events {
  constructor(tag, document) { super(); this.tagName = tag.toUpperCase(); this.ownerDocument = document; this.children = []; this.style = { overflow: "", setProperty(name, value) { this[name] = value; } }; this.attributes = {}; this.parentNode = null; this.className = ""; }
  append(...nodes) { for (const node of nodes) { node.parentNode = this; this.children.push(node); } }
  setAttribute(name, value) { this.attributes[name] = value; }
  focus() { this.ownerDocument.activeElement = this; }
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(node => node !== this); this.parentNode = null; }
  querySelectorAll() { return this.children.flatMap(node => [node, ...node.querySelectorAll()]).filter(node => node.tabIndex === 0 || node.tagName === "BUTTON"); }
}
class Document extends Events {
  constructor() { super(); this.hidden = false; this.activeElement = null; this.body = new Element("body", this); this.documentElement = new Element("html", this); }
  createElement(tag) { return new Element(tag, this); }
}
class Window extends Events {
  constructor() { super(); this.location = { pathname: "/", href: "https://doku.test/", assigned: null, assign: value => { this.location.assigned = value; } }; this.opens = []; }
  open(...args) { this.opens.push(args); return {}; }
}
function scheduler() {
  let now = 0, id = 0;
  const tasks = new Map();
  return {
    now: () => now,
    setTimeout(fn, delay) { const task = ++id; tasks.set(task, { at: now + delay, fn }); return task; },
    clearTimeout(task) { tasks.delete(task); },
    tick(ms) { const end = now + ms; while (true) { const next = [...tasks.entries()].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at)[0]; if (!next) break; now = next[1].at; tasks.delete(next[0]); next[1].fn(); } now = end; },
    count: () => tasks.size
  };
}
const config = overrides => ({ enabled: true, initialDelayMs: 180000, intervalMs: 180000, destinationUrl: "https://ads.test/landing", imageUrl: "", backgroundColor: "#000", openInNewTab: true, showCloseButton: true, minimumVisibleMs: 0, excludedRoutes: ["/auth/", "/checkout/", "/operator/"], ...overrides });
function setup(overrides = {}) {
  const document = new Document(), window = new Window(), clock = scheduler();
  const controller = new FullscreenOverlayController(config(overrides), { document, window, now: clock.now, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout }).start();
  return { controller, document, window, clock };
}
const overlayCount = document => document.body.children.filter(node => node.className === "fullscreen-ad-overlay").length;

test("waits for the configured three-minute delay and creates only one overlay", () => {
  const app = setup();
  app.clock.tick(179999); assert.equal(overlayCount(app.document), 0);
  app.clock.tick(1); assert.equal(overlayCount(app.document), 1);
  app.clock.tick(180000); assert.equal(overlayCount(app.document), 1); assert.equal(app.clock.count(), 0);
  app.controller.destroy();
});

test("surface opens the configured protected URL while close and Escape only dismiss", () => {
  const app = setup({ initialDelayMs: 0 });
  const overlay = app.document.body.children[0], surface = overlay.children[0], close = overlay.children[1];
  surface.dispatch("click");
  assert.deepEqual(app.window.opens, [["https://ads.test/landing", "_blank", "noopener,noreferrer"]]);
  close.dispatch("click"); assert.equal(app.window.opens.length, 1); assert.equal(overlayCount(app.document), 0);
  app.clock.tick(180000); app.document.dispatch("keydown", { key: "Escape" });
  assert.equal(overlayCount(app.document), 0); assert.equal(app.window.opens.length, 1);
  app.controller.destroy();
});

test("scroll locking and focus are restored on dismissal and destruction", () => {
  const app = setup({ initialDelayMs: 0 });
  const oldFocus = new Element("button", app.document); oldFocus.focus();
  app.controller.destroy();
  assert.equal(app.document.body.style.overflow, ""); assert.equal(app.document.documentElement.style.overflow, "");
  const second = setup({ initialDelayMs: 10 }); second.document.body.style.overflow = "clip"; second.clock.tick(10);
  assert.equal(second.document.body.style.overflow, "hidden"); second.controller.dismiss();
  assert.equal(second.document.body.style.overflow, "clip"); second.controller.destroy();
});

test("disabled configuration and excluded routes render nothing", () => {
  const disabled = setup({ enabled: false, initialDelayMs: 0 }); assert.equal(overlayCount(disabled.document), 0); assert.equal(disabled.clock.count(), 0);
  const excluded = setup({ initialDelayMs: 10 }); excluded.window.location.pathname = "/checkout/pay"; excluded.window.dispatch("doku:navigation"); excluded.clock.tick(20);
  assert.equal(overlayCount(excluded.document), 0); assert.equal(excluded.clock.count(), 0);
  excluded.controller.destroy();
});

test("hidden time is paused and client navigation never duplicates the timer", () => {
  const app = setup({ initialDelayMs: 100 });
  app.clock.tick(40); app.document.hidden = true; app.document.dispatch("visibilitychange"); app.clock.tick(1000);
  assert.equal(overlayCount(app.document), 0);
  app.document.hidden = false; app.document.dispatch("visibilitychange");
  app.window.dispatch("doku:navigation"); app.window.dispatch("popstate"); assert.equal(app.clock.count(), 1);
  app.clock.tick(59); assert.equal(overlayCount(app.document), 0); app.clock.tick(1); assert.equal(overlayCount(app.document), 1);
  app.controller.destroy();
  assert.equal(app.clock.count(), 0); assert.equal((app.document.listeners.get("visibilitychange") || []).length, 0); assert.equal((app.window.listeners.get("popstate") || []).length, 0);
});

test("invalid advertisement URL schemes are rejected", () => {
  assert.equal(validAdvertisementUrl("javascript:alert(1)"), null);
  assert.equal(validAdvertisementUrl("data:text/html,bad"), null);
  const app = setup({ initialDelayMs: 0, destinationUrl: "javascript:alert(1)" });
  app.document.body.children[0].children[0].dispatch("click"); assert.equal(app.window.opens.length, 0);
  app.controller.destroy();
});
