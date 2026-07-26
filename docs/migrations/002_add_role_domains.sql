-- Migration: 002_add_role_domains
-- Adds JD classification columns to resume_jobs so the role/domain tags
-- computed by src.agents.jd_tagger survive a reload/restart and can be
-- displayed in the UI.
--
-- Run once against your Supabase project via:
--   psql "$DATABASE_URL" -f 002_add_role_domains.sql
--   OR paste into the Supabase SQL editor.

ALTER TABLE public.resume_jobs
    ADD COLUMN IF NOT EXISTS role text,
    ADD COLUMN IF NOT EXISTS domains jsonb;
