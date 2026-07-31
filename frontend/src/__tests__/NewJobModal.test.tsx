import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NewJobModal } from '../components/newjob/NewJobModal';
import { useStore } from '../store';
import { createJob } from '../api/jobs';
import { listModels } from '../api/models';
import { loadRememberedConfig, saveRememberedConfig } from '../lib/rememberedConfig';
import { DEFAULT_MODELS } from '../lib/models';
import { DEFAULT_TUNING } from '../lib/tuning';

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
  await waitFor(() => {
    expect(screen.getByRole('group', { name: /model presets/i })).toBeInTheDocument();
  });
}

async function openAdvanced() {
  fireEvent.click(screen.getByRole('button', { name: /^advanced$/i }));
  await waitFor(() => {
    expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
  });
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText('Label'), {
    target: { value: 'Backend Engineer' },
  });
  fireEvent.change(screen.getByPlaceholderText(/LaTeX resume/i), {
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
    localStorage.clear();
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
    expect(screen.getByText(/submission-ready PDF/i)).toBeInTheDocument();
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

  it('uses a playground layout with presets visible and advanced collapsed', async () => {
    await renderModalReady();
    expect(screen.getByTestId('playground-inputs')).toBeInTheDocument();
    expect(screen.getByTestId('playground-config')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Balanced' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.queryByLabelText('Pass threshold')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Writer model')).not.toBeInTheDocument();

    await openAdvanced();
    expect(screen.getByLabelText('Pass threshold')).toBeInTheDocument();
    expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    // Rubric hidden until scoring is enabled
    expect(screen.queryByLabelText('Keyword match')).not.toBeInTheDocument();
  });

  it('disables the CTA until required fields are filled', async () => {
    await renderModalReady();
    const submit = screen.getByRole('button', { name: /start typesetting/i });
    expect(submit).toBeDisabled();
    fillRequiredFields();
    expect(submit).not.toBeDisabled();
  });

  it('shows a footer summary of preset and scoring', async () => {
    await renderModalReady();
    expect(screen.getByTestId('config-summary')).toHaveTextContent(/Balanced/);
    expect(screen.getByTestId('config-summary')).toHaveTextContent(/Scoring off/);
    fireEvent.click(screen.getByLabelText(/recruiter persona scoring/i));
    expect(screen.getByTestId('config-summary')).toHaveTextContent(/Scoring on/);
  });

  it('reveals rubric weights when scoring is enabled and advanced is open', async () => {
    await renderModalReady();
    fireEvent.click(screen.getByLabelText(/recruiter persona scoring/i));
    await openAdvanced();
    expect(screen.getByLabelText('Keyword match')).toBeInTheDocument();
    expect(screen.getByLabelText('Skills model')).toBeInTheDocument();
    expect(screen.getByLabelText('Scoring model')).toBeInTheDocument();
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
    expect(arg.models.writer.temperature).toBe(0.7);
    expect(arg.models.parser.model).toBe('google/gemini-2.5-flash-lite');
    expect(arg.models.parser.effort).toBeNull();
    expect(arg.models.parser.temperature).toBe(0);
    expect(arg.models.gap.model).toBe('z-ai/glm-5.2');
    expect(arg.models.gap.effort).toBe('high');
    expect(arg.models.gap.temperature).toBe(0.5);
    expect(arg.models.skills.model).toBe('qwen/qwen3-30b-a3b-instruct-2507');
    expect(arg.models.skills.effort).toBeNull();
    expect(arg.models.skills.temperature).toBe(0.2);
    expect(arg.models.scoring.model).toBe('deepseek/deepseek-v4-flash');
    expect(arg.models.scoring.effort).toBe('xhigh');
    expect(arg.models.scoring.temperature).toBe(0.2);
  });

  it('shows skills and scoring model pickers in advanced without enabling scoring', async () => {
    await renderModalReady();
    fireEvent.click(screen.getByRole('button', { name: /advanced/i }));
    await waitFor(() => {
      expect(screen.getByLabelText('Skills model')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Scoring model')).toBeInTheDocument();
  });

  it('applies a model preset without opening advanced', async () => {
    (createJob as unknown as Mock).mockResolvedValue({
      job_id: 'abc',
      label: 'Backend Engineer',
    });
    await renderModalReady();
    fireEvent.click(screen.getByRole('button', { name: 'Fast' }));
    expect(screen.getByTestId('config-summary')).toHaveTextContent(/Fast/);

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    const arg = (createJob as unknown as Mock).mock.calls.at(-1)![0];
    expect(arg.models.writer.model).toBe('openai/gpt-4o-mini');
    expect(arg.models.gap.model).toBe('openai/gpt-4o-mini');
    expect(arg.models.skills.model).toBe('openai/gpt-4o-mini');
    expect(arg.models.scoring.model).toBe('openai/gpt-4o-mini');
  });

  it('renders the Bullet shapes section in the config panel', async () => {
    await renderModalReady();
    expect(screen.getByText(/Bullet shapes/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Leave all unchecked to rotate shapes automatically/i),
    ).toBeInTheDocument();
  });

  it('default submit sends empty bullet_shapes (rotation)', async () => {
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
    // No shapes selected → bullet_shapes is empty (backend normalises to default rotation)
    expect(arg.bullet_shapes ?? []).toEqual([]);
  });

  it('selecting bullet shapes sends them in canonical order', async () => {
    (createJob as unknown as Mock).mockResolvedValue({
      job_id: 'abc',
      label: 'Backend Engineer',
    });
    await renderModalReady();

    // The bullet shape checkboxes come after the scoring checkbox.
    // We need only those inside the bullet-shape-controls section.
    const shapeControls = screen.getByTestId('bullet-shape-controls');
    const [parCb, , actionStackCb] = Array.from(
      shapeControls.querySelectorAll('input[type="checkbox"]'),
    ) as HTMLInputElement[];

    // Select ACTION+STACK first, then PAR — canonical order must still be [PAR, ACTION+STACK]
    fireEvent.click(actionStackCb);
    fireEvent.click(parCb);

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    const arg = (createJob as unknown as Mock).mock.calls.at(-1)![0];
    expect(arg.bullet_shapes).toEqual(['PAR', 'ACTION+STACK']);
  });

  it('sends obsidian_learn true by default (checkbox unchecked)', async () => {
    (createJob as unknown as Mock).mockResolvedValue({
      job_id: 'abc',
      label: 'Backend Engineer',
    });
    await renderModalReady();

    expect(screen.getByLabelText(/turn off obsidian learning/i)).not.toBeChecked();

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    const arg = (createJob as unknown as Mock).mock.calls.at(-1)![0];
    expect(arg.obsidian_learn).toBe(true);
  });

  it('sends obsidian_learn false when the toggle checkbox is checked', async () => {
    (createJob as unknown as Mock).mockResolvedValue({
      job_id: 'abc',
      label: 'Backend Engineer',
    });
    await renderModalReady();

    fireEvent.click(screen.getByLabelText(/turn off obsidian learning/i));
    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    const arg = (createJob as unknown as Mock).mock.calls.at(-1)![0];
    expect(arg.obsidian_learn).toBe(false);
  });

  it('renders the "remember for next run" checkbox, unchecked by default', async () => {
    await renderModalReady();
    expect(screen.getByLabelText(/remember.*next run/i)).not.toBeChecked();
  });

  it('does not persist models/tuning when the remember checkbox is left unchecked', async () => {
    (createJob as unknown as Mock).mockResolvedValue({ job_id: 'abc', label: 'X' });
    await renderModalReady();

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    expect(loadRememberedConfig()).toBeNull();
  });

  it('persists the current models/tuning when the remember checkbox is checked at submit', async () => {
    (createJob as unknown as Mock).mockResolvedValue({ job_id: 'abc', label: 'X' });
    await renderModalReady();
    await openAdvanced();

    fireEvent.click(screen.getByRole('button', { name: 'Fast' }));
    fireEvent.click(screen.getByLabelText(/remember.*next run/i));
    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    const remembered = loadRememberedConfig();
    expect(remembered).not.toBeNull();
    expect(remembered!.models.writer.model).toBe('openai/gpt-4o-mini');
    expect(remembered!.tuning).toEqual(DEFAULT_TUNING);
  });

  it('pre-fills models from a previously remembered config on mount', async () => {
    const remembered = {
      models: {
        ...DEFAULT_MODELS,
        writer: { model: 'anthropic/claude-opus-5', effort: 'high', temperature: 0.9 },
      },
      tuning: DEFAULT_TUNING,
    };
    saveRememberedConfig(remembered);

    await renderModalReady();
    await openAdvanced();

    expect(screen.getByLabelText('Writer model')).toHaveValue('anthropic/claude-opus-5');
  });

  it('leaves a previously remembered config untouched when submitting with the box unchecked', async () => {
    const remembered = { models: DEFAULT_MODELS, tuning: { ...DEFAULT_TUNING, threshold: 91 } };
    saveRememberedConfig(remembered);

    (createJob as unknown as Mock).mockResolvedValue({ job_id: 'abc', label: 'X' });
    await renderModalReady();

    fillRequiredFields();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });

    expect(loadRememberedConfig()).toEqual(remembered);
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
