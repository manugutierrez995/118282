# Rotunda and advertisement fill fix implementation report

## Repository record

- Starting commit: `d2906c83faa87f159f948e189e94ba6599dd46ad`
- Ending commit: the commit containing this report (the exact hash is recorded in the pull request and completion response).
- Branch: `work`
- Safety tag: `pre-rotunda-and-ad-fill-fix` at the starting commit.
- Safety-tag push: not completed because this checkout has no `origin` remote.

## Implementation

The landing markup now gives the Rotunda a dedicated, full-width row with one child. The former adjacent advertising rail and its responsive grid/offset rules were removed. Advertisements remain in independent rows; no disabled or failed advertising mount is created inside the Rotunda row.

The advertisement renderer now owns a stable per-placement provider host. Each lifecycle creates a fresh `ins`, connects it, starts the exact-URL shared network loader, and executes that placement's serve script once. Magsrv and Pemsrv URLs remain independent registry keys. Verification output is a marked sibling outside provider-owned DOM.

Lifecycle states are `configured`, `mounting`, `provider-loading`, `provider-claimed`, `filled`, `genuinely-empty`, `failed`, `fallback`, and `collapsed`. Fill is terminal. An iframe fills without cross-origin document access; children, media, measurable provider descendants, and replacement of the original `ins` also fill. Provider mutations claim a slot. Timeout and claimed-grace values are centralized. The final fallback path synchronously reinspects the complete host, excludes verification/fallback UI, and cannot remove, cover, or downgrade a claimed or filled slot.

## Verification

- Node test suite: passed 47 tests.
- Python test suite: passed 38 tests.
- Production Vite build: passed (with the pre-existing large-chunk advisory).
- Automated layout checks verify the single-child full-width flex row and absence of adjacent ad/fallback markup or grid columns.
- Required viewport widths (320, 375, 390, 768, 1024, 1280, 1440, 1920): structural responsive rules were checked programmatically; browser screenshots could not be produced because no browser engine is installed in the environment.
- Live advertisement fill: not claimed. No approved deployed-domain URL or deploy credentials/remote were available, so leaderboard, top-banner, and Reader live-provider observation beyond the timeout remains a deployment verification step.

## Known limitations

The repository has no configured Git remote, so the safety tag, branch, and commit cannot be pushed and a hosted draft pull request cannot be created from this checkout. Live ExoClick behavior cannot be asserted without the approved deployed domain. The build continues to report its existing bundle-size advisory.
