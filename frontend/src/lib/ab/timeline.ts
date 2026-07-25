// Pure timeline builder for the A/B résumé tournament replay. Turns a static
// TournamentResult into an ordered, seekable sequence of animation steps. No
// React, no DOM - this module is safe to unit test in isolation.

import type { MatchResult, StepKind, Timeline, TimelineStep, TournamentResult } from './types';

/** Flattened per-step duration used when `reducedMotion` is requested. */
export const REDUCED_STEP_MS = 900;

const BASE_MS = {
  tournamentIntro: 900,
  roundIntro: 700,
  matchFocus: 420,
  matchScore: 1100,
  matchVerdict: 700,
  matchAdvance: 620,
  roundOutro: 400,
  champion: 1600,
} as const;

/** Unscaled focus+score+verdict+advance — one full match iteration at 1x. */
export const MATCH_CYCLE_MS =
  BASE_MS.matchFocus + BASE_MS.matchScore + BASE_MS.matchVerdict + BASE_MS.matchAdvance;

const TOURNAMENT_INTRO_ROUND = -1;

/** Wider rounds move faster so a size-16 bracket doesn't overstay its welcome. */
function paceScale(matchesInRound: number): number {
  if (matchesInRound >= 8) return 0.55;
  if (matchesInRound >= 4) return 0.75;
  return 1;
}

/** Rounds to the nearest ms and floors at 1ms - a step can never be zero-length. */
function scaledDuration(baseMs: number, scale: number): number {
  return Math.max(1, Math.round(baseMs * scale));
}

/** A step before cumulative `startMs` offsets have been assigned. */
interface DraftStep {
  id: string;
  kind: StepKind;
  round: number;
  matchId?: string;
  result?: MatchResult;
  durationMs: number;
}

function buildDraftSteps(result: TournamentResult): DraftStep[] {
  const resultsByMatchId = new Map(result.results.map((r) => [r.matchId, r]));
  const rounds = result.bracket.rounds;
  const lastRound = rounds[rounds.length - 1];

  const draft: DraftStep[] = [
    {
      id: `tournament-intro:${TOURNAMENT_INTRO_ROUND}`,
      kind: 'tournament-intro',
      round: TOURNAMENT_INTRO_ROUND,
      durationMs: BASE_MS.tournamentIntro,
    },
  ];

  for (const round of rounds) {
    const scale = paceScale(round.matchIds.length);

    draft.push({
      id: `round-intro:${round.index}`,
      kind: 'round-intro',
      round: round.index,
      durationMs: scaledDuration(BASE_MS.roundIntro, scale),
    });

    for (const matchId of round.matchIds) {
      const matchResult = resultsByMatchId.get(matchId);
      if (!matchResult) {
        throw new Error(`buildTimeline: missing MatchResult for match ${matchId}`);
      }
      const isFinal = matchId === result.bracket.finalMatchId;

      draft.push({
        id: `match-focus:${matchId}`,
        kind: 'match-focus',
        round: round.index,
        matchId,
        durationMs: scaledDuration(BASE_MS.matchFocus, scale),
      });
      draft.push({
        id: `match-score:${matchId}`,
        kind: 'match-score',
        round: round.index,
        matchId,
        durationMs: scaledDuration(BASE_MS.matchScore, scale),
      });
      draft.push({
        id: `match-verdict:${matchId}`,
        kind: 'match-verdict',
        round: round.index,
        matchId,
        result: matchResult,
        durationMs: scaledDuration(BASE_MS.matchVerdict, scale),
      });
      if (!isFinal) {
        draft.push({
          id: `match-advance:${matchId}`,
          kind: 'match-advance',
          round: round.index,
          matchId,
          durationMs: scaledDuration(BASE_MS.matchAdvance, scale),
        });
      }
    }

    draft.push({
      id: `round-outro:${round.index}`,
      kind: 'round-outro',
      round: round.index,
      durationMs: scaledDuration(BASE_MS.roundOutro, scale),
    });
  }

  draft.push({
    id: `champion:${lastRound.index}`,
    kind: 'champion',
    round: lastRound.index,
    durationMs: BASE_MS.champion,
  });

  return draft;
}

const REDUCED_DROP_KINDS: ReadonlySet<StepKind> = new Set([
  'match-focus',
  'match-advance',
  'round-outro',
]);

/** Drops motion-only steps and flattens every remaining duration to REDUCED_STEP_MS. */
function applyReducedMotion(draft: DraftStep[]): DraftStep[] {
  return draft
    .filter((step) => !REDUCED_DROP_KINDS.has(step.kind))
    .map((step) => ({ ...step, durationMs: REDUCED_STEP_MS }));
}

/** Walks the draft steps in order, assigning cumulative `startMs` offsets. */
function assignOffsets(draft: DraftStep[]): Timeline {
  let cursor = 0;
  const steps: TimelineStep[] = draft.map((step) => {
    const timelineStep: TimelineStep = {
      id: step.id,
      kind: step.kind,
      durationMs: step.durationMs,
      startMs: cursor,
      round: step.round,
      ...(step.matchId !== undefined ? { matchId: step.matchId } : {}),
      ...(step.result !== undefined ? { result: step.result } : {}),
    };
    cursor += step.durationMs;
    return timelineStep;
  });

  const last = steps[steps.length - 1];
  const totalMs = last ? last.startMs + last.durationMs : 0;
  return { steps, totalMs };
}

/**
 * Builds the ordered, cumulative-offset animation timeline for a completed
 * tournament. Pure - never mutates `result`, always returns a fresh Timeline.
 */
export function buildTimeline(
  result: TournamentResult,
  opts?: { reducedMotion?: boolean },
): Timeline {
  const draft = buildDraftSteps(result);
  const finalDraft = opts?.reducedMotion ? applyReducedMotion(draft) : draft;
  return assignOffsets(finalDraft);
}

/**
 * Binary search over `startMs`: returns the index of the step active at `ms`,
 * clamped to the first/last step for out-of-range values.
 */
export function stepIndexAtMs(timeline: Timeline, ms: number): number {
  const { steps, totalMs } = timeline;
  if (steps.length === 0) return -1;
  if (ms <= 0) return 0;
  if (ms >= totalMs) return steps.length - 1;

  let lo = 0;
  let hi = steps.length - 1;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    const step = steps[mid];
    const end = step.startMs + step.durationMs;
    if (ms < step.startMs) {
      hi = mid - 1;
    } else if (ms >= end) {
      lo = mid + 1;
    } else {
      return mid;
    }
  }
  return Math.min(steps.length - 1, Math.max(0, lo));
}

/**
 * Every match resolved by a `match-verdict` step at or before `stepIndex`,
 * keyed by matchId - the bracket's derivable state at any point in the run.
 */
export function resolvedAt(timeline: Timeline, stepIndex: number): Record<string, MatchResult> {
  const resolved: Record<string, MatchResult> = {};
  const lastIndex = Math.min(stepIndex, timeline.steps.length - 1);
  for (let i = 0; i <= lastIndex; i++) {
    const step = timeline.steps[i];
    if (step.kind === 'match-verdict' && step.result) {
      resolved[step.result.matchId] = step.result;
    }
  }
  return resolved;
}
