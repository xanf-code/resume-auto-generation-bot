import { describe, it, expect, vi, afterEach, type Mock } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CopyButton } from '../components/detail/skills/CopyButton';

function setClipboard(value: unknown): void {
  Object.defineProperty(navigator, 'clipboard', { value, configurable: true });
}

// jsdom doesn't implement execCommand, so define a stub we can control.
function setExecCommand(result: boolean): Mock {
  const exec = vi.fn().mockReturnValue(result);
  Object.defineProperty(document, 'execCommand', { value: exec, configurable: true });
  return exec;
}

describe('CopyButton', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows "Copied" after a successful async clipboard write', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setClipboard({ writeText });
    render(<CopyButton text="Python, Go" />);

    fireEvent.click(screen.getByRole('button', { name: /copy/i }));

    expect(await screen.findByText('Copied')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith('Python, Go');
  });

  it('falls back to execCommand when the async clipboard is unavailable', async () => {
    // Insecure origin: navigator.clipboard is undefined.
    setClipboard(undefined);
    const exec = setExecCommand(true);
    render(<CopyButton text="fallback" />);

    fireEvent.click(screen.getByRole('button', { name: /copy/i }));

    expect(await screen.findByText('Copied')).toBeInTheDocument();
    expect(exec).toHaveBeenCalledWith('copy');
  });

  it("surfaces a failure state when every copy path fails", async () => {
    setClipboard({ writeText: (vi.fn() as Mock).mockRejectedValue(new Error('denied')) });
    setExecCommand(false);
    render(<CopyButton text="nope" />);

    fireEvent.click(screen.getByRole('button', { name: /copy/i }));

    expect(await screen.findByText(/couldn't copy/i)).toBeInTheDocument();
  });
});
