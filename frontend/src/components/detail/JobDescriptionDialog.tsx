import { useEffect, useRef, useState } from 'react';
import { getJobJd } from '../../api/jobs';

interface Props {
  /** Job whose stored JD input to display. */
  jobId: string;
  /** Application label, shown as the dialog title. */
  jobLabel: string;
  onClose: () => void;
}

/**
 * Read-only modal that surfaces the job description a run was tailored against.
 * The JD is a persisted pipeline input, so it is fetched lazily on open (kept
 * out of the JobDetail payload) via {@link getJobJd}. Mirrors DownloadDialog's
 * shell conventions: backdrop, focus trap, Escape-to-close.
 */
export function JobDescriptionDialog({ jobId, jobLabel, onClose }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [jdText, setJdText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setJdText(null);
    setFailed(false);
    getJobJd(jobId)
      .then((res) => {
        if (!cancelled) setJdText(res.jd_text ?? '');
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  // Move focus into the panel on open; restore it to the trigger on close.
  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
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

  const isEmpty = jdText !== null && jdText.trim().length === 0;

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
        aria-labelledby="jd-dialog-title"
        tabIndex={-1}
        className="bg-paper border-rule w-full sm:max-w-2xl sm:rounded-[4px] sm:border sm:shadow-[0_24px_60px_rgba(28,27,25,0.25)] overflow-hidden flex flex-col focus:outline-none max-h-full sm:max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 px-5 sm:px-7 pt-5 sm:pt-6 pb-4 border-b border-rule shrink-0">
          <div className="min-w-0">
            <span className="eyebrow">Job description</span>
            <h2
              id="jd-dialog-title"
              className="font-serif text-[22px] sm:text-[24px] leading-tight text-ink mt-1 truncate"
            >
              {jobLabel}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-ink-faint hover:text-ink text-lg leading-none inline-flex items-center justify-center min-w-11 min-h-11 -mr-2 shrink-0"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="px-5 sm:px-7 py-5 overflow-y-auto">
          {failed ? (
            <p className="font-mono text-[13px] text-fail">
              Could not load the job description.
            </p>
          ) : jdText === null ? (
            <p className="font-mono text-[13px] text-ink-faint">Loading…</p>
          ) : isEmpty ? (
            <p className="font-mono text-[13px] text-ink-faint">
              No job description was saved for this application.
            </p>
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-ink-soft">
              {jdText}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
