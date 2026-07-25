import { PersonaCard } from './PersonaCard';
import { AggregateGauge } from './AggregateGauge';
import type { PersonaScore } from '../../api/types';

interface Props {
  personaScores: Record<string, PersonaScore>;
  aggregateScore?: number;
  passed?: boolean;
}

export function RecruiterPanel({ personaScores, aggregateScore, passed }: Props) {
  const scores = Object.values(personaScores);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-6 border border-rule bg-paper-raised rounded-[3px] p-5">
        <AggregateGauge score={aggregateScore} />
        <div className="flex flex-col gap-1">
          <span className="eyebrow">The Panel</span>
          <span className="font-serif text-[17px] text-ink leading-snug">
            {scores.length > 0
              ? `${scores.length} recruiters weighing in`
              : 'Awaiting first read'}
          </span>
          {passed !== undefined && (
            <span
              className="mt-1 font-sans text-[13px] font-medium uppercase tracking-wider"
              style={{ color: passed ? 'var(--color-pass)' : 'var(--color-fail)' }}
            >
              {passed ? 'Clears the bar' : 'Below the bar'}
            </span>
          )}
        </div>
      </div>
      {scores.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {scores.map((s) => (
            <PersonaCard key={s.persona} score={s} />
          ))}
        </div>
      )}
    </div>
  );
}
