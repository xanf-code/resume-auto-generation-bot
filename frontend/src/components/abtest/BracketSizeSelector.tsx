import type { BracketSize } from '../../lib/ab/types';

interface Props {
  value: BracketSize;
  onChange: (size: BracketSize) => void;
}

const SIZES: readonly BracketSize[] = [4, 8, 16];

/**
 * Three-way segmented control for bracket size (4 / 8 / 16). Styled like
 * NewJobModal's mobile pane switcher: the active option gets a bottom accent
 * rule, the rest read as soft-ink tabs.
 */
export function BracketSizeSelector({ value, onChange }: Props) {
  return (
    <div
      className="flex border-b border-rule"
      role="radiogroup"
      aria-label="Bracket size"
    >
      {SIZES.map((size) => (
        <button
          key={size}
          type="button"
          role="radio"
          aria-checked={value === size}
          onClick={() => onChange(size)}
          className={`flex-1 text-[13px] py-2.5 transition-colors ${
            value === size
              ? 'text-ink border-b-2 border-accent font-medium'
              : 'text-ink-soft'
          }`}
        >
          {size}
        </button>
      ))}
    </div>
  );
}
