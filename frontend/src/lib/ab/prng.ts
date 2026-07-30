// Deterministic PRNG + seed utilities for the A/B tournament. No React, no DOM.
// Every tournament outcome must be replayable from its seed string, so
// `Math.random()` is banned everywhere in `src/lib/ab/` except `newSeedToken`
// below, which only needs to mint a fresh, human-readable seed for a *new*
// tournament - it never influences the tournament's own math.

/** Mulberry32: a small, fast, high-quality 32-bit PRNG. Deterministic per seed. */
export function mulberry32(a: number): () => number {
  return function (): number {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a 32-bit hash. Turns any seed string into a stable numeric seed. */
export function hashSeed(s: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    hash ^= s.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

const SEED_WORDS: readonly string[] = [
  'mercer',
  'cobalt',
  'harlow',
  'zephyr',
  'quill',
  'brindle',
  'onyx',
  'sable',
  'thorne',
  'ember',
];

/**
 * Mints a short human-readable seed token like `mercer-7f31`.
 * This is the ONE place in `src/lib/ab/` allowed to call `Math.random()` -
 * everywhere else must derive from a replayable seed via `mulberry32`/`hashSeed`.
 */
export function newSeedToken(): string {
  const word = SEED_WORDS[Math.floor(Math.random() * SEED_WORDS.length)];
  const hex = Math.floor(Math.random() * 0x10000)
    .toString(16)
    .padStart(4, '0');
  return `${word}-${hex}`;
}
