import { describe, it, expect } from 'vitest';
import { reconcileJob, makeEmptyJob, type JobsMap } from '../store/jobsSlice';
import type { JobDetail } from '../api/types';

function baseMap(extra?: Partial<ReturnType<typeof makeEmptyJob>>): JobsMap {
  return {
    'job-1': {
      ...makeEmptyJob('job-1', 'My Resume'),
      status: 'running',
      pct: 40,
      iteration: 2,
      ...extra,
    },
  };
}

function makeDetail(overrides: Partial<JobDetail> = {}): JobDetail {
  return {
    job_id: 'job-1',
    label: 'My Resume',
    status: 'running',
    created_at: '2026-07-24T00:00:00Z',
    iteration: 2,
    pct: 40,
    ...overrides,
  };
}

describe('reconcileJob', () => {
  it('promotes a stuck running job to done when the backend already finished', () => {
    const jobs = baseMap();
    const detail = makeDetail({ status: 'done', aggregate_score: 82, passed: true });
    const result = reconcileJob(jobs, detail);
    expect(result['job-1'].status).toBe('done');
    expect(result['job-1'].pct).toBe(100);
    expect(result['job-1'].aggregateScore).toBe(82);
    expect(result['job-1'].passed).toBe(true);
  });

  it('reconciles a failed job and carries its error message', () => {
    const jobs = baseMap();
    const detail = makeDetail({ status: 'failed', error: 'compile blew up' });
    const result = reconcileJob(jobs, detail);
    expect(result['job-1'].status).toBe('failed');
    expect(result['job-1'].error).toBe('compile blew up');
  });

  it('never regresses progress or iteration for a still-running job', () => {
    const jobs = baseMap({ pct: 70, iteration: 3 });
    const detail = makeDetail({ status: 'running', pct: 55, iteration: 2 });
    const result = reconcileJob(jobs, detail);
    expect(result['job-1'].pct).toBe(70);
    expect(result['job-1'].iteration).toBe(3);
  });

  it('merges persona scores from the snapshot', () => {
    const jobs = baseMap();
    const detail = makeDetail({
      persona_scores: [
        {
          persona: 'skeptic',
          keyword_match: 60,
          impact_quality: 55,
          coherence: 70,
          plausibility: 65,
          formatting: 50,
        },
      ],
    });
    const result = reconcileJob(jobs, detail);
    expect(result['job-1'].personaScores['skeptic']).toMatchObject({ persona: 'skeptic' });
  });

  it('returns the map unchanged when the job is unknown', () => {
    const jobs = baseMap();
    const detail = makeDetail({ job_id: 'ghost' });
    const result = reconcileJob(jobs, detail);
    expect(result).toBe(jobs);
  });
});
