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
      supported_efforts: ['high', 'medium', 'low'],
      default_effort: 'high',
    };
    expect(effortOptionsFor(reasoning)).toEqual(['high', 'medium', 'low']);
  });

  it('returns the full gateway set when supported_efforts is null', () => {
    const reasoning: ModelReasoning = {
      supported_efforts: null,
      default_effort: 'medium',
    };
    expect(effortOptionsFor(reasoning)).toEqual([...GATEWAY_EFFORTS]);
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
    expect(DEFAULT_MODELS.skills.model).toBe('openai/gpt-4o-mini');
  });

  it('returns custom when any role differs', () => {
    const custom: ModelsConfig = {
      ...DEFAULT_MODELS,
      writer: { model: 'openai/gpt-4o-mini', effort: null },
    };
    expect(matchPreset(custom)).toBe('custom');
    expect(presetLabel('custom')).toBe('Custom');
  });
});
