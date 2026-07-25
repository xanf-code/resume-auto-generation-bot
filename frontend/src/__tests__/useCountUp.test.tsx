import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useCountUp } from '../hooks/useCountUp';

describe('useCountUp', () => {
  beforeEach(() => {
    vi.useFakeTimers({
      toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'Date'],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('jumps immediately to target when enabled is false', () => {
    const { result } = renderHook(() => useCountUp(100, 1000, { enabled: false }));
    expect(result.current).toBe(100);
  });

  it('starts at 0 and animates to target over durationMs when enabled', () => {
    const { result } = renderHook(() => useCountUp(100, 1000));

    // Before any time advances, the value should be at (or very near) the start.
    expect(result.current).toBe(0);

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current).toBeGreaterThan(0);
    expect(result.current).toBeLessThan(100);

    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(result.current).toBe(100);
  });

  it('defaults to enabled (animates) when options is omitted', () => {
    const { result } = renderHook(() => useCountUp(50, 200));
    expect(result.current).toBe(0);

    // Advance a little past durationMs (rAF fires on fixed frame ticks, so the
    // exact durationMs boundary may fall between two frames) — "200ms+".
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(result.current).toBe(50);
  });

  it('restarts interpolation from the current displayed value when target changes mid-animation', () => {
    const { result, rerender } = renderHook(
      ({ target }: { target: number }) => useCountUp(target, 1000),
      { initialProps: { target: 100 } },
    );

    act(() => {
      vi.advanceTimersByTime(500);
    });
    const midValue = result.current;
    expect(midValue).toBeGreaterThan(0);
    expect(midValue).toBeLessThan(100);

    // Change target mid-flight — restart should begin from midValue, not 0.
    rerender({ target: 300 });
    expect(result.current).toBe(midValue);

    // "1000ms+" past the restart to land past the durationMs boundary.
    act(() => {
      vi.advanceTimersByTime(1050);
    });
    expect(result.current).toBe(300);
  });

  it('cancels the pending requestAnimationFrame on unmount and does not update after unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');

    const { result, unmount } = renderHook(() => useCountUp(100, 1000));

    act(() => {
      vi.advanceTimersByTime(200);
    });
    const valueBeforeUnmount = result.current;
    expect(valueBeforeUnmount).toBeGreaterThan(0);
    expect(valueBeforeUnmount).toBeLessThan(100);

    unmount();

    expect(cancelSpy).toHaveBeenCalled();

    // Advancing timers after unmount must not throw or warn about updates on
    // an unmounted component; result.current retains its last rendered value.
    expect(() => {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }).not.toThrow();
    expect(result.current).toBe(valueBeforeUnmount);

    cancelSpy.mockRestore();
  });

  it('does not crash when durationMs changes mid-flight', () => {
    const { result, rerender } = renderHook(
      ({ duration }: { duration: number }) => useCountUp(100, duration),
      { initialProps: { duration: 1000 } },
    );

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(() => rerender({ duration: 2000 })).not.toThrow();

    // "2000ms+" past the restart to land past the durationMs boundary.
    act(() => {
      vi.advanceTimersByTime(2050);
    });
    expect(result.current).toBe(100);
  });
});
