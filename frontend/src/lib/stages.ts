export const STAGE_ORDER = [
  'init',
  'parse',
  'writer',
  'compile',
  'score',
  'done',
] as const;

export type StageName = (typeof STAGE_ORDER)[number];

// The backend streams fine-grained node names (parse_resume, analyze_jd,
// recruiter_panel, …); the stepper shows six coarse buckets. Without this
// mapping the spine nodes resolve to index -1 and the stepper stays blank until
// `writer` arrives - the pipeline appears to "jump" straight to writing. Every
// backend stage maps to a bucket, in monotonic execution order.
const FINE_TO_COARSE: Record<string, StageName> = {
  init: 'init',
  // extraction spine
  parse_resume: 'parse',
  analyze_jd: 'parse',
  gap_analysis: 'parse',
  generate_skills: 'parse',
  // revision loop - drafting
  writer: 'writer',
  check_bullet_lengths: 'writer',
  render: 'writer',
  identity_check: 'writer',
  // revision loop - compilation
  compile: 'compile',
  // revision loop - scoring
  recruiter_panel: 'score',
  aggregator: 'score',
  bookkeep: 'score',
  // finalization
  emit: 'done',
  score_report: 'done',
  done: 'done',
};

// Map any backend stage name onto its coarse stepper bucket. Already-coarse
// names pass through; unknown names fall back to 'init' rather than regressing.
export function coarseStage(stage: string): StageName {
  const mapped = FINE_TO_COARSE[stage];
  if (mapped) return mapped;
  return STAGE_ORDER.includes(stage as StageName) ? (stage as StageName) : 'init';
}

export function stageIndex(stage: string): number {
  return STAGE_ORDER.indexOf(stage as StageName);
}
