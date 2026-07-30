> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Private account foundation implementation report

## Outcome
Repository implementation provides one Supabase client/session lifecycle, centralized history router, guarded owner account pages, Google and email/password/recovery APIs and forms, shared landing/reader controls, Auth-owned profile metadata, and RLS-backed bookmark listing/removal. Public landing, rotunda, search, reader query URLs, discussion, and work bookmark toggle contracts remain in place.

Not complete: live provider behavior and live RLS were not verifiable; the new migration was not applied; content-preference UI is deliberately disabled pending a safe vocabulary; anonymous-to-email linking is not implemented without a verified reauthentication design. Profile avatar is provider-read-only and public discussion display-name editing is unchanged.

## Files changed
- Shared auth: `src/auth/supabase.js`, `src/auth/session.js`, discussion compatibility facade/service consumer.
- Routing/views: `src/router/router.js`, `src/page/page.js`, `src/account/{views,navigation,data}.js`.
- Integration/design: `src/main.js`, `src/page/landing.js`, `src/page/reader.js`, `src/styles/landing.css`.
- Database/tests/docs: preference migration, `tests/account_foundation.test.mjs`, and the four account-foundation reports.

## Database and external state
A forward migration creates normalized `user_tag_preferences` with one `(user_id,tag_key)` row, enum conflict prevention, nullable weight, timestamps, RLS, and owner select/insert/update/delete. It was **created but not applied**. Existing bookmark owner policies were not changed. No live Supabase dashboard/schema claim is made. Email provider, confirmation, SMTP, redirect allowlists, and Google settings require the manual actions document.

## Behavior and privacy
Google uses the existing project and preserves anonymous `linkIdentity`; email uses Supabase Auth methods and the same UUID contract. Anonymous sessions remain guests for private routes. Profile email/provider/time comes only from the current Auth user; the public `profiles` table remains public discussion identity and receives no new private fields. Bookmark rows are owner-filtered and depend on existing owner RLS, metadata is resolved from public catalog/manifests, missing works become tombstones, and identity changes rerender rather than reuse private arrays. Settings show owner Auth summary; preference persistence is not claimed. No tokens, UUIDs, email, or private rows enter URLs, localStorage, source HTML, or a service-role client.

## Tests and build
`npm test` passed (including focused route, redirect, singleton, and migration checks). `npm run build` passed with non-fatal chunk-size/dynamic-import warnings. Live browser, two-user RLS, email delivery, Google callback, and deployed refresh checks were not available. Known risks are catalog bundle growth from eager manifest metadata, environment-specific provider configuration, and unverified live migration order.

## Rollback
Revert the implementation commit. If the new migration was applied, first export any preference rows, then drop `public.user_tag_preferences` and `public.user_tag_preference_type` in a new reviewed forward rollback migration; never edit the historical migration. Existing discussion/bookmark schema needs no rollback.

## Final requirement matrix
| Requirement | Status | Implemented files | Database dependency | Manual action | Test evidence | Deviation reference |
|---|---|---|---|---|---|---|
| Shared Supabase client | complete | `src/auth/supabase.js` | none | env vars | singleton static test | none |
| Session restoration | partial | `src/auth/session.js`, `main.js` | live Auth | configure project | singleton test/build | live verification |
| Google login | partial | session/views | provider | redirects/Google | source/build | live verification |
| Anonymous-to-Google linking | partial | session | provider policy | live test | source/build | identity linking |
| Email signup | partial | session/views | Email Auth | enable/SMTP | build | live verification |
| Email login | partial | session/views | Email Auth | enable | build | live verification |
| Email confirmation | partial | views | templates | configure | build | live verification |
| Forgot password | partial | session/views | SMTP/redirect | configure | build | live verification |
| Reset password | partial | session/views | callback session | configure | route test/build | live verification |
| Profile route | complete | router/page/views | none | none | route test | none |
| Owner-specific profile | partial | views | Auth session | live test | build | live verification |
| Profile icon | complete | navigation | none | none | source/build | none |
| Bookmarks route | complete | router/page/views | bookmarks table | verify migration | route test | none |
| Owner-specific bookmark listing | partial | account/data | bookmark RLS | two-user verify | build | live verification |
| Bookmark removal | partial | account/data/views | bookmark RLS | two-user verify | build | live verification |
| Bookmark icon | complete | navigation | none | none | source/build | none |
| Settings route | complete | router/page/views | none | none | route test | none |
| Owner-specific settings | partial | views/migration | unapplied migration | apply/verify | migration test | preferences |
| Preferred tags | blocked | views/migration | vocabulary/migration | publish vocabulary | disabled UI/build | preferences |
| Excluded tags | blocked | views/migration | vocabulary/migration | publish vocabulary | disabled UI/build | preferences |
| Settings gear | complete | navigation | none | none | source/build | none |
| Landing integration | complete | landing/navigation/CSS | none | none | build | none |
| Reader integration | complete | reader/navigation/CSS | none | none | build | none |
| Mobile navigation | complete | CSS/navigation | none | device check recommended | build/source | none |
| Sign out | partial | session/views/discussion | live Auth | live test | build | live verification |
| Route guards | complete | page/router | RLS remains boundary | verify RLS | route tests | none |
| Validated return URL | complete | router/views | none | none | safe-next test | none |
| Back and forward navigation | complete | router | none | browser verify | central handler test/source | none |
| Direct-route refresh | complete-pending-deployment | router/wrangler | none | deploy preview | build | deployment |
| Discussion compatibility | partial | facade/discussion | existing migration | live regression | npm test/build | live verification |
| Reader compatibility | complete | page/reader | none | browser regression | build + legacy test | none |
| Rotunda compatibility | complete | landing | none | browser regression | existing tests/build | none |
| RLS verification | blocked | migrations | live project | two-user test | static SQL test | live verification |
| Build | complete | all | none | none | `npm run build` | none |
| Automated tests | complete | tests | no live project | add live suite later | `npm test` | live verification |
| Branch | complete | git | none | none | git status | none |
| Commit | complete-pending-deployment | git | none | completion step | git log | none |
| Push | partial | git remote | credentials/network | completion attempt | command result | deployment |
| Draft pull request | partial | GitHub | credentials/network | completion attempt | tool result | deployment |
