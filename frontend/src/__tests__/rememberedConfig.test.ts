import { describe, it, expect, beforeEach } from 'vitest';
import {
  loadRememberedConfig,
  saveRememberedConfig,
  REMEMBERED_CONFIG_STORAGE_KEY,
} from '../lib/rememberedConfig';
import { DEFAULT_MODELS } from '../lib/models';
import { DEFAULT_TUNING } from '../lib/tuning';

describe('rememberedConfig', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns null when nothing has been remembered yet', () => {
    expect(loadRememberedConfig()).toBeNull();
  });

  it('round-trips a saved config', () => {
    saveRememberedConfig({ models: DEFAULT_MODELS, tuning: DEFAULT_TUNING });
    expect(loadRememberedConfig()).toEqual({
      models: DEFAULT_MODELS,
      tuning: DEFAULT_TUNING,
    });
  });

  it('writes JSON under the expected storage key', () => {
    saveRememberedConfig({ models: DEFAULT_MODELS, tuning: DEFAULT_TUNING });
    const raw = localStorage.getItem(REMEMBERED_CONFIG_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toEqual({ models: DEFAULT_MODELS, tuning: DEFAULT_TUNING });
  });

  it('returns null when the stored value is corrupt JSON', () => {
    localStorage.setItem(REMEMBERED_CONFIG_STORAGE_KEY, '{not-valid-json');
    expect(loadRememberedConfig()).toBeNull();
  });

  it('returns null when the stored value is missing required keys', () => {
    localStorage.setItem(REMEMBERED_CONFIG_STORAGE_KEY, JSON.stringify({ models: DEFAULT_MODELS }));
    expect(loadRememberedConfig()).toBeNull();
  });

  it('a later save overwrites the previous one', () => {
    saveRememberedConfig({ models: DEFAULT_MODELS, tuning: DEFAULT_TUNING });
    const custom = { ...DEFAULT_TUNING, threshold: 90 };
    saveRememberedConfig({ models: DEFAULT_MODELS, tuning: custom });
    expect(loadRememberedConfig()?.tuning.threshold).toBe(90);
  });

  it('normalizes a pre-existing record saved under the old temperature-only shape', () => {
    // Regression guard: a record saved by an older build (ModelRoleConfig had
    // `temperature: number | null` instead of `extraParams`) must not crash
    // the app on load - it must load with extraParams defaulted to [].
    const staleModels = {
      writer: { model: 'anthropic/claude-sonnet-5', effort: 'medium', temperature: 0.7 },
      parser: { model: 'google/gemini-2.5-flash-lite', effort: null, temperature: 0 },
      gap: { model: 'z-ai/glm-5.2', effort: 'high', temperature: 0.5 },
      skills: { model: 'qwen/qwen3-30b-a3b-instruct-2507', effort: null, temperature: 0.2 },
      scoring: { model: 'deepseek/deepseek-v4-flash', effort: 'xhigh', temperature: 0.2 },
    };
    localStorage.setItem(
      REMEMBERED_CONFIG_STORAGE_KEY,
      JSON.stringify({ models: staleModels, tuning: DEFAULT_TUNING }),
    );

    const loaded = loadRememberedConfig();

    expect(loaded).not.toBeNull();
    expect(loaded!.models.writer.extraParams).toEqual([]);
    expect(loaded!.models.writer.model).toBe('anthropic/claude-sonnet-5');
    expect(loaded!.models.writer.effort).toBe('medium');
  });

  it('normalizes a record whose extraParams is present but not an array', () => {
    const corrupt = {
      ...DEFAULT_MODELS,
      writer: { model: 'anthropic/claude-sonnet-5', effort: 'medium', extraParams: null },
    };
    localStorage.setItem(
      REMEMBERED_CONFIG_STORAGE_KEY,
      JSON.stringify({ models: corrupt, tuning: DEFAULT_TUNING }),
    );

    const loaded = loadRememberedConfig();

    expect(loaded!.models.writer.extraParams).toEqual([]);
  });
});
