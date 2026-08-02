import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BulletCountControls } from '../components/newjob/BulletCountControls';
import { DEFAULT_BULLET_COUNTS, BULLET_COUNT_MIN, BULLET_COUNT_MAX } from '../lib/bulletCounts';

describe('BulletCountControls', () => {
  it('renders current counts for both roles', () => {
    render(<BulletCountControls counts={[4, 3]} onChange={vi.fn()} />);
    expect(screen.getByTestId('bullet-count-value-0').textContent).toBe('4');
    expect(screen.getByTestId('bullet-count-value-1').textContent).toBe('3');
  });

  it('calls onChange with incremented count', () => {
    const onChange = vi.fn();
    render(<BulletCountControls counts={[4, 4]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Increase bullets for Recent role'));
    expect(onChange).toHaveBeenCalledWith([5, 4]);
  });

  it('calls onChange with decremented count', () => {
    const onChange = vi.fn();
    render(<BulletCountControls counts={[4, 4]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Decrease bullets for Recent role'));
    expect(onChange).toHaveBeenCalledWith([3, 4]);
  });

  it('disables decrement at minimum', () => {
    render(<BulletCountControls counts={[BULLET_COUNT_MIN, 4]} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Decrease bullets for Recent role')).toBeDisabled();
  });

  it('disables increment at maximum', () => {
    render(<BulletCountControls counts={[BULLET_COUNT_MAX, 4]} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Increase bullets for Recent role')).toBeDisabled();
  });

  it('decrement enabled above minimum', () => {
    render(<BulletCountControls counts={[3, 4]} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Decrease bullets for Recent role')).not.toBeDisabled();
  });

  it('increment enabled below maximum', () => {
    render(<BulletCountControls counts={[4, 4]} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Increase bullets for Recent role')).not.toBeDisabled();
  });

  it('adjusts previous role independently', () => {
    const onChange = vi.fn();
    render(<BulletCountControls counts={[4, 4]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Decrease bullets for Previous role'));
    expect(onChange).toHaveBeenCalledWith([4, 3]);
  });

  it('shows default count hint', () => {
    render(<BulletCountControls counts={DEFAULT_BULLET_COUNTS} onChange={vi.fn()} />);
    expect(screen.getByText(/Default is 4/)).toBeInTheDocument();
  });
});
