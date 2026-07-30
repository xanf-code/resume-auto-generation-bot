import { useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  /** The explanatory text shown in the tooltip. */
  text: string;
  /** Field name, woven into the accessible button label ("About <label>"). */
  label: string;
}

interface Pos {
  top: number;
  left: number;
  /** Prefer above the trigger; flip below when there isn't room. */
  place: 'above' | 'below';
}

/**
 * A small "?" affordance that reveals a one-line explanation on hover AND focus,
 * so it works for pointer and keyboard users alike. The tooltip is associated
 * with the trigger via `aria-describedby` and carries `role="tooltip"`.
 *
 * Rendered via portal + fixed positioning so parent overflow (modal panes)
 * cannot clip it.
 */
export function HelpTip({ text, label }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tipRef = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return;
    }

    const update = () => {
      const trigger = triggerRef.current;
      const tip = tipRef.current;
      if (!trigger || !tip) return;

      const rect = trigger.getBoundingClientRect();
      const tipWidth = tip.offsetWidth;
      const tipHeight = tip.offsetHeight;
      const gap = 6;
      const margin = 8;

      let place: Pos['place'] = 'above';
      let top = rect.top - gap;
      if (rect.top - tipHeight - gap < margin) {
        place = 'below';
        top = rect.bottom + gap;
      }

      let left = rect.left + rect.width / 2 - tipWidth / 2;
      left = Math.max(
        margin,
        Math.min(left, window.innerWidth - tipWidth - margin),
      );

      setPos({ top, left, place });
    };

    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [open, text]);

  const transform =
    pos?.place === 'below' ? undefined : 'translateY(-100%)';

  return (
    <span className="relative inline-flex items-center">
      <button
        ref={triggerRef}
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
      {open &&
        createPortal(
          <span
            ref={tipRef}
            role="tooltip"
            id={id}
            style={{
              position: 'fixed',
              top: pos?.top ?? 0,
              left: pos?.left ?? 0,
              transform,
              visibility: pos ? 'visible' : 'hidden',
            }}
            className="z-[200] w-56 max-w-[70vw] bg-ink text-paper text-[11.5px] leading-snug font-sans normal-case tracking-normal px-2.5 py-2 rounded-[3px] shadow-[0_6px_20px_rgba(28,27,25,0.3)] pointer-events-none"
          >
            {text}
          </span>,
          document.body,
        )}
    </span>
  );
}
