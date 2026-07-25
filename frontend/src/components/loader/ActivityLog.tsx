import { useEffect, useRef } from 'react';
import type { ActivityEntry } from '../../store/jobsSlice';

interface Props {
  entries: ActivityEntry[];
}

// A terminal-style feed of what the pipeline is actually doing, line by line -
// the control-flow the coarse stepper hides (page-overflow bounces, compile
// failures, panel loops). Auto-scrolls to the newest line as it streams in.
export function ActivityLog({ entries }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' });
  }, [entries.length]);

  if (entries.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <span className="eyebrow">Activity</span>
      <ol
        data-testid="activity-log"
        aria-live="polite"
        className="flex flex-col gap-1 max-h-40 overflow-y-auto border border-rule rounded-[2px] bg-paper-sunk px-3 py-2"
      >
        {entries.map((entry, idx) => {
          const isLatest = idx === entries.length - 1;
          return (
            <li
              key={`${entry.seq}-${idx}`}
              className={`font-mono text-[11px] leading-relaxed flex gap-2 ${
                isLatest ? 'text-ink' : 'text-ink-faint'
              }`}
            >
              <span className="text-accent shrink-0" aria-hidden="true">
                {isLatest ? '▸' : ' '}
              </span>
              <span className="min-w-0">{entry.text}</span>
            </li>
          );
        })}
        <div ref={endRef} />
      </ol>
    </div>
  );
}
