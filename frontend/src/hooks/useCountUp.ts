import { useEffect, useRef, useState } from 'react';

interface UseCountUpOptions {
  enabled?: boolean;
}

/** Cubic ease-out: fast start, gentle landing. */
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Interpolates a number toward `target` over `durationMs` using a single
 * requestAnimationFrame loop and easeOutCubic easing. Restarts from the
 * currently displayed value whenever `target` (or `durationMs`) changes.
 * Pass `{ enabled: false }` to skip animation and jump straight to `target`.
 */
export function useCountUp(
  target: number,
  durationMs: number,
  options?: UseCountUpOptions,
): number {
  const enabled = options?.enabled ?? true;
  const [value, setValue] = useState<number>(() => (enabled ? 0 : target));
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (!enabled) {
      setValue(target);
      return;
    }

    const startValue = valueRef.current;
    const delta = target - startValue;
    const startTime = performance.now();
    let rafId: number;

    const tick = (now: number): void => {
      const elapsed = now - startTime;

      if (elapsed >= durationMs) {
        setValue(target);
        return;
      }

      const t = Math.max(elapsed / durationMs, 0);
      const eased = easeOutCubic(t);
      setValue(startValue + delta * eased);
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(rafId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs, enabled]);

  return value;
}
