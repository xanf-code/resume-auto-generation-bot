import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { RefObject } from 'react';
import {
  DEFAULT_MATCH_DURATION_SEC,
  PlaybackBar,
  speedFromMatchSeconds,
  type MatchDurationSec,
} from '../components/abtest/PlaybackBar';
import { MATCH_CYCLE_MS } from '../lib/ab/timeline';
import type { PlaybackStatus } from '../hooks/useTournamentPlayback';

function makeProgressRef(value = 0): RefObject<number> {
  return { current: value };
}

interface RenderOverrides {
  status?: PlaybackStatus;
  matchSeconds?: MatchDurationSec;
  onTogglePlay?: () => void;
  onSetMatchSeconds?: (s: MatchDurationSec) => void;
  onSkipToEnd?: () => void;
  onReplay?: () => void;
  onHideHud?: () => void;
}

function renderBar(overrides: RenderOverrides = {}) {
  const onTogglePlay = overrides.onTogglePlay ?? vi.fn();
  const onSetMatchSeconds = overrides.onSetMatchSeconds ?? vi.fn();
  const onSkipToEnd = overrides.onSkipToEnd ?? vi.fn();
  const onReplay = overrides.onReplay ?? vi.fn();
  const onHideHud = overrides.onHideHud ?? vi.fn();

  const utils = render(
    <PlaybackBar
      status={overrides.status ?? 'playing'}
      matchSeconds={overrides.matchSeconds ?? DEFAULT_MATCH_DURATION_SEC}
      progressRef={makeProgressRef()}
      onTogglePlay={onTogglePlay}
      onSetMatchSeconds={onSetMatchSeconds}
      onSkipToEnd={onSkipToEnd}
      onReplay={onReplay}
      onHideHud={onHideHud}
    />,
  );

  return { ...utils, onTogglePlay, onSetMatchSeconds, onSkipToEnd, onReplay, onHideHud };
}

describe('PlaybackBar', () => {
  it('calls onTogglePlay when the pause/resume button is clicked, and reflects "playing" status', async () => {
    const user = userEvent.setup();
    const { onTogglePlay } = renderBar({ status: 'playing' });

    const btn = screen.getByRole('button', { name: 'Pause' });
    expect(btn).toHaveAttribute('aria-pressed', 'true');

    await user.click(btn);
    expect(onTogglePlay).toHaveBeenCalledTimes(1);
  });

  it('reflects "paused" status with a Resume label and aria-pressed=false', () => {
    renderBar({ status: 'paused' });

    const btn = screen.getByRole('button', { name: 'Resume' });
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('flips the pause/resume button label and aria-pressed on rerender between playing and paused', () => {
    const { rerender } = render(
      <PlaybackBar
        status="playing"
        matchSeconds={5}
        progressRef={makeProgressRef()}
        onTogglePlay={() => {}}
        onSetMatchSeconds={() => {}}
        onSkipToEnd={() => {}}
        onReplay={() => {}}
        onHideHud={() => {}}
      />,
    );

    expect(screen.getByRole('button', { name: 'Pause' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    rerender(
      <PlaybackBar
        status="paused"
        matchSeconds={5}
        progressRef={makeProgressRef()}
        onTogglePlay={() => {}}
        onSetMatchSeconds={() => {}}
        onSkipToEnd={() => {}}
        onReplay={() => {}}
        onHideHud={() => {}}
      />,
    );

    expect(screen.getByRole('button', { name: 'Resume' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it.each([
    ['idle'] as const,
    ['finished'] as const,
  ])('shows Resume label for non-playing status "%s"', (status) => {
    renderBar({ status });
    expect(screen.getByRole('button', { name: 'Resume' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('calls onSetMatchSeconds(3|5|8|12) when each duration button is clicked', async () => {
    const user = userEvent.setup();
    const { onSetMatchSeconds } = renderBar({ matchSeconds: 5 });

    await user.click(screen.getByRole('button', { name: '3s' }));
    expect(onSetMatchSeconds).toHaveBeenLastCalledWith(3);

    await user.click(screen.getByRole('button', { name: '5s' }));
    expect(onSetMatchSeconds).toHaveBeenLastCalledWith(5);

    await user.click(screen.getByRole('button', { name: '8s' }));
    expect(onSetMatchSeconds).toHaveBeenLastCalledWith(8);

    await user.click(screen.getByRole('button', { name: '12s' }));
    expect(onSetMatchSeconds).toHaveBeenLastCalledWith(12);
  });

  it('marks the duration button matching the current matchSeconds prop as aria-pressed=true (5s)', () => {
    renderBar({ matchSeconds: 5 });

    expect(screen.getByRole('button', { name: '3s' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: '5s' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '8s' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: '12s' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('marks the duration button matching the current matchSeconds prop as aria-pressed=true (12s)', () => {
    renderBar({ matchSeconds: 12 });

    expect(screen.getByRole('button', { name: '3s' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: '5s' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: '8s' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: '12s' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('calls onSkipToEnd when "Skip to result" is clicked', async () => {
    const user = userEvent.setup();
    const { onSkipToEnd } = renderBar();

    await user.click(screen.getByRole('button', { name: /skip to result/i }));
    expect(onSkipToEnd).toHaveBeenCalledTimes(1);
  });

  it('calls onReplay when "Replay" is clicked', async () => {
    const user = userEvent.setup();
    const { onReplay } = renderBar();

    await user.click(screen.getByRole('button', { name: /replay/i }));
    expect(onReplay).toHaveBeenCalledTimes(1);
  });

  it('calls onHideHud when "Hide HUD" is clicked', async () => {
    const user = userEvent.setup();
    const { onHideHud } = renderBar();

    await user.click(screen.getByRole('button', { name: /hide hud/i }));
    expect(onHideHud).toHaveBeenCalledTimes(1);
  });

  it('maps match seconds to a playback rate relative to MATCH_CYCLE_MS', () => {
    expect(speedFromMatchSeconds(5)).toBeCloseTo(MATCH_CYCLE_MS / 5000);
    expect(speedFromMatchSeconds(3)).toBeGreaterThan(speedFromMatchSeconds(12));
  });

  it('mounts and unmounts cleanly with a plain { current: 0 } progressRef object (rAF loop starts and cleans up without throwing)', () => {
    const { unmount } = renderBar();
    expect(() => unmount()).not.toThrow();
  });
});
