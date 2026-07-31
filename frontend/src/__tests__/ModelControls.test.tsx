import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ModelControls } from '../components/newjob/ModelControls';
import { DEFAULT_MODELS, type ModelsConfig } from '../lib/models';
import { listModels } from '../api/models';

vi.mock('../api/models', () => ({
  listModels: vi.fn(),
}));

const CATALOG = {
  models: [
    {
      id: 'z-ai/glm-5.2',
      name: 'GLM 5.2',
      structured_output: true,
      reasoning: {
        mandatory: false,
        supported_efforts: ['max', 'high', 'medium', 'low', 'none'],
        default_effort: 'high',
      },
    },
    {
      id: 'anthropic/claude-opus-5',
      name: 'Claude Opus 5',
      structured_output: true,
      reasoning: {
        mandatory: false,
        supported_efforts: ['max', 'high', 'medium', 'low', 'none'],
        default_effort: 'high',
      },
    },
    {
      id: 'anthropic/claude-sonnet-5',
      name: 'Claude Sonnet 5',
      structured_output: true,
      reasoning: {
        mandatory: false,
        supported_efforts: ['max', 'high', 'medium', 'low', 'none'],
        default_effort: 'medium',
      },
    },
    {
      id: 'openai/gpt-4o-mini',
      name: 'GPT-4o Mini',
      structured_output: true,
      reasoning: null,
    },
    {
      id: 'google/gemini-2.5-pro',
      name: 'Gemini 2.5 Pro',
      structured_output: true,
      reasoning: { mandatory: true },
    },
  ],
};

function setup(models: ModelsConfig = DEFAULT_MODELS) {
  const onChange = vi.fn();
  render(<ModelControls models={models} onChange={onChange} />);
  return { onChange };
}

describe('ModelControls', () => {
  beforeEach(() => {
    (listModels as unknown as Mock).mockReset();
    (listModels as unknown as Mock).mockResolvedValue(CATALOG);
  });

  it('renders a model select for each role after the catalog loads', async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Parser model')).toBeInTheDocument();
    expect(screen.getByLabelText('Gap analyzer model')).toBeInTheDocument();
    expect(screen.getByLabelText('Skills model')).toBeInTheDocument();
    expect(screen.getByLabelText('Scoring model')).toBeInTheDocument();
  });

  it('renders preset chips with Balanced pressed by default', async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Balanced' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Fast' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('applies a preset via onChange', async () => {
    const { onChange } = setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Best' }));
    const arg = onChange.mock.calls.at(-1)![0] as ModelsConfig;
    expect(arg.writer.model).toBe('anthropic/claude-opus-5');
    expect(arg.writer.effort).toBe('high');
    expect(arg.gap.effort).toBe('high');
  });

  it('hides the scoring role when showScoring is false', async () => {
    const onChange = vi.fn();
    render(
      <ModelControls
        models={DEFAULT_MODELS}
        onChange={onChange}
        showScoring={false}
      />,
    );
    await waitFor(() => {
      expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    });
    expect(screen.queryByLabelText('Scoring model')).not.toBeInTheDocument();
  });

  it('shows an effort dropdown for reasoning models with supported_efforts', async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Writer reasoning')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Gap analyzer reasoning')).toBeInTheDocument();
  });

  it('hides effort for models without reasoning', async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Parser model')).toBeInTheDocument();
    });
    expect(screen.queryByLabelText('Parser reasoning')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Skills reasoning')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Scoring reasoning')).not.toBeInTheDocument();
  });

  it('clears effort when switching to a non-reasoning model', async () => {
    const { onChange } = setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Writer model'), {
      target: { value: 'openai/gpt-4o-mini' },
    });

    const arg = onChange.mock.calls.at(-1)![0] as ModelsConfig;
    expect(arg.writer.model).toBe('openai/gpt-4o-mini');
    expect(arg.writer.effort).toBeNull();
  });

  it('sets default effort when switching to a reasoning model', async () => {
    const models: ModelsConfig = {
      ...DEFAULT_MODELS,
      parser: { model: 'openai/gpt-4o-mini', effort: null },
    };
    const { onChange } = setup(models);
    await waitFor(() => {
      expect(screen.getByLabelText('Parser model')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Parser model'), {
      target: { value: 'anthropic/claude-opus-5' },
    });

    const arg = onChange.mock.calls.at(-1)![0] as ModelsConfig;
    expect(arg.parser.model).toBe('anthropic/claude-opus-5');
    expect(arg.parser.effort).toBe('high');
  });

  it('lets the user pick none reasoning when the model supports it', async () => {
    const { onChange } = setup();
    await waitFor(() => {
      expect(screen.getByLabelText('Writer reasoning')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Writer reasoning'), {
      target: { value: 'none' },
    });

    const arg = onChange.mock.calls.at(-1)![0] as ModelsConfig;
    expect(arg.writer.effort).toBe('none');
  });

  it('hides none when reasoning is mandatory', async () => {
    const models: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: { model: 'acme/mandatory-reasoner', effort: 'high' },
    };
    (listModels as unknown as Mock).mockResolvedValue({
      models: [
        ...CATALOG.models,
        {
          id: 'acme/mandatory-reasoner',
          name: 'Mandatory Reasoner',
          structured_output: true,
          reasoning: {
            mandatory: true,
            supported_efforts: ['high', 'medium', 'none'],
            default_effort: 'high',
          },
        },
      ],
    });
    setup(models);
    await waitFor(() => {
      expect(screen.getByLabelText('Writer reasoning')).toBeInTheDocument();
    });
    const select = screen.getByLabelText('Writer reasoning') as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toContain('high');
    expect(values).not.toContain('none');
  });

  it('hides effort when the model has reasoning but no supported_efforts key', async () => {
    const models: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: { model: 'google/gemini-2.5-pro', effort: null },
    };
    setup(models);
    await waitFor(() => {
      expect(screen.getByLabelText('Writer model')).toBeInTheDocument();
    });
    expect(screen.queryByLabelText('Writer reasoning')).not.toBeInTheDocument();
  });
});
