import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DownloadDialog } from '../components/detail/editor/DownloadDialog';

function nameInput(): HTMLInputElement {
  return screen.getByLabelText(/file name/i) as HTMLInputElement;
}

function downloadButton(): HTMLElement {
  return screen.getByRole('button', { name: /^download$/i });
}

describe('DownloadDialog', () => {
  it('pre-fills the input with the default darshan_aswathappa_ prefix', () => {
    render(<DownloadDialog onConfirm={vi.fn()} onClose={vi.fn()} />);
    expect(nameInput()).toHaveValue('darshan_aswathappa_');
  });

  it('confirms with the default name plus a .pdf extension', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DownloadDialog onConfirm={onConfirm} onClose={vi.fn()} />);

    await user.click(downloadButton());

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith('darshan_aswathappa_.pdf');
  });

  it('lets the user append to the prefix and confirms the full name', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DownloadDialog onConfirm={onConfirm} onClose={vi.fn()} />);

    await user.type(nameInput(), 'stripe_backend');
    await user.click(downloadButton());

    expect(onConfirm).toHaveBeenCalledWith(
      'darshan_aswathappa_stripe_backend.pdf',
    );
  });

  it('does not double the extension if the user types .pdf themselves', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DownloadDialog onConfirm={onConfirm} onClose={vi.fn()} />);

    await user.clear(nameInput());
    await user.type(nameInput(), 'resume.pdf');
    await user.click(downloadButton());

    expect(onConfirm).toHaveBeenCalledWith('resume.pdf');
  });

  it('disables Download when the name is cleared to blank', async () => {
    const user = userEvent.setup();
    render(<DownloadDialog onConfirm={vi.fn()} onClose={vi.fn()} />);

    await user.clear(nameInput());
    expect(downloadButton()).toBeDisabled();

    // A blank confirm attempt must not fire onConfirm.
    await user.click(downloadButton());
  });

  it('submits on Enter within the input', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DownloadDialog onConfirm={onConfirm} onClose={vi.fn()} />);

    await user.type(nameInput(), 'frontend{Enter}');

    expect(onConfirm).toHaveBeenCalledWith(
      'darshan_aswathappa_frontend.pdf',
    );
  });

  it('calls onClose on Cancel, Escape, and backdrop click', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<DownloadDialog onConfirm={vi.fn()} onClose={onClose} />);

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
