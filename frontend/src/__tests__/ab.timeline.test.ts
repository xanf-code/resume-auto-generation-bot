import { describe, it, expect } from 'vitest';
import { buildBracket } from '../lib/ab/bracket';
import { DEFAULT_AB_CONFIG } from '../lib/ab/config';
import { simulateTournament } from '../lib/ab/simulate';
import { buildTimeline, resolvedAt, stepIndexAtMs, REDUCED_STEP_MS } from '../lib/ab/timeline';
import type { BracketSize, Competitor, TournamentResult } from '../lib/ab/types';

function makeCompetitors(n: number): Competitor[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `c${i}`,
    label: `Competitor ${i}`,
    origin: 'fixture' as const,
    baseScore: 95 - i * 5,
    traits: {},
  }));
}

function makeResult(size: BracketSize, seed: string): TournamentResult {
  const bracket = buildBracket(makeCompetitors(size), size);
  return simulateTournament(bracket, seed, DEFAULT_AB_CONFIG);
}

describe('buildTimeline', () => {
  it('produces a full sequence bookended by tournament-intro and champion', () => {
    const result = makeResult(8, 'timeline-seed-1');
    const timeline = buildTimeline(result);

    expect(timeline.steps[0].kind).toBe('tournament-intro');
    expect(timeline.steps[timeline.steps.length - 1].kind).toBe('champion');
  });

  it('has strictly increasing, contiguous startMs with no zero-length steps', () => {
    const result = makeResult(8, 'timeline-seed-2');
    const timeline = buildTimeline(result);

    for (let i = 0; i < timeline.steps.length; i++) {
      expect(timeline.steps[i].durationMs).toBeGreaterThan(0);
      if (i > 0) {
        expect(timeline.steps[i].startMs).toBeGreaterThan(timeline.steps[i - 1].startMs);
      }
      if (i < timeline.steps.length - 1) {
        expect(timeline.steps[i].startMs + timeline.steps[i].durationMs).toBe(
          timeline.steps[i + 1].startMs,
        );
      }
    }

    const last = timeline.steps[timeline.steps.length - 1];
    expect(timeline.totalMs).toBe(last.startMs + last.durationMs);
  });

  it('assigns unique ids across the whole timeline', () => {
    const result = makeResult(8, 'timeline-seed-3');
    const timeline = buildTimeline(result);

    const ids = timeline.steps.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('emits exactly one match-verdict per match, matching the source MatchResult', () => {
    const result = makeResult(8, 'timeline-seed-4');
    const timeline = buildTimeline(result);

    const verdictSteps = timeline.steps.filter((s) => s.kind === 'match-verdict');
    expect(verdictSteps).toHaveLength(result.results.length);

    const resultsByMatchId = new Map(result.results.map((r) => [r.matchId, r]));
    for (const step of verdictSteps) {
      expect(step.matchId).toBeDefined();
      const expected = resultsByMatchId.get(step.matchId!);
      expect(expected).toBeDefined();
      expect(step.result).toBeDefined();
      expect(step.result!.matchId).toBe(expected!.matchId);
      expect(step.result!.winnerId).toBe(expected!.winnerId);
    }
  });

  it('emits exactly one round-intro per round', () => {
    const result = makeResult(8, 'timeline-seed-5');
    const timeline = buildTimeline(result);

    const roundIntroSteps = timeline.steps.filter((s) => s.kind === 'round-intro');
    expect(roundIntroSteps).toHaveLength(result.bracket.rounds.length);
  });

  it('scales round-0 match-score duration down for wider brackets', () => {
    const result16 = makeResult(16, 'pace-seed-16');
    const result4 = makeResult(4, 'pace-seed-4');

    const timeline16 = buildTimeline(result16);
    const timeline4 = buildTimeline(result4);

    const firstMatchScore16 = timeline16.steps.find(
      (s) => s.kind === 'match-score' && s.round === 0,
    );
    const firstMatchScore4 = timeline4.steps.find(
      (s) => s.kind === 'match-score' && s.round === 0,
    );

    expect(firstMatchScore16).toBeDefined();
    expect(firstMatchScore4).toBeDefined();
    expect(firstMatchScore16!.durationMs).toBeLessThan(firstMatchScore4!.durationMs);
  });

  describe('reducedMotion', () => {
    it('drops motion-only steps and flattens durations to REDUCED_STEP_MS', () => {
      const result = makeResult(8, 'reduced-seed-1');
      const timeline = buildTimeline(result, { reducedMotion: true });

      const droppedKinds = new Set(['match-focus', 'match-advance', 'round-outro']);
      for (const step of timeline.steps) {
        expect(droppedKinds.has(step.kind)).toBe(false);
        expect(step.durationMs).toBe(REDUCED_STEP_MS);
      }
    });

    it('still emits a match-verdict for every match', () => {
      const result = makeResult(8, 'reduced-seed-2');
      const timeline = buildTimeline(result, { reducedMotion: true });

      const verdictSteps = timeline.steps.filter((s) => s.kind === 'match-verdict');
      expect(verdictSteps).toHaveLength(result.results.length);
    });
  });

  describe('resolvedAt', () => {
    it('contains exactly the matches whose match-verdict step index is <= stepIndex', () => {
      const result = makeResult(8, 'resolved-seed-1');
      const timeline = buildTimeline(result);

      const verdictSteps = timeline.steps
        .map((step, index) => ({ step, index }))
        .filter(({ step }) => step.kind === 'match-verdict');

      // Pick a verdict step somewhere in the middle of the run.
      const middle = verdictSteps[Math.floor(verdictSteps.length / 2)];
      const resolved = resolvedAt(timeline, middle.index);

      const includedMatchIds = verdictSteps
        .filter(({ index }) => index <= middle.index)
        .map(({ step }) => step.matchId!);
      const excludedMatchIds = verdictSteps
        .filter(({ index }) => index > middle.index)
        .map(({ step }) => step.matchId!);

      expect(includedMatchIds.length).toBeGreaterThan(0);
      expect(excludedMatchIds.length).toBeGreaterThan(0);

      for (const matchId of includedMatchIds) {
        expect(resolved[matchId]).toBeDefined();
      }
      for (const matchId of excludedMatchIds) {
        expect(resolved[matchId]).toBeUndefined();
      }
      expect(Object.keys(resolved)).toHaveLength(includedMatchIds.length);
    });
  });

  describe('stepIndexAtMs', () => {
    it('resolves the boundaries at 0 and totalMs', () => {
      const result = makeResult(8, 'seek-seed-1');
      const timeline = buildTimeline(result);

      expect(stepIndexAtMs(timeline, 0)).toBe(0);
      expect(stepIndexAtMs(timeline, timeline.totalMs)).toBe(timeline.steps.length - 1);
    });
  });
});
