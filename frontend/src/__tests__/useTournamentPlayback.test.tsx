import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import { useTournamentPlayback } from '../hooks/useTournamentPlayback';
import type { MatchResult, Timeline } from '../lib/ab/types';

// A minimal, hand-built Timeline with round-number durations so millisecond
// assertions (especially the mid-flight speed change) are exact and easy to
// reason about, independent of rAF frame quantization.
//
// index | kind           | startMs | durationMs | window
//   0   | tournament-intro |    0  |   1000     | [0, 1000)
//   1   | match-focus      | 1000  |   2000     | [1000, 3000)
//   2   | match-verdict    | 3000  |   2000     | [3000, 5000)
//   3   | match-advance    | 5000  |   1000     | [5000, 6000)
//   4   | champion         | 6000  |   1000     | [6000, 7000)
// totalMs = 7000

const MATCH_RESULT: MatchResult = {
  matchId: 'm1',
  round: 0,
  aId: 'a',
  bId: 'b',
  scoreA: { competitorId: 'a', total: 80, verdicts: [{ judge: 'ats', score: 80 }], upset: false },
  scoreB: { competitorId: 'b', total: 60, verdicts: [{ judge: 'ats', score: 60 }], upset: false },
  winnerId: 'a',
  loserId: 'b',
  margin: 20,
};

function makeTimeline(): Timeline {
  return {
    totalMs: 7000,
    steps: [
      { id: 'tournament-intro:-1', kind: 'tournament-intro', round: -1, startMs: 0, durationMs: 1000 },
      { id: 'match-focus:m1', kind: 'match-focus', round: 0, matchId: 'm1', startMs: 1000, durationMs: 2000 },
      {
        id: 'match-verdict:m1',
        kind: 'match-verdict',
        round: 0,
        matchId: 'm1',
        result: MATCH_RESULT,
        startMs: 3000,
        durationMs: 2000,
      },
      { id: 'match-advance:m1', kind: 'match-advance', round: 0, matchId: 'm1', startMs: 5000, durationMs: 1000 },
      { id: 'champion:0', kind: 'champion', round: 0, startMs: 6000, durationMs: 1000 },
    ],
  };
}

