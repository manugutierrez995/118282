> **HISTORICAL / SUPERSEDED:** This document records the former remote-account architecture. Runtime accounts, bookmarks, preferences, and discussion posting were replaced by local browser profiles; see [`docs/local-first-browser-profiles.md`](../local-first-browser-profiles.md).

# Accounts and per-work discussion setup

1. Create a Supabase project and apply `supabase/migrations/202607170001_discussion_mvp.sql` with the SQL editor or CLI.
2. In **Authentication → Providers**, enable Anonymous Sign-Ins and Google. Configure Google with only `openid email profile` and enable manual identity linking. Add the exact local Vite URL and production Cloudflare URL to Supabase's redirect allow list and the Google OAuth client.
3. Copy `.env.example` to `.env.local` and set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`. Configure the same two variables in Cloudflare Pages/Workers. The publishable key is designed for browser use. **Never place a service-role key in frontend variables, source, logs, or a browser bundle.**
4. Verify every table has RLS enabled. Test public reading, anonymous posting, Google posting, linking an existing anonymous identity, editing/deleting, voting/reporting and bookmarks in a staging project before production.

An anonymous database identity is created only on the first post, vote, report, or bookmark. Choosing Google on that identity calls Supabase manual `linkIdentity`, retaining the user UUID and therefore its authorship and bookmarks. “Anonymous” is public display privacy, not network or cryptographic anonymity.

## Data and security

Public comments contain the stable `parent_work_id`, visible mode, optional profile, plain text and timestamps. The separately protected `comment_authorship` table has no client-readable policy. Mutations are authenticated, fixed-search-path security-definer RPCs; they derive `auth.uid()`, validate ownership, depth/work matching, length, cooldown, uniqueness and deletion state. Bookmark RLS permits only `auth.uid()` rows. Moderator tooling can later set `deleted_at` using a trusted server role without changing conversation structure.

Pagination fetches at most 30 top-level comments by `(created_at,id)` cursor and returns their one-level replies in one bounded RPC. No global realtime subscription is used.

## Portable exports

Export public archive data without private identity links:

```sql
copy (select id,work_id,parent_id,display_mode,public_profile_id,body,created_at,edited_at,deleted_at from public.comments order by work_id,created_at,id) to stdout with csv header;
```

For disaster recovery, use Supabase's PostgreSQL backup/export facilities to make an encrypted complete database backup, including private authorship, auth records, reports and bookmarks. Restrict and audit access. Never commit either export when it includes user or private authorship data.
