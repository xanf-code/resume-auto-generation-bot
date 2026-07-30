import { describe, it, expect } from 'vitest';
import { passColor, personaAverage, PASS_COLOR, FAIL_COLOR } from '../lib/scoring';

describe('passColor', () => {
  it('returns the pass color when score equals threshold (78)', () => {
    expect(passColor(78)).toBe(PASS_COLOR);
  });

  it('returns the pass color when score exceeds threshold', () => {
    expect(passColor(90)).toBe(PASS_COLOR);
  });

  it('returns the fail color when score is below threshold (77)', () => {
    expect(passColor(77)).toBe(FAIL_COLOR);
  });

  it('returns the fail color for score 0', () => {
    expect(passColor(0)).toBe(FAIL_COLOR);
  });
});

describe('personaAverage', () => {
  it('returns 70 for equal weights summing to 350', () => {
    const scores = {
      keyword_match: 80,
      impact_quality: 70,
      coherence: 75,
      plausibility: 65,
      formatting: 60,
    };
    expect(personaAverage(scores)).toBe(70);
  });

  it('returns 100 when all scores are 100', () => {
    const scores = {
      keyword_match: 100,
      impact_quality: 100,
      coherence: 100,
      plausibility: 100,
      formatting: 100,
    };
    expect(personaAverage(scores)).toBe(100);
  });

  it('returns 0 when all scores are 0', () => {
    const scores = {
      keyword_match: 0,
      impact_quality: 0,
      coherence: 0,
      plausibility: 0,
      formatting: 0,
    };
    expect(personaAverage(scores)).toBe(0);
  });
});
