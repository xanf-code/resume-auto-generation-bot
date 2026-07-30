import { useNavigate } from 'react-router-dom';
import { JobCard } from './JobCard';
import { useStore } from '../../store';
import { deleteJob, renameJob } from '../../api/jobs';

interface Props {
  loadFailed?: boolean;
  onOpenModal: () => void;
}

export function JobGrid({ loadFailed, onOpenModal }: Props) {
  const jobsMap = useStore((s) => s.jobs);
  const jobs = Object.values(jobsMap);
  const renameInStore = useStore((s) => s.renameJob);
  const removeInStore = useStore((s) => s.removeJob);
  const navigate = useNavigate();

  const handleRename = async (jobId: string, label: string) => {
    const updated = await renameJob(jobId, label);
    renameInStore(jobId, updated.label);
  };

  const handleDelete = async (jobId: string) => {
    await deleteJob(jobId);
    removeInStore(jobId);
  };

  if (loadFailed) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6 sm:px-8">
        <span className="eyebrow" style={{ color: 'var(--color-fail)' }}>
          Server offline
        </span>
        <p className="mt-2 font-serif text-[22px] sm:text-[26px] leading-snug text-ink max-w-md">
          Can't connect to the backend.
        </p>
        <p className="mt-3 text-[14px] text-ink-soft max-w-md leading-relaxed">
          Make sure the backend is running, then reload to pick up your applications.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-6 text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
        >
          Reload
        </button>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6 sm:px-8">
        <p className="font-serif text-[22px] sm:text-[26px] leading-snug text-ink max-w-md">
          Start by adding a job application.
        </p>
        <p className="mt-3 text-[14px] text-ink-soft max-w-md leading-relaxed">
          Add a job description and your{' '}
          <span className="font-mono text-[13px] text-ink">main.tex</span> resume to get started.
        </p>
        <button
          onClick={onOpenModal}
          className="mt-6 text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
        >
          ＋ New resume
        </button>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="px-6 py-6 sm:px-8 sm:py-8 max-w-[1400px]">
        <div className="flex items-baseline gap-3 mb-6">
          <span className="eyebrow">Resumes</span>
          <span className="font-mono text-[11px] text-ink-faint tabular-nums">
            {jobs.length}
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {jobs.map((job) => (
            <JobCard
              key={job.job_id}
              job={job}
              onClick={() => navigate(`/jobs/${job.job_id}`)}
              onRename={(label) => handleRename(job.job_id, label)}
              onDelete={() => handleDelete(job.job_id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
