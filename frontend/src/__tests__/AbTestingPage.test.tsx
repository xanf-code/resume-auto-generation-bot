import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AbTestingPage } from '../components/abtest/AbTestingPage';
import { useStore } from '../store';

function renderPage() {
  return render(
    <MemoryRouter>
      <AbTestingPage />
    </MemoryRouter>,
  );
}

describe('AbTestingPage', () => {
  beforeEach(() => {
    useStore.setState({ jobs: {} });
  });

  it('renders the empty state with a Create A/B test button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /create a\/b test/i })).toBeInTheDocument();
  });

  it('opens the setup modal when the Create A/B test button is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /create a\/b test/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('closes the setup modal on Escape and returns to the empty state', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /create a\/b test/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create a\/b test/i })).toBeInTheDocument();
  });

  it('never renders JobRail content (no applications sidebar)', () => {
    renderPage();
    expect(
      screen.queryByRole('complementary', { name: /applications/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/no applications yet/i)).not.toBeInTheDocument();
  });
});
