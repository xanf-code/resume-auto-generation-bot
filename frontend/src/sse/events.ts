import type { ProgressEvent } from '../api/types';

export type { ProgressEvent };

export function isTerminalStage(stage: string): boolean {
  return stage === 'done' || stage === 'failed';
}

export function isProgressEvent(data: unknown): data is ProgressEvent {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return (
    typeof d.job_id === 'string' &&
    typeof d.seq === 'number' &&
    typeof d.stage === 'string' &&
    typeof d.human_label === 'string' &&
    typeof d.pct === 'number'
  );
}
