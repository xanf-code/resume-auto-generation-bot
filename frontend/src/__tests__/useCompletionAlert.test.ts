import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useCompletionAlert } from '../lib/useCompletionAlert';
import * as sound from '../lib/sound';
import type { JobSlice } from '../store/jobsSlice';

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
  },
}));

vi.mock('../lib/sound', () => ({
  playChime: vi.fn(),
  preloadChime: vi.fn(),
}));

vi.mock('../lib/notify', () => ({
  completionAlert: vi.fn(),
  requestPermission: vi.fn(),
  showNotification: vi.fn(),
}));

function makeJob(overrides: Partial<JobSlice> = {}): JobSlice {
  return {
    job_id: 'job-1',
    label: 'My Job',
    status: 'running',
    iteration: 0,
    pct: 0,
    personaScores: {},
    finishedNotified: false,
    ...overrides,
  };
}

describe('useCompletionAlert', () => {
  let markNotified: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    markNotified = vi.fn();
    vi.clearAllMocks();
  });

  it('fires alert exactly once when job transitions to done', () => {
    const job = makeJob({ status: 'done' });
    renderHook(() => useCompletionAlert(job, markNotified));
    expect(sound.playChime).toHaveBeenCalledTimes(1);
    expect(markNotified).toHaveBeenCalledWith('job-1');
  });

  it('does not fire again when finishedNotified is already true', () => {
    const job = makeJob({ status: 'done', finishedNotified: true });
    renderHook(() => useCompletionAlert(job, markNotified));
    expect(sound.playChime).not.toHaveBeenCalled();
    expect(markNotified).not.toHaveBeenCalled();
  });

  it('does not fire when job is still running', () => {
    const job = makeJob({ status: 'running' });
    renderHook(() => useCompletionAlert(job, markNotified));
    expect(sound.playChime).not.toHaveBeenCalled();
  });

  it('does not fire when job is undefined', () => {
    renderHook(() => useCompletionAlert(undefined, markNotified));
    expect(sound.playChime).not.toHaveBeenCalled();
  });

  it('always calls playChime on completion', () => {
    const job = makeJob({ status: 'done', aggregateScore: 85 });
    renderHook(() => useCompletionAlert(job, markNotified));
    expect(sound.playChime).toHaveBeenCalled();
  });
});
