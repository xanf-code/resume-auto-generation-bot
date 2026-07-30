// Pure tournament simulator: folds over a bracket's rounds, resolving each
// match with `scoreSide`, and propagating winners into the next round on a
// fresh, immutable copy of the bracket. No React, no DOM.

import { scoreSide } from './scoring';
import type { AbConfig, Bracket, Match, MatchResult, TournamentResult } from './types';

/** Shallow-per-field, deep-enough copy of a matches record - never mutates the source. */
function cloneMatches(matches: Record<string, Match>): Record<string, Match> {
  const next: Record<string, Match> = {};
  for (const [id, match] of Object.entries(matches)) {
    next[id] = { ...match, next: match.next ? { ...match.next } : null };
  }
  return next;
}

/**
 * Runs a full tournament deterministically from `seed` + `config`. Identical
 * `(bracket, seed, config)` in always produces a `toEqual`-identical
 * `TournamentResult` out - no shared mutable state leaks between calls.
 */
export function simulateTournament(
  bracket: Bracket,
  seed: string,
  config: AbConfig,
): TournamentResult {
  let matches = cloneMatches(bracket.matches);
  const indexById = new Map(bracket.competitors.map((c, i) => [c.id, i]));
  const competitorById = new Map(bracket.competitors.map((c) => [c.id, c]));
  const results: MatchResult[] = [];

  for (const round of bracket.rounds) {
    for (const matchId of round.matchIds) {
      const match = matches[matchId];
      const { a: aId, b: bId } = match;
      if (aId === null || bId === null) {
        throw new Error(`simulateTournament: match ${matchId} is missing a competitor`);
      }

      const competitorA = competitorById.get(aId);
      const competitorB = competitorById.get(bId);
      if (!competitorA || !competitorB) {
        throw new Error(`simulateTournament: unknown competitor id in match ${matchId}`);
      }

      const ctx = { seed, matchId, round: match.round, config };
      const scoreA = scoreSide(competitorA, ctx);
      const scoreB = scoreSide(competitorB, ctx);

      const indexA = indexById.get(aId) ?? 0;
      const indexB = indexById.get(bId) ?? 0;
      // Exact tie: the better seed (lower index, since index 0 is the
      // 1-seed) wins - deterministic, consumes no extra draw.
      const aWins = scoreA.total !== scoreB.total ? scoreA.total > scoreB.total : indexA < indexB;

      const winner = aWins ? competitorA : competitorB;
      const loser = aWins ? competitorB : competitorA;
      const upset = winner.baseScore < loser.baseScore;

      const finalScoreA = { ...scoreA, upset: aWins ? upset : false };
      const finalScoreB = { ...scoreB, upset: aWins ? false : upset };

      const result: MatchResult = {
        matchId,
        round: match.round,
        aId,
        bId,
        scoreA: finalScoreA,
        scoreB: finalScoreB,
        winnerId: winner.id,
        loserId: loser.id,
        margin: Math.abs(scoreA.total - scoreB.total),
      };
      results.push(result);

      if (match.next) {
        const { matchId: nextMatchId, slot } = match.next;
        matches = {
          ...matches,
          [nextMatchId]: { ...matches[nextMatchId], [slot]: winner.id },
        };
      }
    }
  }

  const finalResult = results.find((r) => r.matchId === bracket.finalMatchId);
  if (!finalResult) {
    throw new Error('simulateTournament: no result produced for the final match');
  }

  return {
    seed,
    bracket: { ...bracket, matches },
    config,
    results,
    championId: finalResult.winnerId,
    runnerUpId: finalResult.loserId,
  };
}
