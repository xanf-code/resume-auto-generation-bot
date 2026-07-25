import { useEffect, useRef, useState } from 'react';
import type { JobSlice } from '../../store/jobsSlice';

interface Props {
  job: JobSlice;
  index: number;
  active: boolean;
  onClick: () => void;
  onRename: (label: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

const STATUS_COLOR: Record<JobSlice['status'], string> = {
  queued: 'var(--color-ink-faint)',
  running: 'var(--color-accent)',
  done: 'var(--color-pass)',
  failed: 'var(--color-fail)',
};

function statusLine(job: JobSlice): string {
  switch (job.status) {
    case 'running':
      return job.humanLabel ?? 'Working…';
    case 'queued':
      return 'Queued';
    case 'done':
      return job.passed === false ? 'Complete · below bar' : 'Complete';
    case 'failed':
      return 'Failed';
  }
}

export function JobRailItem({
  job,
  index,
  active,
  onClick,
  onRename,
  onDelete,
}: Props) {
  const running = job.status === 'running' || job.status === 'queued';
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

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
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
    <div
      className={`relative group w-full text-left pl-6 pr-3 py-4 border-b border-rule flex items-baseline gap-3 transition-colors ${
        active ? 'bg-accent-wash' : 'hover:bg-black/[0.025]'
      }`}
    >
      {(active || running) && (
        <span className="absolute left-0 top-0 bottom-0 w-[2px] bg-accent" />
      )}
      <button
        type="button"
        onClick={onClick}
        className="font-mono text-[11px] text-ink-faint tabular-nums w-5 shrink-0 pt-0.5 text-left"
        aria-label={`Open ${job.label}`}
      >
        {String(index + 1).padStart(2, '0')}
      </button>
      <div className="flex-1 min-w-0">
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
            onClick={(e) => e.stopPropagation()}
            className="w-full font-serif text-[15px] leading-snug text-ink bg-paper-raised border border-rule px-1.5 py-0.5 rounded-[2px] focus:outline-none focus:border-accent/60"
            aria-label="Rename application"
          />
        ) : (
          <button
            type="button"
            onClick={onClick}
            onDoubleClick={(e) => {
              e.stopPropagation();
              setEditing(true);
            }}
            className="block w-full text-left"
          >
            <span className="block font-serif text-[15px] leading-snug text-ink truncate">
              {job.label}
            </span>
            <span
              className="block mt-1 text-[11px] leading-tight truncate"
              style={{ color: STATUS_COLOR[job.status] }}
            >
              {statusLine(job)}
            </span>
          </button>
        )}
      </div>
      {!editing && (
        <div className="flex items-center gap-0.5 shrink-0 opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
          <button
            type="button"
            disabled={busy}
            onClick={(e) => {
              e.stopPropagation();
              setEditing(true);
            }}
            className="font-mono text-[10px] uppercase tracking-wider text-ink-faint hover:text-ink px-1.5 min-h-9 min-w-9 inline-flex items-center justify-center"
            aria-label={`Rename ${job.label}`}
            title="Rename"
          >
            Edit
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={handleDelete}
            className="font-mono text-[10px] uppercase tracking-wider text-ink-faint hover:text-fail px-1.5 min-h-9 min-w-9 inline-flex items-center justify-center"
            aria-label={`Delete ${job.label}`}
            title="Delete"
          >
            Del
          </button>
        </div>
      )}
      {job.aggregateScore !== undefined && !editing && (
        <span
          className="font-mono text-[13px] tabular-nums shrink-0 [@media(hover:hover)]:group-hover:hidden"
          style={{
            color: job.passed === false ? 'var(--color-fail)' : 'var(--color-ink-soft)',
          }}
        >
          {Math.round(job.aggregateScore)}
        </span>
      )}
    </div>
  );
}
