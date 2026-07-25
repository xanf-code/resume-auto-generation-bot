import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useStore } from '../../store';
import { PipelineLoader } from '../loader/PipelineLoader';
import { ThreePane } from './ThreePane';
import { LatexEditor } from './editor/LatexEditor';
import { PdfPane } from './pdf/PdfPane';
import { SkillsSidebar } from './skills/SkillsSidebar';
import { deleteJob, getJob, getJobLatex, renameJob } from '../../api/jobs';
import { StreamManager } from '../../sse/StreamManager';
import type { StreamStatus } from '../../sse/JobStream';
import { useCompletionAlert } from '../../lib/useCompletionAlert';
import { ErrorBoundary } from '../ErrorBoundary';
import type { JobSlice } from '../../store/jobsSlice';

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
    <header className="flex items-center justify-between px-6 py-4 border-b border-rule bg-paper shrink-0 gap-4">
      <div className="flex flex-col min-w-0 flex-1">
        <span className="eyebrow">Application</span>
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
            className="mt-1 font-serif text-[18px] leading-tight text-ink bg-paper-raised border border-rule px-2 py-1 rounded-[2px] focus:outline-none focus:border-accent/60 max-w-xl w-full"
            aria-label="Rename application"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="font-serif text-[18px] leading-tight text-ink truncate mt-1 text-left hover:text-accent-deep transition-colors"
            title="Click to rename"
          >
            {job.label}
          </button>
        )}
      </div>
      <div className="flex items-center gap-5 shrink-0">
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
        <span className="flex items-center gap-2">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${job.status === 'running' ? 'animate-pulse' : ''}`}
            style={{ backgroundColor: meta.color }}
          />
          <span className="text-[12px]" style={{ color: meta.color }}>
            {meta.label}
          </span>
        </span>
        <button
          type="button"
          disabled={busy}
          onClick={() => void handleDelete()}
          className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint hover:text-fail border border-rule hover:border-fail/40 px-2.5 py-1.5 rounded-[2px] transition-colors disabled:opacity-50"
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
  const markFinishedNotified = useStore((s) => s.markFinishedNotified);
  const renameInStore = useStore((s) => s.renameJob);
  const removeInStore = useStore((s) => s.removeJob);

  const [latex, setLatex] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [connState, setConnState] = useState<StreamStatus>('open');

  useCompletionAlert(job, markFinishedNotified);

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
  useEffect(() => {
    if (connState !== 'reconnecting' || !jobId) return;
    let cancelled = false;
    const reconcile = () => {
      getJob(jobId)
        .then((detail) => {
          if (cancelled) return;
          syncJob(detail);
          if (detail.status === 'done' || detail.status === 'failed') {
            streamManager.stop(jobId);
          }
        })
        .catch(() => {
          /* backend still unreachable — keep retrying until the stream recovers */
        });
    };
    reconcile();
    const id = window.setInterval(reconcile, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [connState, jobId, syncJob]);

  useEffect(() => {
    if (job?.status === 'done' && latex === null && jobId) {
      getJobLatex(jobId)
        .then(setLatex)
        .catch(() => setLatex(''));
    }
  }, [job?.status]);

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
    removeInStore(jobId);
    navigate('/');
  };

  const isDone = job.status === 'done';
  const isFailed = job.status === 'failed';

  const main = isFailed ? (
    <div className="p-8 max-w-2xl mx-auto">
      <span className="eyebrow" style={{ color: 'var(--color-fail)' }}>
        Press jam
      </span>
      <h2 className="font-serif text-[26px] text-ink mt-2 mb-3">
        This run didn't finish.
      </h2>
      <p className="font-mono text-[13px] leading-relaxed text-ink-soft border-l-2 border-fail pl-4">
        {job.error ?? 'Unknown error.'}
      </p>
    </div>
  ) : isDone && latex !== null ? (
    <LatexEditor jobId={jobId!} initialLatex={latex} onPdfReady={setPdfBlob} />
  ) : isDone ? (
    <div className="flex items-center justify-center h-full font-serif italic text-[16px] text-ink-faint">
      Loading manuscript…
    </div>
  ) : (
    <PipelineLoader job={job} />
  );

  const reconnecting = connState === 'reconnecting' && !isDone && !isFailed;

  return (
    <div className="flex flex-col h-full min-h-0">
      <WorkspaceHeader job={job} onRename={handleRename} onDelete={handleDelete} />
      {reconnecting && (
        <div className="flex items-center gap-2 px-6 py-1.5 bg-accent-wash border-b border-rule shrink-0">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-[12px] text-ink-soft">
            Lost contact with the press — reconnecting…
          </span>
        </div>
      )}
      <ThreePane
        main={<ErrorBoundary>{main}</ErrorBoundary>}
        proof={
          <ErrorBoundary title="Proof error" message="This proof couldn't be displayed.">
            <PdfPane pdfBlob={pdfBlob} running={!isDone && !isFailed} />
          </ErrorBoundary>
        }
        skills={<SkillsSidebar jobId={jobId!} ready={isDone} />}
      />
    </div>
  );
}
