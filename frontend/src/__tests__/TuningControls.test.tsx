import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TuningControls } from '../components/newjob/TuningControls';
import { DEFAULT_TUNING, type Tuning } from '../lib/tuning';

function setup(tuning: Tuning = DEFAULT_TUNING) {
  const onChange = vi.fn();
  render(<TuningControls tuning={tuning} onChange={onChange} />);
  return { onChange };
}

describe('TuningControls', () => {
  it('renders all six scalar sliders by default (always visible)', () => {
    setup();
    const val = (name: string) =>
      (screen.getByLabelText(name) as HTMLInputElement).value;
    expect(val('Pass threshold')).toBe('78');
    expect(val('Plausibility floor')).toBe('20');
    expect(val('Max revision rounds')).toBe('4');
    expect(val('Compile retries')).toBe('2');
    expect(val('Identity retries')).toBe('2');
    expect(val('Bullet-length retries')).toBe('3');
  });

  it('exposes a keyboard-reachable help tip that explains a field on focus', () => {
    setup();
    const help = screen.getByRole('button', { name: /about pass threshold/i });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.focus(help);
    expect(screen.getByRole('tooltip')).toHaveTextContent(/composite score/i);
  });

  it('emits a changed scalar value as a number', () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByLabelText('Pass threshold'), {
      target: { value: '90' },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ threshold: 90 }),
    );
  });

  it('live-balances rubric weights so they keep summing to 100%', () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByLabelText('Keyword match'), {
      target: { value: '0.5' },
    });
    const arg = onChange.mock.calls.at(-1)![0] as Tuning;
    const sum = Object.values(arg.rubric_weights).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 6);
    expect(arg.rubric_weights.keyword_match).toBeCloseTo(0.5, 6);
  });

  it('shows a live sum readout for the rubric weights', () => {
    setup();
    expect(screen.getByText(/Σ\s*100%/)).toBeInTheDocument();
  });
});
