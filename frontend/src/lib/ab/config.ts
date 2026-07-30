// Default config, judge metadata, and weight-rebalancing helpers for the A/B
// testing résumé tournament. Pure data + logic - no React, no DOM.

import type { AbConfig, JudgeId, TargetRole } from './types';

export const DEFAULT_AB_CONFIG: AbConfig = {
  judges: ['ats', 'hiring_manager', 'technical', 'skeptic', 'peer'],
  judgeWeights: { ats: 0.2, hiring_manager: 0.2, technical: 0.2, skeptic: 0.2, peer: 0.2 },
  upsetFactor: 0.35,
  bestOf: 3,
  targetRole: 'generalist',
  strictness: 50,
  blindJudging: false,
};

export interface JudgeMeta {
  id: JudgeId;
  label: string;
  description: string;
}

export const JUDGES: readonly JudgeMeta[] = [
  {
    id: 'ats',
    label: 'ATS Scanner',
    description:
      "Robotic keyword matcher — rewards exact phrase overlap with the job description.",
  },
  {
    id: 'hiring_manager',
    label: 'Hiring Manager',
    description: 'Reads for narrative arc and role fit over raw keywords.',
  },
  {
    id: 'technical',
    label: 'Technical Lead',
    description: 'Digs into the depth and credibility of technical claims.',
  },
  {
    id: 'skeptic',
    label: 'The Skeptic',
    description: 'Hunts for exaggeration, vagueness, and fabrication.',
  },
  {
    id: 'peer',
    label: 'Peer Reviewer',
    description: "A fellow engineer's gut-check read.",
  },
];

export const ROLE_AFFINITY: Record<TargetRole, Record<JudgeId, number>> = {
  backend: { ats: 2, hiring_manager: 0, technical: 5, skeptic: -1, peer: 3 },
  frontend: { ats: 1, hiring_manager: 2, technical: 3, skeptic: -1, peer: 4 },
  ml: { ats: 0, hiring_manager: -1, technical: 6, skeptic: -2, peer: 2 },
  platform: { ats: 2, hiring_manager: -1, technical: 5, skeptic: 0, peer: 1 },
  generalist: { ats: 3, hiring_manager: 3, technical: 1, skeptic: 1, peer: 1 },
};

const clamp01 = (n: number): number => Math.min(1, Math.max(0, n));

/**
 * Return a new weight map with *key* set to *newValue* (clamped to [0,1]) and
 * the other currently-selected judges scaled so the selected subset always
 * sums to 1.0 (live-balance), generalizing tuning.ts's fixed-5-key
 * rebalanceWeights to an arbitrary selected `judges` subset. The remainder is
 * distributed proportionally to the other selected judges' existing weights,
 * preserving their ratios; if they are all zero it is split equally. Judges
 * outside the `judges` panel are copied through untouched. Never mutates the
 * input.
 */
export function rebalanceJudgeWeights(
  weights: Record<JudgeId, number>,
  judges: JudgeId[],
  key: JudgeId,
  newValue: number,
): Record<JudgeId, number> {
  // A panel of fewer than 2 (or one that doesn't include `key`) has nothing
  // sensible to rebalance against - just pin `key` to full weight and leave
  // everything else as-is.
  if (judges.length < 2 || !judges.includes(key)) {
    return { ...weights, [key]: 1 };
  }

  const value = clamp01(newValue);
  const remaining = 1 - value;
  const others = judges.filter((j) => j !== key);
  const othersSum = others.reduce((acc, j) => acc + weights[j], 0);

  const next = { ...weights, [key]: value };
  for (const j of others) {
    next[j] = othersSum > 0 ? weights[j] * (remaining / othersSum) : remaining / others.length;
  }
  return next;
}
