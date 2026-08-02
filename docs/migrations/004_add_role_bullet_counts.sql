-- Migration: 004_add_role_bullet_counts
-- Adds per-role bullet budget column to resume_jobs so user-selected
-- counts survive a reload/restart and are stored alongside the job.
--
-- Run once against your Supabase project via:
--   psql "$DATABASE_URL" -f 004_add_role_bullet_counts.sql
--   OR paste into the Supabase SQL editor.

ALTER TABLE public.resume_jobs
    ADD COLUMN IF NOT EXISTS role_bullet_counts jsonb;
