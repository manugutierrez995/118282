# Full-screen advertisement overlay

The application-wide overlay is configured by the single `fullscreenOverlay` object in
`src/data/monetization/placements.json`. The application shell mounts one controller from
`src/monetization/fullscreen-overlay.js`; pages and the existing advertisement providers do
not create their own timers.

## Configuration

- Set `enabled` to `false` to disable the feature without changing application code.
- Set `destinationUrl` to the `http:` or `https:` address opened by the advertisement.
  Other URL schemes and malformed URLs are rejected.
- `initialDelayMs` controls the first appearance and `intervalMs` controls subsequent
  appearances after dismissal. Both default to `180000` milliseconds (three minutes).
- Set `imageUrl` to a creative image URL. An empty value displays the neutral advertisement
  container using `backgroundColor`, ready for future provider content.
- `openInNewTab` controls whether the destination opens in a protected new tab or the current
  tab. `showCloseButton` controls the visible close control, and `minimumVisibleMs` prevents
  immediate dismissal.

## Route exclusions

`excludedRoutes` is an array of pathname prefixes. For example, `/checkout/` excludes every
path below that prefix. The overlay is dismissed if navigation enters an excluded route, and
it will not appear there. Add authentication callbacks, payment flows, and administrative
forms to this list.

## Timer and tab visibility

Only visible-tab time counts. Hiding the document pauses the active countdown with its
remaining time; returning to the tab resumes that countdown. If the countdown expires while
a route is excluded, it is deferred until browsing returns to an eligible route. Ordinary
client-side navigation uses the same shell-owned controller and does not create another timer.
