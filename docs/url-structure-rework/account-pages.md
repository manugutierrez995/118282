# Authenticated account pages and shared navigation

## Boundary with current local profiles

Today `/account/*` renders a selected IndexedDB profile (`src/page/page.js`, `src/account/views.js`), and `/profiles` manages multiple device-local profiles. Target `/account/*` means the signed-in Supabase user. Preserve `/profiles` as explicitly local/offline management until import is complete; do not silently call a local profile authenticated, and do not delete local data after login without confirmation.

All authenticated views consume one top-level auth/session store. They must not call `getSession` independently or duplicate OAuth logic. The store exposes `{status: loading|signedOut|signedIn|error, session, user, profile}` and one subscription. The router guard waits for `loading` to settle.

## Private profile — `/account/profile`

Only the current user can read/edit it. Display:

- display name and avatar from the private application profile;
- verified email from Supabase Auth (read-only unless a dedicated email-change flow exists);
- Auth account creation timestamp;
- provider summary derived from Auth identities/app metadata (Google, email/password, or linked providers), never trusted from an editable profile field;
- private account basics and links to bookmarks/settings;
- explicit local-profile import/export/account deletion actions when implemented.

Do not create `/@username` or public profile routes. If public discussion identity remains needed, use a minimal separate projection and never expose email/provider/private timestamps.

## Bookmarks — `/account/bookmarks`

Join private bookmark rows by stable `work_id` to the public work identity/metadata map; do not copy title, cover, tags, or slug into each row. Show missing/unpublished items without leaking metadata (for example “Unavailable saved work”) and permit deletion.

Distinguish four concepts:

1. **Work bookmark:** work only; minimum first release.
2. **Chapter bookmark:** work + chapter, no page.
3. **Position bookmark:** work + chapter + page (+ mode), optionally label/notes; multiple positions may exist.
4. **Reading progress:** automatically updated last position, exactly one row per user/work/chapter (or per work if product chooses); not a bookmark and opt-out/resettable.

The current local bookmark is work-unique with optional chapter. Initial remote release may support one work bookmark while schema/API contracts preserve nullable chapter/page and a bookmark kind. Progress belongs in its own table and should wait until URL/page identity is stable.

Each card links to canonical work/read URL. Removing/clearing is confirmed, optimistic only with rollback, and announced. Bookmarks remain visible even when excluded by personal tags, while globally unavailable works do not reveal private metadata.

## Settings — `/account/settings`

Initial sections: preferred tags, excluded tags, reader defaults, local-data import, and privacy/data controls. Tag input should use canonical suggestions/keys rather than only a comma text field. Adding to one list atomically removes the same normalized tag from the other. Excluded is the hard discovery filter; preferred affects stable ranking. Explicit reset and save status are required. Weighted controls wait.

A reader settings gear may open a compact reader-settings panel for display controls and link to full account settings; it must not imply that all content preferences are changed inline.

## Shared account navigation

Refactor the existing `mountAccountNavigation` into one shared component used by landing header, rotunda shell, reader top chrome, and account shell. It consumes session state, route helpers, and sign-out action through injected/shared services. Mount it once per surface, return cleanup, and close on route change/unmount.

| State | Account trigger/menu |
|---|---|
| Auth loading | Disabled skeleton/spinner with `aria-label="Checking account"`; do not flash Login or private data |
| Signed out | Account icon opens Login and Sign up; local profile link may remain explicitly labeled |
| Signed in | Avatar/account icon opens Profile, Bookmarks, Settings, Sign out |
| Auth error/offline | Non-destructive retry/status; public reading and local profile remain available |

Sign out calls the shared Auth service, clears in-memory private caches/subscriptions, closes menus, and routes a private page to `/` or `/login`; it does not erase local profiles. Do not use link hiding as authorization.

### Landing and rotunda

Keep the current `.landing-account` mount in the header; the rotunda is inside the landing surface and uses that same control rather than a duplicate overlay. Cards remain keyboard-operable canonical links.

### Reader

The current top/bottom reader bars already mount compact account navigation in the right group beside “Last.” Preserve one account icon at top right and add a gear with a distinct accessible name. On desktop, group them after reading controls with adequate spacing and no overlap with chapter navigation/search. On mobile, use icon buttons with at least a 44px target; allow the middle chapter controls to wrap/condense. The auto-hide routine must remain visible while either menu has focus/open state. The bottom bar may link to the same actions but should not create duplicate open menus.

## Interaction and accessibility contract

- Use semantic `<button>` for menu triggers and `<a data-route>` for destinations. Trigger has `aria-haspopup="menu"` and synchronized `aria-expanded`/`aria-controls`.
- Every icon has a visible tooltip where appropriate and a stable screen-reader label (“Open account menu”, “Open reader settings”, “Sign out”). Decorative avatars use empty alt; meaningful user avatar uses the user's display-name context.
- Keyboard: Tab reaches trigger/items; Enter/Space opens/activates; Escape closes and returns focus to trigger; Arrow keys/Home/End follow the chosen menu pattern consistently.
- On open, focus first item (menu pattern) or heading (dialog pattern). On route navigation, close first, then move focus to the new page `<h1 tabindex="-1">`. Never trap focus in a nonmodal dropdown.
- Close on outside pointer interaction, Escape, route/popstate change, sign-out, and unmount. Do not close merely because focus moves within the menu.
- Account pages share a nav landmark with current-page indication (`aria-current="page"`) and skip/main heading structure.
- Loading/submit errors use `role="status"` or `role="alert"`; controls remain recoverable. Respect reduced motion.
- Mobile menus use a positioned popover or modal sheet that stays in viewport, handles safe-area insets, locks scroll only if modal, and restores focus.

## Signed-out private-route flow

After auth resolution, guard redirects to `/login?next={encoded same-origin allowlisted route}`. Login/signup share that destination through Google redirects and email confirmation. Successful auth uses replace navigation to `next`; cancellation/error remains on auth view with a safe retry. A returning session must render a neutral loading shell until ownership is known, never briefly render another/local profile.
