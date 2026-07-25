import { describe, it, expect } from 'vitest';
import {
  DEFAULT_TUNING,
  RUBRIC_KEYS,
  rebalanceWeights,
  weightsSum,
} from '../lib/tuning';

const sum = (w: Record<string, number>) =>
  Object.values(w).reduce((a, b) => a + b, 0);

describe('DEFAULT_TUNING', () => {
  it('mirrors the backend defaults and weights sum to 1', () => {
    expect(DEFAULT_TUNING.threshold).toBe(78);
    expect(DEFAULT_TUNING.plausibility_floor).toBe(20);
    expect(DEFAULT_TUNING.max_iterations).toBe(4);
    expect(DEFAULT_TUNING.max_compile_retries).toBe(2);
    expect(DEFAULT_TUNING.max_identity_retries).toBe(2);
    expect(DEFAULT_TUNING.max_length_retries).toBe(3);
    expect(sum(DEFAULT_TUNING.rubric_weights)).toBeCloseTo(1.0, 6);
  });
});

describe('rebalanceWeights', () => {
  it('keeps the five weights summing to 1.0 after a change', () => {
    const next = rebalanceWeights(DEFAULT_TUNING.rubric_weights, 'keyword_match', 0.5);
    expect(next.keyword_match).toBeCloseTo(0.5, 6);
    expect(weightsSum(next)).toBeCloseTo(1.0, 6);
  });

  it('distributes the remainder proportionally to the other weights', () => {
    // Start from an even split so proportional == equal for a clean assertion.
    const even = {
      keyword_match: 0.2,
      impact_quality: 0.2,
      coherence: 0.2,
      plausibility: 0.2,
      formatting: 0.2,
    };
    const next = rebalanceWeights(even, 'keyword_match', 0.6);
    expect(next.keyword_match).toBeCloseTo(0.6, 6);
    // remaining 0.4 split equally across the other four = 0.1 each
    expect(next.impact_quality).toBeCloseTo(0.1, 6);
    expect(next.coherence).toBeCloseTo(0.1, 6);
    expect(next.plausibility).toBeCloseTo(0.1, 6);
    expect(next.formatting).toBeCloseTo(0.1, 6);
    expect(weightsSum(next)).toBeCloseTo(1.0, 6);
  });

  it('preserves the ratio between the untouched weights', () => {
    const skewed = {
      keyword_match: 0.4,
      impact_quality: 0.3,
      coherence: 0.1,
      plausibility: 0.1,
      formatting: 0.1,
    };
    const next = rebalanceWeights(skewed, 'keyword_match', 0.2);
    // impact_quality was 3x coherence; ratio must survive rebalancing.
    expect(next.impact_quality / next.coherence).toBeCloseTo(3, 5);
    expect(weightsSum(next)).toBeCloseTo(1.0, 6);
  });

  it('clamps the new value to [0, 1]', () => {
    const hi = rebalanceWeights(DEFAULT_TUNING.rubric_weights, 'formatting', 5);
    expect(hi.formatting).toBeCloseTo(1.0, 6);
    expect(weightsSum(hi)).toBeCloseTo(1.0, 6);

    const lo = rebalanceWeights(DEFAULT_TUNING.rubric_weights, 'formatting', -3);
    expect(lo.formatting).toBeCloseTo(0.0, 6);
    expect(weightsSum(lo)).toBeCloseTo(1.0, 6);
  });

  it('splits equally when the other weights are all zero', () => {
    const allOnOne = {
      keyword_match: 1,
      impact_quality: 0,
      coherence: 0,
      plausibility: 0,
      formatting: 0,
    };
    // Drop keyword_match to 0.2 - the other four are 0, so remainder splits equally.
    const next = rebalanceWeights(allOnOne, 'keyword_match', 0.2);
    expect(next.keyword_match).toBeCloseTo(0.2, 6);
    expect(next.impact_quality).toBeCloseTo(0.2, 6);
    expect(next.formatting).toBeCloseTo(0.2, 6);
    expect(weightsSum(next)).toBeCloseTo(1.0, 6);
  });

  it('does not mutate the input', () => {
    const before = { ...DEFAULT_TUNING.rubric_weights };
    rebalanceWeights(DEFAULT_TUNING.rubric_weights, 'coherence', 0.9);
    expect(DEFAULT_TUNING.rubric_weights).toEqual(before);
  });

  it('covers all five rubric dimensions', () => {
    expect(RUBRIC_KEYS).toHaveLength(5);
    expect(new Set(RUBRIC_KEYS)).toEqual(
      new Set(['keyword_match', 'impact_quality', 'coherence', 'plausibility', 'formatting']),
    );
  });
});
