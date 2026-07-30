import { useEffect, useRef, useState } from 'react';
import { toPdfFileName } from '../../../lib/download';

const DEFAULT_BASE_NAME = 'darshan_aswathappa_';

interface Props {
  /** Initial value for the name field. Defaults to the house prefix. */
  defaultBaseName?: string;
  /** Fires with the finished filename (including the `.pdf` extension). */
  onConfirm: (fileName: string) => void;
  onClose: () => void;
}

/**
 * Small modal that lets the user name the PDF before it downloads. The base
 * name is pre-filled with the house prefix so they only type the suffix; the
 * `.pdf` extension is appended for them. Mirrors AbSetupModal's shell
 * conventions (backdrop, focus trap, Escape-to-close).
 */
export function DownloadDialog({
  defaultBaseName = DEFAULT_BASE_NAME,
  onConfirm,
  onClose,
}: Props) {
  const [name, setName] = useState(defaultBaseName);
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const canSubmit = name.trim().length > 0;

  // Focus the field on open and place the caret at the end so the user can
  // keep typing straight after the prefix. Restore focus to the trigger on close.
  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    const input = inputRef.current;
    if (input) {
      input.focus();
      const end = input.value.length;
      input.setSelectionRange(end, end);
    }
    return () => restoreTo?.focus?.();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleConfirm = (): void => {
    if (!canSubmit) return;
    onConfirm(toPdfFileName(name));
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    handleConfirm();
  };

  return (
    <div
      className="fixed inset-0 bg-ink/40 backdrop-blur-[2px] flex items-stretch sm:items-center justify-center z-50 sm:p-4"
      style={{
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="download-dialog-title"
        tabIndex={-1}
        className="bg-paper border-rule w-full sm:max-w-md sm:rounded-[4px] sm:border sm:shadow-[0_24px_60px_rgba(28,27,25,0.25)] overflow-hidden flex flex-col focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-5 sm:px-7 pt-5 sm:pt-6 pb-4 border-b border-rule shrink-0">
          <div>
            <span className="eyebrow">Download PDF</span>
            <h2
              id="download-dialog-title"
              className="font-serif text-[22px] sm:text-[24px] leading-tight text-ink mt-1"
            >
              Name your file
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-ink-faint hover:text-ink text-lg leading-none inline-flex items-center justify-center min-w-11 min-h-11 -mr-2"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col">
          <div className="px-5 sm:px-7 py-5">
            <label
              htmlFor="download-filename"
              className="eyebrow block mb-2"
            >
              File name
            </label>
            <div className="flex items-center border border-rule rounded-[3px] bg-paper-raised focus-within:border-accent transition-colors">
              <input
                id="download-filename"
                ref={inputRef}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="flex-1 min-w-0 bg-transparent px-3 min-h-11 h-11 text-[14px] font-mono text-ink focus:outline-none"
                autoComplete="off"
                spellCheck={false}
              />
              <span className="px-3 text-[13px] font-mono text-ink-faint select-none border-l border-rule self-stretch flex items-center">
                .pdf
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end px-5 sm:px-7 py-4 border-t border-rule shrink-0 bg-paper pb-[max(0.5rem,env(safe-area-inset-bottom))]">
            <button
              type="button"
              onClick={onClose}
              className="text-[13px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-5 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors disabled:opacity-50"
            >
              Download
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
