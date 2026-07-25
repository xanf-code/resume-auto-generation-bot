export const STAGE_ORDER = [
  'init',
  'parse',
  'writer',
  'compile',
  'score',
  'done',
] as const;

export type StageName = (typeof STAGE_ORDER)[number];

export function stageIndex(stage: string): number {
  return STAGE_ORDER.indexOf(stage as StageName);
}
