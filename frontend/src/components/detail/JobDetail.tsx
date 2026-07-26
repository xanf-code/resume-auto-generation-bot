import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useStore } from '../../store';
import { PipelineLoader } from '../loader/PipelineLoader';
import { ThreePane } from './ThreePane';
import { LatexEditor, type LatexEditorHandle } from './editor/LatexEditor';
import { PdfPane } from './pdf/PdfPane';
import { SkillsSidebar } from './skills/SkillsSidebar';
import { ScoresPane } from './scores/ScoresPane';
import { cancelJob, deleteJob, getJob, getJobLatex, renameJob } from '../../api/jobs';
import { StreamManager } from '../../sse/StreamManager';
import type { StreamStatus } from '../../sse/JobStream';
import { ErrorBoundary } from '../ErrorBoundary';
import type { JobSlice } from '../../store/jobsSlice';
import type { PaneId } from './ThreePane';
import { formatClassification } from '../../lib/classification';

const streamManager = new StreamManager();

const STATUS_META: Record<JobSlice['status'], { label: string; color: string }> = {
  queued: { label: 'Queued', color: 'var(--color-ink-faint)' },
  running: { label: 'On the press', color: 'var(--color-accent)' },
  done: { label: 'Set', color: 'var(--color-pass)' },
  failed: { label: 'Failed', color: 'var(--color-fail)' },
};

