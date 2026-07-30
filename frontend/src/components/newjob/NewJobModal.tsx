import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileOrPasteField } from './FileOrPasteField';
import { ModelControls } from './ModelControls';
import { TuningControls } from './TuningControls';
import { BulletShapeControls } from './BulletShapeControls';
import { createJob } from '../../api/jobs';
import {
  DEFAULT_MODELS,
  matchPreset,
  presetLabel,
  type ModelsConfig,
} from '../../lib/models';
import { DEFAULT_TUNING, type Tuning } from '../../lib/tuning';
import { DEFAULT_BULLET_SHAPES, type BulletShape } from '../../lib/bulletShapes';
import { useStore } from '../../store';

type MobilePane = 'inputs' | 'config';

export function NewJobModal() {
  const closeModal = useStore((s) => s.closeNewJobModal);
  const addJob = useStore((s) => s.addJob);
  const navigate = useNavigate();

  const [label, setLabel] = useState('');
  const [resumeTex, setResumeTex] = useState('');
  const [jdText, setJdText] = useState('');
  const [enableScoring, setEnableScoring] = useState(false);
  const [obsidianLearnOff, setObsidianLearnOff] = useState(false);
  const [tuning, setTuning] = useState<Tuning>(DEFAULT_TUNING);
  const [models, setModels] = useState<ModelsConfig>(DEFAULT_MODELS);
  const [bulletShapes, setBulletShapes] = useState<BulletShape[]>(DEFAULT_BULLET_SHAPES);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [mobilePane, setMobilePane] = useState<MobilePane>('inputs');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLInputElement>(null);

  const canSubmit =
    label.trim() !== '' && resumeTex.trim() !== '' && jdText.trim() !== '';
  const activePreset = matchPreset(models);

  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    labelRef.current?.focus();
    return () => restoreTo?.focus?.();
  }, []);

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
      setError('A label, a resume, and a job description are all required.');
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
        models,
        bullet_shapes: bulletShapes,
        obsidian_learn: !obsidianLearnOff,
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
        className="bg-paper border-rule w-full sm:max-w-6xl sm:rounded-[4px] sm:border sm:shadow-[0_24px_60px_rgba(28,27,25,0.25)] h-dvh sm:h-[min(90vh,880px)] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-5 sm:px-7 pt-5 sm:pt-6 pb-4 border-b border-rule shrink-0">
          <div>
            <span className="eyebrow">New application</span>
            <h2
              id="new-job-title"
              className="font-serif text-[22px] sm:text-[26px] leading-tight text-ink mt-1"
            >
              Feed the press
            </h2>
            <p className="text-[13px] text-ink-soft mt-1.5 max-w-md leading-snug">
              Paste a master resume and job description — the desk rewrites,
              scores, and typesets a submission-ready PDF.
            </p>
          </div>
          <button
            onClick={closeModal}
            className="text-ink-faint hover:text-ink text-lg leading-none inline-flex items-center justify-center min-w-11 min-h-11 -mr-2"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Mobile pane switcher */}
        <div
          className="md:hidden flex border-b border-rule shrink-0"
          role="tablist"
          aria-label="Playground panes"
        >
          {(
            [
              ['inputs', 'Inputs'],
              ['config', 'Configuration'],
            ] as const
          ).map(([id, labelText]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mobilePane === id}
              onClick={() => setMobilePane(id)}
              className={`flex-1 text-[13px] py-2.5 transition-colors ${
                mobilePane === id
                  ? 'text-ink border-b-2 border-accent font-medium'
                  : 'text-ink-soft'
              }`}
            >
              {labelText}
            </button>
          ))}
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col flex-1 min-h-0"
        >
          <div className="flex-1 min-h-0 grid md:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
            <div
              data-testid="playground-inputs"
              className={`flex flex-col gap-5 px-5 sm:px-7 py-5 overflow-y-auto min-h-0 ${
                mobilePane === 'inputs' ? 'flex' : 'hidden md:flex'
              }`}
            >
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
                label="resume · main.tex"
                value={resumeTex}
                onChange={setResumeTex}
                placeholder="Paste your LaTeX resume source here…"
                accept=".tex"
                rows={9}
              />

              <FileOrPasteField
                label="Job description"
                value={jdText}
                onChange={setJdText}
                placeholder="Paste the job description here…"
                accept=".txt,.md"
                rows={5}
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

              <label className="flex items-center gap-2.5 text-[13px] text-ink-soft cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={obsidianLearnOff}
                  onChange={(e) => setObsidianLearnOff(e.target.checked)}
                  className="accent-[#c0362c] w-4 h-4"
                />
                Turn off Obsidian learning
              </label>
            </div>

            <aside
              data-testid="playground-config"
              className={`flex flex-col gap-5 px-5 sm:px-6 py-5 overflow-y-auto min-h-0 border-t md:border-t-0 md:border-l border-rule bg-paper-sunk/40 ${
                mobilePane === 'config' ? 'flex' : 'hidden md:flex'
              }`}
            >
              <ModelControls
                models={models}
                onChange={setModels}
                showScoring={enableScoring}
                showRoleDetails={false}
              />

              <div className="border-t border-rule pt-4">
                <button
                  type="button"
                  aria-expanded={advancedOpen}
                  onClick={() => setAdvancedOpen((o) => !o)}
                  className="flex w-full items-center justify-between gap-2 text-[12px] font-medium text-ink-soft hover:text-ink transition-colors"
                >
                  <span>Advanced</span>
                  <span className="font-mono text-[11px] text-ink-faint" aria-hidden>
                    {advancedOpen ? '−' : '+'}
                  </span>
                </button>
                {advancedOpen && (
                  <div className="mt-4 flex flex-col gap-6">
                    <ModelControls
                      models={models}
                      onChange={setModels}
                      showScoring={enableScoring}
                      showPresets={false}
                      showRoleDetails
                    />
                    <div className="border-t border-rule pt-5">
                      <TuningControls
                        tuning={tuning}
                        onChange={setTuning}
                        showRubric={enableScoring}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-rule pt-4">
                <BulletShapeControls
                  shapes={bulletShapes}
                  onChange={setBulletShapes}
                />
              </div>
            </aside>
          </div>

          {error && (
            <p className="mx-5 sm:mx-7 mb-2 text-[13px] text-fail border border-fail/30 bg-[#fbeeec] px-3 py-2 rounded-[3px] break-words shrink-0">
              {error}
            </p>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-5 sm:px-7 py-4 border-t border-rule shrink-0 bg-paper pb-[max(0.5rem,env(safe-area-inset-bottom))]">
            <p
              className="text-[12px] text-ink-faint font-mono tabular-nums order-2 sm:order-1"
              data-testid="config-summary"
            >
              {presetLabel(activePreset)}
              <span className="mx-1.5 text-rule">·</span>
              Scoring {enableScoring ? 'on' : 'off'}
            </p>
            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-3 order-1 sm:order-2">
              <button
                type="button"
                onClick={closeModal}
                className="text-[13px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !canSubmit}
                title={
                  canSubmit
                    ? undefined
                    : 'Add a label, resume, and job description to continue'
                }
                className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-5 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors disabled:opacity-50"
              >
                {submitting ? 'Sending to press…' : 'Start typesetting'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
