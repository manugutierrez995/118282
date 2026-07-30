# Authentication, authorization, and proposed data model

## Current fact

There is no active authentication client. Runtime profiles/bookmarks/preferences are IndexedDB-only. Environment variables and two checked-in Supabase migrations remain, but `package.json` has no Supabase JS dependency and source contains no Google/email calls. Live provider/schema/migration status is unknown. The 20260717 SQL's `profiles_public_read` is suitable only for public comment display and violates the requested private-profile meaning.

Everything below is **proposed, not applied**. Before implementation, inventory the live Supabase project read-only and reconcile migration history.

## Unified identity and session service

Use Supabase Auth `auth.users.id` as the canonical application user UUID for Google and email/password alike. Provider is an identity attribute, not a separate application account/table. Enable account linking only through Supabase-supported, verified flows; do not merge users solely because client-submitted emails match. A user with multiple linked identities still owns one UUID and one set of rows.

A single `AuthStore` creates one Supabase client and performs:

1. synchronous `loading` initial state;
2. `getSession()` restoration using Supabase's persisted session;
3. one `onAuthStateChange` subscription for sign-in, refresh, linking, password recovery, and sign-out;
4. private profile fetch/upsert only after a verified user exists;
5. generation/abort checks so stale requests from a prior user cannot populate the next user's UI;
6. cleanup of private query caches on user change/sign-out.

Google uses OAuth with an allowlisted `/auth/callback` and signed/sanitized local destination. Email/password supplies sign-up, sign-in, confirmation, forgot/reset, rate-limit/error, and email-enumeration-safe messaging. Both land in the same session store and account routes. Never store access tokens in custom URL parameters or profile rows.

Because deployment is static, initial guards are client-side UX. Cloudflare's shell can be public; private data is fetched after session resolution. Database RLS is the actual authorization boundary. If edge SSR is later introduced, it may add server guards but cannot replace RLS.

## Route guard

```text
if auth.status == loading: render neutral busy shell
else if private route and no authenticated non-anonymous user:
  replace /login?next=<safe allowlisted current pathname+query+hash>
else render route
```

`next` must be same-origin, begin with one slash (not `//`), contain no control/backslash, and resolve only to known internal routes. On logout: unsubscribe/private-cache clear, `supabase.auth.signOut()`, replace away from private route, preserve local IndexedDB unless separately deleted.

## Immediate versus later tables

**After identity/route foundations, immediate account release:** private `account_profiles`, enhanced `user_bookmarks`, `user_tag_preferences`. If live `bookmarks`/preference tables already exist, alter/migrate deliberately rather than create duplicates. Keep public work metadata in a generated catalog initially; a database `works` foreign key is optional until the public work registry is authoritative in Postgres.

**Wait:** `user_reading_progress` until page/chapter/mode semantics and consent are stable; bookmark notes/labels may wait behind basic work bookmarks; behavior-derived recommendations, likes/dismissals, and event history are later opt-in product work.

Do not store arrays of bookmarks/preferences in a remote profile row. The existing local arrays are acceptable only for self-contained device profiles.

## Preliminary SQL pseudocode — PROPOSED, NOT APPLIED

```sql
-- Names intentionally avoid reusing the currently public discussion `profiles` blindly.
create table public.account_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null check (char_length(btrim(display_name)) between 1 and 80),
  avatar_url text check (avatar_url is null or avatar_url ~ '^https://'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create type public.bookmark_kind as enum ('work', 'chapter', 'position');
create table public.user_bookmarks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  work_id text not null,
  kind public.bookmark_kind not null default 'work',
  chapter_id text,
  page_number integer check (page_number is null or page_number >= 1),
  reader_mode text check (reader_mode is null or reader_mode in ('continuous','single')),
  label text check (label is null or char_length(label) <= 120),
  notes text check (notes is null or char_length(notes) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((kind='work' and chapter_id is null and page_number is null)
      or (kind='chapter' and chapter_id is not null and page_number is null)
      or (kind='position' and chapter_id is not null and page_number is not null))
);
create unique index user_bookmark_work_unique
  on public.user_bookmarks(user_id, work_id) where kind='work';
create unique index user_bookmark_chapter_unique
  on public.user_bookmarks(user_id, work_id, chapter_id) where kind='chapter';
create index user_bookmarks_owner_updated on public.user_bookmarks(user_id, updated_at desc);
create index user_bookmarks_work on public.user_bookmarks(work_id);

create type public.tag_preference_type as enum ('preferred','excluded');
create table public.user_tag_preferences (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tag_key text not null check (tag_key = lower(tag_key) and tag_key ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  preference_type public.tag_preference_type not null,
  weight smallint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, tag_key),
  check (weight is null or weight between -100 and 100)
);
create index user_tag_preferences_owner_type on public.user_tag_preferences(user_id, preference_type);

create table public.user_reading_progress (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  work_id text not null,
  chapter_id text not null,
  page_number integer not null check (page_number >= 1),
  reader_mode text not null default 'continuous' check (reader_mode in ('continuous','single')),
  progress_percent numeric(5,2) check (progress_percent between 0 and 100),
  updated_at timestamptz not null default now(),
  primary key (user_id, work_id, chapter_id)
);
create index user_progress_owner_updated on public.user_reading_progress(user_id, updated_at desc);
```

