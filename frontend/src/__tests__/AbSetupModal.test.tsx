import { describe, it, expect, vi } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AbSetupModal } from '../components/abtest/AbSetupModal';
import type { Competitor } from '../lib/ab/types';

/** 16-competitor fixture pool: alternating job/fixture origin, distinct baseScores. */
function buildPool(): Competitor[] {
  return Array.from({ length: 16 }, (_, i) => ({
    id: `c${i + 1}`,
    label: `Résumé variant ${i + 1}`,
    origin: i % 2 === 0 ? 'job' : 'fixture',
    baseScore: 95 - i * 3,
    traits: {},
  }));
}

/** The roster checkbox for a given competitor id, scoped to its row. */
function rosterCheckbox(id: string): HTMLElement {
  return within(screen.getByTestId(`roster-row-${id}`)).getByRole('checkbox');
}

function startButton(): HTMLElement {
  return screen.getByRole('button', { name: /^start$/i });
}

describe('AbSetupModal', () => {
  it('disables Start until exactly `size` résumés are selected, and blocks over-selection', async () => {
    const user = userEvent.setup();
    const pool = buildPool();
    render(<AbSetupModal pool={pool} onClose={vi.fn()} onStart={vi.fn()} />);

    expect(startButton()).toBeDisabled();
    expect(startButton()).toHaveAttribute(
      'title',
      expect.stringMatching(/select exactly 8/i),
    );

    for (let i = 1; i <= 7; i++) {
      await user.click(rosterCheckbox(`c${i}`));
    }
    expect(screen.getByTestId('roster-counter')).toHaveTextContent('7 of 8');
    expect(startButton()).toBeDisabled();

    await user.click(rosterCheckbox('c8'));
    expect(screen.getByTestId('roster-counter')).toHaveTextContent('8 of 8');
    expect(startButton()).not.toBeDisabled();
    expect(startButton()).not.toHaveAttribute('title');

    // A 9th selection is blocked by RosterPicker itself once the bracket is full -
    // the checkbox is disabled, and clicking it must not push the count past 8
    // or break the Start button's enabled state.
    const ninth = rosterCheckbox('c9');
    expect(ninth).toBeDisabled();
    await user.click(ninth);
    expect(screen.getByTestId('roster-counter')).toHaveTextContent('8 of 8');
    expect(startButton()).not.toBeDisabled();
  });

  it('clamps the selection down when the bracket size shrinks, keeping the counter and Start gating in sync', async () => {
    const user = userEvent.setup();
    const pool = buildPool();
    render(<AbSetupModal pool={pool} onClose={vi.fn()} onStart={vi.fn()} />);

    for (let i = 1; i <= 6; i++) {
      await user.click(rosterCheckbox(`c${i}`));
    }
    expect(screen.getByTestId('roster-counter')).toHaveTextContent('6 of 8');

    await user.click(screen.getByRole('radio', { name: '4' }));

    // Truncating the existing 6-long selection to the new size of 4 keeps the
    // first 4 ids and drops the rest - count reads "4 of 4", never "6 of 4".
    expect(screen.getByTestId('roster-counter')).toHaveTextContent('4 of 4');
    // The clamp lands exactly on the new size here, so Start is enabled -
    // demonstrating the counter and the Start gate stay consistent immediately.
    expect(startButton()).not.toBeDisabled();
  });

  it('never lets the judging panel drop below 2 judges', async () => {
    const user = userEvent.setup();
    const pool = buildPool();
    render(<AbSetupModal pool={pool} onClose={vi.fn()} onStart={vi.fn()} />);

    const judgingHeading = screen.getByText('Judging panel');
    const judgingSection = judgingHeading.parentElement as HTMLElement;
    const judgeCheckboxes = within(judgingSection).getAllByRole(
      'checkbox',
    ) as HTMLInputElement[];
    expect(judgeCheckboxes).toHaveLength(5);

    await user.click(judgeCheckboxes[0]);
    await user.click(judgeCheckboxes[1]);
    await user.click(judgeCheckboxes[2]);

    const checkedAfterThree = judgeCheckboxes.filter((cb) => cb.checked);
    expect(checkedAfterThree).toHaveLength(2);
    checkedAfterThree.forEach((cb) => expect(cb).toBeDisabled());

    // Attempting to uncheck one of the last two must be a no-op.
    await user.click(checkedAfterThree[0]);
    const checkedAfterAttempt = judgeCheckboxes.filter((cb) => cb.checked);
    expect(checkedAfterAttempt).toHaveLength(2);
  });

  it('calls onStart with the assembled payload when Start is clicked', async () => {
    const user = userEvent.setup();
    const pool = buildPool();
    const onStart = vi.fn();
    render(<AbSetupModal pool={pool} onClose={vi.fn()} onStart={onStart} />);

    const ids = Array.from({ length: 8 }, (_, i) => `c${i + 1}`);
    for (const id of ids) {
      await user.click(rosterCheckbox(id));
    }

    await user.click(startButton());

    expect(onStart).toHaveBeenCalledTimes(1);
    const payload = onStart.mock.calls[0][0];
    expect(payload.selectedIds).toEqual(ids);
    expect(payload.size).toBe(8);
    expect(payload.config).toEqual(
      expect.objectContaining({
        judges: expect.any(Array),
        judgeWeights: expect.any(Object),
        bestOf: expect.any(Number),
        targetRole: expect.any(String),
        strictness: expect.any(Number),
        blindJudging: expect.any(Boolean),
      }),
    );
    expect(typeof payload.seed).toBe('string');
    expect(payload.seed.length).toBeGreaterThan(0);
  });

  it('calls onClose when Escape is pressed', () => {
    const pool = buildPool();
    const onClose = vi.fn();
    render(<AbSetupModal pool={pool} onClose={onClose} onStart={vi.fn()} />);

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
