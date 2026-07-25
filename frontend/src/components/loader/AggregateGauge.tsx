import { THRESHOLD } from '../../lib/constants';
import { passColor } from '../../lib/scoring';

interface Props {
  score?: number;
}

const RADIUS = 40;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function AggregateGauge({ score }: Props) {
  // Guard non-finite (NaN/Infinity from a malformed frame) and clamp both ends —
  // a negative or >100 score would otherwise sweep the arc past a full turn.
  const hasScore = score !== undefined && Number.isFinite(score);
  const pct = hasScore ? Math.max(0, Math.min(score / 100, 1)) : 0;
  const offset = CIRCUMFERENCE * (1 - pct);
  const color = hasScore ? passColor(score) : 'var(--color-ink-faint)';

  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg width="104" height="104" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={RADIUS} fill="none" stroke="#e4ddd0" strokeWidth="6" />
        <circle
          cx="48"
          cy="48"
          r={RADIUS}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 48 48)"
          style={{ transition: 'stroke-dashoffset 400ms ease, stroke 200ms ease' }}
        />
        <text
          x="48"
          y="49"
          textAnchor="middle"
          dominantBaseline="central"
          fill={hasScore ? 'var(--color-ink)' : 'var(--color-ink-faint)'}
          fontSize="26"
          fontFamily="Fraunces, Georgia, serif"
          fontWeight="600"
        >
          {hasScore ? Math.round(score) : '—'}
        </text>
      </svg>
      <span className="eyebrow text-[10px]">Min score · {THRESHOLD}</span>
    </div>
  );
}
