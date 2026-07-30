> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Authentication, authorization, and proposed data model

> **Status:** Everything under “Proposed SQL” is design pseudocode. It was not applied in this run. The only checked-in migration is discussion MVP SQL, and repository presence does not prove remote application.

## Current authentication

The single lazy Supabase client in `src/discussion/supabase.js` enables session persistence, refresh, and OAuth callback detection. It supports anonymous sign-in, Google OAuth, and linking a Google identity to an existing anonymous user. Discussion retrieves the session when its lazy UI initializes. Email/password, password reset, shared auth state, and account route guards do not exist.

## Unified identity design

Use `auth.users.id` as the canonical application user ID for Google, email/password, and linked identities. Both login methods must land in the same private tables keyed by this UUID. Provider identity belongs to Supabase `auth.identities`; do not create separate “Google users” and “email users” profile rows.

Account linking deserves explicit UI. Supabase may create distinct users if the same human authenticates through unlinked identities depending on provider/email settings; never merge solely on an unverified matching email. Prefer verified automatic linking only according to current Supabase policy, or a reauthenticated link flow. Anonymous → Google/email must link/upgrade the current auth user so work created under its UUID survives.

Add email/password flows through `signUp`, `signInWithPassword`, reset-password email, and update-password callback in the shared auth module. Configure exact allowed redirect URLs for production/preview/local environments. Do not leak whether an email exists more than Supabase's safe responses.

## Shared session lifecycle

Create one session store/service initialized before routing private pages:

1. create/get the singleton client;
2. call `getSession()` and hold route in `loading` state;
3. subscribe once to `onAuthStateChange` for OAuth completion, refresh, sign-in/out, and user updates;
4. expose `{status, session, user}` plus methods; unsubscribe on app teardown/HMR;
5. load user rows only after authenticated durable identity is established.

Private routes wait for resolution. Signed-out visitors are replaced to `/login?next=<validated relative target>`. During Google OAuth store the intended relative target separately, then send `redirectTo` to a fixed allowed callback/application origin—not arbitrary input. Email login uses the same target. Returning sessions avoid a signed-out flash.

Because the host is static, guards are client-side navigation controls; they are not authorization. Supabase RLS is the security boundary. No private route HTML should contain user data before client fetch.

## Current schema conflicts

The migration defines `profiles` with public select because comments display names. New private profile requirements conflict. Recommended migration strategy later:

1. rename/split public display identity to `discussion_profiles(user_id, display_name, avatar_url)` with deliberately public fields, **or** have a safe RPC project only those fields;
2. make `profiles` owner-selectable and owner-writable;
3. preserve comment foreign keys/behavior through a reversible migration;
4. migrate current `bookmarks` into `user_bookmarks` or evolve it carefully.

Do not silently change the public policy before discussion compatibility tests.

## Immediate versus later tables

**Needed for account foundation:** private `profiles`; evolved `user_bookmarks` (at least work bookmark and optional position columns); `user_tag_preferences`. **Create when automatic progress ships, not merely for URL routing:** `user_reading_progress`. Likes, dismissals, interaction events, recommendation resets, and weighted behavioral models wait.

Work catalog metadata currently lives statically, not in Postgres. Therefore `work_id` cannot honestly have a database foreign key until a canonical `works` registry exists. Validate IDs application-side and use a constrained text column initially; later add a small registry/table or synchronize catalog IDs before adding FK. Do not copy titles/tags/covers into every private row.

## Proposed SQL/schema pseudocode — not applied

