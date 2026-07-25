import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThreePane } from '../components/detail/ThreePane';
import { useMediaQuery } from '../hooks/useMediaQuery';
import { useStore } from '../store';

vi.mock('../hooks/useMediaQuery', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useMediaQuery')>();
  return { ...actual, useMediaQuery: vi.fn() };
});

const mockMediaQuery = useMediaQuery as unknown as Mock;

function renderPane() {
  return render(
    <ThreePane
      main={<div>MAIN_CONTENT</div>}
      proof={<div>PROOF_CONTENT</div>}
      scores={<div>SCORES_CONTENT</div>}
      skills={<div>SKILLS_CONTENT</div>}
    />,
  );
}

describe('ThreePane — Scores tab', () => {
  beforeEach(() => {
    mockMediaQuery.mockReset();
    useStore.setState({ scoresSidebarCollapsed: true, skillsSidebarCollapsed: false });
  });

  describe('narrow layout (segmented tabs)', () => {
    beforeEach(() => {
      mockMediaQuery.mockReturnValue(false);
    });

    it('exposes a Scores tab alongside the other panes', () => {
      renderPane();
      expect(screen.getByRole('tab', { name: 'Editor' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Proof' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Scores' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Skills' })).toBeInTheDocument();
    });

    it('defaults to the Editor pane', () => {
      renderPane();
      expect(screen.getByRole('tab', { name: 'Editor' })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      expect(screen.getByRole('tab', { name: 'Scores' })).toHaveAttribute(
        'aria-selected',
        'false',
      );
    });

    it('reveals the scores content when the Scores tab is clicked', () => {
      renderPane();
      fireEvent.click(screen.getByRole('tab', { name: 'Scores' }));
      expect(screen.getByRole('tab', { name: 'Scores' })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      expect(screen.getByText('SCORES_CONTENT')).toBeVisible();
    });

    it('keeps all panes mounted so state survives tab switches', () => {
      renderPane();
      // Scores content is present in the DOM even while the manuscript tab is active.
      expect(screen.getByText('SCORES_CONTENT')).toBeInTheDocument();
    });
  });

  describe('wide layout (side-by-side panes)', () => {
    beforeEach(() => {
      mockMediaQuery.mockReturnValue(true);
    });

    it('renders the scores content in its own aside when expanded', () => {
      useStore.setState({ scoresSidebarCollapsed: false });
      renderPane();
      expect(screen.getByText('SCORES_CONTENT')).toBeVisible();
    });

    it('offers an expand affordance when the scores aside is collapsed', () => {
      useStore.setState({ scoresSidebarCollapsed: true });
      renderPane();
      expect(
        screen.getByRole('button', { name: /expand scores/i }),
      ).toBeInTheDocument();
    });
  });
});
