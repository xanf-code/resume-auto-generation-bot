import { useNavigate, useLocation } from 'react-router-dom';
import { JobRailItem } from './JobRailItem';
import { PanelCollapseButton } from '../layout/PanelCollapseButton';
import { useStore } from '../../store';
import { deleteJob, renameJob } from '../../api/jobs';

export type JobRailMode = 'sidebar' | 'drawer' | 'page';

interface Props {
  /** sidebar = desktop rail; drawer = overlay; page = phone home list. */
  mode?: JobRailMode;
  onNavigate?: () => void;
}

export function JobRail({ mode = 'sidebar', onNavigate }: Props) {
  const jobsMap = useStore((s) => s.jobs);
  const jobs = Object.values(jobsMap);
  const renameInStore = useStore((s) => s.renameJob);
  const removeInStore = useStore((s) => s.removeJob);
  const collapsed = useStore((s) => s.jobRailCollapsed);
  const toggleJobRail = useStore((s) => s.toggleJobRail);
  const closeMobileNav = useStore((s) => s.closeMobileNav);
  const location = useLocation();
  const navigate = useNavigate();

  const isSidebar = mode === 'sidebar';
  const showCollapsed = isSidebar && collapsed;

  const handleRename = async (jobId: string, label: string) => {
    const updated = await renameJob(jobId, label);
    renameInStore(jobId, updated.label);
  };

  const handleDelete = async (jobId: string) => {
    const viewingDeleted = location.pathname === `/jobs/${jobId}`;
    await deleteJob(jobId);
    if (viewingDeleted) {
      navigate('/', { replace: true });
    }
    removeInStore(jobId);
    onNavigate?.();
  };

  const openJob = (jobId: string) => {
    navigate(`/jobs/${jobId}`);
    onNavigate?.();
    if (mode === 'drawer') closeMobileNav();
  };

  const shellClass =
    mode === 'page'
      ? 'flex flex-col flex-1 min-h-0 bg-paper overflow-hidden'
      : mode === 'drawer'
        ? 'flex flex-col h-full w-[min(20rem,88vw)] bg-paper border-r border-rule overflow-hidden'
        : `border-r border-rule bg-paper flex flex-col shrink-0 overflow-hidden transition-[width] duration-200 ease-out ${
            showCollapsed ? 'w-9' : 'w-64'
          }`;

  return (
    <aside className={shellClass} aria-label="Applications">
      {showCollapsed ? (
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
          <div className="px-4 py-3 flex items-center justify-between border-b border-rule gap-2 shrink-0 min-h-12">
            <div className="flex items-baseline gap-2 min-w-0 pl-2">
              <span className="eyebrow">Applications</span>
              {jobs.length > 0 && (
                <span className="font-mono text-[11px] text-ink-faint tabular-nums">
                  {jobs.length}
                </span>
              )}
            </div>
            {isSidebar ? (
              <PanelCollapseButton
                direction="left"
                collapsed={false}
                onToggle={toggleJobRail}
                label="Collapse applications"
              />
            ) : mode === 'drawer' ? (
              <button
                type="button"
                onClick={closeMobileNav}
                className="inline-flex items-center justify-center min-w-11 min-h-11 -mr-1 text-ink-faint hover:text-ink rounded-[2px] transition-colors"
                aria-label="Close applications"
              >
                ✕
              </button>
            ) : null}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0">
            {jobs.length === 0 ? (
              <div className="px-6 py-5 font-serif italic text-[15px] text-ink-faint leading-relaxed">
                No applications yet.
                <span className="block mt-1 text-[13px] not-italic font-sans">
                  Start one from New resume above.
                </span>
              </div>
            ) : (
              <div>
                {jobs.map((job, i) => (
                  <JobRailItem
                    key={job.job_id}
                    job={job}
                    index={i}
                    active={location.pathname === `/jobs/${job.job_id}`}
                    onClick={() => openJob(job.job_id)}
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
