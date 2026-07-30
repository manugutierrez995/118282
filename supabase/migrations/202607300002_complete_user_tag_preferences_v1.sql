create table public.public_tag_vocabulary (
  tag_key text primary key,
  display_label text not null,
  category text,
  aliases text[] not null default '{}',
  user_selectable boolean not null default true,
  status text not null check (status in ('active', 'deprecated'))
);
insert into public.public_tag_vocabulary(tag_key, display_label, category) values ('futanari', 'Futanari', 'Content');
revoke all on public.public_tag_vocabulary from anon, authenticated;
grant select on public.public_tag_vocabulary to anon, authenticated;

do $$ begin
  if exists (select 1 from public.user_tag_preferences p left join public.public_tag_vocabulary v using(tag_key) where v.tag_key is null) then
    raise exception 'Invalid existing user tag preferences require review before applying the vocabulary constraint';
  end if;
end $$;
alter table public.user_tag_preferences add constraint user_tag_preferences_allowed_tag
  foreign key (tag_key) references public.public_tag_vocabulary(tag_key);
create index user_tag_preferences_owner_type_idx on public.user_tag_preferences(user_id, preference_type);

create function public.set_user_tag_preferences_updated_at() returns trigger language plpgsql set search_path = '' as $$
begin new.updated_at = now(); return new; end $$;
create trigger user_tag_preferences_updated_at before update on public.user_tag_preferences
for each row execute function public.set_user_tag_preferences_updated_at();

create function public.set_user_tag_preference(p_tag_key text, p_preference_type public.user_tag_preference_type)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if not exists (select 1 from public.public_tag_vocabulary where tag_key = p_tag_key and user_selectable and status = 'active') then raise exception 'Tag is not selectable'; end if;
  insert into public.user_tag_preferences(user_id, tag_key, preference_type)
  values (auth.uid(), p_tag_key, p_preference_type)
  on conflict (user_id, tag_key) do update set preference_type = excluded.preference_type;
end $$;
create function public.remove_user_tag_preference(p_tag_key text) returns void language sql security invoker set search_path = '' as $$
  delete from public.user_tag_preferences where user_id = auth.uid() and tag_key = p_tag_key
$$;
create function public.reset_user_tag_preferences() returns void language sql security invoker set search_path = '' as $$
  delete from public.user_tag_preferences where user_id = auth.uid()
$$;
revoke all on function public.set_user_tag_preference(text, public.user_tag_preference_type) from public;
revoke all on function public.remove_user_tag_preference(text) from public;
revoke all on function public.reset_user_tag_preferences() from public;
grant execute on function public.set_user_tag_preference(text, public.user_tag_preference_type) to authenticated;
grant execute on function public.remove_user_tag_preference(text) to authenticated;
grant execute on function public.reset_user_tag_preferences() to authenticated;
