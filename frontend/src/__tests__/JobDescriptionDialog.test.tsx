import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { JobDescriptionDialog } from '../components/detail/JobDescriptionDialog';
import { getJobJd } from '../api/jobs';

vi.mock('../api/jobs', () => ({
  getJobJd: vi.fn(),
}));

const mockGetJobJd = vi.mocked(getJobJd);

describe('JobDescriptionDialog', () => {
  beforeEach(() => {
    mockGetJobJd.mockReset();
  });

  it('shows the application label as the dialog title', async () => {
    mockGetJobJd.mockResolvedValue({ jd_name: 'x', jd_text: 'Some JD.' });
    render(
      <JobDescriptionDialog
        jobId="job-1"
        jobLabel="State Street (AI Engineer)"
        onClose={vi.fn()}
      />,
    );
    expect(
      screen.getByRole('heading', { name: /State Street \(AI Engineer\)/i }),
    ).toBeInTheDocument();
  });

  it('fetches the JD by job id and renders the text', async () => {
    mockGetJobJd.mockResolvedValue({
      jd_name: 'State Street',
      jd_text: 'Senior engineer role requiring Python and FastAPI skills.',
    });
    render(
      <JobDescriptionDialog jobId="job-42" jobLabel="Any" onClose={vi.fn()} />,
    );

    expect(mockGetJobJd).toHaveBeenCalledWith('job-42');
    expect(
      await screen.findByText(/requiring Python and FastAPI/i),
    ).toBeInTheDocument();
  });

  it('renders an empty-state message when no JD was saved', async () => {
    mockGetJobJd.mockResolvedValue({ jd_name: '', jd_text: '   ' });
    render(
      <JobDescriptionDialog jobId="job-1" jobLabel="Any" onClose={vi.fn()} />,
    );
    expect(await screen.findByText(/no job description/i)).toBeInTheDocument();
  });

  it('renders an error message when the fetch fails', async () => {
    mockGetJobJd.mockRejectedValue(new Error('API 500'));
    render(
      <JobDescriptionDialog jobId="job-1" jobLabel="Any" onClose={vi.fn()} />,
    );
    expect(
      await screen.findByText(/could not load the job description/i),
    ).toBeInTheDocument();
  });

  it('closes on the close button, Escape, and backdrop click', async () => {
    mockGetJobJd.mockResolvedValue({ jd_name: '', jd_text: 'JD.' });
    const onClose = vi.fn();
    render(
      <JobDescriptionDialog jobId="job-1" jobLabel="Any" onClose={onClose} />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