A position bookmark may intentionally have duplicates; if product wants idempotent saves, add a unique index on `(user_id, work_id, chapter_id, page_number, coalesce(reader_mode,''))`. Do not store `work_slug`; join it from stable ID. If Postgres gains a canonical `works(id)` registry, add validated foreign keys later. Chapter foreign keys should wait for a stable chapter registry rather than reference mutable path text incorrectly.

## RLS template

Enable RLS on every private table. For each, policies are:

```sql
create policy own_select on TABLE for select to authenticated using (user_id = auth.uid());
create policy own_insert on TABLE for insert to authenticated with check (user_id = auth.uid());
create policy own_update on TABLE for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_delete on TABLE for delete to authenticated using (user_id = auth.uid());
```

Revoke `anon`; grant only required operations to `authenticated`. Test cross-user select/insert/update/delete, not just UI visibility. Service-role credentials never enter Vite/browser bundles. Security-definer functions must set a safe `search_path`, validate `auth.uid()`, minimize grants, and receive adversarial tests.

## Profile/public discussion split

Recommended: `account_profiles` is owner-only. If comments need a public name/avatar, use `discussion_profiles(user_id, display_name, avatar_url)` or an allowlisted view/RPC with no email/provider/private dates. Reconcile the existing `comments.public_profile_id` deliberately. Never simply change current public reads without checking comment functionality.

Email, provider identities, `created_at`, and verification state should normally be read from the Auth user in the current session, not copied into editable application rows. Profile creation should be idempotent (`insert ... on conflict`) through a trusted trigger/RPC or client insert protected by RLS.

## Normalization and deletion

- Stable work ID is an opaque string in private tables until the catalog contract is fixed; never key by title/slug.
- Public slugs use the route-manifest normalization policy, but are not stored per bookmark.
- Tags normalize through one shared client/server function: trim, lowercase, Unicode policy, whitespace/punctuation to hyphens, validate length. Primary key ensures one polarity per tag/user.
- `auth.users` foreign keys use `on delete cascade`; account deletion requires recent reauthentication and a trusted server/edge function capable of deleting the Auth user. Preview scope, confirm, delete Auth user (cascades private rows), clear session/private cache, and optionally ask separately whether to erase local profiles.
- Avoid URL-based avatar secrets; proxy/allowlist policy may be needed. Escape text and enforce sizes server-side.

## Anonymous local-to-authenticated migration

After login, show a preview of selected local profile data. User chooses categories (display/avatar, work bookmarks, tag preferences; progress only later). Resolve every local `workId` through the canonical identity manifest, skip/report unknown/unpublished IDs, normalize tags, and import with idempotent upserts in a transaction/RPC where practical. Remote conflicts default to union for bookmarks and explicit remote-vs-local choice for profile fields; preference conflict uses the most explicit user choice and never leaves both polarities. Record a local migration receipt/version to prevent repeated prompts, but retain the local profile until the user explicitly deletes it. Never migrate archived comments as public posts automatically.

## Security verification

Test two Google/email users plus signed-out/expired sessions; prove profile, bookmark, preference, and progress isolation with direct Supabase requests using each JWT. Test forged `user_id`, stale-tab user switching, OAuth `next` injection, reset-link replay/expiry, provider linking, account deletion, and that public caches contain no user response/body/header. Hiding account links is not a security test.
