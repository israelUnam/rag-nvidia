-- Directory: rag-nvidia/sql/init_supabase.sql
--
-- Supabase database setup for the RAG application (NVIDIA API Catalog models).
--
-- Creates the table rag_chunks_ies and the functions match_chunks_ies and
-- get_chunk_stats_ies. It does not touch other tables (e.g. older rag_chunks or
-- rag_chunks_nvidia), so it can be run safely on an existing project.
--
-- Instructions:
-- 1. Open your Supabase project dashboard (https://supabase.com/dashboard)
-- 2. Go to SQL Editor and create a new query ("New query")
-- 3. Copy and paste this ENTIRE script
-- 4. Click "Run" to execute everything at once
--
-- Embeddings come from the NVIDIA API Catalog (nvidia/nemotron-3-embed-1b -> 2048 dimensions).
-- If you change NVIDIA_EMBED_MODEL, change VECTOR(2048) below and EMBEDDING_DIMENSIONS in .env.

-- =============================================================================
-- STEP 1: Enable pgvector extension for vector similarity search
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- STEP 2: Create the main RAG chunks table
-- =============================================================================

CREATE TABLE IF NOT EXISTS rag_chunks_ies (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(2048),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================================================================
-- STEP 3: Create indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS rag_chunks_ies_src_idx ON rag_chunks_ies (source);
CREATE INDEX IF NOT EXISTS rag_chunks_ies_created_at_idx ON rag_chunks_ies (created_at DESC);

-- =============================================================================
-- STEP 4: Create vector similarity search function
-- =============================================================================

CREATE OR REPLACE FUNCTION match_chunks_ies (
  query_embedding vector(2048),
  match_count int DEFAULT 6,
  min_similarity float DEFAULT 0.0
)
RETURNS TABLE (
  chunk_id text,
  source text,
  text text,
  similarity float,
  created_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    rag_chunks_ies.chunk_id,
    rag_chunks_ies.source,
    rag_chunks_ies.text,
    1 - (rag_chunks_ies.embedding <=> query_embedding) as similarity,
    rag_chunks_ies.created_at
  FROM rag_chunks_ies
  WHERE 1 - (rag_chunks_ies.embedding <=> query_embedding) >= min_similarity
  ORDER BY rag_chunks_ies.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Alias/fallback for match_chunks_nvidia pointing to rag_chunks_ies as well
CREATE OR REPLACE FUNCTION match_chunks_nvidia (
  query_embedding vector(2048),
  match_count int DEFAULT 6,
  min_similarity float DEFAULT 0.0
)
RETURNS TABLE (
  chunk_id text,
  source text,
  text text,
  similarity float,
  created_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    rag_chunks_ies.chunk_id,
    rag_chunks_ies.source,
    rag_chunks_ies.text,
    1 - (rag_chunks_ies.embedding <=> query_embedding) as similarity,
    rag_chunks_ies.created_at
  FROM rag_chunks_ies
  WHERE 1 - (rag_chunks_ies.embedding <=> query_embedding) >= min_similarity
  ORDER BY rag_chunks_ies.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 5: Create helper function to get database statistics
-- =============================================================================

CREATE OR REPLACE FUNCTION get_chunk_stats_ies()
RETURNS TABLE (
  total_chunks bigint,
  unique_sources bigint,
  latest_chunk timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*) as total_chunks,
    COUNT(DISTINCT rag_chunks_ies.source) as unique_sources,
    MAX(rag_chunks_ies.created_at) as latest_chunk
  FROM rag_chunks_ies;
END;
$$;

-- Alias/fallback for get_chunk_stats_nvidia pointing to rag_chunks_ies
CREATE OR REPLACE FUNCTION get_chunk_stats_nvidia()
RETURNS TABLE (
  total_chunks bigint,
  unique_sources bigint,
  latest_chunk timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*) as total_chunks,
    COUNT(DISTINCT rag_chunks_ies.source) as unique_sources,
    MAX(rag_chunks_ies.created_at) as latest_chunk
  FROM rag_chunks_ies;
END;
$$;

-- =============================================================================
-- STEP 6: Create Row Level Security (RLS) policies
-- =============================================================================

ALTER TABLE rag_chunks_ies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow service role full access" ON rag_chunks_ies;
DROP POLICY IF EXISTS "Allow authenticated read access" ON rag_chunks_ies;
DROP POLICY IF EXISTS "Allow anonymous read access" ON rag_chunks_ies;

-- Allow all operations for service role (backend)
CREATE POLICY "Allow service role full access" ON rag_chunks_ies
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Allow read access for authenticated users
CREATE POLICY "Allow authenticated read access" ON rag_chunks_ies
  FOR SELECT USING (auth.role() = 'authenticated');

-- Allow anonymous read access for development
CREATE POLICY "Allow anonymous read access" ON rag_chunks_ies
  FOR SELECT USING (true);

-- =============================================================================
-- STEP 7: Verification
-- =============================================================================

SELECT 'Database ready - rag_chunks_ies has ' || total_chunks::text || ' chunks' as test_result
FROM get_chunk_stats_ies();
