-- SourceMind M6a: core schema with Row Level Security.
--
-- STATUS: DRAFT for review. Not applied to any database yet.
-- Apply ONLY to the dedicated SourceMind Supabase project.
-- Undo (dev project only): drop trigger on_auth_user_created on auth.users;
--   drop function public.handle_new_user(); drop table public.chunks, public.documents, public.profiles;

-- ---------------------------------------------------------------- tables

create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 80),
  created_at   timestamptz not null default now()
);

create table public.documents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name        text not null check (char_length(name) between 1 and 130),
  mime_type   text,
  size_bytes  bigint  not null check (size_bytes >= 0),
  page_count  integer not null check (page_count >= 1),
  status      text    not null default 'ready'
              check (status in ('uploading', 'extracting', 'chunking', 'indexing', 'ready', 'failed', 'deleting')),
  storage_key text unique,              -- filled in by M6c (private file storage)
  created_at  timestamptz not null default now(),
  unique (id, user_id)                  -- target for chunks' composite foreign key
);

create index documents_user_created_idx on public.documents (user_id, created_at desc);

create table public.chunks (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null,
  user_id      uuid not null default auth.uid(),
  page_number  integer not null check (page_number >= 1),   -- true PDF page, starts at 1
  chunk_index  integer not null check (chunk_index >= 0),
  start_offset integer not null check (start_offset >= 0),
  end_offset   integer not null,
  text         text not null check (char_length(text) between 1 and 5000),
  token_count  integer,
  check (end_offset > start_offset),
  unique (document_id, page_number, chunk_index),
  -- A chunk's owner must equal its document's owner. Enforced by the database
  -- itself, so even a mistake in a policy cannot attach a chunk to someone else's document.
  foreign key (document_id, user_id)
    references public.documents (id, user_id) on delete cascade
);

create index chunks_user_document_idx on public.chunks (user_id, document_id);

-- ------------------------------------------------- privileges (default deny)
-- Supabase grants broad default privileges on new tables; remove them, then
-- grant back only what the app needs. The anonymous role gets nothing.

revoke all on public.profiles, public.documents, public.chunks from anon, authenticated;

grant select, update (display_name) on public.profiles  to authenticated;
-- Update is limited to these columns: user_id, sizes and timestamps can never be changed by a client.
grant select, insert, delete on public.documents to authenticated;
grant update (name, status, storage_key) on public.documents to authenticated;
grant select, insert, delete         on public.chunks    to authenticated;  -- chunks are immutable

-- ------------------------------------------------------ row level security

alter table public.profiles  enable row level security;
alter table public.documents enable row level security;
alter table public.chunks    enable row level security;

-- (select auth.uid()) is evaluated once per statement instead of once per row.

create policy profiles_select_own on public.profiles
  for select to authenticated using (id = (select auth.uid()));
create policy profiles_update_own on public.profiles
  for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

create policy documents_select_own on public.documents
  for select to authenticated using (user_id = (select auth.uid()));
create policy documents_insert_own on public.documents
  for insert to authenticated with check (user_id = (select auth.uid()));
create policy documents_update_own on public.documents
  for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy documents_delete_own on public.documents
  for delete to authenticated using (user_id = (select auth.uid()));

create policy chunks_select_own on public.chunks
  for select to authenticated using (user_id = (select auth.uid()));
create policy chunks_insert_own on public.chunks
  for insert to authenticated with check (user_id = (select auth.uid()));
create policy chunks_delete_own on public.chunks
  for delete to authenticated using (user_id = (select auth.uid()));

-- ------------------------------------------------- profile on sign-up

create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''          -- prevents search-path hijacking of a privileged function
as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$;

revoke all on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
