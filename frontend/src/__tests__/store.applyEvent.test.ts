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

  it('appends event.detail onto the activity log with stage + sequence', () => {
    const jobs = baseMap();
    const event = makeEvent({
      stage: 'compile',
      detail: 'Page overflow - bouncing back to the writer',
      seq: 7,
    });
    const result = applyEvent(jobs, event);
    const log = result['job-1'].activityLog;
    expect(log).toHaveLength(1);
    expect(log[0]).toMatchObject({
      seq: 7,
      stage: 'compile',
      text: 'Page overflow - bouncing back to the writer',
    });
  });

  it('accumulates multiple detail lines in arrival order', () => {
    let jobs = baseMap();
    jobs = applyEvent(jobs, makeEvent({ stage: 'writer', detail: 'Drafting the first pass', seq: 1 }));
    jobs = applyEvent(jobs, makeEvent({ stage: 'compile', detail: 'Compiled to a single page', seq: 2 }));
    const log = jobs['job-1'].activityLog;
    expect(log.map((e) => e.text)).toEqual(['Drafting the first pass', 'Compiled to a single page']);
  });

  it('does not append when detail is absent', () => {
    const jobs = baseMap();
    const result = applyEvent(jobs, makeEvent({ stage: 'writer', detail: undefined }));
    expect(result['job-1'].activityLog).toHaveLength(0);
  });

  it('skips a detail identical to the previous entry (dedupe consecutive repeats)', () => {
    let jobs = baseMap();
    jobs = applyEvent(jobs, makeEvent({ stage: 'compile', detail: 'Compile failed', seq: 1 }));
    jobs = applyEvent(jobs, makeEvent({ stage: 'compile', detail: 'Compile failed', seq: 2 }));
    expect(jobs['job-1'].activityLog).toHaveLength(1);
  });
});
