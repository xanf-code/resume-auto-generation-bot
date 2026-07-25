import { MAX_ITERATIONS } from '../../lib/constants';

interface Props {
  iteration: number;
}

export function IterationCounter({ iteration }: Props) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="eyebrow">Revision</span>
      <span className="font-mono text-[13px] text-ink tabular-nums">
        {String(Math.max(iteration, 1)).padStart(2, '0')}
      </span>
      <span className="font-mono text-[13px] text-ink-faint tabular-nums">
        / {String(MAX_ITERATIONS).padStart(2, '0')}
      </span>
    </div>
  );
}
