export const BULLET_COUNT_MIN = 2;
export const BULLET_COUNT_MAX = 5;
export const DEFAULT_BULLET_COUNTS: [number, number] = [4, 4];

export const ROLE_LABELS: [string, string] = ['Recent role', 'Previous role'];

export function clampCount(n: number): number {
  return Math.max(BULLET_COUNT_MIN, Math.min(BULLET_COUNT_MAX, n));
}

export function setCount(
  counts: [number, number],
  index: 0 | 1,
  value: number,
): [number, number] {
  const next: [number, number] = [counts[0], counts[1]];
  next[index] = clampCount(value);
  return next;
}
