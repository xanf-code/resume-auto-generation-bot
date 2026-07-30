# Phase 2 - Timeline & Playback Controller

**Goal:** Turn a `TournamentResult` into an ordered `Timeline` of steps with absolute offsets, and build the rAF elapsed-time controller that walks it. At the end of this phase the full run can be driven, paused, sped up, skipped and replayed in a test - still with nothing on screen.

**Prereq:** Phase 1. **Blocks:** Phases 3-5.

## Modules (each <500 lines)

- `frontend/src/lib/ab/timeline.ts` - `buildTimeline(result, opts)`, `stepIndexAtMs(timeline, ms)`, `resolvedAt(timeline, stepIndex)`.
- `frontend/src/hooks/useTournamentPlayback.ts` - the rAF controller.
- `frontend/src/hooks/useCountUp.ts` - rAF number interpolation.
- `frontend/src/hooks/useMediaQuery.ts` *(modified)* - add `export const REDUCED_MOTION_MQ = '(prefers-reduced-motion: reduce)';` beside the existing `DESKTOP_MQ` / `WIDE_MQ`.

## Timeline contract

```ts
export type StepKind =
  | 'tournament-intro'  // title card; bracket fades in seeded
  | 'round-intro'       // round name sweeps in
  | 'match-focus'       // bracket dims, spotlight opens on the pair
  | 'match-score'       // bars race, numbers count up
  | 'match-verdict'     // winner flash, loser fades
  | 'match-advance'     // winner travels to its next slot, connector draws
  | 'round-outro'       // spotlight closes, bracket un-dims
  | 'champion';

export interface TimelineStep {
  id: string;             // `${kind}:${matchId ?? round}` - unique, readable in assertions
  kind: StepKind;
  durationMs: number;     // at 1x; never 0 - a zero-length step cannot be seeked to
  startMs: number;        // cumulative at 1x - makes seeking a binary search, not a replay
  round: number;
  matchId?: string;
  result?: MatchResult;   // denormalised so render never does a lookup
}

export interface Timeline { steps: TimelineStep[]; totalMs: number }
```

### Step durations (at 1x)

| Kind | Base ms | Cardinality |
|---|---|---|
| `tournament-intro` | 900 | 1 |
| `round-intro` | 700 | per round |
| `match-focus` | 420 | per match |
| `match-score` | 1100 | per match |
| `match-verdict` | 700 | per match |
| `match-advance` | 620 | per match |
| `round-outro` | 400 | per round |
| `champion` | 1600 | 1 |

A match costs 2840ms unscaled, so a 16-bracket would run ~49s. Too long. `buildTimeline` applies a per-round **pace scale** by round width:

```
matchesInRound >= 8 -> 0.55
matchesInRound >= 4 -> 0.75
otherwise           -> 1.00
```

16-bracket total: ~36s at 1x, 18s at 2x, 9s at 4x. Default speed is `1` for sizes 4 and 8, `2` for size 16.

### Invariants

- `startMs` strictly increasing.
- `startMs[i] + durationMs[i] === startMs[i+1]`.
- `totalMs === last.startMs + last.durationMs`.

### Companion helpers

- `stepIndexAtMs(timeline, ms): number` - binary search over `startMs`.
- `resolvedAt(timeline, stepIndex): Record<string, MatchResult>` - every match whose `match-verdict` step index is `<= stepIndex`. **This is how the bracket knows its own state at any point, including immediately after a skip.**

### Reduced motion

`buildTimeline(result, { reducedMotion: true })` drops `match-focus`, `match-advance` and `round-outro` - they carry no information, only motion - and flattens every remaining duration to `REDUCED_STEP_MS = 900`. Same results, same champion, no tweening. **A `match-verdict` still exists for every match**, so the run still completes and every score is still shown.

## Playback controller

**One `requestAnimationFrame` loop over an elapsed-time model.** Not a `setTimeout` chain: with a chain, per-step scheduling error accumulates across ~30 steps, a mid-flight speed change requires recomputing the remaining slice of the current step, skip has to unwind a queue, and every pending timer is a leak. Here the position is always derived from an accumulator, so drift is impossible by construction and all four controls are one-liners.

```ts
const clock = useRef({ virtualMs: 0, lastTs: 0, raf: 0 });
const speedRef = useRef<PlaybackSpeed>(initialSpeed);
const pausedRef = useRef(false);

const frame = (now: number) => {
  const dt = now - clock.current.lastTs;
  clock.current.lastTs = now;
  if (!pausedRef.current) {
    clock.current.virtualMs = Math.min(
      clock.current.virtualMs + dt * speedRef.current,
      timeline.totalMs,
    );
  }
  const i = stepIndexAtMs(timeline, clock.current.virtualMs);
  progressRef.current = clock.current.virtualMs / timeline.totalMs;
  if (i !== stepIndexRef.current) { stepIndexRef.current = i; setStepIndex(i); }  // <- ONLY setState
  if (clock.current.virtualMs >= timeline.totalMs) { setStatus('finished'); return; }
  clock.current.raf = requestAnimationFrame(frame);
};
```

**Re-render policy is the load-bearing perf decision.** `setState` is called *only when the step index changes* - about 30 times across a whole 16-competitor run, not ~2000. Continuous motion within a step is owned by CSS transitions and `useCountUp`, both keyed off the step, so React is never in the animation loop. The one thing that genuinely needs per-frame continuity - the playback progress line - reads `progressRef` from its own tiny rAF in `PlaybackBar` (phase 5) and writes `el.style.transform` imperatively.

