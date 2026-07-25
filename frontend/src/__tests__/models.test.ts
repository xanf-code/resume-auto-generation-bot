import { describe, it, expect } from 'vitest';
import {
  effortOptionsFor,
  GATEWAY_EFFORTS,
  type ModelReasoning,
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
