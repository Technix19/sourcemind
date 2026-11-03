-- SourceMind M6c: private bucket for original files, with ownership-based policies.
--
-- STATUS: DRAFT for review until applied. Apply ONLY to the dedicated SourceMind project,
-- AFTER 20261103000001_core_schema.sql.
-- Undo (dev project only): drop the three policies below, then
--   delete from storage.objects where bucket_id = 'documents';  delete from storage.buckets where id = 'documents';
--
-- Object names are "<user id>/<document id>": ids only, never a user-supplied filename.

-- ----------------------------------------------------------------- bucket
-- Private. The size and type limits are a second line of defense behind the API's own checks.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documents', 'documents', false, 12582912, array['application/pdf', 'text/plain'])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- ---------------------------------------------------------------- policies
-- RLS is already enabled on storage.objects by Supabase. With no policy for the anonymous
-- role, anonymous callers get nothing. There is NO update policy: stored files are immutable.
--
-- Careful: inside these subqueries `documents` also has a column called "name", so the
-- object's name is always written as storage.objects.name.

-- Read (and create signed links for) a file only if you own the document that points at it.
create policy documents_objects_select_own on storage.objects
  for select to authenticated
  using (
    bucket_id = 'documents'
    and exists (
      select 1 from public.documents d
      where d.storage_key = storage.objects.name
        and d.user_id = (select auth.uid())
    )
  );

-- Upload only into your own folder, and only for a document row you already created.
-- This stops "orphan" files that no document owns (storage-quota abuse).
create policy documents_objects_insert_own on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'documents'
    and (storage.foldername(storage.objects.name))[1] = (select auth.uid())::text
    and exists (
      select 1 from public.documents d
      where d.storage_key = storage.objects.name
        and d.user_id = (select auth.uid())
    )
  );

-- Delete anything in your own folder (so leftovers from a failed upload can always be cleaned up).
create policy documents_objects_delete_own on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(storage.objects.name))[1] = (select auth.uid())::text
  );
