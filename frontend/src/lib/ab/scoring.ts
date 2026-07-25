// Per-side scoring for a single tournament match. Pure math, no React, no DOM.
//
// Randomness rule: every single random read derives a FRESH mulberry32
// generator keyed on `${seed}|${matchId}|${competitorId}|${judge}|${readIndex}`
// and takes exactly the first value it produces. This makes every draw
// independently addressable - adding a judge or changing `bestOf` never
// shifts any other draw's outcome.

import { hashSeed, mulberry32 } from './prng';
import { ROLE_AFFINITY } from './config';
import type { AbConfig, Competitor, JudgeId, JudgeVerdict, MatchScore } from './types';

export interface ScoreSideCtx {
  seed: string;
  matchId: string;
  round: number;
  config: AbConfig;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function round1dp(value: number): number {
  return Math.round(value * 10) / 10;
}

/** One noisy read of a single judge's score for a single bestOf trial. */
function drawRead(
  ctx: ScoreSideCtx,
  competitor: Competitor,
  judge: JudgeId,
  readIndex: number,
  prior: number,
  roleAdj: number,
): number {
  const { config } = ctx;
  let noise = 0;
  // Chalk mode (upsetFactor === 0) must be 100% independent of the RNG so it
  // is provably deterministic across judges/bestOf - do not draw at all.
  if (config.upsetFactor !== 0) {
    const rng = mulberry32(
      hashSeed(`${ctx.seed}|${ctx.matchId}|${competitor.id}|${judge}|${readIndex}`),
    );
    noise = (rng() * 2 - 1) * (8 + 34 * config.upsetFactor);
  }
  const form = ctx.round * 0.75;
  const raw = prior + roleAdj + noise + form - config.strictness * 0.12;
  return clamp(raw, 0, 100);
}

function selectedWeightSum(config: AbConfig): number {
  return config.judges.reduce((sum, judge) => sum + (config.judgeWeights[judge] ?? 0), 0);
}

function normalizedWeight(config: AbConfig, judge: JudgeId, weightSum: number): number {
  if (weightSum > 0) {
    return (config.judgeWeights[judge] ?? 0) / weightSum;
  }
  // Defensive fallback for a caller-supplied all-zero weight subset: split
  // evenly rather than producing NaN/Infinity.
  return 1 / config.judges.length;
}

/**
 * Scores one competitor's side of a match. `upset` is always returned as
 * `false` here - it cannot be determined without knowing the opponent's
 * result, so `simulate.ts` overwrites it on the winner's `MatchScore` once
 * the match is resolved.
 */
export function scoreSide(competitor: Competitor, ctx: ScoreSideCtx): MatchScore {
  const { config } = ctx;
  const roleAffinity = ROLE_AFFINITY[config.targetRole];

  const verdicts: JudgeVerdict[] = config.judges.map((judge) => {
    const prior = competitor.traits[judge] ?? competitor.baseScore;
    const roleAdj = roleAffinity[judge];
    let sum = 0;
    for (let readIndex = 0; readIndex < config.bestOf; readIndex++) {
      sum += drawRead(ctx, competitor, judge, readIndex, prior, roleAdj);
    }
    return { judge, score: round1dp(sum / config.bestOf) };
  });

  const weightSum = selectedWeightSum(config);
  const composite = verdicts.reduce(
    (sum, verdict) => sum + verdict.score * normalizedWeight(config, verdict.judge, weightSum),
    0,
  );

  return {
    competitorId: competitor.id,
    total: clamp(round1dp(composite), 0, 100),
    verdicts,
    upset: false,
  };
}
