# Ad Runner Integration Standard v1

Ad Runner is a small, appendable advertising layer with a stable public contract. A website integrates by loading the runtime script, setting `data-ad-runner-site`, and exposing named advertisement anchors such as `data-ad-runner-slot="top"`.

## Public endpoints

- `GET /v1/ad-runner.min.js` serves the browser runtime.
- `GET /v1/sites/{site-id}/bootstrap.json` returns a small bootstrap document that points at the live manifest version.
- `GET /v1/sites/{site-id}/manifests/{version}.json` returns an immutable compiled manifest.
- `GET /v1/sites/{site-id}/health.json` reports the currently live manifest.
- `POST /v1/sites/{site-id}/events` is optional; the runtime must work without analytics.

## Slot names

Standard slots include `top`, `below-header`, `above-content`, `before-content`, `inside-content`, `after-content`, `chapter-end`, `left-rail`, `right-rail`, `footer`, `mobile-top`, `mobile-bottom`, `overlay`, `interstitial`, and `popunder`. Custom anchors are allowed.

## Integration rule

Websites expose locations. The spreadsheet describes the advertising system. Ad Runner connects the two.
