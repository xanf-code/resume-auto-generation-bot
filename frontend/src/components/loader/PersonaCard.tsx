import { passColor, personaAverage } from '../../lib/scoring';
import type { PersonaScore } from '../../api/types';

interface Props {
  score: PersonaScore;
}

const METRICS: { key: keyof PersonaScore; label: string }[] = [
  { key: 'keyword_match', label: 'Keywords' },
  { key: 'impact_quality', label: 'Impact' },
  { key: 'coherence', label: 'Coherence' },
  { key: 'plausibility', label: 'Plausibility' },
  { key: 'formatting', label: 'Format' },
];

export function PersonaCard({ score }: Props) {
  const avg = personaAverage(score);
  const color = passColor(avg);

  return (
    <div className="border border-rule bg-paper-raised rounded-[3px] p-4">
      <div className="flex items-baseline justify-between mb-3 pb-3 border-b border-rule">
        <span className="font-serif text-[15px] text-ink">{score.persona}</span>
        <span className="font-mono text-[15px] tabular-nums" style={{ color }}>
          {avg.toFixed(0)}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-5 gap-y-1.5">
        {METRICS.map((m) => (
          <div key={m.key} className="flex items-baseline justify-between">
            <dt className="text-[12px] text-ink-faint">{m.label}</dt>
            <dd className="font-mono text-[12px] text-ink-soft tabular-nums">
              {score[m.key] as number}
            </dd>
          </div>
        ))}
      </dl>
      {score.notes && (
        <p className="mt-3 pt-3 border-t border-rule font-serif italic text-[13px] leading-relaxed text-ink-soft">
          {score.notes}
        </p>
      )}
    </div>
  );
}
