-- Migration: 001_create_resume_jobs
-- Creates the resume_jobs table and indexes for the resume-bot Supabase project.
--
-- Required env vars:
--   SUPABASE_URL=https://<project-ref>.supabase.co
--   SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
--   SUPABASE_BUCKET=resumes   (optional; default "resumes")
--
-- Run once against your Supabase project via:
--   psql "$DATABASE_URL" -f 001_create_resume_jobs.sql
--   OR paste into the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS public.resume_jobs (
    job_id uuid PRIMARY KEY,
    user_id uuid,
    label text NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','done','failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    error text,
    resume_tex_raw text NOT NULL DEFAULT '',
    jd_raw text NOT NULL DEFAULT '',
    jd_name text NOT NULL DEFAULT '',
    enable_scoring boolean NOT NULL DEFAULT false,
    tuning jsonb,
    models jsonb,
    bullet_shapes jsonb,
    best_latex text,
    output_skills jsonb,
    score_report jsonb,
    aggregate_score double precision,
    passed boolean,
    pdf_object_key text
);

CREATE INDEX IF NOT EXISTS idx_resume_jobs_created_at ON public.resume_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resume_jobs_user_created ON public.resume_jobs (user_id, created_at DESC);
