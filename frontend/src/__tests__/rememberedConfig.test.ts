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
});
