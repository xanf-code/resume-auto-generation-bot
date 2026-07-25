import type { BracketSize, Competitor } from '../../lib/ab/types';

interface Props {
  pool: Competitor[]; // full candidate pool (already deduped/padded upstream), NOT filtered to `size`
  size: BracketSize; // how many the user must select
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}

const ORIGIN_COLOR: Record<Competitor['origin'], string> = {
  job: 'text-accent',
  fixture: 'text-ink-faint',
};

/** Same tie-break as `roster.ts`'s internal sort: baseScore desc, id asc. */
function byBaseScoreDescThenIdAsc(a: Competitor, b: Competitor): number {
  if (b.baseScore !== a.baseScore) return b.baseScore - a.baseScore;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

export function RosterPicker({ pool, size, selectedIds, onChange }: Props) {
  const toggle = (id: string) => {
    const isSelected = selectedIds.includes(id);
    if (isSelected) {
      onChange(selectedIds.filter((selectedId) => selectedId !== id));
      return;
    }
    // Cap the selection at `size`: ignore clicks on unselected rows once full,
    // rather than growing past the bracket size.
    if (selectedIds.length >= size) return;
    onChange([...selectedIds, id]);
  };

  const selectTopN = () => {
    const top = [...pool].sort(byBaseScoreDescThenIdAsc).slice(0, size);
    onChange(top.map((competitor) => competitor.id));
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <span
          data-testid="roster-counter"
          className="font-mono text-[12px] tabular-nums text-ink-soft"
        >
          {selectedIds.length} of {size}
        </span>
        <button
          type="button"
          onClick={selectTopN}
          className="font-mono text-[10px] uppercase tracking-wider text-accent hover:text-accent-deep px-2 py-1 border border-rule rounded-[2px] transition-colors"
        >
          Select top {size}
        </button>
      </div>

      <div className="border border-rule rounded-[2px] max-h-72 overflow-y-auto bg-paper-raised">
        {pool.map((competitor) => {
          const checked = selectedIds.includes(competitor.id);
          const disabled = !checked && selectedIds.length >= size;
          return (
            <label
              key={competitor.id}
              htmlFor={`roster-${competitor.id}`}
              data-testid={`roster-row-${competitor.id}`}
              className={`flex items-center gap-3 px-3 py-2 border-b border-rule last:border-b-0 select-none ${
                disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
              }`}
            >
              <input
                id={`roster-${competitor.id}`}
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={() => toggle(competitor.id)}
                className="shrink-0 accent-accent"
              />
              <span
                data-testid={`origin-${competitor.id}`}
                className={`font-mono text-[10px] uppercase tracking-wider shrink-0 ${ORIGIN_COLOR[competitor.origin]}`}
              >
                {competitor.origin}
              </span>
              <span className="font-serif text-[14px] text-ink flex-1 min-w-0 truncate">
                {competitor.label}
              </span>
              <span className="font-mono text-[12px] tabular-nums text-ink-soft shrink-0">
                {competitor.baseScore}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
