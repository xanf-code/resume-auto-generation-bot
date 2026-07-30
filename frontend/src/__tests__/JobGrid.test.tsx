import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { JobGrid } from '../components/home/JobGrid';
import { useStore } from '../store';
import { deleteJob, renameJob } from '../api/jobs';

vi.mock('../api/jobs', () => ({
  deleteJob: vi.fn(),
  renameJob: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderGrid(props: { loadFailed?: boolean; onOpenModal?: () => void } = {}) {
  return render(
    <MemoryRouter>
      <JobGrid loadFailed={props.loadFailed} onOpenModal={props.onOpenModal ?? vi.fn()} />
    </MemoryRouter>,
  );
}

describe('JobGrid', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    (deleteJob as unknown as Mock).mockReset();
    (renameJob as unknown as Mock).mockReset();
    useStore.setState({ jobs: {} });
  });

  it('shows empty-desk state when there are no jobs', () => {
    renderGrid();
    expect(screen.getByText(/start by adding/i)).toBeInTheDocument();
  });

  it('calls onOpenModal from the empty-state button', () => {
    const onOpenModal = vi.fn();
    renderGrid({ onOpenModal });
    fireEvent.click(screen.getByRole('button', { name: /new resume/i }));
    expect(onOpenModal).toHaveBeenCalledTimes(1);
  });

  it('shows load-failed state when loadFailed is true', () => {
    renderGrid({ loadFailed: true });
    expect(screen.getByText(/can't connect to the backend/i)).toBeInTheDocument();
  });

  it('renders a card for each job in the store', () => {
    useStore.setState({
      jobs: {
        'job-a': {
          job_id: 'job-a',
          label: 'Frontend Engineer',
          status: 'done',
          iteration: 1,
          pct: 100,
          personaScores: {},
        },
        'job-b': {
          job_id: 'job-b',
          label: 'Backend Lead',
          status: 'queued',
          iteration: 0,
          pct: 0,
          personaScores: {},
        },
      },
    });
    renderGrid();
    expect(screen.getByText('Frontend Engineer')).toBeInTheDocument();
    expect(screen.getByText('Backend Lead')).toBeInTheDocument();
  });

  it('shows resumes count header when jobs are present', () => {
    useStore.setState({
      jobs: {
        'job-a': {
          job_id: 'job-a',
          label: 'SWE Role',
          status: 'done',
          iteration: 1,
          pct: 100,
          personaScores: {},
        },
      },
    });
    renderGrid();
    expect(screen.getByText('Resumes')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('navigates to job detail when a card is clicked', () => {
    useStore.setState({
      jobs: {
        'job-x': {
          job_id: 'job-x',
          label: 'PM Role',
          status: 'done',
          iteration: 1,
          pct: 100,
          personaScores: {},
        },
      },
    });
    renderGrid();
    fireEvent.click(screen.getByText('PM Role'));
    expect(mockNavigate).toHaveBeenCalledWith('/jobs/job-x');
  });
});
