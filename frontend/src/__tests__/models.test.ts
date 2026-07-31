import { describe, it, expect } from 'vitest';
import {
  DEFAULT_MODELS,
  effortOptionsFor,
  GATEWAY_EFFORTS,
  MODEL_PRESETS,
  matchPreset,
  modelsEqual,
  presetLabel,
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
      writer: { model: 'openai/gpt-4o-mini', effort: null, temperature: 0 },
    };
    expect(matchPreset(custom)).toBe('custom');
    expect(presetLabel('custom')).toBe('Custom');
  });

  it('returns custom when only temperature differs', () => {
    const custom: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: { ...DEFAULT_MODELS.writer, temperature: 0.99 },
    };
    expect(matchPreset(custom)).toBe('custom');
  });
});

describe('DEFAULT_MODELS', () => {
  it('matches the specified per-role model/effort/temperature defaults', () => {
    expect(DEFAULT_MODELS.writer).toEqual({
      model: 'anthropic/claude-sonnet-5',
      effort: 'medium',
      temperature: 0.7,
    });
    expect(DEFAULT_MODELS.parser).toEqual({
      model: 'google/gemini-2.5-flash-lite',
      effort: null,
      temperature: 0,
    });
    expect(DEFAULT_MODELS.gap).toEqual({
      model: 'z-ai/glm-5.2',
      effort: 'high',
      temperature: 0.5,
    });
    expect(DEFAULT_MODELS.skills).toEqual({
      model: 'qwen/qwen3-30b-a3b-instruct-2507',
      effort: null,
      temperature: 0.2,
    });
    expect(DEFAULT_MODELS.scoring).toEqual({
      model: 'deepseek/deepseek-v4-flash',
      effort: 'xhigh',
      temperature: 0.2,
    });
  });
});

describe('preset temperature bundles', () => {
  it('sets temperature 0 for every role in the Fast preset', () => {
    const fast = MODEL_PRESETS.find((p) => p.id === 'fast')!.models;
    for (const role of ['writer', 'parser', 'gap', 'skills', 'scoring'] as const) {
      expect(fast[role].temperature).toBe(0);
    }
  });

  it('reuses Balanced per-role temperatures in the Best preset', () => {
    const best = MODEL_PRESETS.find((p) => p.id === 'best')!.models;
    for (const role of ['writer', 'parser', 'gap', 'skills', 'scoring'] as const) {
      expect(best[role].temperature).toBe(DEFAULT_MODELS[role].temperature);
    }
  });
});
