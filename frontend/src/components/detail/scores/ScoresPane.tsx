import type { ReactNode } from 'react';
import { PersonaCard } from '../../loader/PersonaCard';
import { AggregateGauge } from '../../loader/AggregateGauge';
import { PanelCollapseButton } from '../../layout/PanelCollapseButton';
import { useStore } from '../../../store';
import { WIDE_MQ, useMediaQuery } from '../../../hooks/useMediaQuery';
import type { PersonaScore } from '../../../api/types';

interface Props {
  personaScores: Record<string, PersonaScore>;
  aggregateScore?: number;
  passed?: boolean;
}

function Shell({ children }: { children: ReactNode }) {
  const toggleScores = useStore((s) => s.toggleScoresSidebar);
  const isWide = useMediaQuery(WIDE_MQ);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-3 py-2.5 border-b border-rule bg-paper shrink-0 flex items-center justify-between gap-2 min-h-11">
        <span className="eyebrow pl-1">Recruiter Scores</span>
        {isWide && (
          <PanelCollapseButton
            direction="right"
            collapsed={false}
            onToggle={toggleScores}
            label="Collapse scores"
          />
        )}
      </div>
      {children}
    </div>
  );
}

/**
 * The recruiter panel's verdict, kept reviewable after the run finishes: an
 * aggregate gauge, a pass/fail read, and one card per persona. Reuses the same
 * gauge and card the live loader shows so the numbers never drift between views.
 */
export function ScoresPane({ personaScores, aggregateScore, passed }: Props) {
  const scores = Object.values(personaScores);

  if (scores.length === 0) {
    return (
      <Shell>
        <div className="flex-1 flex items-center justify-center px-4 text-center">
          <p className="font-serif italic text-[14px] leading-relaxed text-ink-faint">
            Scores will appear here once the analysis is complete.
          </p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-5 border border-rule bg-paper-raised rounded-[3px] p-4">
          <AggregateGauge score={aggregateScore} />
          <div className="flex flex-col gap-1">
            <span className="eyebrow">Result</span>
            <span className="font-serif text-[16px] text-ink leading-snug">
              {scores.length} {scores.length === 1 ? 'recruiter' : 'recruiters'}{' '}
              reviewed
            </span>
            {passed !== undefined && (
              <span
                className="mt-1 font-sans text-[13px] font-medium uppercase tracking-wider"
                style={{ color: passed ? 'var(--color-pass)' : 'var(--color-fail)' }}
              >
                {passed ? 'Passed' : 'Below threshold'}
              </span>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3">
          {scores.map((s) => (
            <PersonaCard key={s.persona} score={s} />
          ))}
        </div>
      </div>
    </Shell>
  );
}
