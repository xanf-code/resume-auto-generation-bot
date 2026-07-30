import { describe, it, expect } from 'vitest';
import { FIXTURE_ROSTER, competitorsFromJobs, buildRoster } from '../lib/ab/roster';
import type { JobSlice } from '../store/jobsSlice';
import type { PersonaScore } from '../api/types';

function makeJob(overrides: Partial<JobSlice> & Pick<JobSlice, 'job_id' | 'label'>): JobSlice {
  return {
    status: 'done',
    iteration: 0,
    pct: 100,
    personaScores: {},
    activityLog: [],
    ...overrides,
  };
}

function makePersonaScore(persona: string, value: number): PersonaScore {
  return {
    persona,
    keyword_match: value,
    impact_quality: value,
    coherence: value,
    plausibility: value,
    formatting: value,
  };
}

describe('FIXTURE_ROSTER', () => {
  it('has at least 16 entries', () => {
    expect(FIXTURE_ROSTER.length).toBeGreaterThanOrEqual(16);
  });

  it('has all-unique ids', () => {
    const ids = FIXTURE_ROSTER.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('every entry has origin "fixture"', () => {
    expect(FIXTURE_ROSTER.every((c) => c.origin === 'fixture')).toBe(true);
  });
});

describe('competitorsFromJobs', () => {
  it('maps job fields to competitor fields with origin "job"', () => {
    const jobs = [
      makeJob({ job_id: 'job-1', label: 'Backend resume', aggregateScore: 82 }),
    ];
    const [c] = competitorsFromJobs(jobs);
    expect(c.id).toBe('job-1');
    expect(c.label).toBe('Backend resume');
    expect(c.origin).toBe('job');
    expect(c.baseScore).toBe(82);
  });

  it('derives a finite pseudo-score when aggregateScore is undefined', () => {
    const jobs = [makeJob({ job_id: 'job-no-score', label: 'No Score Yet' })];
    const [c] = competitorsFromJobs(jobs);
    expect(Number.isFinite(c.baseScore)).toBe(true);
    expect(Number.isNaN(c.baseScore)).toBe(false);
  });

  it('is deterministic: same job_id always yields the same pseudo-score', () => {
    const jobA = makeJob({ job_id: 'stable-id', label: 'A' });
    const jobB = makeJob({ job_id: 'stable-id', label: 'B' });
    const [ca] = competitorsFromJobs([jobA]);
    const [cb] = competitorsFromJobs([jobB]);
    expect(ca.baseScore).toBe(cb.baseScore);
  });

  it('builds traits only for judge ids with a matching persona entry', () => {
    const jobs = [
      makeJob({
        job_id: 'job-traits',
        label: 'Traits Job',
        aggregateScore: 70,
        personaScores: {
          ats: makePersonaScore('ats', 80),
          technical: makePersonaScore('technical', 60),
        },
      }),
    ];
    const [c] = competitorsFromJobs(jobs);
    expect(c.traits.ats).toBe(80);
    expect(c.traits.technical).toBe(60);
    expect(c.traits.hiring_manager).toBeUndefined();
    expect(c.traits.skeptic).toBeUndefined();
    expect(c.traits.peer).toBeUndefined();
  });
});

describe('buildRoster', () => {
  it('pads from FIXTURE_ROSTER when fewer jobs than size are available', () => {
    const jobs = [makeJob({ job_id: 'only-job', label: 'Only Job', aggregateScore: 90 })];
    const roster = buildRoster(jobs, 8);
    expect(roster.length).toBe(8);
    const ids = roster.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(roster.some((c) => c.origin === 'fixture')).toBe(true);
  });

  it('selects the top `size` jobs by aggregateScore when more are available', () => {
    const jobs: JobSlice[] = Array.from({ length: 6 }, (_, i) =>
      makeJob({ job_id: `job-${i}`, label: `Job ${i}`, aggregateScore: i * 10 }),
    );
    const roster = buildRoster(jobs, 4);
    expect(roster.length).toBe(4);
    const ids = roster.map((c) => c.id).sort();
    expect(ids).toEqual(['job-2', 'job-3', 'job-4', 'job-5']);
    expect(roster.every((c) => c.origin === 'job')).toBe(true);
  });

  it('always returns exactly `size` competitors with unique ids', () => {
    const jobs: JobSlice[] = [
      makeJob({ job_id: 'job-x', label: 'X' }),
      makeJob({ job_id: 'job-y', label: 'Y', aggregateScore: 55 }),
    ];
    const roster = buildRoster(jobs, 16);
    expect(roster.length).toBe(16);
    const ids = roster.map((c) => c.id);
    expect(new Set(ids).size).toBe(16);
  });

  it('keeps jobs with an undefined aggregateScore finite when padding is needed', () => {
    const jobs = [makeJob({ job_id: 'job-no-agg', label: 'No Agg' })];
    const roster = buildRoster(jobs, 4);
    const jobCompetitor = roster.find((c) => c.id === 'job-no-agg');
    expect(jobCompetitor).toBeDefined();
    expect(Number.isFinite(jobCompetitor?.baseScore)).toBe(true);
  });
});
