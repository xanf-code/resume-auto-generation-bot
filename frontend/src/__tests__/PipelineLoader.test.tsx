import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PipelineLoader } from '../components/loader/PipelineLoader';
import type { JobSlice } from '../store/jobsSlice';

vi.mock('../components/loader/ActivityLog', () => ({
  ActivityLog: () => null,
}));
vi.mock('../components/loader/RecruiterPanel', () => ({
  RecruiterPanel: () => null,
}));

function makeJob(overrides: Partial<JobSlice> = {}): JobSlice {
  return {
    job_id: 'job-1',
    label: 'Test',
    status: 'running',
    stage: 'parse',
    humanLabel: 'Generating skill dump',
    iteration: 1,
    pct: 18,
    personaScores: {},
    activityLog: [],
    ...overrides,
  };
}

describe('PipelineLoader stop UX', () => {
  it('shows Stop while the run is live', () => {
    render(
      <PipelineLoader job={makeJob()} onAbort={() => {}} aborting={false} />,
    );
    expect(screen.getByRole('button', { name: 'Stop' })).toBeEnabled();
    expect(screen.getByText('Generating')).toBeInTheDocument();
    expect(screen.getByText('Generating skill dump')).toBeInTheDocument();
  });

  it('explains the cooperative wind-down while aborting', () => {
    render(
      <PipelineLoader job={makeJob()} onAbort={() => {}} aborting={true} />,
    );
    const btn = screen.getByRole('button', { name: 'Stopping…' });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Stopping')).toBeInTheDocument();
    expect(screen.getByText('Winding down this run…')).toBeInTheDocument();
    expect(
      screen.getByText(/Stop heard\. The current step finishes first/),
    ).toBeInTheDocument();
  });
});
