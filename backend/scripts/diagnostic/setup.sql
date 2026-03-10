-- Run this once in the Supabase SQL editor

-- 1. Enable pgvector (if not already enabled)
create extension if not exists vector;

-- 2. Create the chunks table
drop table if exists document_chunks;
create table document_chunks (
  chunk_id    uuid primary key,
  document_id uuid not null,
  filename    text not null,
  chunk_index int  not null,
  total_chunks int not null,
  content     text not null,
  embedding   vector(1024) not null
);

-- 3. Index for fast similarity search (cosine distance)
create index on document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- 4. RPC function used by the Python script
create or replace function match_document_chunks(
  query_embedding vector(1024),
  match_count     int default 5
)
returns table (
  chunk_id    uuid,
  document_id uuid,
  filename    text,
  content     text,
  similarity  float
)
language sql stable
as $$
  select
    chunk_id,
    document_id,
    filename,
    content,
    1 - (embedding <=> query_embedding) as similarity
  from document_chunks
  order by embedding <=> query_embedding
  limit match_count;
$$;
