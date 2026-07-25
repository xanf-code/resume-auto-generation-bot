import { describe, it, expect } from 'vitest';
import { mulberry32, hashSeed, newSeedToken } from '../lib/ab/prng';

describe('mulberry32', () => {
  it('produces a fixed known sequence for seed 1 (regression lock)', () => {
    const rand = mulberry32(1);
    const first = rand();
    const second = rand();
    const third = rand();
    expect(first).toBeCloseTo(0.6270739405881613, 12);
    expect(second).toBeCloseTo(0.002735721180215478, 12);
    expect(third).toBeCloseTo(0.5274470399599522, 12);
  });

  it('produces an identical sequence for the same seed', () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const seqA = Array.from({ length: 5 }, () => a());
    const seqB = Array.from({ length: 5 }, () => b());
    expect(seqA).toEqual(seqB);
  });

  it('produces different first outputs for different seeds', () => {
    const a = mulberry32(1);
    const b = mulberry32(2);
    expect(a()).not.toBe(b());
  });

  it('always yields values in [0, 1)', () => {
    const rand = mulberry32(hashSeed('test'));
    for (let i = 0; i < 1000; i++) {
      const v = rand();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe('hashSeed', () => {
  it('is stable across repeated calls with the same string', () => {
    expect(hashSeed('abc')).toBe(hashSeed('abc'));
  });

  it('differs for a one-character change', () => {
    expect(hashSeed('abc')).not.toBe(hashSeed('abd'));
  });

  it('returns an unsigned 32-bit integer', () => {
    const h = hashSeed('some-longer-seed-string');
    expect(Number.isInteger(h)).toBe(true);
    expect(h).toBeGreaterThanOrEqual(0);
    expect(h).toBeLessThanOrEqual(0xffffffff);
  });
});

describe('newSeedToken', () => {
  it('matches the `word-hex4` shape', () => {
    const token = newSeedToken();
    expect(token).toMatch(/^[a-z]+-[0-9a-f]{4}$/);
  });

  it('produces different tokens across calls (extremely unlikely to collide)', () => {
    const tokens = new Set(Array.from({ length: 20 }, () => newSeedToken()));
    expect(tokens.size).toBeGreaterThan(1);
  });
});
