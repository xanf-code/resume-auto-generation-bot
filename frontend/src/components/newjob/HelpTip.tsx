import { useId, useState } from 'react';

interface Props {
  /** The explanatory text shown in the tooltip. */
  text: string;
  /** Field name, woven into the accessible button label ("About <label>"). */
  label: string;
}

/**
 * A small "?" affordance that reveals a one-line explanation on hover AND focus,
 * so it works for pointer and keyboard users alike. The tooltip is associated
 * with the trigger via `aria-describedby` and carries `role="tooltip"`.
 */
export function HelpTip({ text, label }: Props) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span className="relative inline-flex items-center">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full border border-rule text-ink-faint hover:text-accent hover:border-accent/50 text-[10px] leading-none font-medium transition-colors focus:outline-none focus-visible:border-accent"
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 z-10 w-56 max-w-[70vw] bg-ink text-paper text-[11.5px] leading-snug font-sans normal-case tracking-normal px-2.5 py-2 rounded-[3px] shadow-[0_6px_20px_rgba(28,27,25,0.3)] pointer-events-none"
        >
          {text}
        </span>
      )}
    </span>
  );
}
