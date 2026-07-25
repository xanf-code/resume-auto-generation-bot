import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NewJobModal } from '../components/newjob/NewJobModal';
import { useStore } from '../store';
import { createJob } from '../api/jobs';
import { listModels } from '../api/models';

vi.mock('../api/jobs', () => ({
  createJob: vi.fn(),
}));

vi.mock('../api/models', () => ({
  listModels: vi.fn(),
}));

const CATALOG = {
  models: [
    {
      id: 'anthropic/claude-sonnet-5',
      name: 'Claude Sonnet 5',
      structured_output: true,
      reasoning: {
        supported_efforts: ['max', 'high', 'medium', 'low'],
        default_effort: 'medium',
      },
    },
    {
      id: 'anthropic/claude-opus-5',
      name: 'Claude Opus 5',
      structured_output: true,
      reasoning: {
        supported_efforts: ['max', 'high', 'medium', 'low'],
        default_effort: 'high',
      },
    },
    {
      id: 'openai/gpt-4o-mini',
      name: 'GPT-4o Mini',
      structured_output: true,
      reasoning: null,
    },
  ],
};

function renderModal() {
  return render(
    <MemoryRouter>
      <NewJobModal />
    </MemoryRouter>,
  );
}

async function renderModalReady() {
  renderModal();
  // Flush ModelControls catalog fetch so async setState is inside act.
  await waitFor(() => {
    expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
  });
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText('Label'), {
    target: { value: 'Backend Engineer' },
  });
  fireEvent.change(screen.getByPlaceholderText(/LaTeX résumé/i), {
    target: { value: '\\documentclass{article}\\begin{document}x\\end{document}' },
  });
  fireEvent.change(screen.getByPlaceholderText(/job description/i), {
    target: { value: 'We are hiring a backend engineer.' },
  });
}

describe('NewJobModal', () => {
  beforeEach(() => {
    (createJob as unknown as Mock).mockReset();
    (listModels as unknown as Mock).mockReset();
    (listModels as unknown as Mock).mockResolvedValue(CATALOG);
    useStore.setState({
      closeNewJobModal: () => useStore.setState({ newJobModalOpen: false }),
    });
  });

  it('exposes dialog semantics and a labelled title', async () => {
    await renderModalReady();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'new-job-title');
    expect(document.getElementById('new-job-title')).toHaveTextContent('Feed the press');
  });

  it('moves focus to the label field on open and caps its length', async () => {
    await renderModalReady();
    const label = screen.getByLabelText('Label');
    expect(label).toHaveFocus();
    expect(label).toHaveAttribute('maxlength', '200');
  });

  it('closes on Escape while idle', async () => {
    const closeSpy = vi.fn();
    useStore.setState({ closeNewJobModal: closeSpy });
    await renderModalReady();

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it('uses a playground layout with inputs left and configuration right', async () => {
    await renderModalReady();
    expect(screen.getByTestId('playground-inputs')).toBeInTheDocument();
    expect(screen.getByTestId('playground-config')).toBeInTheDocument();
    // Tuning sliders are always visible (no disclosure gate).
    expect(screen.getByLabelText('Pass threshold')).toBeInTheDocument();
    expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
  });

  it('submits default tuning and models with the job', async () => {
    (createJob as unknown as Mock).mockResolvedValue({
      job_id: 'abc',
      label: 'Backend Engineer',
    });
    await renderModalReady();

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    const arg = (createJob as unknown as Mock).mock.calls.at(-1)![0];
    expect(arg.tuning).toBeDefined();
    expect(arg.tuning.threshold).toBe(78);
    const sum = Object.values(arg.tuning.rubric_weights as Record<string, number>).reduce(
      (a, b) => a + b,
      0,
    );
    expect(sum).toBeCloseTo(1.0, 6);

    expect(arg.models).toBeDefined();
    expect(arg.models.writer.model).toBe('anthropic/claude-sonnet-5');
    expect(arg.models.writer.effort).toBe('medium');
    expect(arg.models.parser.model).toBe('openai/gpt-4o-mini');
    expect(arg.models.parser.effort).toBeNull();
    expect(arg.models.gap.model).toBe('anthropic/claude-opus-5');
    expect(arg.models.scoring.model).toBe('openai/gpt-4o-mini');
  });

  it('does not close on Escape while a submission is in flight', async () => {
    const closeSpy = vi.fn();
    useStore.setState({ closeNewJobModal: closeSpy });
    (createJob as unknown as Mock).mockReturnValue(new Promise(() => {}));
    await renderModalReady();

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });
    expect(screen.getByText('Sending to press…')).toBeInTheDocument();

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(closeSpy).not.toHaveBeenCalled();
  });
});
