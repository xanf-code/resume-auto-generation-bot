import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StageStepper } from '../components/loader/StageStepper';
import { STAGE_ORDER } from '../lib/stages';

describe('StageStepper', () => {
  it('stages before currentStage have data-status="done"', () => {
    render(<StageStepper currentStage="compile" iteration={1} />);
    const compileIdx = STAGE_ORDER.indexOf('compile');
    for (let i = 0; i < compileIdx; i++) {
      const el = screen.getByText(new RegExp(STAGE_ORDER[i])).closest('li');
      expect(el).toHaveAttribute('data-status', 'done');
    }
  });

  it('"compile" stage has data-status="current"', () => {
    render(<StageStepper currentStage="compile" iteration={1} />);
    const el = screen.getByText(/compile/).closest('li');
    expect(el).toHaveAttribute('data-status', 'current');
  });

  it('stages after currentStage have data-status="pending"', () => {
    render(<StageStepper currentStage="compile" iteration={1} />);
    const compileIdx = STAGE_ORDER.indexOf('compile');
    for (let i = compileIdx + 1; i < STAGE_ORDER.length; i++) {
      const el = screen.getByText(new RegExp(STAGE_ORDER[i])).closest('li');
      expect(el).toHaveAttribute('data-status', 'pending');
    }
  });

  it('shows iteration badge when currentStage is "writer" and iteration > 0', () => {
    render(<StageStepper currentStage="writer" iteration={2} />);
    const badge = screen.getByTestId('iteration-badge');
    expect(badge).toHaveTextContent('iter 2');
  });

  it('does not show iteration badge when stage is not "writer"', () => {
    render(<StageStepper currentStage="compile" iteration={2} />);
    expect(screen.queryByTestId('iteration-badge')).toBeNull();
  });

  it('maps a fine-grained spine stage onto the "parse" bucket', () => {
    // Regression: backend streams "generate_skills" mid-spine; the stepper must
    // light "parse" as current rather than leaving every dot pending.
    render(<StageStepper currentStage="generate_skills" iteration={1} />);
    expect(screen.getByText(/parse/).closest('li')).toHaveAttribute(
      'data-status',
      'current',
    );
    expect(screen.getByText(/init/).closest('li')).toHaveAttribute(
      'data-status',
      'done',
    );
    expect(screen.getByText(/writer/).closest('li')).toHaveAttribute(
      'data-status',
      'pending',
    );
  });

  it('maps a fine-grained scoring stage onto the "score" bucket', () => {
    render(<StageStepper currentStage="recruiter_panel" iteration={1} />);
    expect(screen.getByText(/score/).closest('li')).toHaveAttribute(
      'data-status',
      'current',
    );
    expect(screen.getByText(/compile/).closest('li')).toHaveAttribute(
      'data-status',
      'done',
    );
  });
});
