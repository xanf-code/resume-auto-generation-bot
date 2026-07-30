import { useEffect, useState } from 'react';

/**
 * Subscribe to a CSS media query. SSR-safe default is `false` (mobile-first).
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/** Persistent applications rail + three-pane workspace. */
export const DESKTOP_MQ = '(min-width: 1024px)';

/** Side-by-side manuscript / proof / skills (needs ~1280px). */
export const WIDE_MQ = '(min-width: 1280px)';

/** OS-level reduced motion preference. */
export const REDUCED_MOTION_MQ = '(prefers-reduced-motion: reduce)';
