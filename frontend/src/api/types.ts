import type { Tuning } from '../lib/tuning';

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface JobSummary {
  job_id: string;
  label: string;
  status: JobStatus;
  created_at: string;
  aggregate_score?: number;
  passed?: boolean;
}

export interface PersonaScore {
  persona: string;
  keyword_match: number;
  impact_quality: number;
  coherence: number;
  plausibility: number;
  formatting: number;
  notes?: string;
}

export interface JobDetail extends JobSummary {
  stage?: string;
  human_label?: string;
  iteration: number;
  pct: number;
  persona_scores?: PersonaScore[];
  error?: string;
  finished_at?: string;
}

export interface ProgressEvent {
  job_id: string;
  seq: number;
  stage: string;
  human_label: string;
  pct: number;
  iteration?: number;
  aggregate_score?: number;
  passed?: boolean;
  persona_scores?: PersonaScore[];
  error?: string;
}

export interface CreateJobRequest {
  label: string;
  resume_tex: string;
  jd_text: string;
  enable_scoring?: boolean;
  // Per-application pipeline tuning. Omitted → the backend uses its defaults.
  tuning?: Tuning;
}

export interface CreateJobResponse {
  job_id: string;
  label: string;
  status: JobStatus;
  created_at: string;
}

export interface SkillsResponse {
  language_and_framework: string[];
  infrastructure: string[];
  database: string[];
  ai_tools: string[];
  total: number;
}

export interface CompileErrorResponse {
  ok: false;
  errors: string[];
}