function WorkspaceHeader({
  job,
  onRename,
  onDelete,
}: {
  job: JobSlice;
  onRename: (label: string) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const meta = STATUS_META[job.status];
  const classification = formatClassification(job.role, job.domains);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(job.label);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) setDraft(job.label);
  }, [job.label, editing]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const commitRename = async () => {
    const next = draft.trim();
    if (!next || next === job.label) {
      setDraft(job.label);
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      await onRename(next);
      setEditing(false);
    } catch {
      setDraft(job.label);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (
      !window.confirm(
        `Delete “${job.label}”? This removes the application and its artifacts.`,
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await onDelete();
    } finally {
      setBusy(false);
    }
  };

  return (
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-rule bg-paper shrink-0 gap-3 sm:gap-4">
      <div className="flex flex-col min-w-0 flex-1">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="lg:hidden font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint hover:text-ink min-h-9 inline-flex items-center"
          >
            ← Desk
          </Link>
          <span className="eyebrow hidden lg:inline">Application</span>
        </div>
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => void commitRename()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void commitRename();
              } else if (e.key === 'Escape') {
                setDraft(job.label);
                setEditing(false);
              }
            }}
            className="mt-1 font-serif text-[17px] sm:text-[18px] leading-tight text-ink bg-paper-raised border border-rule px-2 py-1 rounded-[2px] focus:outline-none focus:border-accent/60 max-w-xl w-full"
            aria-label="Rename application"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="font-serif text-[17px] sm:text-[18px] leading-tight text-ink truncate mt-1 text-left hover:text-accent-deep transition-colors"
            title="Click to rename"
          >
            {job.label}
          </button>
        )}
        {classification && (
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint mt-1">
            {classification}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 sm:gap-5 shrink-0 flex-wrap">
        {job.aggregateScore !== undefined && (
          <div className="flex items-baseline gap-1.5">
            <span className="eyebrow text-[10px]">Score</span>
            <span
              className="font-mono text-[15px] tabular-nums"
              style={{
                color: job.passed === false ? 'var(--color-fail)' : 'var(--color-ink)',
              }}
            >
              {Math.round(job.aggregateScore)}
            </span>
          </div>
        )}
        {job.status !== 'done' && (
          <span className="flex items-center gap-2">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${job.status === 'running' ? 'animate-pulse' : ''}`}
              style={{ backgroundColor: meta.color }}
            />
            <span className="text-[12px]" style={{ color: meta.color }}>
              {meta.label}
            </span>
          </span>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => void handleDelete()}
          className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint hover:text-fail border border-rule hover:border-fail/40 px-2.5 min-h-9 inline-flex items-center rounded-[2px] transition-colors disabled:opacity-50"
        >
          Delete
        </button>
      </div>
    </header>
  );
}

export function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const job = useStore((s) => (jobId ? s.jobs[jobId] : undefined));
  const applyEvent = useStore((s) => s.applyEvent);
  const syncJob = useStore((s) => s.syncJob);
  const renameInStore = useStore((s) => s.renameJob);
  const removeInStore = useStore((s) => s.removeJob);

  const [latex, setLatex] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [connState, setConnState] = useState<StreamStatus>('open');
  const [aborting, setAborting] = useState(false);
  const [focusRequest, setFocusRequest] = useState<{
    pane: PaneId;
    token: number;
  } | null>(null);
  const editorRef = useRef<LatexEditorHandle>(null);

  // Reset the abort-in-progress flag when switching between applications so a
  // pending abort on one job never bleeds into the view of another.
  useEffect(() => {
    setAborting(false);
  }, [jobId]);

  useEffect(() => {
    if (!job || !jobId) return;
    if (job.status === 'running' || job.status === 'queued') {
      streamManager.start(jobId, applyEvent, setConnState);
    }
    return () => {
      streamManager.stop(jobId);
    };
  }, [jobId]);

  // While the live stream is down, poll the authoritative status so a job that
  // finished (or failed) on the backend can't stay frozen mid-progress in the UI.
  // Same poll runs while a stop is in flight: cancel is cooperative (waits for
  // the in-flight LLM), and a missed terminal SSE frame must not leave the UI
  // stuck on "Stopping…" forever.
  useEffect(() => {
    const shouldPoll =
      Boolean(jobId) && (connState === 'reconnecting' || aborting);
    if (!shouldPoll || !jobId) return;
    if (job?.status === 'done' || job?.status === 'failed') return;
    let cancelled = false;
    const reconcile = () => {
      getJob(jobId)
        .then((detail) => {
          if (cancelled) return;
          syncJob(detail);
          if (detail.status === 'done' || detail.status === 'failed') {
            streamManager.stop(jobId);
            setAborting(false);
          }
        })
        .catch(() => {
          /* backend still unreachable - keep retrying until the stream recovers */
        });
    };
    reconcile();
    const id = window.setInterval(reconcile, aborting ? 2000 : 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [connState, jobId, aborting, job?.status, syncJob]);

  // Drop the local abort spinner once the store reflects a terminal status
  // (via SSE or the poll above).
  useEffect(() => {
    if (job?.status === 'done' || job?.status === 'failed') {
      setAborting(false);
    }
  }, [job?.status]);

  useEffect(() => {
    if (job?.status === 'done' && latex === null && jobId) {
      getJobLatex(jobId)
        .then(setLatex)
        .catch(() => setLatex(''));
    }
  }, [job?.status]);

  // A job that was already finished when this view opened never receives the
  // SSE frames that carry the recruiter panel's verdict, so its scores stay
  // empty. Pull the authoritative detail once to hydrate persona scores +
  // aggregate + pass/fail from score_report.json on disk. Guarded on an empty
  // panel so a job we watched finish live (already populated via SSE) is left
  // untouched and never refetched.
  useEffect(() => {
    if (!jobId || job?.status !== 'done') return;
    if (Object.keys(job.personaScores).length > 0) return;
    getJob(jobId)
      .then(syncJob)
      .catch(() => {
        /* scores stay empty - the panel keeps its placeholder */
      });
  }, [jobId, job?.status]);

  // Same gap for a job that failed before this view opened: the list endpoint
  // that seeds the store on app load has no `error` field, and there is no
  // terminal SSE frame left to carry it. Without this, the failure reason
  // collapses to the "Unknown error." placeholder even though the backend
  // recorded the real one. Guarded on a missing error so a job we watched
  // fail live (already populated via SSE) is left untouched.
  useEffect(() => {
    if (!jobId || job?.status !== 'failed' || job.error) return;
    getJob(jobId)
      .then(syncJob)
      .catch(() => {
        /* error stays empty - the view keeps its "Unknown error." fallback */
      });
  }, [jobId, job?.status, job?.error]);

  if (!job) {
    return (
      <div className="flex items-center justify-center h-full font-serif italic text-[16px] text-ink-faint">
        Application not found.
      </div>
    );
  }

  const handleRename = async (label: string) => {
    if (!jobId) return;
    const updated = await renameJob(jobId, label);
    renameInStore(jobId, updated.label);
  };

  const handleDelete = async () => {
    if (!jobId) return;
    streamManager.stop(jobId);
    await deleteJob(jobId);
    navigate('/', { replace: true });
    removeInStore(jobId);
  };

  // Request abort; the backend stops at the next node boundary and pushes a
  // terminal "failed" frame, which flips this view to the stopped state. Keep
  // `aborting` set on success so the button stays disabled until that arrives.
  const handleAbort = async () => {
    if (!jobId) return;
    setAborting(true);
    try {
      await cancelJob(jobId);
    } catch {
      setAborting(false);
    }
  };

  const isDone = job.status === 'done';
  const isFailed = job.status === 'failed';

  // PDF text-layer dblclick → reveal Editor tab (narrow) and select the match.
  const handleSyncToSource = (text: string) => {
    setFocusRequest({ pane: 'main', token: Date.now() });
    // Let the tab switch commit before focusing CodeMirror.
    window.requestAnimationFrame(() => {
      editorRef.current?.jumpToText(text);
    });
  };

  const main = isFailed ? (
    <div className="p-8 max-w-2xl mx-auto">
      <span className="eyebrow" style={{ color: 'var(--color-fail)' }}>
        {(job.error ?? '').toLowerCase().includes('stopped')
          ? 'Stopped'
          : 'Press jam'}
      </span>
      <h2 className="font-serif text-[26px] text-ink mt-2 mb-3">
        {(job.error ?? '').toLowerCase().includes('stopped')
          ? 'You stopped this run.'
          : "This run didn't finish."}
      </h2>
      <p className="font-mono text-[13px] leading-relaxed text-ink-soft border-l-2 border-fail pl-4">
        {job.error ?? 'Unknown error.'}
      </p>
    </div>
  ) : isDone && latex !== null ? (
    <LatexEditor
      ref={editorRef}
      jobId={jobId!}
      initialLatex={latex}
      onPdfReady={setPdfBlob}
    />
  ) : isDone ? (
    <div className="flex items-center justify-center h-full font-serif italic text-[16px] text-ink-faint">
      Loading manuscript…
    </div>
  ) : (
    <PipelineLoader job={job} onAbort={() => void handleAbort()} aborting={aborting} />
  );

  const reconnecting = connState === 'reconnecting' && !isDone && !isFailed;

  return (
    <div className="flex flex-col h-full min-h-0">
      <WorkspaceHeader job={job} onRename={handleRename} onDelete={handleDelete} />
      {reconnecting && (
        <div className="flex items-center gap-2 px-4 sm:px-6 py-1.5 bg-accent-wash border-b border-rule shrink-0">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-[12px] text-ink-soft">
            Lost contact with the press - reconnecting…
          </span>
        </div>
      )}
      <ThreePane
        focusRequest={focusRequest}
        main={<ErrorBoundary>{main}</ErrorBoundary>}
        proof={
          <ErrorBoundary title="Proof error" message="This proof couldn't be displayed.">
            <PdfPane
              pdfBlob={pdfBlob}
              running={!isDone && !isFailed}
              onSyncToSource={isDone ? handleSyncToSource : undefined}
            />
          </ErrorBoundary>
        }
        scores={
          <ErrorBoundary title="Scores error" message="These scores couldn't be displayed.">
            <ScoresPane
              personaScores={job.personaScores}
              aggregateScore={job.aggregateScore}
              passed={job.passed}
            />
          </ErrorBoundary>
        }
        skills={<SkillsSidebar jobId={jobId!} ready={isDone} />}
      />
    </div>
  );
}