```sql
-- PSEUDOCODE: refine names/types against the deployed discussion schema first.
create type public.bookmark_kind as enum ('work', 'chapter', 'page');
create type public.tag_preference_type as enum ('preferred', 'excluded');

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null check (char_length(btrim(display_name)) between 1 and 80),
  avatar_url text check (avatar_url is null or avatar_url ~ '^https://'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.user_bookmarks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  work_id text not null check (char_length(work_id) between 1 and 128),
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
      or (kind='page' and chapter_id is not null and page_number is not null))
);
create unique index user_bookmark_location_uq on public.user_bookmarks
  (user_id, work_id, kind, coalesce(chapter_id,''), coalesce(page_number,0), coalesce(reader_mode,''));
create index user_bookmarks_owner_updated_idx on public.user_bookmarks(user_id, updated_at desc);
create index user_bookmarks_work_idx on public.user_bookmarks(work_id); -- only if operationally needed

create table public.user_tag_preferences (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tag_key text not null,
  preference_type public.tag_preference_type not null,
  weight smallint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, tag_key),
  check (tag_key = lower(tag_key) and tag_key ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  check (weight is null or weight between -100 and 100),
  check ((preference_type='excluded' and (weight is null or weight <= 0))
      or (preference_type='preferred' and (weight is null or weight >= 0)))
);
create index user_tag_preferences_owner_type_idx
  on public.user_tag_preferences(user_id, preference_type, tag_key);

-- Add only when automatic progress is implemented.
create table public.user_reading_progress (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  work_id text not null,
  chapter_id text not null,
  page_number integer not null check (page_number >= 1),
  reader_mode text not null default 'continuous' check (reader_mode in ('continuous','single')),
  progress_percent numeric(5,2) check (progress_percent between 0 and 100),
  updated_at timestamptz not null default now(),
  primary key (user_id, work_id, chapter_id, reader_mode)
);
create index user_progress_owner_updated_idx
  on public.user_reading_progress(user_id, updated_at desc);
```

Do not store `work_slug` redundantly in bookmark/progress rows; resolve current slug from the identity map by stable ID. A historical slug belongs in a route-alias table, not every bookmark.

## RLS pseudocode

```sql
alter table public.profiles enable row level security;
alter table public.user_bookmarks enable row level security;
alter table public.user_tag_preferences enable row level security;
alter table public.user_reading_progress enable row level security;

create policy profile_own_select on public.profiles for select to authenticated
  using (user_id = auth.uid());
create policy profile_own_insert on public.profiles for insert to authenticated
  with check (user_id = auth.uid());
create policy profile_own_update on public.profiles for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
-- Repeat owner equality for SELECT/INSERT/UPDATE/DELETE on each private table.
-- Prefer explicit policies per operation; grant only required table privileges.
```

RLS tests must authenticate as user A/user B and attempt direct REST queries and mutations, not merely inspect hidden UI. Never use a service-role key in the browser. RPCs must set a safe `search_path`, verify `auth.uid()`, validate all work/chapter/page inputs, and avoid SECURITY DEFINER unless necessary and reviewed.

## Constraints, normalization, and deletion

- User ID: FK/cascade to Auth.
- Work ID: opaque text matching generated identity map; add FK only after a stable DB work registry exists.
- Chapter ID: exact stable manifest ID, constrained length; never raw URL/path traversal.
- Tag key: canonical vocabulary key, normalized server-side/client-side with the same tested function. Display labels live in public tag vocabulary, not private rows.
- Profile display names preserve Unicode; trim and length-limit. They are not usernames/routes.
- Timestamps update through a common trigger or explicit updates; prevent client spoofing where relevant.
- Account deletion requires a trusted server/edge function using admin privileges after reauthentication, deletes the Auth user, cascades private rows, and applies discussion retention/anonymization policy. A browser cannot delete `auth.users` with a publishable key.
- A user may delete individual profile/bookmark/preference/progress rows where policy permits; deleting profile should not delete Auth accidentally.

## Existing bookmark migration

Copy each `bookmarks(user_id, work_id, created_at)` to `user_bookmarks(kind='work')`, preserving timestamp and ID semantics. Deduplicate under the location unique constraint. Decide whether anonymous bookmark owners upgrade in place; do not expose them as account bookmarks until durable login. Keep a compatibility view/RPC or dual-read only for a bounded rollout, then remove it.

## Anonymous progress migration

No reading progress exists today. If future anonymous local progress is introduced, store versioned records keyed by stable work ID in IndexedDB/localStorage with no account data. After durable login:

1. show explicit “Import reading progress” or apply a documented safe default;
2. validate each work/chapter/page against current public metadata;
3. merge by newest timestamp, never overwrite newer server progress;
4. upload through owner-RLS rows;
5. mark/import transaction idempotently, then remove local data only after success;
6. do not migrate between different signed-in users on a shared device.

Bookmarks represent intent and should require a deliberate merge/conflict screen if both local/server versions exist.

## Security checks

Test OAuth open redirects, malformed callback fragments, session loading races, stale private UI after sign-out/user switch, cross-user reads/writes, anonymous role behavior, XSS in names/labels/notes, URL validation, public-profile leakage, shared cache headers, deletion, and service-role absence. The account icon/guard is UX only; RLS and trusted deletion endpoints enforce ownership.
