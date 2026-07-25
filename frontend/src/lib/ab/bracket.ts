// Pure bracket-structure builder for the A/B résumé tournament. No React, no DOM.

import type { Bracket, BracketSize, Competitor, Match, Round } from './types';

const ROUND_NAMES_FROM_FINAL = ['Final', 'Semifinals', 'Quarterfinals', 'Round of 16'];

/**
 * Standard recursive slot order — no byes, guarantees the 1-seed and 2-seed
 * can only meet in the final.
 *   seedOrder(2)  = [1, 2]
 *   seedOrder(2n) = seedOrder(n).flatMap(s => [s, 2n + 1 - s])
 */
export function seedOrder(size: BracketSize): number[] {
  return seedOrderRec(size);
}

// Recursion bottoms out at size 2, which isn't itself a valid public
// `BracketSize` - kept as a plain-number helper so the public signature
// never needs an unsafe cast.
function seedOrderRec(size: number): number[] {
  if (size === 2) return [1, 2];
  const half = seedOrderRec(size / 2);
  return half.flatMap((s) => [s, size + 1 - s]);
}

function roundNameFor(roundIndex: number, totalRounds: number): string {
  const distanceFromFinal = totalRounds - 1 - roundIndex;
  return ROUND_NAMES_FROM_FINAL[distanceFromFinal];
}

function sortCompetitorsBySeed(competitors: Competitor[]): Competitor[] {
  return [...competitors].sort((a, b) => {
    if (b.baseScore !== a.baseScore) return b.baseScore - a.baseScore;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}

/**
 * Builds round 0 matches from the seed order, and empty-shelled matches for
 * every later round. `next` links are assigned in a second pass since a
 * match's `next` target depends on matches in the following round already
 * existing.
 */
function buildEmptyMatches(
  size: BracketSize,
  totalRounds: number,
): Record<string, Match> {
  const matches: Record<string, Match> = {};
  for (let round = 0; round < totalRounds; round++) {
    const matchesInRound = size / 2 ** (round + 1);
    for (let index = 0; index < matchesInRound; index++) {
      const id = `r${round}-m${index}`;
      const side: 'left' | 'right' =
        round === 0 ? (index < size / 4 ? 'left' : 'right') : 'left'; // placeholder; resolved below for round 0, inherited for later rounds
      matches[id] = {
        id,
        round,
        index,
        side,
        a: null,
        b: null,
        next: null,
      };
    }
  }
  return matches;
}

function linkMatchesAndAssignSides(
  matches: Record<string, Match>,
  size: BracketSize,
  totalRounds: number,
): void {
  for (let round = 0; round < totalRounds - 1; round++) {
    const matchesInRound = size / 2 ** (round + 1);
    for (let index = 0; index < matchesInRound; index++) {
      const match = matches[`r${round}-m${index}`];
      const nextIndex = Math.floor(index / 2);
      const slot: 'a' | 'b' = index % 2 === 0 ? 'a' : 'b';
      const nextId = `r${round + 1}-m${nextIndex}`;
      matches[match.id] = { ...match, next: { matchId: nextId, slot } };
      // The next round's match inherits this feeder's side (both feeders of
      // a given later-round match always share the same side).
      const nextMatch = matches[nextId];
      matches[nextId] = { ...nextMatch, side: match.side };
    }
  }
}

function fillRoundZeroCompetitors(
  matches: Record<string, Match>,
  sortedCompetitors: Competitor[],
  size: BracketSize,
): void {
  const order = seedOrder(size);
  const matchCount = size / 2;
  for (let m = 0; m < matchCount; m++) {
    const seedA = order[2 * m];
    const seedB = order[2 * m + 1];
    const idA = sortedCompetitors[seedA - 1].id;
    const idB = sortedCompetitors[seedB - 1].id;
    const id = `r0-m${m}`;
    matches[id] = { ...matches[id], a: idA, b: idB };
  }
}

function buildRounds(
  matches: Record<string, Match>,
  size: BracketSize,
  totalRounds: number,
): Round[] {
  return Array.from({ length: totalRounds }, (_, round) => {
    const matchesInRound = size / 2 ** (round + 1);
    const matchIds = Array.from(
      { length: matchesInRound },
      (_, index) => `r${round}-m${index}`,
    );
    return {
      index: round,
      name: roundNameFor(round, totalRounds),
      matchIds,
    };
  });
}

export function buildBracket(competitors: Competitor[], size: BracketSize): Bracket {
  if (competitors.length !== size) {
    throw new Error(
      `buildBracket: competitors.length (${competitors.length}) !== size (${size})`,
    );
  }

  const sortedCompetitors = sortCompetitorsBySeed(competitors).map((c) => ({
    ...c,
    traits: { ...c.traits },
  }));

  const totalRounds = Math.log2(size);
  const matches = buildEmptyMatches(size, totalRounds);
  linkMatchesAndAssignSides(matches, size, totalRounds);
  fillRoundZeroCompetitors(matches, sortedCompetitors, size);

  const rounds = buildRounds(matches, size, totalRounds);
  const finalRound = rounds[rounds.length - 1];
  const finalMatchId = finalRound.matchIds[0];

  return {
    size,
    competitors: sortedCompetitors,
    rounds,
    matches,
    finalMatchId,
  };
}
