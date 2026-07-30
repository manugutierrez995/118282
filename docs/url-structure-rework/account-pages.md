> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Private account pages and shared navigation

## Account shell

Create one `AccountShell` and one shared `AccountMenu`/session presenter used by landing, rotunda (through the landing header), reader, and all account pages. It consumes a top-level auth/session service; it must not create Supabase clients or restore sessions independently. The shell provides consistent breadcrumbs/title, account navigation, loading/error states, and a view outlet.

Routes are private and owner-only:

- `/account/profile`
- `/account/bookmarks`
- `/account/settings`

There is no `/@username` or public user page in this scope. If public discussion names remain necessary, expose a minimal discussion identity separately from private account data.

## Profile page

Show the signed-in user's display name/avatar, verified email (read-only unless a dedicated Supabase change-email flow is built), account creation time, linked providers, and links to bookmarks/settings. Provider display must account for multiple identities rather than labeling a user exclusively “Google” or “email.” Basic profile fields come from an owner-only profile row; security-sensitive email/provider data comes from the Auth session/user, not copied as an authoritative profile field.

Editing display name/avatar uses accessible labeled controls, validation, optimistic UI only with rollback, and an owner-scoped update under RLS. Account deletion is a separate destructive flow with reauthentication/confirmation and server-side deletion; it must not be a client table delete masquerading as complete deletion.

## Bookmarks page and concepts

Distinguish these states in UI and storage:

1. **Work bookmark:** saved work, no chapter/page.
2. **Chapter bookmark:** work + stable chapter ID, no page.
3. **Page bookmark:** work + chapter + page (+ mode snapshot).
4. **Reading progress:** automatically updated last position; not a bookmark and not shown as user intent.

The initial migration can preserve/import existing work bookmarks, then add page/chapter fields in a normalized `user_bookmarks` table. The page lists owner rows and joins them client-side to the public identity/work index; it does not duplicate cover/title/tags in private records. Missing/deleted works display a tombstone and allow removal. Sort/filter by update time and type; labels/notes can wait.

Reader affordances should clearly separate “Bookmark work,” “Bookmark this page,” and automatic “Continue reading.” Bookmarks page entries link to canonical work/read URLs. `last-read status` belongs in progress unless it is a bookmark presentation flag.

## Settings page

Initial sections:

- content preferences: Excluded tags and Preferred tags;
- reader defaults: reserved for mode/theme/accessibility choices, added only when backed by real settings;
- account/security links and sign out.

Adding a tag to one list atomically upserts that preference and removes/replaces the opposite preference. The database unique key `(user_id, tag_key)` prevents simultaneous opposites. Exclusions are hard filters in discovery, preferences rank remaining works. Direct public links are not authorization-filtered. Do not edit `src/data/tags.json` or per-work manifests from this page.

## Shared navigation placement

### Landing and rotunda

Add an account icon/button to the existing `.landing-header`, after search on desktop. The rotunda is part of the landing surface and should not render a second auth control. Signed out: icon opens menu with Log in/Sign up. Signed in: avatar/account icon opens Profile, Bookmarks, Settings, Sign out. A settings gear may be an item rather than another always-visible landing icon.

### Reader

Extend `buildReaderNavBar` rather than floating controls over page images. Reserve a right-side group for an account icon and a distinct settings gear near the existing Last control. On narrow screens, retain Home, chapter navigation, and account trigger; place low-priority Last/search/settings actions in an overflow sheet if measurements show collision. The bottom reader bar can reuse navigation destinations but should not initialize another auth subscription/menu state.

### Account pages

Desktop: persistent/compact side or top subnavigation with Profile, Bookmarks, Settings; account menu includes Sign out. Mobile: a single account trigger opens a modal-like menu/sheet, plus visible current-section heading. Do not rely solely on icons; tooltips/accessible names and active state are required.

## Session UI state matrix

| Session state | Account control | Private route behavior |
|---|---|---|
| loading/unknown | disabled skeleton button, `aria-busy`; no signed-out flash | render neutral guarded shell; do not fetch private rows or redirect yet |
| signed out | generic account icon; Login/Sign up menu | replace to `/login?next=...` after resolution |
| anonymous Supabase user | treat as guest for private account product; offer upgrade/link | require/link durable identity before account pages unless product decides otherwise |
| signed in email | avatar/initial; full account menu | load only owner data |
| signed in Google | same as email | identical account system |
| error/offline | stable icon + retry/status; cached public reader remains usable | do not reveal stale data from another user; explicit retry/sign-out |

Avoid layout shift by reserving the icon footprint during auth loading.

## Sign out

Call the shared auth service's Supabase `signOut`, clear in-memory private queries and user-derived personalization, close menus, then replace to `/` (or keep a public work route if sign-out began there). Do not clear public asset caches. Never leave prior user's account DOM or indexed private snapshot visible. If sign-out fails, announce the error and do not pretend it succeeded.

## Accessibility and interaction contract

- Use buttons for menu actions and anchors for routes, preserving open-in-new-tab.
- Account trigger: `aria-label="Open account menu"`, `aria-haspopup="menu"`, `aria-expanded`, `aria-controls`.
- Settings icon: `aria-label="Account settings"`; Sign out is text, not an ambiguous exit glyph.
- Menus support Tab/Shift+Tab and Escape; optional arrow-key menu semantics must be implemented fully if `role="menu"` is used. A simple disclosure list with normal links is safer.
- On open, move focus to the first actionable item only for keyboard-triggered/modal mobile presentation; otherwise preserve sensible pointer behavior. On Escape/outside click, close and restore focus to trigger.
- Close on outside pointerdown, Escape, route changes, sign-out, and session identity change. Remove listeners on unmount.
- Route changes move focus to the new page `<h1>` (programmatically focusable with `tabindex="-1"`) and announce title. Reader fragment/passive page changes must not steal focus.
- Visible focus styles must survive dark reader chrome; targets should meet 44×44 CSS pixels on touch.
- Menus must not auto-hide while focused. Integrate with the reader's existing chrome focus/search checks.
- Use `aria-live="polite"` for session, bookmark, preference, and deep-link results; errors associate to fields.
- Respect reduced motion for menu and reader scrolling.

## Mobile/desktop verification

Test keyboard-only at desktop widths; touch and screen rotation at representative narrow widths; account menu while reader chrome is auto-hiding; search open simultaneously; page navigation controls; safe-area insets; 200% zoom/reflow; and a screen reader. The mobile HTML maintenance entry is not a second mobile app—responsive behavior is within the primary shell when it is deployed.
