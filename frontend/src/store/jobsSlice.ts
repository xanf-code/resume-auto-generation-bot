import type { ProgressEvent, PersonaScore, JobDetail } from '../api/types';

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface JobSlice {
  job_id: string;
  label: string;
  status: JobStatus;
  stage?: string;
  humanLabel?: string;
  iteration: number;
  pct: number;
  personaScores: Record<string, PersonaScore>;
  aggregateScore?: number;
  passed?: boolean;
  error?: string;
  finishedAt?: string;
  finishedNotified: boolean;
}

export type JobsMap = Record<string, JobSlice>;

export interface JobsState {
  jobs: JobsMap;
}

export interface JobsActions {
  addJob: (job: Pick<JobSlice, 'job_id' | 'label'>) => void;
  applyEvent: (event: ProgressEvent) => void;
  syncJob: (detail: JobDetail) => void;
  markFinishedNotified: (jobId: string) => void;
  setJobs: (jobs: JobSlice[]) => void;
  renameJob: (jobId: string, label: string) => void;
  removeJob: (jobId: string) => void;
}

export function makeEmptyJob(
  job_id: string,
  label: string,
): JobSlice {
  return {
    job_id,
    label,
    status: 'queued',
    iteration: 0,
    pct: 0,
    personaScores: {},
    finishedNotified: false,
  };
}

export function applyEvent(jobs: JobsMap, event: ProgressEvent): JobsMap {
  const existing = jobs[event.job_id];
  if (!existing) return jobs;

  const updated: JobSlice = { ...existing };

  if (event.stage === 'done') {
    updated.status = 'done';
    updated.stage = 'done';
    updated.humanLabel = event.human_label;
    updated.pct = 100;
    updated.finishedAt = new Date().toISOString();
  } else if (event.stage === 'failed') {
    updated.status = 'failed';
    updated.stage = 'failed';
    updated.humanLabel = event.human_label;
    updated.finishedAt = new Date().toISOString();
  } else {
    updated.status = 'running';
    updated.stage = event.stage;
    updated.humanLabel = event.human_label;
    updated.pct = event.pct;

    if (event.iteration !== undefined && event.iteration > updated.iteration) {
      updated.iteration = event.iteration;
    }
  }

  if (event.persona_scores && event.persona_scores.length > 0) {
    const newScores = { ...updated.personaScores };
    for (const ps of event.persona_scores) {
      newScores[ps.persona] = ps;
    }
    updated.personaScores = newScores;
  }

  if (event.aggregate_score !== undefined) {
    updated.aggregateScore = event.aggregate_score;
  }

  if (event.passed !== undefined) {
    updated.passed = event.passed;
  }

  return { ...jobs, [event.job_id]: updated };
}

// Reconcile a job against an authoritative snapshot fetched over HTTP. Used when
// the SSE stream drops and may have missed the terminal event — so a job that
// actually finished on the backend can never stay stuck "running" in the UI.
export function reconcileJob(jobs: JobsMap, detail: JobDetail): JobsMap {
  const existing = jobs[detail.job_id];
  if (!existing) return jobs;

  const updated: JobSlice = {
    ...existing,
    status: detail.status,
    stage: detail.stage ?? existing.stage,
    humanLabel: detail.human_label ?? existing.humanLabel,
    iteration: Math.max(existing.iteration, detail.iteration),
    pct: detail.status === 'done' ? 100 : Math.max(existing.pct, detail.pct),
    aggregateScore: detail.aggregate_score ?? existing.aggregateScore,
    passed: detail.passed ?? existing.passed,
    error: detail.error ?? existing.error,
  };

  if (detail.persona_scores && detail.persona_scores.length > 0) {
    const scores = { ...existing.personaScores };
    for (const ps of detail.persona_scores) {
      scores[ps.persona] = ps;
    }
    updated.personaScores = scores;
  }

  return { ...jobs, [detail.job_id]: updated };
}
