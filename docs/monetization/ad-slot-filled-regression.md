# Filled ad slot lifecycle regression

## Root cause

`renderAdPlacement` previously treated every call for an existing container as a new mount. It immediately invoked the active cleanup, and that cleanup cleared the container with `replaceChildren()`. A route or parent/Rotunda refresh could therefore delete a provider-owned, already-filled `<ins>` and start a fresh attempt. The new attempt's timeout then followed the ordinary fallback path, whose own `replaceChildren(createFallback(...))` installed the black Doku-Doujins panel. The visible creative proved delivery had succeeded; the destructive re-entry and later fallback were local lifecycle behavior.

Fill detection also canceled only the single timeout and disconnected only mutation and resize observers. The slot's filled status lived only in a mutable DOM data attribute, rather than in a terminal mounted-slot state, and the intersection observer was not part of a unified cancellation boundary.

## Fix

- Added a mounted-slot lifecycle with the explicit states `initializing`, `requesting`, `filled`, `failed`, and `fallback`.
- Made `filled` terminal until genuine cleanup/unmount and cancel all registered fallback timers and observers at fill time.
- Made repeated render requests return the existing filled slot cleanup instead of clearing, moving, recreating, or remounting provider DOM.
- Guarded failure, collapse, and fallback paths with the terminal lifecycle rather than a DOM attribute.
- Added development-only transition diagnostics containing the previous state, next state, exact reason, and caller.
- Added a regression test covering a real `<ins>` creative followed by a delayed timeout callback, a temporary `0x0` resize, an intersection/visibility change, and a Rotunda-driven rerender request.

## Changed files

- `src/monetization/renderer.js`
- `src/monetization/slot-lifecycle.js`
- `tests/ad_slot_lifecycle.test.mjs`
- `docs/monetization/ad-slot-filled-regression.md`
