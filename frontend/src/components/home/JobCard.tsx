import { useEffect, useRef, useState } from 'react';
import type { JobSlice } from '../../store/jobsSlice';

interface Props {
  job: JobSlice;
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

const STATUS_LABEL: Record<JobSlice['status'], string> = {
  queued: 'Queued',
  running: 'Working…',
  done: 'Complete',
  failed: 'Failed',
};

function statusText(job: JobSlice): string {
  if (job.status === 'running') return job.humanLabel ?? 'Working…';
  if (job.status === 'done' && job.passed === false) return 'Complete · below bar';
  return STATUS_LABEL[job.status];
}

export function JobCard({ job, onClick, onRename, onDelete }: Props) {
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
        `Delete "${job.label}"? This removes the application and its artifacts.`,
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

  const color = STATUS_COLOR[job.status];

  return (
    <div
      className={`relative group bg-paper-raised border border-rule rounded-[2px] flex flex-col cursor-pointer transition-shadow hover:shadow-[0_2px_12px_rgba(28,27,25,0.10)] select-none ${busy ? 'opacity-60 pointer-events-none' : ''}`}
      onClick={() => !editing && onClick()}
    >
      {/* status tab at top */}
      <div className="h-[3px] rounded-t-[2px]" style={{ backgroundColor: color }} />

      <div className="px-4 pt-3 pb-4 flex flex-col flex-1" style={{ minHeight: '148px' }}>
        {/* status row */}
        <div className="flex items-center justify-between gap-2 mb-4">
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${job.status === 'running' ? 'animate-pulse' : ''}`}
              style={{ backgroundColor: color }}
            />
            <span
              className="font-mono text-[10px] uppercase tracking-[0.12em] truncate"
              style={{ color }}
            >
              {statusText(job)}
            </span>
          </div>
          {job.aggregateScore !== undefined && (
            <span
              className="font-mono text-[12px] tabular-nums shrink-0"
              style={{
                color:
                  job.passed === false
                    ? 'var(--color-fail)'
                    : 'var(--color-ink-faint)',
              }}
            >
              {Math.round(job.aggregateScore)}
            </span>
          )}
        </div>

        {/* label */}
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
              className="w-full font-serif text-[15px] leading-snug text-ink bg-paper border border-rule px-1.5 py-0.5 rounded-[2px] focus:outline-none focus:border-accent/60"
              aria-label="Rename application"
            />
          ) : (
            <span
              className="block font-serif text-[15px] sm:text-[16px] leading-snug text-ink"
              onDoubleClick={(e) => {
                e.stopPropagation();
                setEditing(true);
              }}
            >
              {job.label}
            </span>
          )}
        </div>

        {/* actions - visible on hover/focus */}
        {!editing && (
          <div className="flex items-center gap-0.5 mt-3 opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
            <button
              type="button"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                setEditing(true);
              }}
              className="font-mono text-[10px] uppercase tracking-wider text-ink-faint hover:text-ink px-1.5 py-1 min-h-8 inline-flex items-center rounded-[2px] transition-colors"
              aria-label={`Rename ${job.label}`}
            >
              Edit
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={handleDelete}
              className="font-mono text-[10px] uppercase tracking-wider text-ink-faint hover:text-fail px-1.5 py-1 min-h-8 inline-flex items-center rounded-[2px] transition-colors"
              aria-label={`Delete ${job.label}`}
            >
              Del
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
