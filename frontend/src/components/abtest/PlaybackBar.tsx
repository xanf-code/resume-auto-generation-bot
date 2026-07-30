import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';
import { MATCH_CYCLE_MS } from '../../lib/ab/timeline';
import type { PlaybackStatus } from '../../hooks/useTournamentPlayback';

/** Seconds one unscaled match iteration (focus→advance) should take. */
export type MatchDurationSec = 120 | 150 | 180 | 240;

export const MATCH_DURATION_OPTIONS: readonly MatchDurationSec[] = [120, 150, 180, 240];

export const DEFAULT_MATCH_DURATION_SEC: MatchDurationSec = 150;

/** Convert a target match length into the playback rate the rAF loop expects. */
export function speedFromMatchSeconds(seconds: MatchDurationSec): number {
  return MATCH_CYCLE_MS / (seconds * 1000);
}

/** Renders whole minutes as "2m", fractional minutes as "2.5m". */
function formatMatchSeconds(seconds: MatchDurationSec): string {
  const minutes = seconds / 60;
  return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)}m`;
}

interface Props {
  status: PlaybackStatus;
  matchSeconds: MatchDurationSec;
  progressRef: RefObject<number>;
  onTogglePlay: () => void;
  onSetMatchSeconds: (s: MatchDurationSec) => void;
  onSkipToEnd: () => void;
  onReplay: () => void;
  onHideHud: () => void;
}

/**
 * Transport controls for resume-tournament replay: pause/resume toggle,
 * seconds-per-match pace, skip-to-result, replay, hide-HUD, and a progress
 * line. Everything here is normal React state/props except the progress fill,
 * which is written imperatively from its own rAF loop reading `progressRef`
 * every frame - never during render - so per-frame updates never trigger
 * React re-renders on this bar.
 */
export function PlaybackBar({
  status,
  matchSeconds,
  progressRef,
  onTogglePlay,
  onSetMatchSeconds,
  onSkipToEnd,
  onReplay,
  onHideHud,
}: Props) {
  const fillRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    // StrictMode double-invokes effects in dev - cancel any stray loop from a
    // prior invocation before starting a fresh one.
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }

    const tick = () => {
      const el = fillRef.current;
      if (el) {
        const p = progressRef.current ?? 0;
        el.style.transform = `scaleX(${p})`;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
      }
    };
  }, [progressRef]);

  const isPlaying = status === 'playing';

  return (
    <div className="flex flex-col gap-3 w-full">
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={onTogglePlay}
          aria-pressed={isPlaying}
          aria-label={isPlaying ? 'Pause' : 'Resume'}
          title={isPlaying ? 'Pause' : 'Resume'}
          className="inline-flex items-center justify-center w-8 h-8 rounded-[2px] text-ink-soft hover:text-ink border border-transparent hover:border-rule transition-colors duration-200 focus:outline-none focus-visible:border-accent/60"
        >
          {isPlaying ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
              <rect x="3" y="2" width="3" height="10" fill="currentColor" />
              <rect x="8" y="2" width="3" height="10" fill="currentColor" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
              <path d="M3.5 2.5v9l8-4.5-8-4.5Z" fill="currentColor" />
            </svg>
          )}
        </button>

        <div
          role="group"
          aria-label="Seconds per match"
          className="inline-flex items-center gap-3 font-mono text-[12px]"
        >
          <span className="text-ink-faint uppercase tracking-[0.08em] text-[10px]">Match</span>
          {MATCH_DURATION_OPTIONS.map((sec) => {
            const active = matchSeconds === sec;
            return (
              <button
                key={sec}
                type="button"
                onClick={() => onSetMatchSeconds(sec)}
                aria-pressed={active}
                className={`pb-0.5 border-b-2 transition-colors duration-200 ${
                  active
                    ? 'text-ink border-accent'
                    : 'text-ink-soft border-transparent hover:text-ink'
                }`}
              >
                {formatMatchSeconds(sec)}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={onSkipToEnd}
          className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink border border-rule hover:border-ink-faint px-2.5 py-1 rounded-[2px] transition-colors duration-200"
        >
          Skip to result
        </button>

        <button
          type="button"
          onClick={onReplay}
          className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink border border-rule hover:border-ink-faint px-2.5 py-1 rounded-[2px] transition-colors duration-200"
        >
          Replay
        </button>

        <button
          type="button"
          onClick={onHideHud}
          aria-label="Hide HUD"
          title="Hide HUD"
          className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink border border-rule hover:border-ink-faint px-2.5 py-1 rounded-[2px] transition-colors duration-200 ml-auto"
        >
          Hide HUD
        </button>
      </div>

      <div className="relative h-[2px] w-full bg-rule overflow-hidden">
        <div
          ref={fillRef}
          className="absolute inset-y-0 left-0 w-full bg-accent"
          style={{ transformOrigin: 'left', transform: 'scaleX(0)' }}
        />
      </div>
    </div>
  );
}
