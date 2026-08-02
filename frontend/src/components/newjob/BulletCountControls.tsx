import {
  BULLET_COUNT_MAX,
  BULLET_COUNT_MIN,
  DEFAULT_BULLET_COUNTS,
  ROLE_LABELS,
  setCount,
} from '../../lib/bulletCounts';

interface Props {
  counts: [number, number];
  onChange: (counts: [number, number]) => void;
}

export function BulletCountControls({ counts, onChange }: Props) {
  return (
    <div data-testid="bullet-count-controls" className="flex flex-col gap-2.5">
      <span className="eyebrow">Bullets per role</span>
      <p className="text-[12px] text-ink-soft leading-snug">
        Default is {DEFAULT_BULLET_COUNTS[0]} for each. Range {BULLET_COUNT_MIN}–{BULLET_COUNT_MAX}.
      </p>
      {([0, 1] as const).map((idx) => (
        <div key={idx} className="flex items-center justify-between gap-3">
          <span className="text-[13px] text-ink-soft">{ROLE_LABELS[idx]}</span>
          <div className="flex items-center gap-0 border border-rule rounded-[3px] overflow-hidden">
            <button
              type="button"
              aria-label={`Decrease bullets for ${ROLE_LABELS[idx]}`}
              disabled={counts[idx] <= BULLET_COUNT_MIN}
              onClick={() => onChange(setCount(counts, idx, counts[idx] - 1))}
              className="w-7 h-7 flex items-center justify-center text-[14px] font-mono text-ink-soft hover:text-ink hover:bg-paper-sunk disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              −
            </button>
            <span
              data-testid={`bullet-count-value-${idx}`}
              className="w-6 text-center text-[13px] font-mono tabular-nums text-ink select-none"
            >
              {counts[idx]}
            </span>
            <button
              type="button"
              aria-label={`Increase bullets for ${ROLE_LABELS[idx]}`}
              disabled={counts[idx] >= BULLET_COUNT_MAX}
              onClick={() => onChange(setCount(counts, idx, counts[idx] + 1))}
              className="w-7 h-7 flex items-center justify-center text-[14px] font-mono text-ink-soft hover:text-ink hover:bg-paper-sunk disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              +
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
