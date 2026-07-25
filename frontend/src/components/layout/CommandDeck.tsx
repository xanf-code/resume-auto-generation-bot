import { useEffect, useState } from 'react';
import { Outlet, useMatch } from 'react-router-dom';
import { TopBar } from './TopBar';
import { JobRail } from '../rail/JobRail';
import { NewJobModal } from '../newjob/NewJobModal';
import { useStore } from '../../store';
import { listJobs } from '../../api/jobs';
import { makeEmptyJob } from '../../store/jobsSlice';
import { Toaster } from 'sonner';

export function CommandDeck() {
  const modalOpen = useStore((s) => s.newJobModalOpen);
  const openModal = useStore((s) => s.openNewJobModal);
  const setJobs = useStore((s) => s.setJobs);
  const hasJobRoute = useMatch('/jobs/:jobId');
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    listJobs()
      .then((list) => {
        setLoadFailed(false);
        setJobs(
          list.map((s) => ({
            ...makeEmptyJob(s.job_id, s.label),
            status: s.status,
            aggregateScore: s.aggregate_score,
            passed: s.passed,
            pct: s.status === 'done' ? 100 : 0,
          })),
        );
      })
      .catch(() => {
        // Distinguish "unreachable backend" from a genuinely empty desk so the
        // empty state doesn't invite work the press can't accept.
        setLoadFailed(true);
      });
  }, [setJobs]);

  return (
    <div className="flex flex-col h-screen bg-paper text-ink">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <JobRail />
        <main className="flex-1 overflow-hidden bg-paper">
          {hasJobRoute ? (
            <Outlet />
          ) : loadFailed ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <span className="eyebrow" style={{ color: 'var(--color-fail)' }}>
                Press offline
              </span>
              <p className="mt-2 font-serif text-[26px] leading-snug text-ink max-w-md">
                The desk can't reach the press.
              </p>
              <p className="mt-3 text-[14px] text-ink-soft max-w-md leading-relaxed">
                Make sure the backend is running, then reload to pick up your
                applications.
              </p>
              <button
                onClick={() => window.location.reload()}
                className="mt-6 text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 h-9 rounded-[3px] transition-colors"
              >
                Reload
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <p className="font-serif text-[26px] leading-snug text-ink max-w-md">
                A clean desk for tailoring your résumé.
              </p>
              <p className="mt-3 text-[14px] text-ink-soft max-w-md leading-relaxed">
                Select an application from the left, or open a new one to feed a
                job description and your&nbsp;
                <span className="font-mono text-[13px] text-ink">main.tex</span> into
                the press.
              </p>
              <button
                onClick={openModal}
                className="mt-6 text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 h-9 rounded-[3px] transition-colors"
              >
                ＋ New résumé
              </button>
            </div>
          )}
        </main>
      </div>
      {modalOpen && <NewJobModal />}
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#fdfbf6',
            border: '1px solid #e4ddd0',
            color: '#1c1b19',
            fontFamily: 'Inter, system-ui, sans-serif',
            fontSize: '13px',
            borderRadius: '3px',
          },
        }}
      />
    </div>
  );
}
