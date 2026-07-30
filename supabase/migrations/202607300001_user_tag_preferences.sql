create type public.user_tag_preference_type as enum ('preferred', 'excluded');
create table public.user_tag_preferences (
  user_id uuid not null references auth.users(id) on delete cascade,
  tag_key text not null check (char_length(tag_key) between 1 and 80),
  preference_type public.user_tag_preference_type not null,
  weight smallint,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  primary key (user_id, tag_key)
);
alter table public.user_tag_preferences enable row level security;
create policy user_tag_preferences_own_select on public.user_tag_preferences for select to authenticated using (user_id = auth.uid());
create policy user_tag_preferences_own_insert on public.user_tag_preferences for insert to authenticated with check (user_id = auth.uid());
create policy user_tag_preferences_own_update on public.user_tag_preferences for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy user_tag_preferences_own_delete on public.user_tag_preferences for delete to authenticated using (user_id = auth.uid());
grant select, insert, update, delete on public.user_tag_preferences to authenticated;
