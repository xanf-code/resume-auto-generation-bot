import { describe, it, expect } from 'vitest';
import {
  DEFAULT_MODELS,
  effortOptionsFor,
  GATEWAY_EFFORTS,
  MODEL_PRESETS,
  matchPreset,
  modelsEqual,
  presetLabel,
  serializeExtraParams,
  toApiModels,
  type ModelReasoning,
  type ModelsConfig,
} from '../lib/models';

describe('effortOptionsFor', () => {
  it('returns null when the model has no reasoning', () => {
    expect(effortOptionsFor(null)).toBeNull();
    expect(effortOptionsFor(undefined)).toBeNull();
  });

  it('returns null when supported_efforts is omitted (no effort selector)', () => {
    const reasoning: ModelReasoning = { mandatory: true };
    expect(effortOptionsFor(reasoning)).toBeNull();
  });

  it('returns the listed efforts when supported_efforts is a list', () => {
    const reasoning: ModelReasoning = {
      supported_efforts: ['high', 'medium', 'low', 'none'],
      default_effort: 'high',
    };
    expect(effortOptionsFor(reasoning)).toEqual([
      'high',
      'medium',
      'low',
      'none',
    ]);
  });

  it('returns the full gateway set including none when supported_efforts is null', () => {
    const reasoning: ModelReasoning = {
      supported_efforts: null,
      default_effort: 'medium',
    };
    expect(effortOptionsFor(reasoning)).toEqual([...GATEWAY_EFFORTS]);
    expect(GATEWAY_EFFORTS).toContain('none');
  });

  it('strips none when reasoning is mandatory', () => {
    const fromList: ModelReasoning = {
      mandatory: true,
      supported_efforts: ['high', 'medium', 'none'],
    };
    expect(effortOptionsFor(fromList)).toEqual(['high', 'medium']);

    const fromGateway: ModelReasoning = {
      mandatory: true,
      supported_efforts: null,
    };
    expect(effortOptionsFor(fromGateway)).toEqual(
      GATEWAY_EFFORTS.filter((e) => e !== 'none'),
    );
  });
});

describe('model presets', () => {
  it('treats DEFAULT_MODELS as the Balanced preset', () => {
    expect(matchPreset(DEFAULT_MODELS)).toBe('balanced');
    expect(modelsEqual(DEFAULT_MODELS, MODEL_PRESETS[1].models)).toBe(true);
  });

  it('detects Fast and Best presets', () => {
    const fast = MODEL_PRESETS.find((p) => p.id === 'fast')!.models;
    const best = MODEL_PRESETS.find((p) => p.id === 'best')!.models;
    expect(matchPreset(fast)).toBe('fast');
    expect(matchPreset(best)).toBe('best');
    expect(presetLabel('fast')).toBe('Fast');
    expect(presetLabel('best')).toBe('Best');
    expect(fast.skills.model).toBe('openai/gpt-4o-mini');
    expect(best.skills.model).toBe('openai/gpt-4o-mini');
    expect(DEFAULT_MODELS.skills.model).toBe('qwen/qwen3-30b-a3b-instruct-2507');
  });

  it('returns custom when any role differs', () => {
    const custom: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: { model: 'openai/gpt-4o-mini', effort: null, extraParams: [] },
    };
    expect(matchPreset(custom)).toBe('custom');
    expect(presetLabel('custom')).toBe('Custom');
  });

  it('returns custom when only an extra param differs', () => {
    const custom: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: {
        ...DEFAULT_MODELS.writer,
        extraParams: [{ key: 'temperature', value: '0.99' }],
      },
    };
    expect(matchPreset(custom)).toBe('custom');
  });

  it('treats differently-ordered but equivalent param rows as the same config', () => {
    const reordered: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: {
        ...DEFAULT_MODELS.writer,
        extraParams: [{ key: 'temperature', value: '0.7' }, { key: '', value: '' }],
      },
    };
    expect(matchPreset(reordered)).toBe('balanced');
  });
});