describe('useTournamentPlayback', () => {
  beforeEach(() => {
    vi.useFakeTimers({
      toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'Date'],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('is inert when timeline is null: idle status, stepIndex -1, empty resolved, safe no-op controls', () => {
    const { result } = renderHook(() => useTournamentPlayback(null));
    const [state, controls] = result.current;

    expect(state.status).toBe('idle');
    expect(state.stepIndex).toBe(-1);
    expect(state.step).toBeNull();
    expect(state.resolved).toEqual({});

    expect(() => {
      act(() => {
        controls.play();
        controls.pause();
        controls.toggle();
        controls.setSpeed(2);
        controls.skipToEnd();
        controls.restart();
      });
    }).not.toThrow();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current[0].status).toBe('idle');
    expect(result.current[0].stepIndex).toBe(-1);
  });

  it('auto-plays by default and advances stepIndex to 1 once past steps[0].durationMs', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    expect(result.current[0].status).toBe('playing');

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(result.current[0].stepIndex).toBe(1);
    expect(result.current[0].step?.id).toBe('match-focus:m1');
  });

  it('does not auto-play when autoPlay is false', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline, { autoPlay: false }));

    expect(result.current[0].status).toBe('idle');
    expect(result.current[0].stepIndex).toBe(-1);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Nothing should have advanced - the loop never started.
    expect(result.current[0].status).toBe('idle');
    expect(result.current[0].stepIndex).toBe(-1);
  });

  it('pause() freezes stepIndex and status even as more time elapses', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    act(() => {
      vi.advanceTimersByTime(1500);
    });
    const frozenIndex = result.current[0].stepIndex;
    expect(frozenIndex).toBe(1);

    act(() => {
      result.current[1].pause();
    });
    expect(result.current[0].status).toBe('paused');

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(result.current[0].stepIndex).toBe(frozenIndex);
    expect(result.current[0].status).toBe('paused');
  });

  it('play() resumes advancing virtual time after a pause', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    act(() => {
      vi.advanceTimersByTime(1500);
    });
    act(() => {
      result.current[1].pause();
    });
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current[0].stepIndex).toBe(1);

    act(() => {
      result.current[1].play();
    });
    expect(result.current[0].status).toBe('playing');

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    // Virtual time resumes from ~1500ms and advances further into match-verdict.
    expect(result.current[0].stepIndex).toBe(2);
  });

  it('toggle() flips between playing and paused', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    expect(result.current[0].status).toBe('playing');

    act(() => {
      result.current[1].toggle();
    });
    expect(result.current[0].status).toBe('paused');

    act(() => {
      result.current[1].toggle();
    });
    expect(result.current[0].status).toBe('playing');
  });

  it('setSpeed(4) applies mid-flight with no recomputation: 1000ms of elapsed time lands ~4000ms of virtual time', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    // Change speed immediately, before any virtual time has accumulated.
    act(() => {
      result.current[1].setSpeed(4);
    });
    expect(result.current[0].speed).toBe(4);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // 1000ms of real time * 4x speed ~= 4000ms virtual time -> match-verdict window [3000, 5000).
    expect(result.current[0].stepIndex).toBe(2);
    expect(result.current[0].step?.id).toBe('match-verdict:m1');
  });

  it('skipToEnd() jumps to the last step, marks finished, and resolves every match', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    act(() => {
      result.current[1].skipToEnd();
    });

    expect(result.current[0].status).toBe('finished');
    expect(result.current[0].stepIndex).toBe(timeline.steps.length - 1);
    expect(result.current[0].resolved.m1).toEqual(MATCH_RESULT);

    // Advancing further after finishing should not throw or change anything.
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current[0].status).toBe('finished');
    expect(result.current[0].stepIndex).toBe(timeline.steps.length - 1);
  });

  it('restart() resets to stepIndex -1 immediately, then 0 after the first frame commits, with status playing', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline));

    act(() => {
      result.current[1].skipToEnd();
    });
    expect(result.current[0].status).toBe('finished');

    act(() => {
      result.current[1].restart();
    });
    expect(result.current[0].status).toBe('playing');

    act(() => {
      vi.advanceTimersByTime(20);
    });
    expect(result.current[0].stepIndex).toBe(0);
    expect(result.current[0].status).toBe('playing');
  });

  it('cancels the rAF loop on unmount and stops issuing state updates', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const timeline = makeTimeline();
    const { result, unmount } = renderHook(() => useTournamentPlayback(timeline));

    act(() => {
      vi.advanceTimersByTime(1500);
    });
    const stateBeforeUnmount = result.current[0];
    expect(stateBeforeUnmount.stepIndex).toBe(1);

    unmount();

    expect(cancelSpy).toHaveBeenCalled();

    expect(() => {
      act(() => {
        vi.advanceTimersByTime(5000);
      });
    }).not.toThrow();

    // result.current is frozen at its last rendered value post-unmount.
    expect(result.current[0].stepIndex).toBe(stateBeforeUnmount.stepIndex);
    expect(result.current[0].status).toBe(stateBeforeUnmount.status);

    cancelSpy.mockRestore();
  });

  it('a new timeline identity cancels the old loop exactly once and restarts from -1 -> 0', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const timelineA = makeTimeline();
    const timelineB = makeTimeline();

    const { result, rerender } = renderHook(
      ({ timeline }: { timeline: Timeline }) => useTournamentPlayback(timeline),
      { initialProps: { timeline: timelineA } },
    );

    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(result.current[0].stepIndex).toBe(1);

    const cancelCallsBeforeSwap = cancelSpy.mock.calls.length;

    rerender({ timeline: timelineB });

    // Reset happens synchronously as part of the swap's effect commit.
    expect(result.current[0].stepIndex).toBe(-1);
    expect(cancelSpy.mock.calls.length - cancelCallsBeforeSwap).toBe(1);

    act(() => {
      vi.advanceTimersByTime(20);
    });
    expect(result.current[0].stepIndex).toBe(0);

    cancelSpy.mockRestore();
  });

  it('tolerates React StrictMode double-invoked effects without jitter or duplicated loops', () => {
    const timeline = makeTimeline();
    const { result } = renderHook(() => useTournamentPlayback(timeline), {
      wrapper: ({ children }) => <StrictMode>{children}</StrictMode>,
    });

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    // If two loops raced, virtual time would advance ~2x too fast, landing
    // past step 1 already. A single clean loop lands exactly on step 1.
    expect(result.current[0].stepIndex).toBe(1);
    expect(result.current[0].status).toBe('playing');
  });
});
