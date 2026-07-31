import { placements } from "./config.js";

const NAVIGATION_EVENT = "doku:navigation";

export function validAdvertisementUrl(value, base = globalThis.location?.href || "https://doku.invalid/") {
  try {
    const url = new URL(value, base);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export function routeIsExcluded(pathname, excludedRoutes = []) {
  return excludedRoutes.some(prefix => typeof prefix === "string" && prefix.length > 0 && pathname.startsWith(prefix));
}

export class FullscreenOverlayController {
  constructor(config, environment = {}) {
    this.config = config || {};
    this.window = environment.window || globalThis.window;
    this.document = environment.document || globalThis.document;
    this.now = environment.now || Date.now;
    this.setTimer = environment.setTimeout || globalThis.setTimeout;
    this.clearTimer = environment.clearTimeout || globalThis.clearTimeout;
    this.remainingMs = Math.max(0, Number(this.config.initialDelayMs) || 0);
    this.timer = null;
    this.startedAt = 0;
    this.overlay = null;
    this.previousFocus = null;
    this.previousBodyOverflow = "";
    this.previousHtmlOverflow = "";
    this.closeAvailableAt = 0;
    this.started = false;
    this.onVisibilityChange = this.onVisibilityChange.bind(this);
    this.onNavigation = this.onNavigation.bind(this);
    this.onKeyDown = this.onKeyDown.bind(this);
  }

  start() {
    if (this.started || !this.config.enabled || !this.document || !this.window) return this;
    this.started = true;
    this.document.addEventListener("visibilitychange", this.onVisibilityChange);
    this.window.addEventListener("popstate", this.onNavigation);
    this.window.addEventListener(NAVIGATION_EVENT, this.onNavigation);
    if (!this.document.hidden) this.schedule();
    return this;
  }

  schedule() {
    this.cancelTimer(false);
    if (!this.started || this.document.hidden || this.overlay || this.isExcluded()) return;
    if (this.remainingMs <= 0) return this.show();
    this.startedAt = this.now();
    this.timer = this.setTimer(() => {
      this.timer = null;
      this.remainingMs = 0;
      if (!this.document.hidden && !this.isExcluded()) this.show();
    }, this.remainingMs);
  }

  cancelTimer(updateRemaining = true) {
    if (this.timer === null) return;
    if (updateRemaining) this.remainingMs = Math.max(0, this.remainingMs - (this.now() - this.startedAt));
    this.clearTimer(this.timer);
    this.timer = null;
  }

  isExcluded() {
    return routeIsExcluded(this.window.location.pathname, this.config.excludedRoutes);
  }

  onVisibilityChange() {
    if (this.document.hidden) this.cancelTimer(true);
    else this.schedule();
  }

  onNavigation() {
    if (this.isExcluded()) {
      this.cancelTimer(true);
      if (this.overlay) this.dismiss(true);
      return;
    }
    if (!this.document.hidden && !this.overlay) this.schedule();
  }

  show() {
    if (this.overlay || this.document.hidden || this.isExcluded()) return;
    const overlay = this.document.createElement("div");
    overlay.className = "fullscreen-ad-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Advertisement");
    overlay.style.setProperty("--fullscreen-ad-background", this.config.backgroundColor || "#000000");

    const surface = this.document.createElement("div");
    surface.className = "fullscreen-ad-overlay__surface";
    surface.tabIndex = 0;
    surface.setAttribute("role", "link");
    surface.setAttribute("aria-label", "Open advertisement");
    surface.addEventListener("click", () => this.openDestination());
    surface.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); this.openDestination(); }
    });
    if (this.config.imageUrl) {
      const image = this.document.createElement("img");
      image.className = "fullscreen-ad-overlay__creative";
      image.src = this.config.imageUrl;
      image.alt = "Advertisement";
      surface.append(image);
    } else {
      const placeholder = this.document.createElement("span");
      placeholder.className = "fullscreen-ad-overlay__placeholder";
      placeholder.textContent = "Advertisement";
      surface.append(placeholder);
    }
    overlay.append(surface);

    if (this.config.showCloseButton) {
      const close = this.document.createElement("button");
      close.className = "fullscreen-ad-overlay__close";
      close.type = "button";
      close.setAttribute("aria-label", "Close advertisement");
      close.textContent = "×";
      close.addEventListener("click", event => { event.stopPropagation(); this.dismiss(); });
      overlay.append(close);
    }

    this.previousFocus = this.document.activeElement;
    this.previousBodyOverflow = this.document.body.style.overflow;
    this.previousHtmlOverflow = this.document.documentElement.style.overflow;
    this.document.body.style.overflow = "hidden";
    this.document.documentElement.style.overflow = "hidden";
    this.document.body.append(overlay);
    this.overlay = overlay;
    this.closeAvailableAt = this.now() + Math.max(0, Number(this.config.minimumVisibleMs) || 0);
    this.document.addEventListener("keydown", this.onKeyDown);
    surface.focus();
  }

  openDestination() {
    const url = validAdvertisementUrl(this.config.destinationUrl, this.window.location.href);
    if (!url) return false;
    if (this.config.openInNewTab) {
      const opened = this.window.open(url, "_blank", "noopener,noreferrer");
      if (opened) opened.opener = null;
    } else {
      this.window.location.assign(url);
    }
    return true;
  }

  onKeyDown(event) {
    if (!this.overlay) return;
    if (event.key === "Escape") { event.preventDefault(); this.dismiss(); return; }
    if (event.key !== "Tab") return;
    const focusable = [...this.overlay.querySelectorAll('[tabindex="0"],button:not([disabled])')];
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && this.document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && this.document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  dismiss(force = false) {
    if (!this.overlay || (!force && this.now() < this.closeAvailableAt)) return false;
    this.document.removeEventListener("keydown", this.onKeyDown);
    this.overlay.remove();
    this.overlay = null;
    this.document.body.style.overflow = this.previousBodyOverflow;
    this.document.documentElement.style.overflow = this.previousHtmlOverflow;
    this.previousFocus?.focus?.();
    this.previousFocus = null;
    this.remainingMs = Math.max(0, Number(this.config.intervalMs) || 0);
    this.schedule();
    return true;
  }

  destroy() {
    if (!this.started) return;
    this.cancelTimer(false);
    this.document.removeEventListener("visibilitychange", this.onVisibilityChange);
    this.window.removeEventListener("popstate", this.onNavigation);
    this.window.removeEventListener(NAVIGATION_EVENT, this.onNavigation);
    this.document.removeEventListener("keydown", this.onKeyDown);
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
      this.document.body.style.overflow = this.previousBodyOverflow;
      this.document.documentElement.style.overflow = this.previousHtmlOverflow;
      this.previousFocus?.focus?.();
    }
    this.started = false;
  }
}

let controller;
export function initializeFullscreenOverlay(config = placements.fullscreenOverlay) {
  if (controller) return () => {};
  controller = new FullscreenOverlayController(config).start();
  return () => { controller?.destroy(); controller = undefined; };
}