describe('DEFAULT_MODELS', () => {
  it('matches the specified per-role model/effort/extraParams defaults', () => {
    expect(DEFAULT_MODELS.writer).toEqual({
      model: 'anthropic/claude-sonnet-5',
      effort: 'medium',
      extraParams: [{ key: 'temperature', value: '0.7' }],
    });
    expect(DEFAULT_MODELS.parser).toEqual({
      model: 'google/gemini-2.5-flash-lite',
      effort: null,
      extraParams: [{ key: 'temperature', value: '0' }],
    });
    expect(DEFAULT_MODELS.gap).toEqual({
      model: 'z-ai/glm-5.2',
      effort: 'high',
      extraParams: [{ key: 'temperature', value: '0.5' }],
    });
    expect(DEFAULT_MODELS.skills).toEqual({
      model: 'qwen/qwen3-30b-a3b-instruct-2507',
      effort: null,
      extraParams: [{ key: 'temperature', value: '0.2' }],
    });
    expect(DEFAULT_MODELS.scoring).toEqual({
      model: 'deepseek/deepseek-v4-flash',
      effort: 'xhigh',
      extraParams: [{ key: 'temperature', value: '0.2' }],
    });
  });
});

describe('preset extraParams bundles', () => {
  it('sets temperature 0 for every role in the Fast preset', () => {
    const fast = MODEL_PRESETS.find((p) => p.id === 'fast')!.models;
    for (const role of ['writer', 'parser', 'gap', 'skills', 'scoring'] as const) {
      expect(serializeExtraParams(fast[role].extraParams)).toEqual({ temperature: 0 });
    }
  });

  it('reuses Balanced per-role extraParams in the Best preset', () => {
    const best = MODEL_PRESETS.find((p) => p.id === 'best')!.models;
    for (const role of ['writer', 'parser', 'gap', 'skills', 'scoring'] as const) {
      expect(best[role].extraParams).toEqual(DEFAULT_MODELS[role].extraParams);
    }
  });
});

describe('serializeExtraParams', () => {
  it('trims keys and drops blank-key rows', () => {
    expect(
      serializeExtraParams([
        { key: '  temperature  ', value: '0.7' },
        { key: '   ', value: 'ignored' },
      ]),
    ).toEqual({ temperature: 0.7 });
  });

  it('coerces numeric-looking values to numbers', () => {
    expect(serializeExtraParams([{ key: 'top_k', value: '40' }])).toEqual({ top_k: 40 });
    expect(serializeExtraParams([{ key: 'temperature', value: '0' }])).toEqual({
      temperature: 0,
    });
  });

  it('coerces true/false (case-insensitive) to booleans', () => {
    expect(serializeExtraParams([{ key: 'stream', value: 'true' }])).toEqual({
      stream: true,
    });
    expect(serializeExtraParams([{ key: 'stream', value: 'FALSE' }])).toEqual({
      stream: false,
    });
  });

  it('keeps non-numeric, non-boolean values as strings', () => {
    expect(serializeExtraParams([{ key: 'reasoning_mode', value: 'deep' }])).toEqual({
      reasoning_mode: 'deep',
    });
  });

  it('keeps an explicit empty value as an empty string, not zero', () => {
    expect(serializeExtraParams([{ key: 'stop', value: '' }])).toEqual({ stop: '' });
  });

  it('last row wins for duplicate keys', () => {
    expect(
      serializeExtraParams([
        { key: 'temperature', value: '0.7' },
        { key: 'temperature', value: '0.9' },
      ]),
    ).toEqual({ temperature: 0.9 });
  });

  it('returns an empty object for an empty row list', () => {
    expect(serializeExtraParams([])).toEqual({});
  });
});

describe('toApiModels', () => {
  it('converts each role into the wire shape, omitting extra_params when empty', () => {
    const config: ModelsConfig = {
      ...DEFAULT_MODELS,
      parser: { model: 'openai/gpt-4o-mini', effort: null, extraParams: [] },
    };
    const api = toApiModels(config);
    expect(api.writer).toEqual({
      model: 'anthropic/claude-sonnet-5',
      effort: 'medium',
      extra_params: { temperature: 0.7 },
    });
    expect(api.parser).toEqual({ model: 'openai/gpt-4o-mini', effort: null });
    expect(api.parser).not.toHaveProperty('extra_params');
  });

  it('forwards arbitrary parameter names, not just temperature', () => {
    const config: ModelsConfig = {
      ...DEFAULT_MODELS,
      gap: {
        model: 'z-ai/glm-5.2',
        effort: 'high',
        extraParams: [
          { key: 'temperature', value: '0.5' },
          { key: 'top_k', value: '40' },
        ],
      },
    };
    const api = toApiModels(config);
    expect(api.gap.extra_params).toEqual({ temperature: 0.5, top_k: 40 });
  });
});
