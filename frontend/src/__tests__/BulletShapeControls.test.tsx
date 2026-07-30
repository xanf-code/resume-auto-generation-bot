import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BulletShapeControls } from '../components/newjob/BulletShapeControls';
import type { BulletShape } from '../lib/bulletShapes';

function setup(shapes: BulletShape[] = [], onChange = vi.fn()) {
  render(<BulletShapeControls shapes={shapes} onChange={onChange} />);
  return { onChange };
}

describe('BulletShapeControls', () => {
  it('renders four checkboxes', () => {
    setup();
    expect(screen.getAllByRole('checkbox')).toHaveLength(4);
  });

  it('all checkboxes are unchecked when shapes is empty', () => {
    setup();
    for (const cb of screen.getAllByRole('checkbox')) {
      expect(cb).not.toBeChecked();
    }
  });

  it('renders the "Bullet shapes" eyebrow header', () => {
    setup();
    expect(screen.getByText(/Bullet shapes/i)).toBeInTheDocument();
  });

  it('renders a hint line about automatic rotation', () => {
    setup();
    expect(
      screen.getByText(/Leave all unchecked to rotate shapes automatically/i),
    ).toBeInTheDocument();
  });

  it('renders a help tip button for each shape', () => {
    setup();
    // HelpTip renders a "?" button with aria-label "About {label}"
    const helpButtons = screen.getAllByRole('button');
    expect(helpButtons.length).toBeGreaterThanOrEqual(4);
  });

  it('marks the PAR checkbox as checked when PAR is in shapes', () => {
    setup(['PAR']);
    const [parCb] = screen.getAllByRole('checkbox');
    expect(parCb).toBeChecked();
  });

  it('marks only the selected checkboxes as checked', () => {
    setup(['PAR', 'ACTION+STACK']);
    const [parCb, resultFirstCb, actionStackCb, contextParCb] =
      screen.getAllByRole('checkbox');
    expect(parCb).toBeChecked();
    expect(resultFirstCb).not.toBeChecked();
    expect(actionStackCb).toBeChecked();
    expect(contextParCb).not.toBeChecked();
  });

  it('calls onChange when a checkbox is toggled (add)', () => {
    const { onChange } = setup([]);
    const [parCb] = screen.getAllByRole('checkbox');
    fireEvent.click(parCb);
    expect(onChange).toHaveBeenCalledWith(['PAR']);
  });

  it('calls onChange when a checked checkbox is toggled (remove)', () => {
    const { onChange } = setup(['PAR']);
    const [parCb] = screen.getAllByRole('checkbox');
    fireEvent.click(parCb);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('clicking RESULT-FIRST when PAR is selected calls onChange with both in canonical order', () => {
    const { onChange } = setup(['PAR']);
    const [, resultFirstCb] = screen.getAllByRole('checkbox');
    fireEvent.click(resultFirstCb);
    expect(onChange).toHaveBeenCalledWith(['PAR', 'RESULT-FIRST']);
  });

  it('clicking PAR when RESULT-FIRST is selected calls onChange with both in canonical order', () => {
    const { onChange } = setup(['RESULT-FIRST']);
    const [parCb] = screen.getAllByRole('checkbox');
    fireEvent.click(parCb);
    expect(onChange).toHaveBeenCalledWith(['PAR', 'RESULT-FIRST']);
  });
});
