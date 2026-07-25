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
});
