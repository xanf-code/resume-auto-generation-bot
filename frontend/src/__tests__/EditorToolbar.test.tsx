import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EditorToolbar } from '../components/detail/editor/EditorToolbar';

describe('EditorToolbar', () => {
  it('exposes Compile and Download, but not a separate Save', () => {
    render(
      <EditorToolbar
        onCompile={() => {}}
        onDownload={() => {}}
        compiling={false}
      />,
    );

    expect(screen.getByRole('button', { name: /^Compile$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download PDF|PDF/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Save$/i })).not.toBeInTheDocument();
  });

  it('invokes onCompile when Compile is clicked', () => {
    const onCompile = vi.fn();
    render(
      <EditorToolbar
        onCompile={onCompile}
        onDownload={() => {}}
        compiling={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /^Compile$/i }));
    expect(onCompile).toHaveBeenCalledTimes(1);
  });

  it('shows Compiling… and disables actions while busy', () => {
    render(
      <EditorToolbar
        onCompile={() => {}}
        onDownload={() => {}}
        compiling={true}
      />,
    );

    const compile = screen.getByRole('button', { name: /Compiling/i });
    expect(compile).toBeDisabled();
    expect(screen.getByRole('button', { name: /Download PDF|PDF/i })).toBeDisabled();
  });
});
