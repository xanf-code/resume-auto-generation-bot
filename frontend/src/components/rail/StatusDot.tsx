import type { JobStatus } from '../../store/jobsSlice';

interface Props {
  status: JobStatus;
}

const COLOR: Record<JobStatus, string> = {
  queued: 'var(--color-ink-faint)',
  running: 'var(--color-accent)',
  done: 'var(--color-pass)',
  failed: 'var(--color-fail)',
};

export function StatusDot({ status }: Props) {
  return (
    <span
      style={{ backgroundColor: COLOR[status] }}
      className={`inline-block w-1.5 h-1.5 rounded-full ${status === 'running' ? 'animate-pulse' : ''}`}
      aria-label={status}
    />
  );
}
