import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { SpotlightHud } from '../components/abtest/SpotlightHud';
import type { Competitor, MatchScore } from '../lib/ab/types';

type SpotlightHudProps = Parameters<typeof SpotlightHud>[0];

const competitorA: Competitor = {
  id: 'comp-a',
  label: 'Alice — Backend Engineer',
  origin: 'fixture',
  baseScore: 72,
  traits: {},
};

const competitorB: Competitor = {
  id: 'comp-b',
  label: 'Bob — Backend Engineer',
  origin: 'fixture',
  baseScore: 65,
  traits: {},
};

const scoreA: MatchScore = {
  competitorId: competitorA.id,
  total: 82.5,
  verdicts: [
    { judge: 'ats', score: 85 },
    { judge: 'hiring_manager', score: 80 },
    { judge: 'technical', score: 82 },
  ],
  upset: false,
};

const scoreB: MatchScore = {
  competitorId: competitorB.id,
  total: 70.1,
  verdicts: [
    { judge: 'ats', score: 68 },
    { judge: 'hiring_manager', score: 71 },
    { judge: 'technical', score: 72 },
  ],
  upset: false,
};

const judges: SpotlightHudProps['judges'] = ['ats', 'hiring_manager', 'technical'];

function renderHud(overrides: Partial<SpotlightHudProps> = {}) {
  return render(
    <SpotlightHud
      open
      a={competitorA}
      b={competitorB}
      scoreA={scoreA}
      scoreB={scoreB}
      animate={false}
      blindJudging={false}
      judges={judges}
      {...overrides}
    />,
  );
}

describe('SpotlightHud', () => {
  it('shows both competitor labels when not blind and no outcome yet', () => {
    renderHud();
    expect(screen.getByText(competitorA.label)).toBeInTheDocument();
    expect(screen.getByText(competitorB.label)).toBeInTheDocument();
  });

  it('renders one verdict row per configured judge for each side', () => {
    const { container } = renderHud();
    const sides = container.querySelectorAll('[data-outcome]');
    expect(sides).toHaveLength(2);

    expect(sides[0].querySelectorAll('li')).toHaveLength(scoreA.verdicts.length);
    expect(sides[1].querySelectorAll('li')).toHaveLength(scoreB.verdicts.length);

    const sideA = within(sides[0] as HTMLElement);
    const sideB = within(sides[1] as HTMLElement);

    expect(sideA.getByText('ATS Scanner')).toBeInTheDocument();
    expect(sideA.getByText('Hiring Manager')).toBeInTheDocument();
    expect(sideA.getByText('Technical Lead')).toBeInTheDocument();

    expect(sideB.getByText('ATS Scanner')).toBeInTheDocument();
    expect(sideB.getByText('Hiring Manager')).toBeInTheDocument();
    expect(sideB.getByText('Technical Lead')).toBeInTheDocument();
  });

  it('masks real labels behind a placeholder under blind judging, then reveals them once the verdict lands', () => {
    const { rerender } = render(
      <SpotlightHud
        open
        a={competitorA}
        b={competitorB}
        scoreA={scoreA}
        scoreB={scoreB}
        animate={false}
        blindJudging
        judges={judges}
      />,
    );

    expect(screen.queryByText(competitorA.label)).not.toBeInTheDocument();
    expect(screen.queryByText(competitorB.label)).not.toBeInTheDocument();
    expect(screen.getAllByText('Candidate')).toHaveLength(2);

    rerender(
      <SpotlightHud
        open
        a={competitorA}
        b={competitorB}
        scoreA={scoreA}
        scoreB={scoreB}
        animate={false}
        blindJudging
        judges={judges}
        outcome={{ winnerId: competitorA.id, loserId: competitorB.id }}
      />,
    );

    expect(screen.getByText(competitorA.label)).toBeInTheDocument();
    expect(screen.getByText(competitorB.label)).toBeInTheDocument();
    expect(screen.queryByText('Candidate')).not.toBeInTheDocument();
  });

  it('flags the winning and losing sides via data-outcome once the verdict lands', () => {
    const { container } = renderHud({
      outcome: { winnerId: competitorA.id, loserId: competitorB.id },
    });

    const won = container.querySelector('[data-outcome="won"]');
    const lost = container.querySelector('[data-outcome="lost"]');

    expect(won).not.toBeNull();
    expect(lost).not.toBeNull();
    expect(within(won as HTMLElement).getByText(competitorA.label)).toBeInTheDocument();
    expect(within(lost as HTMLElement).getByText(competitorB.label)).toBeInTheDocument();
  });

  it('renders nothing when closed', () => {
    const { container } = renderHud({ open: false });
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a "Deliberating…" placeholder with one row per active judge before a score lands', () => {
    const { container } = renderHud({ scoreA: undefined, scoreB: undefined });

    expect(screen.getAllByText('Deliberating…')).toHaveLength(2);

    const sides = container.querySelectorAll('[data-outcome]');
    expect(sides[0].querySelectorAll('li')).toHaveLength(judges.length);
    expect(sides[1].querySelectorAll('li')).toHaveLength(judges.length);
  });
});
