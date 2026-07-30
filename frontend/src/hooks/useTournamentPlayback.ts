import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { resolvedAt, stepIndexAtMs } from '../lib/ab/timeline';
import type { MatchResult, Timeline, TimelineStep } from '../lib/ab/types';

/** Positive playback rate. 1 = timeline wall-clock; <1 slows, >1 speeds. */
export type PlaybackSpeed = number;
export type PlaybackStatus = 'idle' | 'playing' | 'paused' | 'finished';

export interface PlaybackState {
  status: PlaybackStatus;
  stepIndex: number; // -1 before the first frame commits
  step: TimelineStep | null;
  resolved: Record<string, MatchResult>; // correct after a skip too
  speed: PlaybackSpeed;
  progressRef: RefObject<number>; // 0..1, read imperatively, never during render
}

export interface PlaybackControls {
  play(): void;
  pause(): void;
  toggle(): void;
  setSpeed(s: PlaybackSpeed): void;
  skipToEnd(): void;
  restart(): void;
}

export interface UseTournamentPlaybackOptions {
  autoPlay?: boolean;
  initialSpeed?: PlaybackSpeed;
  /** Informational passthrough only - buildTimeline already shapes reduced-motion steps upstream. */
  reducedMotion?: boolean;
  /** Test escape hatch; defaults to performance.now. */
  now?: () => number;
}

interface Clock {
  virtualMs: number;
  lastTs: number;
  raf: number;
}

const defaultNow = (): number => performance.now();

/**
 * Drives résumé-tournament replay via a single requestAnimationFrame loop
 * using an elapsed-time model: virtual time accumulates as `dt * speed` each
 * frame, so changing speed takes effect on the very next frame with no
 * recomputation of the schedule. `stepIndex` only triggers a re-render when
 * the active TimelineStep actually changes; `progressRef` is a plain ref
 * mutated every frame and must be read imperatively, never during render.
 */
