import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { JobCard } from '../components/home/JobCard';
import type { JobSlice } from '../store/jobsSlice';

function makeJob(overrides: Partial<JobSlice> = {}): JobSlice {
  return {
    job_id: 'job-1',
    label: 'Software Engineer - Acme Corp',
    status: 'done',
    iteration: 3,
    pct: 100,
    personaScores: {},
    ...overrides,
  };
}

function renderCard(
  job: JobSlice,
  onClick = vi.fn(),
  onRename: Mock = vi.fn().mockResolvedValue(undefined),
  onDelete: Mock = vi.fn().mockResolvedValue(undefined),
) {
  return render(
    <MemoryRouter>
      <JobCard job={job} onClick={onClick} onRename={onRename} onDelete={onDelete} />
    </MemoryRouter>,
  );
}

describe('JobCard', () => {
  it('renders the job label', () => {
    renderCard(makeJob());
    expect(screen.getByText('Software Engineer - Acme Corp')).toBeInTheDocument();
  });

  it('renders "Complete" status for done job', () => {
    renderCard(makeJob({ status: 'done' }));
    expect(screen.getByText('Complete')).toBeInTheDocument();
  });

  it('renders "Failed" status for failed job', () => {
    renderCard(makeJob({ status: 'failed' }));
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders "Queued" status for queued job', () => {
    renderCard(makeJob({ status: 'queued' }));
    expect(screen.getByText('Queued')).toBeInTheDocument();
  });

  it('renders humanLabel as status text when running', () => {
    renderCard(makeJob({ status: 'running', humanLabel: 'Tailoring LaTeX…' }));
    expect(screen.getByText('Tailoring LaTeX…')).toBeInTheDocument();
  });

  it('renders aggregate score when provided', () => {
    renderCard(makeJob({ aggregateScore: 87, passed: true }));
    expect(screen.getByText('87')).toBeInTheDocument();
  });

  it('does not render score when aggregateScore is undefined', () => {
    renderCard(makeJob({ aggregateScore: undefined }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('calls onClick when the card body is clicked', () => {
    const onClick = vi.fn();
    renderCard(makeJob(), onClick);
    fireEvent.click(screen.getByText('Software Engineer - Acme Corp'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('shows edit button accessible by aria-label', () => {
    renderCard(makeJob());
    expect(
      screen.getByRole('button', { name: /rename software engineer/i }),
    ).toBeInTheDocument();
  });

  it('shows delete button accessible by aria-label', () => {
    renderCard(makeJob());
    expect(
      screen.getByRole('button', { name: /delete software engineer/i }),
    ).toBeInTheDocument();
  });

  it('switches to inline edit input when Edit button is clicked', () => {
    renderCard(makeJob());
    fireEvent.click(screen.getByRole('button', { name: /rename software engineer/i }));
    expect(screen.getByRole('textbox', { name: /rename application/i })).toBeInTheDocument();
  });

  it('commits rename on Enter and calls onRename', async () => {
    const onRename = vi.fn().mockResolvedValue(undefined);
    renderCard(makeJob(), vi.fn(), onRename);
    fireEvent.click(screen.getByRole('button', { name: /rename/i }));
    const input = screen.getByRole('textbox', { name: /rename application/i });
    fireEvent.change(input, { target: { value: 'New Label' } });
    await act(async () => {
      fireEvent.keyDown(input, { key: 'Enter' });
    });
    expect(onRename).toHaveBeenCalledWith('New Label');
  });

  it('cancels rename on Escape without calling onRename', () => {
    const onRename = vi.fn();
    renderCard(makeJob(), vi.fn(), onRename);
    fireEvent.click(screen.getByRole('button', { name: /rename/i }));
    const input = screen.getByRole('textbox', { name: /rename application/i });
    fireEvent.change(input, { target: { value: 'Discarded' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(onRename).not.toHaveBeenCalled();
    expect(screen.getByText('Software Engineer - Acme Corp')).toBeInTheDocument();
  });

  it('calls onDelete after confirm dialog is accepted', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    window.confirm = vi.fn().mockReturnValue(true);
    renderCard(makeJob(), vi.fn(), vi.fn(), onDelete);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    });
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it('does not call onDelete when confirm dialog is rejected', async () => {
    const onDelete = vi.fn();
    window.confirm = vi.fn().mockReturnValue(false);
    renderCard(makeJob(), vi.fn(), vi.fn(), onDelete);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    });
    expect(onDelete).not.toHaveBeenCalled();
  });
});
