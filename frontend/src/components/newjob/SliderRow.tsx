import { useId } from 'react';
import { HelpTip } from './HelpTip';

interface Props {
  label: string;
  help: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  /** Formatted value shown at the right of the row (e.g. "78" or "30%"). */
  valueLabel: string;
}

/**
 * One labelled slider row: eyebrow label + inline HelpTip, a full-width range
 * input on the accent, and a right-aligned value readout. The `<label htmlFor>`
 * ties the visible label to the range so it's reachable via its accessible name.
 */
export function SliderRow({
  label,
  help,
  min,
  max,
  step,
  value,
  onChange,
  valueLabel,
}: Props) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5">
          <label htmlFor={id} className="text-[12px] font-medium text-ink-soft">
            {label}
          </label>
          <HelpTip text={help} label={label} />
        </span>
        <span className="font-mono text-[12px] text-ink tabular-nums">{valueLabel}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={valueLabel}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent h-1.5 cursor-pointer"
      />
    </div>
  );
}
