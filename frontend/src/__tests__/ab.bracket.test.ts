import { describe, it, expect } from 'vitest';
import { seedOrder, buildBracket } from '../lib/ab/bracket';
import type { Competitor, BracketSize } from '../lib/ab/types';

function makeCompetitors(n: number): Competitor[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `c${i}`,
    label: `C${i}`,
    origin: 'fixture' as const,
    baseScore: 100 - i,
    traits: {},
  }));
}

describe('seedOrder', () => {
  it('matches the known literal for size 4', () => {
    expect(seedOrder(4)).toEqual([1, 4, 2, 3]);
  });

  it('matches the known literal for size 8', () => {
    expect(seedOrder(8)).toEqual([1, 8, 4, 5, 2, 7, 3, 6]);
  });

  it('matches the known prefix for size 16', () => {
    expect(seedOrder(16).slice(0, 4)).toEqual([1, 16, 8, 9]);
  });

  it.each([4, 8, 16] as BracketSize[])(
    'contains every seed 1..%s exactly once',
    (size) => {
      const order = seedOrder(size);
      const sorted = [...order].sort((a, b) => a - b);
      expect(sorted).toEqual(Array.from({ length: size }, (_, i) => i + 1));
    },
  );
});

describe('buildBracket', () => {
  it('throws when competitors.length !== size', () => {
    const competitors = makeCompetitors(3);
    expect(() => buildBracket(competitors, 4)).toThrow();
  });

  it.each([4, 8, 16] as BracketSize[])(
    'builds log2(size) rounds with the correct match count per round for size %s',
    (size) => {
      const competitors = makeCompetitors(size);
      const bracket = buildBracket(competitors, size);
      const totalRounds = Math.log2(size);
      expect(bracket.rounds).toHaveLength(totalRounds);
      bracket.rounds.forEach((round, r) => {
        expect(round.matchIds).toHaveLength(size / 2 ** (r + 1));
      });
    },
  );

  it('sorts competitors descending by baseScore, ties broken by id ascending, seed 1 at index 0', () => {
    const competitors: Competitor[] = [
      { id: 'z', label: 'Z', origin: 'fixture', baseScore: 50, traits: {} },
      { id: 'a', label: 'A', origin: 'fixture', baseScore: 90, traits: {} },
      { id: 'm', label: 'M', origin: 'fixture', baseScore: 50, traits: {} },
      { id: 'b', label: 'B', origin: 'fixture', baseScore: 10, traits: {} },
    ];
    const bracket = buildBracket(competitors, 4);
    expect(bracket.competitors.map((c) => c.id)).toEqual(['a', 'm', 'z', 'b']);
  });

  it('does not mutate the input competitors array', () => {
    const competitors = makeCompetitors(4);
    const original = JSON.parse(JSON.stringify(competitors));
    buildBracket(competitors, 4);
    expect(competitors).toEqual(original);
  });

  it('fills round-0 match a/b with competitor ids per seedOrder pairing', () => {
    const competitors = makeCompetitors(4);
    const bracket = buildBracket(competitors, 4);
    // seedOrder(4) = [1,4,2,3] -> match0: seed1 vs seed4, match1: seed2 vs seed3
    const seed1 = bracket.competitors[0].id;
    const seed2 = bracket.competitors[1].id;
    const seed3 = bracket.competitors[2].id;
    const seed4 = bracket.competitors[3].id;
    const m0 = bracket.matches['r0-m0'];
    const m1 = bracket.matches['r0-m1'];
    expect([m0.a, m0.b]).toEqual([seed1, seed4]);
    expect([m1.a, m1.b]).toEqual([seed2, seed3]);
  });

  it('leaves round-1+ matches with null a/b', () => {
    const competitors = makeCompetitors(8);
    const bracket = buildBracket(competitors, 8);
    Object.values(bracket.matches)
      .filter((m) => m.round > 0)
      .forEach((m) => {
        expect(m.a).toBeNull();
        expect(m.b).toBeNull();
      });
  });

  it.each([4, 8, 16] as BracketSize[])(
    'every non-final match next points at an existing match id (size %s)',
    (size) => {
      const competitors = makeCompetitors(size);
      const bracket = buildBracket(competitors, size);
      Object.values(bracket.matches).forEach((m) => {
        if (m.next !== null) {
          expect(bracket.matches[m.next.matchId]).toBeDefined();
        }
      });
    },
  );

  it.each([4, 8, 16] as BracketSize[])(
    'exactly one match has next === null, and its id is finalMatchId (size %s)',
    (size) => {
      const competitors = makeCompetitors(size);
      const bracket = buildBracket(competitors, size);
      const nullNextMatches = Object.values(bracket.matches).filter(
        (m) => m.next === null,
      );
      expect(nullNextMatches).toHaveLength(1);
      expect(nullNextMatches[0].id).toBe(bracket.finalMatchId);
    },
  );

  it.each([4, 8, 16] as BracketSize[])(
    'each round r+1 match is the target of exactly two feeders, one per slot (size %s)',
    (size) => {
      const competitors = makeCompetitors(size);
      const bracket = buildBracket(competitors, size);
      const totalRounds = Math.log2(size);
      for (let r = 0; r < totalRounds - 1; r++) {
        const roundMatches = Object.values(bracket.matches).filter(
          (m) => m.round === r,
        );
        const targets: Record<string, ('a' | 'b')[]> = {};
        roundMatches.forEach((m) => {
          expect(m.next).not.toBeNull();
          const next = m.next as { matchId: string; slot: 'a' | 'b' };
          if (!targets[next.matchId]) targets[next.matchId] = [];
          targets[next.matchId].push(next.slot);
        });
        Object.values(targets).forEach((slots) => {
          expect(slots.sort()).toEqual(['a', 'b']);
        });
        // every round-(r+1) match must appear as a target
        const nextRoundMatches = Object.values(bracket.matches).filter(
          (m) => m.round === r + 1,
        );
        expect(Object.keys(targets).sort()).toEqual(
          nextRoundMatches.map((m) => m.id).sort(),
        );
      }
    },
  );

  it('splits round-0 matches evenly left/right per the side rule for size 4', () => {
    const competitors = makeCompetitors(4);
    const bracket = buildBracket(competitors, 4);
    expect(bracket.matches['r0-m0'].side).toBe('left');
    expect(bracket.matches['r0-m1'].side).toBe('right');
  });

  it('splits round-0 matches evenly left/right per the side rule for size 8', () => {
    const competitors = makeCompetitors(8);
    const bracket = buildBracket(competitors, 8);
    const round0 = Object.values(bracket.matches).filter((m) => m.round === 0);
    const leftCount = round0.filter((m) => m.side === 'left').length;
    const rightCount = round0.filter((m) => m.side === 'right').length;
    expect(leftCount).toBe(2);
    expect(rightCount).toBe(2);
    round0.forEach((m) => {
      expect(m.side).toBe(m.index < 2 ? 'left' : 'right');
    });
  });

  it('later rounds inherit the side of their feeders', () => {
    const competitors = makeCompetitors(8);
    const bracket = buildBracket(competitors, 8);
    Object.values(bracket.matches)
      .filter((m) => m.round === 0 && m.next !== null)
      .forEach((m) => {
        const next = m.next as { matchId: string; slot: 'a' | 'b' };
        const target = bracket.matches[next.matchId];
        if (target.round < Math.log2(8) - 1) {
          expect(target.side).toBe(m.side);
        }
      });
  });

  it('names rounds correctly for size 4', () => {
    const competitors = makeCompetitors(4);
    const bracket = buildBracket(competitors, 4);
    expect(bracket.rounds.map((r) => r.name)).toEqual(['Semifinals', 'Final']);
  });

  it('names rounds correctly for size 8', () => {
    const competitors = makeCompetitors(8);
    const bracket = buildBracket(competitors, 8);
    expect(bracket.rounds.map((r) => r.name)).toEqual([
      'Quarterfinals',
      'Semifinals',
      'Final',
    ]);
  });

  it('names the earliest round "Round of 16" for size 16', () => {
    const competitors = makeCompetitors(16);
    const bracket = buildBracket(competitors, 16);
    expect(bracket.rounds.map((r) => r.name)).toEqual([
      'Round of 16',
      'Quarterfinals',
      'Semifinals',
      'Final',
    ]);
  });

  it('assigns match ids as r{round}-m{index}, 0-indexed', () => {
    const competitors = makeCompetitors(4);
    const bracket = buildBracket(competitors, 4);
    Object.values(bracket.matches).forEach((m) => {
      expect(m.id).toBe(`r${m.round}-m${m.index}`);
    });
  });
});
