import { THRESHOLD } from './constants';
import type { PersonaScore } from '../api/types';

// Editorial palette: muted sage for pass, ink-red for fail. Tokens mirror
// --color-pass / --color-fail in index.css (SVG/inline styles can't read vars).
export const PASS_COLOR = '#3f6b4e';
export const FAIL_COLOR = '#b02e26';

export function passColor(score: number): string {
  return score >= THRESHOLD ? PASS_COLOR : FAIL_COLOR;
}

export function personaAverage(
  scores: Pick<
    PersonaScore,
    'keyword_match' | 'impact_quality' | 'coherence' | 'plausibility' | 'formatting'
  >,
): number {
  const { keyword_match, impact_quality, coherence, plausibility, formatting } = scores;
  const total = keyword_match + impact_quality + coherence + plausibility + formatting;
  return total / 5;
}
