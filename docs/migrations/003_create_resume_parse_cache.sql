-- Migration: 003_create_resume_parse_cache
-- Caches the deterministic parse_resume() output (ResumeStruct + IdentityLedger)
-- keyed by a sha256 hash of the raw resume .tex, so identical resumes across
-- separate job runs skip the parser LLM call entirely.
--
-- Invalidation: automatic. Any change to the resume text changes resume_hash,
-- which is a cache miss - there is no explicit invalidation/expiry needed.
--
-- Run once against your Supabase project via:
--   psql "$DATABASE_URL" -f 003_create_resume_parse_cache.sql
--   OR paste into the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS public.resume_parse_cache (
    resume_hash text PRIMARY KEY,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
