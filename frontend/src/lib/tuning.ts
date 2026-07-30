// Per-application pipeline tuning - mirrors the backend TuningDTO / PipelineTuning.
// Keys are snake_case to match the API wire format exactly (like the rest of the
// api/types.ts models), so the object can be sent as-is with no remapping.

export const RUBRIC_KEYS = [
  'keyword_match',
  'impact_quality',
  'coherence',
  'plausibility',
  'formatting',
] as const;

export type RubricKey = (typeof RUBRIC_KEYS)[number];

export type RubricWeights = Record<RubricKey, number>;

export interface Tuning {
  threshold: number;
  plausibility_floor: number;
  max_iterations: number;
  max_compile_retries: number;
  max_identity_retries: number;
  max_length_retries: number;
  rubric_weights: RubricWeights;
}

// Defaults sourced from config/settings.py - keep in lockstep with the backend.
export const DEFAULT_TUNING: Tuning = {
  threshold: 78,
  plausibility_floor: 20,
  max_iterations: 4,
  max_compile_retries: 2,
  max_identity_retries: 2,
  max_length_retries: 3,
  rubric_weights: {
    keyword_match: 0.3,
    impact_quality: 0.2,
    coherence: 0.2,
    plausibility: 0.15,
    formatting: 0.15,
  },
};

// --- UI field metadata --------------------------------------------------------

export type ScalarKey = Exclude<keyof Tuning, 'rubric_weights'>;

export interface ScalarField {
  key: ScalarKey;
  label: string;
  min: number;
  max: number;
  step: number;
  unit?: string;
  help: string;
}

export const SCALAR_FIELDS: readonly ScalarField[] = [
  {
    key: 'threshold',
    label: 'Pass threshold',
    min: 0,
    max: 100,
    step: 1,
    help: 'The composite score a draft must reach for the recruiter panel to accept it. Higher = stricter, more revision rounds.',
  },
  {
    key: 'plausibility_floor',
    label: 'Plausibility floor',
    min: 0,
    max: 100,
    step: 1,
    help: "The minimum the Skeptic must give for believability. Vetoes an otherwise-passing draft - the fabrication guard. Raise it to demand résumés that read as more truthful.",
  },
  {
    key: 'max_iterations',
    label: 'Max revision rounds',
    min: 1,
    max: 8,
    step: 1,
    help: 'How many times the writer may rewrite and be re-scored. More rounds can lift the score but cost time and tokens; on exhaustion the best draft so far ships.',
  },
  {
    key: 'max_compile_retries',
    label: 'Compile retries',
    min: 0,
    max: 5,
    step: 1,
    help: 'Per-round budget for bouncing back to the writer when the LaTeX fails to compile or overflows one page.',
  },
  {
    key: 'max_identity_retries',
    label: 'Identity retries',
    min: 0,
    max: 5,
    step: 1,
    help: 'Budget for rewrites when the identity check finds your name, contact details, or dates were altered. Exhausting it ships the best clean draft.',
  },
  {
    key: 'max_length_retries',
    label: 'Bullet-length retries',
    min: 0,
    max: 6,
    step: 1,
    help: 'Per-round budget for nudging bullets back into the target character band. Cosmetic - on exhaustion the pipeline proceeds anyway.',
  },
];

export interface RubricField {
  key: RubricKey;
  label: string;
  help: string;
}

export const RUBRIC_FIELDS: readonly RubricField[] = [
  {
    key: 'keyword_match',
    label: 'Keyword match',
    help: 'Weight on how well the résumé covers the job description’s keywords (ATS coverage).',
  },
  {
    key: 'impact_quality',
    label: 'Impact quality',
    help: 'Weight on quantified, outcome-driven bullets over vague responsibility statements.',
  },
  {
    key: 'coherence',
    label: 'Coherence',
    help: 'Weight on a clear, consistent narrative across roles.',
  },
  {
    key: 'plausibility',
    label: 'Plausibility',
    help: 'Weight on how believable the claims read. Separate from the hard plausibility floor above.',
  },
  {
    key: 'formatting',
    label: 'Formatting',
    help: 'Weight on clean, scannable, well-structured layout.',
  },
];

// --- helpers ------------------------------------------------------------------

export function weightsSum(weights: RubricWeights): number {
  return RUBRIC_KEYS.reduce((acc, k) => acc + weights[k], 0);
}

const clamp01 = (n: number): number => Math.min(1, Math.max(0, n));

/**
 * Return a new weight map with *key* set to *newValue* (clamped to [0,1]) and the
 * other four scaled so the five always sum to 1.0 (live-balance). The remainder
 * is distributed proportionally to the untouched weights, preserving their
 * ratios; if they are all zero it is split equally. Never mutates the input.
 */
export function rebalanceWeights(
  weights: RubricWeights,
  key: RubricKey,
  newValue: number,
): RubricWeights {
  const value = clamp01(newValue);
  const remaining = 1 - value;
  const others = RUBRIC_KEYS.filter((k) => k !== key);
  const othersSum = others.reduce((acc, k) => acc + weights[k], 0);

  const next = { ...weights, [key]: value } as RubricWeights;
  for (const k of others) {
    next[k] =
      othersSum > 0
        ? weights[k] * (remaining / othersSum)
        : remaining / others.length;
  }
  return next;
}
