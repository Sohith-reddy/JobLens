-- Run this in Supabase SQL Editor.
-- Creates profile data table + profile picture metadata table with RLS policies.

create table if not exists public.user_profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  first_name text,
  last_name text,
  bio text,
  skills text[] default '{}',
  avatar_url text,
  avatar_storage_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.profile_pictures (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  bucket_name text not null default 'profilepics',
  storage_path text not null unique,
  public_url text,
  file_name text,
  file_size bigint,
  mime_type text,
  is_current boolean not null default false,
  uploaded_at timestamptz not null default now()
);

create index if not exists idx_profile_pictures_user_id on public.profile_pictures (user_id);

alter table public.user_profiles enable row level security;
alter table public.profile_pictures enable row level security;

-- user_profiles policies
create policy if not exists "users can read own profile"
on public.user_profiles
for select
to authenticated
using (auth.uid() = user_id);

create policy if not exists "users can insert own profile"
on public.user_profiles
for insert
to authenticated
with check (auth.uid() = user_id);

create policy if not exists "users can update own profile"
on public.user_profiles
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- profile_pictures policies
create policy if not exists "users can read own picture metadata"
on public.profile_pictures
for select
to authenticated
using (auth.uid() = user_id);

create policy if not exists "users can insert own picture metadata"
on public.profile_pictures
for insert
to authenticated
with check (auth.uid() = user_id);

create policy if not exists "users can update own picture metadata"
on public.profile_pictures
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- Optional trigger to keep updated_at current
create or replace function public.set_user_profiles_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_set_user_profiles_updated_at on public.user_profiles;
create trigger trg_set_user_profiles_updated_at
before update on public.user_profiles
for each row
execute function public.set_user_profiles_updated_at();

-- Storage policies for bucket: profilepics
-- Requires bucket to exist. You mentioned it is already created.

create policy if not exists "users can upload own profile pics"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'profilepics' and
  auth.uid()::text = (storage.foldername(name))[1]
);

create policy if not exists "users can update own profile pics"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'profilepics' and
  auth.uid()::text = (storage.foldername(name))[1]
)
with check (
  bucket_id = 'profilepics' and
  auth.uid()::text = (storage.foldername(name))[1]
);

create policy if not exists "users can read profile pics"
on storage.objects
for select
to authenticated
using (bucket_id = 'profilepics');

create policy if not exists "users can delete own profile pics"
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'profilepics' and
  auth.uid()::text = (storage.foldername(name))[1]
);