export function useTournamentPlayback(
  timeline: Timeline | null,
  options?: UseTournamentPlaybackOptions,
): [PlaybackState, PlaybackControls] {
  const autoPlay = options?.autoPlay ?? true;
  const initialSpeed = options?.initialSpeed ?? 1;

  const [status, setStatus] = useState<PlaybackStatus>('idle');
  const [stepIndex, setStepIndex] = useState<number>(-1);
  const [speed, setSpeedState] = useState<PlaybackSpeed>(initialSpeed);

  const progressRef = useRef<number>(0);
  const stepIndexRef = useRef<number>(-1);
  const statusRef = useRef<PlaybackStatus>('idle');
  const mountedRef = useRef(false);
  const speedRef = useRef<PlaybackSpeed>(initialSpeed);
  const pausedRef = useRef<boolean>(!autoPlay);
  const clockRef = useRef<Clock>({ virtualMs: 0, lastTs: 0, raf: 0 });
  const timelineRef = useRef<Timeline | null>(timeline);
  const nowRef = useRef<() => number>(options?.now ?? defaultNow);

  // Latest-ref pattern: keeps the hot rAF loop reading fresh values without
  // re-subscribing the effect on every render.
  timelineRef.current = timeline;
  nowRef.current = options?.now ?? defaultNow;

  const setStatusSafe = useCallback((next: PlaybackStatus) => {
    statusRef.current = next;
    if (mountedRef.current) setStatus(next);
  }, []);

  const setStepIndexSafe = useCallback((next: number) => {
    stepIndexRef.current = next;
    if (mountedRef.current) setStepIndex(next);
  }, []);

  const cancelLoop = useCallback(() => {
    if (clockRef.current.raf) {
      cancelAnimationFrame(clockRef.current.raf);
      clockRef.current.raf = 0;
    }
  }, []);

  const frame = useCallback(
    (now: number) => {
      if (!mountedRef.current) return;
      const active = timelineRef.current;
      if (!active) return;

      const dt = now - clockRef.current.lastTs;
      clockRef.current.lastTs = now;
      if (!pausedRef.current) {
        clockRef.current.virtualMs = Math.min(
          clockRef.current.virtualMs + dt * speedRef.current,
          active.totalMs,
        );
      }

      const i = stepIndexAtMs(active, clockRef.current.virtualMs);
      progressRef.current = active.totalMs > 0 ? clockRef.current.virtualMs / active.totalMs : 0;
      if (i !== stepIndexRef.current) {
        setStepIndexSafe(i);
      }

      if (clockRef.current.virtualMs >= active.totalMs) {
        setStatusSafe('finished');
        return;
      }

      clockRef.current.raf = requestAnimationFrame(frame);
    },
    [setStepIndexSafe, setStatusSafe],
  );

  const startLoop = useCallback(() => {
    clockRef.current.lastTs = nowRef.current();
    clockRef.current.raf = requestAnimationFrame(frame);
  }, [frame]);

  useEffect(() => {
    mountedRef.current = true;
    // StrictMode double-invokes effects in dev - cancel any stray loop from a
    // prior invocation before resetting, in addition to the cleanup below.
    cancelLoop();
    clockRef.current = { virtualMs: 0, lastTs: nowRef.current(), raf: 0 };
    setStepIndexSafe(-1);

    if (timeline) {
      pausedRef.current = !autoPlay;
      setStatusSafe(autoPlay ? 'playing' : 'idle');
      if (autoPlay) startLoop();
    } else {
      setStatusSafe('idle');
    }

    return () => {
      mountedRef.current = false;
      cancelLoop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeline]);

  const play = useCallback(() => {
    if (!timelineRef.current) return;
    pausedRef.current = false;
    setStatusSafe('playing');
    if (!clockRef.current.raf) startLoop();
  }, [setStatusSafe, startLoop]);

  const pause = useCallback(() => {
    if (!timelineRef.current) return;
    pausedRef.current = true;
    setStatusSafe('paused');
  }, [setStatusSafe]);

  const toggle = useCallback(() => {
    if (!timelineRef.current) return;
    if (statusRef.current === 'playing') {
      pause();
    } else {
      play();
    }
  }, [play, pause]);

  const setSpeed = useCallback((s: PlaybackSpeed) => {
    if (!(s > 0) || !Number.isFinite(s)) return;
    speedRef.current = s;
    if (mountedRef.current) setSpeedState(s);
  }, []);

  const skipToEnd = useCallback(() => {
    const active = timelineRef.current;
    if (!active) return;
    cancelLoop();
    clockRef.current.virtualMs = active.totalMs;
    progressRef.current = 1;
    setStepIndexSafe(active.steps.length - 1);
    setStatusSafe('finished');
  }, [cancelLoop, setStepIndexSafe, setStatusSafe]);

  const restart = useCallback(() => {
    const active = timelineRef.current;
    if (!active) return;
    cancelLoop();
    clockRef.current = { virtualMs: 0, lastTs: nowRef.current(), raf: 0 };
    progressRef.current = 0;
    pausedRef.current = false;
    setStepIndexSafe(-1);
    setStatusSafe('playing');
    startLoop();
  }, [cancelLoop, setStepIndexSafe, setStatusSafe, startLoop]);

  const step = useMemo<TimelineStep | null>(
    () => (timeline && stepIndex >= 0 ? timeline.steps[stepIndex] : null),
    [timeline, stepIndex],
  );

  const resolved = useMemo<Record<string, MatchResult>>(
    () => (timeline ? resolvedAt(timeline, stepIndex) : {}),
    [timeline, stepIndex],
  );

  const state: PlaybackState = {
    status,
    stepIndex,
    step,
    resolved,
    speed,
    progressRef,
  };

  const controls: PlaybackControls = { play, pause, toggle, setSpeed, skipToEnd, restart };

  return [state, controls];
}
