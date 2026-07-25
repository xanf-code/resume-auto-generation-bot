import { describe, it, expect } from 'vitest';
import { buildBracket } from '../lib/ab/bracket';
import { DEFAULT_AB_CONFIG } from '../lib/ab/config';
import { simulateTournament } from '../lib/ab/simulate';
import type { AbConfig, BracketSize, Competitor } from '../lib/ab/types';

function makeCompetitors(n: number): Competitor[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `c${i}`,
    label: `Competitor ${i}`,
    origin: 'fixture' as const,
    baseScore: 95 - i * 5,
    traits: {},
  }));
}

describe('simulateTournament', () => {
  it('is deterministic for the same seed, bracket, and config', () => {
    const size: BracketSize = 8;
    const bracketA = buildBracket(makeCompetitors(size), size);
    const bracketB = buildBracket(makeCompetitors(size), size);
    const config = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.4 };

    const resultA = simulateTournament(bracketA, 'seed-a', config);
    const resultB = simulateTournament(bracketB, 'seed-a', config);

    expect(resultA).toEqual(resultB);
  });

  it('produces different results for a different seed (upsetFactor > 0)', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.4 };

    const resultA = simulateTournament(bracket, 'seed-a', config);
    const resultB = simulateTournament(bracket, 'seed-b', config);

    expect(resultA.results).not.toEqual(resultB.results);
  });

  it('produces size - 1 results ordered by round ascending for a size-8 bracket', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.4 };

    const result = simulateTournament(bracket, 'seed-order', config);

    expect(result.results).toHaveLength(size - 1);
    const rounds = result.results.map((r) => r.round);
    const sortedRounds = [...rounds].sort((a, b) => a - b);
    expect(rounds).toEqual(sortedRounds);
  });

  it("propagates winners: each round > 0 match's aId/bId equal the winnerId of its feeders", () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.4 };

    const result = simulateTournament(bracket, 'seed-propagate', config);
    const resultByMatchId = new Map(result.results.map((r) => [r.matchId, r]));

    for (const match of Object.values(result.bracket.matches)) {
      if (match.round === 0) continue;
      const feeders = Object.values(result.bracket.matches).filter(
        (m) => m.next?.matchId === match.id,
      );
      expect(feeders).toHaveLength(2);
      const feederWinners = feeders.map((feeder) => {
        const feederResult = resultByMatchId.get(feeder.id);
        expect(feederResult).toBeDefined();
        return feederResult!.winnerId;
      });
      expect([match.a, match.b].sort()).toEqual(feederWinners.sort());
    }
  });

  it('championId equals the winnerId of the final match result', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.4 };

    const result = simulateTournament(bracket, 'seed-champion', config);
    const finalResult = result.results.find((r) => r.matchId === bracket.finalMatchId);

    expect(finalResult).toBeDefined();
    expect(result.championId).toBe(finalResult!.winnerId);
    expect(result.runnerUpId).toBe(finalResult!.loserId);
  });

  it('chalk mode (upsetFactor: 0) always advances the 1-seed to champion', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config: AbConfig = { ...DEFAULT_AB_CONFIG, upsetFactor: 0 };

    const result = simulateTournament(bracket, 'seed-chalk', config);
    const topSeedId = bracket.competitors[0].id;

    for (const r of result.results) {
      if (r.aId === topSeedId || r.bId === topSeedId) {
        expect(r.winnerId).toBe(topSeedId);
      }
    }
    expect(result.championId).toBe(topSeedId);
  });

  it('best-of-5 produces strictly fewer upsets than best-of-1 across 50 fixed seeds', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const seeds = Array.from({ length: 50 }, (_, i) => `fixed-${i}`);

    const countUpsets = (bestOf: 1 | 3 | 5): number => {
      const config: AbConfig = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.5, bestOf };
      return seeds.reduce((total, seed) => {
        const result = simulateTournament(bracket, seed, config);
        const upsets = result.results.filter((r) => r.scoreA.upset || r.scoreB.upset).length;
        return total + upsets;
      }, 0);
    };

    const bestOf1Upsets = countUpsets(1);
    const bestOf5Upsets = countUpsets(5);

    expect(bestOf5Upsets).toBeLessThan(bestOf1Upsets);
  });

  it('with a single judge, total equals the sole verdict score', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config: AbConfig = { ...DEFAULT_AB_CONFIG, judges: ['ats'], upsetFactor: 0.3 };

    const result = simulateTournament(bracket, 'seed-single-judge', config);

    for (const r of result.results) {
      expect(r.scoreA.verdicts).toHaveLength(1);
      expect(r.scoreB.verdicts).toHaveLength(1);
      expect(r.scoreA.total).toBe(r.scoreA.verdicts[0].score);
      expect(r.scoreB.total).toBe(r.scoreB.verdicts[0].score);
    }
  });

  it('keeps every total within [0, 100]', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config: AbConfig = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.6 };

    const result = simulateTournament(bracket, 'seed-bounds', config);

    for (const r of result.results) {
      expect(r.scoreA.total).toBeGreaterThanOrEqual(0);
      expect(r.scoreA.total).toBeLessThanOrEqual(100);
      expect(r.scoreB.total).toBeGreaterThanOrEqual(0);
      expect(r.scoreB.total).toBeLessThanOrEqual(100);
    }
  });

  it('marks upset true iff the winner has a lower baseScore than the loser', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const config: AbConfig = { ...DEFAULT_AB_CONFIG, upsetFactor: 0.5 };
    const competitorsById = new Map(bracket.competitors.map((c) => [c.id, c]));

    const result = simulateTournament(bracket, 'seed-upset-check', config);

    for (const r of result.results) {
      const winner = competitorsById.get(r.winnerId)!;
      const loser = competitorsById.get(r.loserId)!;
      const winnerScore = r.scoreA.competitorId === r.winnerId ? r.scoreA : r.scoreB;
      const expectedUpset = winner.baseScore < loser.baseScore;
      expect(winnerScore.upset).toBe(expectedUpset);
    }
  });

  it('changing targetRole changes at least one total, all else equal', () => {
    const size: BracketSize = 8;
    const bracket = buildBracket(makeCompetitors(size), size);
    const backendConfig: AbConfig = { ...DEFAULT_AB_CONFIG, targetRole: 'backend', upsetFactor: 0 };
    const mlConfig: AbConfig = { ...DEFAULT_AB_CONFIG, targetRole: 'ml', upsetFactor: 0 };

    const backendResult = simulateTournament(bracket, 'seed-role', backendConfig);
    const mlResult = simulateTournament(bracket, 'seed-role', mlConfig);

    let sawDifference = false;
    for (let i = 0; i < backendResult.results.length; i++) {
      if (
        backendResult.results[i].scoreA.total !== mlResult.results[i].scoreA.total ||
        backendResult.results[i].scoreB.total !== mlResult.results[i].scoreB.total
      ) {
        sawDifference = true;
        break;
      }
    }
    expect(sawDifference).toBe(true);
  });
});
