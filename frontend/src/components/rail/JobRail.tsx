import { useNavigate, useParams } from 'react-router-dom';
import { JobRailItem } from './JobRailItem';
import { PanelCollapseButton } from '../layout/PanelCollapseButton';
import { useStore } from '../../store';
import { deleteJob, renameJob } from '../../api/jobs';

export function JobRail() {
  const jobsMap = useStore((s) => s.jobs);
  const jobs = Object.values(jobsMap);
  const renameInStore = useStore((s) => s.renameJob);
  const removeInStore = useStore((s) => s.removeJob);
  const collapsed = useStore((s) => s.jobRailCollapsed);
  const toggleJobRail = useStore((s) => s.toggleJobRail);
  const { jobId: activeJobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const handleRename = async (jobId: string, label: string) => {
    const updated = await renameJob(jobId, label);
    renameInStore(jobId, updated.label);
  };

  const handleDelete = async (jobId: string) => {
    await deleteJob(jobId);
    removeInStore(jobId);
    if (activeJobId === jobId) {
      navigate('/');
    }
  };

  return (
    <aside
      className={`border-r border-rule bg-paper flex flex-col shrink-0 overflow-hidden transition-[width] duration-200 ease-out ${
        collapsed ? 'w-9' : 'w-64'
      }`}
      aria-label="Applications"
    >
      {collapsed ? (
        <div className="flex flex-col items-center pt-3 gap-3 h-full">
          <PanelCollapseButton
            direction="left"
            collapsed
            onToggle={toggleJobRail}
            label="Expand applications"
          />
          <span
            className="eyebrow writing-mode-vertical text-[10px] select-none"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            Applications
          </span>
        </div>
      ) : (
        <>
          <div className="px-4 py-3 flex items-center justify-between border-b border-rule gap-2 shrink-0">
            <div className="flex items-baseline gap-2 min-w-0 pl-2">
              <span className="eyebrow">Applications</span>
              {jobs.length > 0 && (
                <span className="font-mono text-[11px] text-ink-faint tabular-nums">
                  {jobs.length}
                </span>
              )}
            </div>
            <PanelCollapseButton
              direction="left"
              collapsed={false}
              onToggle={toggleJobRail}
              label="Collapse applications"
            />
          </div>

          <div className="flex-1 overflow-y-auto min-h-0">
            {jobs.length === 0 ? (
              <div className="px-6 py-5 font-serif italic text-[15px] text-ink-faint leading-relaxed">
                No applications yet.
                <span className="block mt-1 text-[13px] not-italic font-sans">
                  Start one from the desk above.
                </span>
              </div>
            ) : (
              <div>
                {jobs.map((job, i) => (
                  <JobRailItem
                    key={job.job_id}
                    job={job}
                    index={i}
                    active={job.job_id === activeJobId}
                    onClick={() => navigate(`/jobs/${job.job_id}`)}
                    onRename={(label) => handleRename(job.job_id, label)}
                    onDelete={() => handleDelete(job.job_id)}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
