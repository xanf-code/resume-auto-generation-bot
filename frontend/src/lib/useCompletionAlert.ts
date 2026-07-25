import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { completionAlert } from './notify';
import { playChime } from './sound';
import type { JobSlice } from '../store/jobsSlice';

export function useCompletionAlert(
  job: JobSlice | undefined,
  markNotified: (id: string) => void,
): void {
  const notifiedRef = useRef(false);

  useEffect(() => {
    if (!job) return;
    if (job.status !== 'done') return;
    if (job.finishedNotified) return;
    if (notifiedRef.current) return;

    notifiedRef.current = true;

    playChime();
    toast.success(`${job.label} finished — score ${job.aggregateScore ?? '—'}`);
    completionAlert(job.job_id, job.label, job.aggregateScore);
    markNotified(job.job_id);
  }, [job?.status, job?.finishedNotified]);
}
