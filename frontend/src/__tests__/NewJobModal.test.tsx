import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NewJobModal } from '../components/newjob/NewJobModal';
import { useStore } from '../store';
import { createJob } from '../api/jobs';

vi.mock('../api/jobs', () => ({
  createJob: vi.fn(),
}));

function renderModal() {
  return render(
    <MemoryRouter>
      <NewJobModal />
    </MemoryRouter>,
  );
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText('Label'), {
    target: { value: 'Backend Engineer' },
  });
  fireEvent.change(screen.getByPlaceholderText(/LaTeX résumé/i), {
    target: { value: '\\documentclass{article}\\begin{document}x\\end{document}' },
  });
  fireEvent.change(screen.getByPlaceholderText(/job description/i), {
    target: { value: 'We are hiring a backend engineer.' },
  });
}

describe('NewJobModal', () => {
  beforeEach(() => {
    (createJob as unknown as Mock).mockReset();
    // Restore the real close action before each render (no component is mounted
    // yet, so this can't trigger an out-of-act re-render). Tests that need to
    // observe close override it with a spy before rendering.
    useStore.setState({
      closeNewJobModal: () => useStore.setState({ newJobModalOpen: false }),
    });
  });

  it('exposes dialog semantics and a labelled title', () => {
    renderModal();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'new-job-title');
    expect(document.getElementById('new-job-title')).toHaveTextContent('Feed the press');
  });

  it('moves focus to the label field on open and caps its length', () => {
    renderModal();
    const label = screen.getByLabelText('Label');
    expect(label).toHaveFocus();
    expect(label).toHaveAttribute('maxlength', '200');
  });

  it('closes on Escape while idle', () => {
    const closeSpy = vi.fn();
    useStore.setState({ closeNewJobModal: closeSpy });
    renderModal();

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it('does not close on Escape while a submission is in flight', async () => {
    const closeSpy = vi.fn();
    useStore.setState({ closeNewJobModal: closeSpy });
    // Never resolves — keeps the modal in its submitting state.
    (createJob as unknown as Mock).mockReturnValue(new Promise(() => {}));
    renderModal();

    fillRequiredFields();
    // Flush the submit handler's synchronous state flip inside act; the mocked
    // request never resolves, so the modal stays in its submitting state.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /start typesetting/i }));
    });
    expect(screen.getByText('Sending to press…')).toBeInTheDocument();

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(closeSpy).not.toHaveBeenCalled();
  });
});
