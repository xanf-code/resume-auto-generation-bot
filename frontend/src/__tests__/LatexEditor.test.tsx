import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LatexEditor } from '../components/detail/editor/LatexEditor';
import { saveJobLatex, getJobPdf } from '../api/jobs';
import { toast } from 'sonner';

vi.mock('../api/jobs', () => ({
  getJobPdf: vi.fn(),
  saveJobLatex: vi.fn(),
}));

vi.mock('../api/compile', () => ({
  compileLatex: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    message: vi.fn(),
  },
}));

const mockSaveJobLatex = vi.mocked(saveJobLatex);
const mockGetJobPdf = vi.mocked(getJobPdf);

describe('LatexEditor compile action', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetJobPdf.mockRejectedValue(new Error('no pdf'));
  });

  it('compiles and saves when Compile is clicked', async () => {
    const pdf = new Blob(['%PDF'], { type: 'application/pdf' });
    mockSaveJobLatex.mockResolvedValue({ ok: true, blob: pdf });

    render(
      <LatexEditor jobId="job-1" initialLatex="\\documentclass{article}\\begin{document}Hi\\end{document}" />,
    );

    fireEvent.click(screen.getByRole('button', { name: /^Compile$/i }));

    await waitFor(() => {
      expect(mockSaveJobLatex).toHaveBeenCalledTimes(1);
    });
    expect(mockSaveJobLatex).toHaveBeenCalledWith(
      'job-1',
      expect.stringContaining('Hi'),
    );
    expect(toast.success).toHaveBeenCalledWith('Compiled and saved');
    expect(screen.queryByRole('button', { name: /^Save$/i })).not.toBeInTheDocument();
  });

  it('surfaces compiler marks when save/compile fails', async () => {
    mockSaveJobLatex.mockResolvedValue({
      ok: false,
      errors: ['Undefined control sequence'],
    });

    render(
      <LatexEditor jobId="job-1" initialLatex="\\bad" />,
    );

    fireEvent.click(screen.getByRole('button', { name: /^Compile$/i }));

    expect(await screen.findByText('Undefined control sequence')).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith('Compile failed - see the marks below');
  });
});
