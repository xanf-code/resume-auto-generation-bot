import { describe, it, expect, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ActivityLog } from '../components/loader/ActivityLog';
import type { ActivityEntry } from '../store/jobsSlice';

beforeAll(() => {
  // jsdom lacks scrollIntoView; the component calls it after mount.
  Element.prototype.scrollIntoView = () => {};
});

const entries: ActivityEntry[] = [
  { seq: 1, stage: 'writer', text: 'Drafting the first pass' },
  { seq: 2, stage: 'compile', text: 'Page overflow - bouncing back to the writer' },
];

describe('ActivityLog', () => {
  it('renders each activity line in order', () => {
    render(<ActivityLog entries={entries} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Drafting the first pass');
    expect(items[1]).toHaveTextContent('Page overflow - bouncing back to the writer');
  });

  it('renders nothing when there are no entries', () => {
    const { container } = render(<ActivityLog entries={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('exposes an aria-live region so the feed is announced', () => {
    render(<ActivityLog entries={entries} />);
    expect(screen.getByTestId('activity-log')).toHaveAttribute('aria-live', 'polite');
  });

  it('holds a fixed-height viewport that clips overflow (no layout push)', () => {
    render(<ActivityLog entries={entries} />);
    const viewport = screen.getByTestId('activity-log');
    expect(viewport.style.height).not.toBe('');
    expect(viewport).toHaveClass('overflow-hidden');
  });

  it('does not translate the list while entries fit the visible window', () => {
    render(<ActivityLog entries={entries} />);
    const list = screen.getByRole('list');
    expect(list.style.transform).toBe('translateY(0px)');
  });

  it('scrolls the list up once entries exceed the visible window', () => {
    const many: ActivityEntry[] = Array.from({ length: 6 }, (_, i) => ({
      seq: i + 1,
      stage: 'writer',
      text: `line ${i + 1}`,
    }));
    render(<ActivityLog entries={many} />);
    const list = screen.getByRole('list');
    const match = list.style.transform.match(/translateY\(-(\d+(?:\.\d+)?)px\)/);
    expect(match).not.toBeNull();
    expect(Number(match![1])).toBeGreaterThan(0);
  });
});
