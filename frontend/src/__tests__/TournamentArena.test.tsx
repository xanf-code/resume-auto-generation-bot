import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TournamentArena } from '../components/abtest/TournamentArena';
import { buildBracket } from '../lib/ab/bracket';
import { buildTimeline } from '../lib/ab/timeline';
import { simulateTournament } from '../lib/ab/simulate';
import { DEFAULT_AB_CONFIG } from '../lib/ab/config';
import type { BracketSize, Competitor } from '../lib/ab/types';

function makeCompetitors(n: number): Competitor[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `c${i}`,
    label: `Competitor ${i}`,
    origin: 'fixture' as const,
    baseScore: 95 - i * 5,
    traits: {},
  }));
}

function renderFinishedArena() {
  const size: BracketSize = 4;
  const bracket = buildBracket(makeCompetitors(size), size);
  const result = simulateTournament(bracket, 'seed-arena', DEFAULT_AB_CONFIG);
  const timeline = buildTimeline(result, { reducedMotion: true });

  render(
    <TournamentArena
      result={result}
      timeline={timeline}
      blindJudging={false}
      judges={DEFAULT_AB_CONFIG.judges}
      reducedMotion
      onReplay={vi.fn()}
    />,
  );

  // Jump straight to the champion step rather than waiting on the rAF clock.
  fireEvent.click(screen.getByRole('button', { name: /skip to result/i }));
}

describe('TournamentArena champion card', () => {
  it('shows the champion overlay with a close button once the tournament finishes', () => {
    renderFinishedArena();
    expect(screen.getByTestId('champion-overlay')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /close champion card/i })).toBeInTheDocument();
  });

  it('dismisses the overlay on close, revealing the bracket, and can be reopened', () => {
    renderFinishedArena();

    fireEvent.click(screen.getByRole('button', { name: /close champion card/i }));
    expect(screen.queryByTestId('champion-overlay')).not.toBeInTheDocument();

    const reopen = screen.getByRole('button', { name: /show champion card/i });
    expect(reopen).toBeInTheDocument();

    fireEvent.click(reopen);
    expect(screen.getByTestId('champion-overlay')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /show champion card/i })).not.toBeInTheDocument();
  });
});
