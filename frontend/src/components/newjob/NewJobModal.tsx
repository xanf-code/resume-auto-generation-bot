import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileOrPasteField } from './FileOrPasteField';
import { TuningControls } from './TuningControls';
import { createJob } from '../../api/jobs';
import { DEFAULT_TUNING, type Tuning } from '../../lib/tuning';
import { useStore } from '../../store';

export function NewJobModal() {
  const closeModal = useStore((s) => s.closeNewJobModal);
  const addJob = useStore((s) => s.addJob);
  const navigate = useNavigate();

  const [label, setLabel] = useState('');
  const [resumeTex, setResumeTex] = useState('');
  const [jdText, setJdText] = useState('');
  const [enableScoring, setEnableScoring] = useState(false);
  const [tuning, setTuning] = useState<Tuning>(DEFAULT_TUNING);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLInputElement>(null);

  // Move focus into the dialog on open and hand it back to whatever was focused
  // (the trigger) on close, so keyboard users aren't dropped at the top of the
  // page behind the overlay.
  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    labelRef.current?.focus();
    return () => restoreTo?.focus?.();
  }, []);

  // Escape closes and Tab is trapped inside the dialog - but never while a
  // submission is in flight, since the job has already been created and losing
  // the modal would strand the user off the navigation.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!submitting) closeModal();
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
  }, [closeModal, submitting]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim() || !resumeTex.trim() || !jdText.trim()) {
      setError('A label, a résumé, and a job description are all required.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const job = await createJob({
        label: label.trim(),
        resume_tex: resumeTex,
        jd_text: jdText,
        enable_scoring: enableScoring,
        tuning,
      });
      addJob({ job_id: job.job_id, label: job.label });
      closeModal();
      navigate(`/jobs/${job.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-ink/40 backdrop-blur-[2px] flex items-stretch sm:items-center justify-center z-50 sm:p-4"
      style={{
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
      onClick={() => {
        if (!submitting) closeModal();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-job-title"
        className="bg-paper border-rule w-full sm:max-w-2xl sm:rounded-[4px] sm:border sm:shadow-[0_24px_60px_rgba(28,27,25,0.25)] h-dvh sm:h-auto sm:max-h-[90vh] overflow-y-auto flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-5 sm:px-8 pt-5 sm:pt-7 pb-4 sm:pb-5 border-b border-rule shrink-0">
          <div>
            <span className="eyebrow">New application</span>
            <h2
              id="new-job-title"
              className="font-serif text-[22px] sm:text-[26px] leading-tight text-ink mt-1"
            >
              Feed the press
            </h2>
          </div>
          <button
            onClick={closeModal}
            className="text-ink-faint hover:text-ink text-lg leading-none inline-flex items-center justify-center min-w-11 min-h-11 -mr-2"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5 px-5 sm:px-8 py-5 sm:py-6 flex-1">
          <div className="flex flex-col gap-2">
            <label className="eyebrow" htmlFor="job-label">
              Label
            </label>
            <input
              id="job-label"
              ref={labelRef}
              type="text"
              value={label}
              maxLength={200}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Vestwell - Backend Engineer"
              className="bg-paper-raised border border-rule text-ink text-[14px] px-3 py-2.5 rounded-[3px] focus:outline-none focus:border-accent/60 placeholder:text-ink-faint"
            />
          </div>

          <FileOrPasteField
            label="Résumé · main.tex"
            value={resumeTex}
            onChange={setResumeTex}
            placeholder="Paste your LaTeX résumé source here…"
            accept=".tex"
          />

          <FileOrPasteField
            label="Job description"
            value={jdText}
            onChange={setJdText}
            placeholder="Paste the job description here…"
            accept=".txt,.md"
          />

          <label className="flex items-center gap-2.5 text-[13px] text-ink-soft cursor-pointer select-none">
            <input
              type="checkbox"
              checked={enableScoring}
              onChange={(e) => setEnableScoring(e.target.checked)}
              className="accent-[#c0362c] w-4 h-4"
            />
            Enable recruiter persona scoring
          </label>

          <TuningControls tuning={tuning} onChange={setTuning} />

          {error && (
            <p className="text-[13px] text-fail border border-fail/30 bg-[#fbeeec] px-3 py-2 rounded-[3px] break-words">
              {error}
            </p>
          )}

          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-3 pt-4 border-t border-rule mt-auto sticky bottom-0 bg-paper pb-[max(0.5rem,env(safe-area-inset-bottom))]">
            <button
              type="button"
              onClick={closeModal}
              className="text-[13px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-5 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors disabled:opacity-50"
            >
              {submitting ? 'Sending to press…' : 'Start typesetting'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
