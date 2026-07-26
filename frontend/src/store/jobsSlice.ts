import type { ProgressEvent, PersonaScore, JobDetail } from '../api/types';

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

// One line in the live activity feed shown under the pipeline stepper.
export interface ActivityEntry {
  seq: number;
  stage: string;
  text: string;
}

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
  // Chronological "what is happening" feed, newest last. Populated from each
  // ProgressEvent.detail so the UI can show the control-flow the stepper hides.
  activityLog: ActivityEntry[];
  error?: string;
  finishedAt?: string;
  // JD classification (role/domain tag). None/empty until classification runs.
  role?: string | null;
  domains?: string[];
}

export type JobsMap = Record<string, JobSlice>;

export interface JobsState {
  jobs: JobsMap;
}

export interface JobsActions {
  addJob: (job: Pick<JobSlice, 'job_id' | 'label'>) => void;
  applyEvent: (event: ProgressEvent) => void;
  syncJob: (detail: JobDetail) => void;
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
    activityLog: [],
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
    updated.error = event.error ?? updated.error;
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

  // Append the activity line, skipping empties and consecutive duplicates so a
  // node that emits the same message twice (e.g. a retried compile) reads once.
  if (event.detail) {
    const prev = updated.activityLog[updated.activityLog.length - 1];
    if (!prev || prev.text !== event.detail) {
      updated.activityLog = [
        ...updated.activityLog,
        { seq: event.seq, stage: event.stage, text: event.detail },
      ];
    }
  }

  return { ...jobs, [event.job_id]: updated };
}

// Reconcile a job against an authoritative snapshot fetched over HTTP. Used when
// the SSE stream drops and may have missed the terminal event - so a job that
// actually finished on the backend can never stay stuck "running" in the UI.
export function reconcileJob(jobs: JobsMap, detail: JobDetail): JobsMap {
  const existing = jobs[detail.job_id];
  if (!existing) return jobs;

  // The HTTP detail snapshot omits the live-only fields (stage/human_label/
  // iteration/pct), so coalesce each against what we already have rather than
  // letting `undefined` poison the slice (e.g. Math.max(n, undefined) → NaN).
  const updated: JobSlice = {
    ...existing,
    status: detail.status,
    stage: detail.stage ?? existing.stage,
    humanLabel: detail.human_label ?? existing.humanLabel,
    iteration: Math.max(existing.iteration, detail.iteration ?? 0),
    pct:
      detail.status === 'done'
        ? 100
        : Math.max(existing.pct, detail.pct ?? 0),
    aggregateScore: detail.aggregate_score ?? existing.aggregateScore,
    passed: detail.passed ?? existing.passed,
    error: detail.error ?? existing.error,
    role: detail.role ?? existing.role,
    domains: detail.domains ?? existing.domains,
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
