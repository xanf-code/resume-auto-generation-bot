import type { ActivityEntry } from '../../store/jobsSlice';

interface Props {
  entries: ActivityEntry[];
}

// A fixed-height viewport that shows the last few activity lines. As new lines
// arrive the inner list is translated upward so the newest sits at the bottom -
// older lines slide up and out. The container height never changes, so the feed
// scrolls naturally instead of pushing the panel below it down the page.
const ROW_H = 22; // px per line - must match the row height/lineHeight below
const VISIBLE = 3; // lines shown in the fixed window
const PAD_Y = 16; // px-3 py-2 → 8px top + 8px bottom

export function ActivityLog({ entries }: Props) {
  if (entries.length === 0) return null;

  // Shift the list up by however many rows have scrolled past the top of the
  // window. Zero while the log still fits, so early lines simply fill in place.
  const offset = Math.max(0, entries.length - VISIBLE);

  return (
    <div className="flex flex-col gap-2">
      <span className="eyebrow">Activity</span>
      <div
        data-testid="activity-log"
        aria-live="polite"
        className="relative overflow-hidden border border-rule rounded-[2px] bg-paper-sunk px-3 py-2"
        style={{ height: VISIBLE * ROW_H + PAD_Y }}
      >
        {/* Dissolve lines into the paper as they scroll off the top edge. */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-10"
          style={{
            height: ROW_H,
            background: 'linear-gradient(to bottom, var(--color-paper-sunk), transparent)',
          }}
        />
        <ol
          className="transition-transform duration-500 ease-out"
          style={{ transform: `translateY(${-offset * ROW_H}px)` }}
        >
          {entries.map((entry, idx) => {
            const isLatest = idx === entries.length - 1;
            const visible = idx >= offset;
            return (
              <li
                key={`${entry.seq}-${idx}`}
                style={{ height: ROW_H, lineHeight: `${ROW_H}px` }}
                className={`font-mono text-[11px] flex items-center gap-2 transition-opacity duration-500 ${
                  isLatest ? 'text-ink' : visible ? 'text-ink-faint' : 'text-ink-faint/40'
                }`}
              >
                <span className="w-2 shrink-0 text-accent" aria-hidden="true">
                  {isLatest ? '▸' : ''}
                </span>
                <span className="truncate">{entry.text}</span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
