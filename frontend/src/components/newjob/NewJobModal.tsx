import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileOrPasteField } from './FileOrPasteField';
import { createJob } from '../../api/jobs';
import { useStore } from '../../store';

export function NewJobModal() {
  const closeModal = useStore((s) => s.closeNewJobModal);
  const addJob = useStore((s) => s.addJob);
  const navigate = useNavigate();

  const [label, setLabel] = useState('');
  const [resumeTex, setResumeTex] = useState('');
  const [jdText, setJdText] = useState('');
  const [enableScoring, setEnableScoring] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeModal();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [closeModal]);

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
      className="fixed inset-0 bg-ink/40 backdrop-blur-[2px] flex items-center justify-center z-50 p-4"
      onClick={closeModal}
    >
      <div
        className="bg-paper border border-rule w-full max-w-2xl rounded-[4px] shadow-[0_24px_60px_rgba(28,27,25,0.25)] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-8 pt-7 pb-5 border-b border-rule">
          <div>
            <span className="eyebrow">New application</span>
            <h2 className="font-serif text-[26px] leading-tight text-ink mt-1">
              Feed the press
            </h2>
          </div>
          <button
            onClick={closeModal}
            className="text-ink-faint hover:text-ink text-lg leading-none p-1 -mr-1"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5 px-8 py-6">
          <div className="flex flex-col gap-2">
            <label className="eyebrow" htmlFor="job-label">
              Label
            </label>
            <input
              id="job-label"
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Vestwell — Backend Engineer"
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
            Run the recruiter panel and score each revision
          </label>

          {error && (
            <p className="text-[13px] text-fail border border-fail/30 bg-[#fbeeec] px-3 py-2 rounded-[3px]">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-rule">
            <button
              type="button"
              onClick={closeModal}
              className="text-[13px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-4 h-9 rounded-[3px] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-5 h-9 rounded-[3px] transition-colors disabled:opacity-50"
            >
              {submitting ? 'Sending to press…' : 'Start typesetting'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
