import { describe, it, expect } from 'vitest';
import { applyEvent, makeEmptyJob, type JobsMap } from '../store/jobsSlice';
import type { ProgressEvent } from '../api/types';

function baseMap(extra?: Partial<ReturnType<typeof makeEmptyJob>>): JobsMap {
  return {
    'job-1': {
      ...makeEmptyJob('job-1', 'My Resume'),
      status: 'running',
      ...extra,
    },
  };
}

function makeEvent(overrides: Partial<ProgressEvent> = {}): ProgressEvent {
  return {
    job_id: 'job-1',
    seq: 1,
    stage: 'writer',
    human_label: 'Writing resume',
    pct: 25,
    ...overrides,
  };
}

describe('applyEvent', () => {
  it('updates stage, humanLabel and pct on a stage event', () => {
    const jobs = baseMap();
    const event = makeEvent({ stage: 'compile', human_label: 'Compiling', pct: 60 });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].stage).toBe('compile');
    expect(result['job-1'].humanLabel).toBe('Compiling');
    expect(result['job-1'].pct).toBe(60);
  });

  it('bumps iteration when provided and greater than current', () => {
    const jobs = baseMap({ iteration: 1 });
    const event = makeEvent({ stage: 'writer', iteration: 2 });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].iteration).toBe(2);
  });

  it('does not regress iteration when provided value is lower', () => {
    const jobs = baseMap({ iteration: 3 });
    const event = makeEvent({ stage: 'writer', iteration: 2 });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].iteration).toBe(3);
  });

  it('updates persona_scores for each score in the array', () => {
    const jobs = baseMap();
    const event = makeEvent({
      persona_scores: [
        {
          persona: 'recruiter',
          keyword_match: 80,
          impact_quality: 70,
          coherence: 75,
          plausibility: 65,
          formatting: 60,
          notes: 'good',
        },
      ],
    });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].personaScores['recruiter']).toMatchObject({
      persona: 'recruiter',
      keyword_match: 80,
    });
  });

  it('updates aggregateScore and passed when present', () => {
    const jobs = baseMap();
    const event = makeEvent({ aggregate_score: 82, passed: true });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].aggregateScore).toBe(82);
    expect(result['job-1'].passed).toBe(true);
  });

  it('sets status=done and finishedAt on done event', () => {
    const jobs = baseMap();
    const event = makeEvent({ stage: 'done', human_label: 'Done!', pct: 100 });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].status).toBe('done');
    expect(result['job-1'].finishedAt).toBeDefined();
  });

  it('sets status=failed on failed event', () => {
    const jobs = baseMap();
    const event = makeEvent({ stage: 'failed', human_label: 'Error', pct: 0 });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].status).toBe('failed');
    expect(result['job-1'].finishedAt).toBeDefined();
  });

  it('writer back-edge: higher iteration increments correctly', () => {
    const jobs = baseMap({ stage: 'score', iteration: 1 });
    const event = makeEvent({ stage: 'writer', iteration: 2 });
    const result = applyEvent(jobs, event);
    expect(result['job-1'].stage).toBe('writer');
    expect(result['job-1'].iteration).toBe(2);
  });

  it('returns unchanged map when job_id is unknown', () => {
    const jobs = baseMap();
    const event = makeEvent({ job_id: 'unknown-id' });
    const result = applyEvent(jobs, event);
    expect(result).toBe(jobs);
  });
});
