const STATES = new Set(["initializing", "requesting", "filled", "failed", "fallback"]);

function developmentMode() {
  return Boolean(import.meta.env?.DEV);
}

/** Owns the one-way state of one mounted provider slot. */
export function createSlotLifecycle(container, {
  debug = developmentMode(),
  setTimer = setTimeout,
  clearTimer = clearTimeout
} = {}) {
  let state = "initializing";
  let disposed = false;
  const timers = new Set();
  const observers = new Set();

  const log = (next, reason, caller) => {
    if (debug) console.debug("[ad-slot] transition", { from: state, to: next, reason, caller });
  };
  const cancelFallbackWork = () => {
    for (const timer of timers) clearTimer(timer);
    timers.clear();
    for (const observer of observers) observer?.disconnect?.();
    observers.clear();
  };
  const transition = (next, reason, caller) => {
    if (!STATES.has(next)) throw new Error(`Unknown ad slot state: ${next}`);
    if (disposed) return false;
    if (state === "filled" && next !== "filled") {
      log(next, `ignored after fill: ${reason}`, caller);
      return false;
    }
    if (state === "fallback") return false;
    if (state === next) return false;
    log(next, reason, caller);
    state = next;
    container.dataset.state = next;
    container.dataset.reason = reason || "";
    if (next === "filled" || next === "failed" || next === "fallback") cancelFallbackWork();
    return true;
  };

  container.dataset.state = state;
  container.dataset.reason = "slot mounted";
  if (debug) console.debug("[ad-slot] transition", { from: null, to: state, reason: "slot mounted", caller: "renderAdPlacement" });

  return {
    get state() { return state; },
    get filled() { return state === "filled"; },
    transition,
    observe(observer) {
      if (state === "filled" || disposed) observer?.disconnect?.();
      else observers.add(observer);
      return observer;
    },
    fallbackTimer(callback, delay) {
      if (state === "filled" || disposed) return null;
      const timer = setTimer(() => { timers.delete(timer); callback(); }, delay);
      timers.add(timer);
      return timer;
    },
    dispose() {
      disposed = true;
      cancelFallbackWork();
    }
  };
}
