-- SourceMind M6d: vector embeddings and user-scoped similarity search.
--
-- STATUS: DRAFT for review until applied. Apply ONLY to the dedicated SourceMind project,
-- AFTER migrations 20261103000001 and 20261103000002.
-- Undo (dev project only): drop function public.match_chunks(extensions.vector, integer, uuid[], text);
--   drop table public.embeddings; alter table public.documents drop column embedding_model;
--   alter table public.chunks drop constraint chunks_id_user_unique;   (the extension can stay)

create extension if not exists vector with schema extensions;

-- ----------------------------------------------------- what the schema needs first
-- Lets embeddings carry a composite foreign key, exactly like chunks do for documents.
alter table public.chunks add constraint chunks_id_user_unique unique (id, user_id);

-- Which embedding model (if any) indexed this document. Lets the API tell, per document,
-- whether meaning search is possible without scanning the vectors.
alter table public.documents add column embedding_model text
  check (embedding_model is null or char_length(embedding_model) between 1 and 100);
grant update (embedding_model) on public.documents to authenticated;

-- --------------------------------------------------------------------- embeddings
-- 384 dimensions = BAAI/bge-small-en-v1.5. A different model needs a different column size
-- (and a new migration); model_id is stored so vectors from different models never mix.
create table public.embeddings (
  chunk_id   uuid primary key,
  user_id    uuid not null default auth.uid(),
  model_id   text not null check (char_length(model_id) between 1 and 100),
  embedding  extensions.vector(384) not null,
  created_at timestamptz not null default now(),
  -- An embedding's owner must equal its chunk's owner, enforced by the database itself.
  foreign key (chunk_id, user_id) references public.chunks (id, user_id) on delete cascade
);

create index embeddings_user_model_idx on public.embeddings (user_id, model_id);
-- No ANN (HNSW/IVF) index on purpose: each user has at most a few thousand vectors, an exact scan
-- filtered by user_id is exact and simple, and approximate indexes combined with row filtering
-- can silently return fewer results than asked for.

-- Default deny, then grant narrowly. Vectors are immutable: no update.
revoke all on public.embeddings from anon, authenticated;
grant select, insert, delete on public.embeddings to authenticated;

alter table public.embeddings enable row level security;

create policy embeddings_select_own on public.embeddings
  for select to authenticated using (user_id = (select auth.uid()));
create policy embeddings_insert_own on public.embeddings
  for insert to authenticated with check (user_id = (select auth.uid()));
create policy embeddings_delete_own on public.embeddings
  for delete to authenticated using (user_id = (select auth.uid()));

-- ------------------------------------------------------------------ similarity search
-- SECURITY INVOKER (the default, written out on purpose): runs with the CALLER's rights, so
-- Row Level Security applies to every table it touches. A SECURITY DEFINER version would
-- bypass RLS and leak other users' chunks; never change it. It also filters on the caller's
-- id explicitly (belt and braces), only reads READY documents, and only compares vectors
-- from the same model. Similarity is cosine similarity (1 = identical direction).
create function public.match_chunks(
  p_query_embedding extensions.vector(384),
  p_match_count     integer,
  p_document_ids    uuid[] default null,
  p_model_id        text default null
)
returns table (
  document_id uuid,
  page_number integer,
  chunk_index integer,
  text        text,
  similarity  double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
  select c.document_id, c.page_number, c.chunk_index, c.text,
         (1 - (e.embedding operator(extensions.<=>) p_query_embedding))::double precision as similarity
  from public.embeddings e
  join public.chunks c    on c.id = e.chunk_id and c.user_id = e.user_id
  join public.documents d on d.id = c.document_id and d.user_id = c.user_id
  where e.user_id = (select auth.uid())
    and d.status = 'ready'
    and (p_model_id is null or e.model_id = p_model_id)
    and (p_document_ids is null or c.document_id = any (p_document_ids))
  order by e.embedding operator(extensions.<=>) p_query_embedding
  limit least(greatest(p_match_count, 1), 50)
$$;

revoke all on function public.match_chunks(extensions.vector, integer, uuid[], text) from public, anon, authenticated;
grant execute on function public.match_chunks(extensions.vector, integer, uuid[], text) to authenticated;
