import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { AggregateGauge } from '../components/loader/AggregateGauge';

const CIRCUMFERENCE = 2 * Math.PI * 40;

// The progress arc is the second <circle> (the first is the track).
function arcOffset(container: HTMLElement): number {
  const arc = container.querySelectorAll('circle')[1];
  return Number(arc.getAttribute('stroke-dashoffset'));
}

describe('AggregateGauge', () => {
  it('renders the rounded score', () => {
    const { getByText } = render(<AggregateGauge score={81.6} />);
    expect(getByText('82')).toBeInTheDocument();
  });

  it('shows a placeholder when no score is present', () => {
    const { getByText } = render(<AggregateGauge score={undefined} />);
    expect(getByText('—')).toBeInTheDocument();
  });

  it('treats a non-finite score as no score', () => {
    const { getByText } = render(<AggregateGauge score={NaN} />);
    expect(getByText('—')).toBeInTheDocument();
  });

  it('clamps a negative score so the arc empties rather than inverting', () => {
    const { container } = render(<AggregateGauge score={-40} />);
    const offset = arcOffset(container);
    expect(offset).toBeGreaterThanOrEqual(0);
    expect(offset).toBeLessThanOrEqual(CIRCUMFERENCE);
    expect(offset).toBeCloseTo(CIRCUMFERENCE, 1);
  });

  it('clamps a score above 100 so the arc fills rather than overshooting', () => {
    const { container } = render(<AggregateGauge score={140} />);
    const offset = arcOffset(container);
    expect(offset).toBeGreaterThanOrEqual(0);
    expect(offset).toBeLessThanOrEqual(CIRCUMFERENCE);
    expect(offset).toBeCloseTo(0, 1);
  });
});
