import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RosterPicker } from '../components/abtest/RosterPicker';
import type { Competitor } from '../lib/ab/types';

// Fixture pool: mix of job/fixture origins, distinct baseScores, well over the
// bracket `size` used in tests (8) so the "top N" / scroll behaviour is exercised.
const POOL: Competitor[] = [
  { id: 'p1', label: 'Alice Amos', origin: 'job', baseScore: 95, traits: {} },
  { id: 'p2', label: 'Bob Baker', origin: 'fixture', baseScore: 90, traits: {} },
  { id: 'p3', label: 'Cara Cole', origin: 'job', baseScore: 85, traits: {} },
  { id: 'p4', label: 'Dana Diaz', origin: 'fixture', baseScore: 80, traits: {} },
  { id: 'p5', label: 'Eli Ellis', origin: 'job', baseScore: 75, traits: {} },
  { id: 'p6', label: 'Fay Ford', origin: 'fixture', baseScore: 70, traits: {} },
  { id: 'p7', label: 'Gus Grant', origin: 'job', baseScore: 65, traits: {} },
  { id: 'p8', label: 'Hana Hart', origin: 'fixture', baseScore: 60, traits: {} },
  { id: 'p9', label: 'Ivy Ives', origin: 'job', baseScore: 55, traits: {} },
  { id: 'p10', label: 'Jax Jones', origin: 'fixture', baseScore: 50, traits: {} },
];

const TOP_8_IDS = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8'];

describe('RosterPicker', () => {
  it('lists every competitor in the pool with the correct origin tag', () => {
    render(
      <RosterPicker pool={POOL} size={8} selectedIds={[]} onChange={vi.fn()} />,
    );

    for (const competitor of POOL) {
      expect(screen.getByText(competitor.label)).toBeInTheDocument();
      const tag = screen.getByTestId(`origin-${competitor.id}`);
      expect(tag).toHaveTextContent(competitor.origin);
    }
  });

  it('calls onChange with the id added when an unselected row is toggled', () => {
    const onChange = vi.fn();
    render(
      <RosterPicker pool={POOL} size={8} selectedIds={['p2']} onChange={onChange} />,
    );

    fireEvent.click(screen.getByRole('checkbox', { name: /Alice Amos/ }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(['p2', 'p1']);
  });

  it('calls onChange with the id removed when a selected row is toggled', () => {
    const onChange = vi.fn();
    render(
      <RosterPicker
        pool={POOL}
        size={8}
        selectedIds={['p1', 'p2']}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('checkbox', { name: /Alice Amos/ }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(['p2']);
  });

  it('does not grow the selection past `size` when toggling an unselected row', () => {
    const onChange = vi.fn();
    render(
      <RosterPicker
        pool={POOL}
        size={4}
        selectedIds={['p1', 'p2', 'p3', 'p4']}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('checkbox', { name: /Eli Ellis/ }));

    expect(onChange).not.toHaveBeenCalled();
  });

  it('"Select top N" replaces the selection with exactly the top `size` ids by baseScore', () => {
    const onChange = vi.fn();
    render(
      <RosterPicker pool={POOL} size={8} selectedIds={[]} onChange={onChange} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /select top 8/i }));

    expect(onChange).toHaveBeenCalledTimes(1);
    const result = onChange.mock.calls[0][0] as string[];
    expect(result).toHaveLength(8);
    expect(new Set(result)).toEqual(new Set(TOP_8_IDS));
    // Sanity check: this implementation emits them already sorted desc by baseScore.
    expect(result).toEqual(TOP_8_IDS);
  });

  it('shows a live "N of M" counter that updates when `selectedIds` changes', () => {
    const { rerender } = render(
      <RosterPicker pool={POOL} size={8} selectedIds={[]} onChange={vi.fn()} />,
    );

    expect(screen.getByTestId('roster-counter')).toHaveTextContent('0 of 8');

    rerender(
      <RosterPicker
        pool={POOL}
        size={8}
        selectedIds={['p1', 'p2', 'p3']}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId('roster-counter')).toHaveTextContent('3 of 8');
  });
});
