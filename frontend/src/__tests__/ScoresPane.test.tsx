import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ScoresPane } from '../components/detail/scores/ScoresPane';
import type { PersonaScore } from '../api/types';

function makeScore(overrides: Partial<PersonaScore> = {}): PersonaScore {
  return {
    persona: 'Backend Recruiter',
    keyword_match: 80,
    impact_quality: 70,
    coherence: 90,
    plausibility: 85,
    formatting: 75,
    ...overrides,
  };
}

function scoreMap(...scores: PersonaScore[]): Record<string, PersonaScore> {
  return Object.fromEntries(scores.map((s) => [s.persona, s]));
}

describe('ScoresPane', () => {
  it('shows an awaiting-scores message when no personas have weighed in', () => {
    render(<ScoresPane personaScores={{}} />);
    expect(screen.getByText(/appear here/i)).toBeInTheDocument();
    expect(screen.queryByText('Backend Recruiter')).not.toBeInTheDocument();
  });

  it('renders a card for each persona with its name', () => {
    render(
      <ScoresPane
        personaScores={scoreMap(
          makeScore({ persona: 'Backend Recruiter' }),
          makeScore({ persona: 'Hiring Manager' }),
        )}
      />,
    );
    expect(screen.getByText('Backend Recruiter')).toBeInTheDocument();
    expect(screen.getByText('Hiring Manager')).toBeInTheDocument();
  });

  it('renders the aggregate score', () => {
    render(
      <ScoresPane
        personaScores={scoreMap(makeScore())}
        aggregateScore={82.4}
      />,
    );
    expect(screen.getByText('82')).toBeInTheDocument();
  });

  it('shows a passing verdict when passed is true', () => {
    render(
      <ScoresPane
        personaScores={scoreMap(makeScore())}
        aggregateScore={90}
        passed={true}
      />,
    );
    expect(screen.getByText(/passed/i)).toBeInTheDocument();
  });

  it('shows a failing verdict when passed is false', () => {
    render(
      <ScoresPane
        personaScores={scoreMap(makeScore())}
        aggregateScore={40}
        passed={false}
      />,
    );
    expect(screen.getByText(/below threshold/i)).toBeInTheDocument();
  });

  // Notes UI is currently commented out in PersonaCard.
  // it('renders persona notes when present', () => {
  //   render(
  //     <ScoresPane
  //       personaScores={scoreMap(
  //         makeScore({ notes: 'Strong on impact, light on keywords.' }),
  //       )}
  //     />,
  //   );
  //   expect(
  //     screen.getByText('Strong on impact, light on keywords.'),
  //   ).toBeInTheDocument();
  // });
});