Speed changes apply from the next frame with no recomputation, because `speedRef` is read inside `frame`. That is precisely why the elapsed-time model beats the timeout chain.

### Exposed shape

```ts
export type PlaybackSpeed = 1 | 2 | 4;
export type PlaybackStatus = 'idle' | 'playing' | 'paused' | 'finished';

export interface PlaybackState {
  status: PlaybackStatus;
  stepIndex: number;                        // -1 before the first frame commits
  step: TimelineStep | null;
  resolved: Record<string, MatchResult>;    // correct after a skip too
  speed: PlaybackSpeed;
  progressRef: React.RefObject<number>;     // 0..1, read imperatively, never during render
}

export interface PlaybackControls {
  play(): void; pause(): void; toggle(): void;
  setSpeed(s: PlaybackSpeed): void; skipToEnd(): void; restart(): void;
}

export function useTournamentPlayback(
  timeline: Timeline | null,
  options?: {
    autoPlay?: boolean;
    initialSpeed?: PlaybackSpeed;
    reducedMotion?: boolean;
    now?: () => number;   // test escape hatch; defaults to performance.now
  },
): [PlaybackState, PlaybackControls];
```

- `resolved` is `useMemo(() => resolvedAt(timeline, stepIndex), [timeline, stepIndex])` - O(30), recomputed ~30 times per run.
- `skipToEnd()` sets `virtualMs = totalMs`, cancels the rAF, and sets `stepIndex` to the last index with `status: 'finished'` synchronously.
- **"Replay with new seed" is deliberately NOT a control on this hook.** It lives on `AbTestingPage` (phase 3), which mints a fresh seed, re-runs `simulateTournament` + `buildTimeline`, and hands down a new `timeline` identity. The hook's effect keys on `[timeline]`, so it cancels the old loop and starts clean. This keeps the hook a pure timeline-walker.

### Cleanup

`main.tsx:9` wraps the app in `<StrictMode>`, so effects double-invoke in dev. Every rAF loop needs `cancelAnimationFrame` **at the top of the effect body as well as in the returned cleanup**, plus a `mountedRef` guard before every `setState`. Without this, two loops race and the step index visibly jitters.

## useCountUp

`useCountUp(target, durationMs, { enabled })` - ~20 lines, rAF interpolation with easeOutCubic.

CSS cannot interpolate text content, and the `@property` + `counter()` workaround breaks `tabular-nums` alignment with no clean way to short-circuit. Critically, rAF is the only approach that can **jump straight to the target when `skipToEnd` fires or reduced motion is on**. A count-up still ticking after a skip is the classic bug here.

## TDD

### RED

- `frontend/src/__tests__/ab.timeline.test.ts`: `steps[0].kind === 'tournament-intro'` and the last is `'champion'`; `startMs` strictly increasing; `startMs[i] + durationMs[i] === startMs[i+1]`; `totalMs === last.startMs + last.durationMs`; every `durationMs > 0`; every `id` unique; exactly one `match-verdict` per match, each carrying the matching `result`; one `round-intro` per round; pace scaling - a 16-bracket's round-0 `match-score` duration < a size-4 `match-score` duration; `reducedMotion: true` emits no `match-focus`/`match-advance`/`round-outro`, every remaining duration `=== REDUCED_STEP_MS`, and **a `match-verdict` still exists for every match**; `resolvedAt(timeline, i)` contains exactly the matches whose verdict index `<= i`; `stepIndexAtMs(timeline, 0) === 0` and `stepIndexAtMs(timeline, totalMs)` is the last index.

- `frontend/src/__tests__/useTournamentPlayback.test.tsx`, under fake timers:
  ```ts
  vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'Date'] });
  ```
  Vitest 2's sinon-backed timers fake rAF *and* `performance.now`, which is exactly what the elapsed-time model reads. Drive with `act(() => vi.advanceTimersByTime(2000))`.
  - after advancing past `steps[0].durationMs`, `stepIndex === 1`;
  - `pause()` then advance 5s -> `stepIndex` unchanged, `status === 'paused'`;
  - **`setSpeed(4)` then advance 1000ms -> lands on the step whose `startMs` window contains 4000ms** (this is the assertion that proves speed applies mid-flight without recomputation);
  - `skipToEnd()` -> `status === 'finished'`, `stepIndex === steps.length - 1`, `resolved` has all `size - 1` matches;
  - `restart()` -> `stepIndex === 0`, `status === 'playing'`;
  - **unmount** - spy `cancelAnimationFrame`, assert it fired, then advance timers and assert no further state update (no `act()` warning, no unmounted-setState error);
  - a new `timeline` identity cancels the old loop exactly once and restarts at 0.

- `frontend/src/__tests__/useCountUp.test.tsx`: `enabled: false` -> immediately at target; `enabled: true` -> an intermediate value at half duration and exactly the target at full duration; unmount mid-count cancels.

### GREEN

Implement `timeline.ts`, the two hooks, and the `REDUCED_MOTION_MQ` export to pass.

## Acceptance

```bash
cd frontend
npx vitest run src/__tests__/ab.timeline src/__tests__/useTournamentPlayback src/__tests__/useCountUp
npm run lint
```

All green. Still zero UI - no component under `src/components/abtest/` exists yet.

## Files

`frontend/src/lib/ab/timeline.ts`, `frontend/src/hooks/{useTournamentPlayback,useCountUp}.ts`,
`frontend/src/hooks/useMediaQuery.ts` *(modified)*,
`frontend/src/__tests__/{ab.timeline.test.ts,useTournamentPlayback.test.tsx,useCountUp.test.tsx}`.
