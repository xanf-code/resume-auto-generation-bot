import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { BracketCanvas } from '../components/abtest/BracketCanvas';
import { buildBracket } from '../lib/ab/bracket';
import { simulateTournament } from '../lib/ab/simulate';
import { DEFAULT_AB_CONFIG } from '../lib/ab/config';
import { bracketGeometry } from '../lib/ab/layout';
import type { Competitor, MatchResult } from '../lib/ab/types';

function makeFixtureCompetitors(n: number): Competitor[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `c${i}`,
    label: `Competitor ${i}`,
    origin: 'fixture' as const,
    baseScore: 95 - i * 5,
    traits: {},
  }));
}

function buildResolvedTournament() {
  const bracket = buildBracket(makeFixtureCompetitors(8), 8);
  const tournament = simulateTournament(bracket, 'seed-x', DEFAULT_AB_CONFIG);
  const resolved = Object.fromEntries(
    tournament.results.map((r) => [r.matchId, r]),
  ) as Record<string, MatchResult>;
  return { bracket: tournament.bracket, resolved };
}

describe('BracketCanvas', () => {
  it('renders all competitor labels and one CompetitorSlot per match in the desktop tree', () => {
    const { bracket, resolved } = buildResolvedTournament();
    render(
      <BracketCanvas
        bracket={bracket}
        resolved={resolved}
        activeRound={0}
        onActiveRoundChange={vi.fn()}
      />,
    );

    // A competitor's label can legitimately appear in more than one slot (it
    // shows again in every later round it advanced to), so assert presence
    // via getAllByText rather than the single-match getByText.
    const desktop = screen.getByTestId('bracket-desktop');
    for (const competitor of bracket.competitors) {
      expect(within(desktop).getAllByText(competitor.label).length).toBeGreaterThan(0);
    }

    const slots = desktop.querySelectorAll('[data-match-id]');
    expect(slots).toHaveLength(bracket.size - 1);
  });

  it('renders one connector path per non-final match in the desktop tree', () => {
    const { bracket, resolved } = buildResolvedTournament();
    render(
      <BracketCanvas
        bracket={bracket}
        resolved={resolved}
        activeRound={0}
        onActiveRoundChange={vi.fn()}
      />,
    );

    const desktop = screen.getByTestId('bracket-desktop');
    const expectedConnectors = bracketGeometry(bracket.size).connectors.length;
    expect(expectedConnectors).toBe(6); // size 8: size - 2 connectors
    const paths = desktop.querySelectorAll('path');
    expect(paths).toHaveLength(expectedConnectors);
  });

  it('marks the desktop canvas wrapper data-dimmed="true" when dimmed is passed', () => {
    const { bracket, resolved } = buildResolvedTournament();
    render(
      <BracketCanvas
        bracket={bracket}
        resolved={resolved}
        activeRound={0}
        onActiveRoundChange={vi.fn()}
        dimmed
      />,
    );

    const desktop = screen.getByTestId('bracket-desktop');
    const canvasWrapper = desktop.querySelector('[data-dimmed]');
    expect(canvasWrapper).toHaveAttribute('data-dimmed', 'true');
  });

  it('marks the desktop canvas wrapper data-dimmed="false" when dimmed is omitted', () => {
    const { bracket, resolved } = buildResolvedTournament();
    render(
      <BracketCanvas
        bracket={bracket}
        resolved={resolved}
        activeRound={0}
        onActiveRoundChange={vi.fn()}
      />,
    );

    const desktop = screen.getByTestId('bracket-desktop');
    const canvasWrapper = desktop.querySelector('[data-dimmed]');
    expect(canvasWrapper).toHaveAttribute('data-dimmed', 'false');
  });

  it('renders the em-dash placeholder (not a score) for a round-0 match whose result is omitted', () => {
    // Both competitors of a round-0 match are already known (buildBracket
    // fills round 0's a/b directly), so per the derivation rules an
    // unresolved round-0 match is 'idle' (not 'pending' - that's reserved for
    // an as-yet-unfed later-round slot whose a/b is still null). The
    // observable, unambiguous signal that this match hasn't been decided is
    // that both sides show the score placeholder instead of a number.
    const { bracket, resolved } = buildResolvedTournament();
    const round0FirstMatchId = bracket.rounds[0].matchIds[0];
    const partiallyResolved = { ...resolved };
    delete partiallyResolved[round0FirstMatchId];

    render(
      <BracketCanvas
        bracket={bracket}
        resolved={partiallyResolved}
        activeRound={0}
        onActiveRoundChange={vi.fn()}
      />,
    );

    const desktop = screen.getByTestId('bracket-desktop');
    const slot = desktop.querySelector(`[data-match-id="${round0FirstMatchId}"]`);
    expect(slot).not.toBeNull();
    expect(within(slot as HTMLElement).getAllByText('—')).toHaveLength(2);
    expect(slot!.querySelectorAll('[data-state="won"], [data-state="lost"]')).toHaveLength(0);
  });

  it('mobile tree with activeRound=0 shows only round-0 matches and no connector paths', () => {
    const { bracket, resolved } = buildResolvedTournament();
    render(
      <BracketCanvas
        bracket={bracket}
        resolved={resolved}
        activeRound={0}
        onActiveRoundChange={vi.fn()}
      />,
    );

    const mobile = screen.getByTestId('bracket-mobile');
    const slots = mobile.querySelectorAll('[data-match-id]');
    const round0MatchCount = bracket.rounds[0].matchIds.length;
    expect(slots).toHaveLength(round0MatchCount);

    const paths = mobile.querySelectorAll('path');
    expect(paths).toHaveLength(0);
  });
});
