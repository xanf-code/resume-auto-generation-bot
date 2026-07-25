import { useEffect, useState } from 'react';
import { Outlet, useMatch } from 'react-router-dom';
import { TopBar } from './TopBar';
import { JobRail } from '../rail/JobRail';
import { JobGrid } from '../home/JobGrid';
import { NewJobModal } from '../newjob/NewJobModal';
import { useStore } from '../../store';
import { listJobs } from '../../api/jobs';
import { makeEmptyJob } from '../../store/jobsSlice';
import { Toaster } from 'sonner';
import { DESKTOP_MQ, useMediaQuery } from '../../hooks/useMediaQuery';

export function CommandDeck() {
  const modalOpen = useStore((s) => s.newJobModalOpen);
  const openModal = useStore((s) => s.openNewJobModal);
  const setJobs = useStore((s) => s.setJobs);
  const mobileNavOpen = useStore((s) => s.mobileNavOpen);
  const closeMobileNav = useStore((s) => s.closeMobileNav);
  const hasJobRoute = useMatch('/jobs/:jobId');
  const [loadFailed, setLoadFailed] = useState(false);
  const isDesktop = useMediaQuery(DESKTOP_MQ);

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

  // Close the drawer when crossing into desktop, or when leaving a job route.
  useEffect(() => {
    if (isDesktop || !hasJobRoute) closeMobileNav();
  }, [isDesktop, hasJobRoute, closeMobileNav]);

  // Escape closes the mobile applications drawer.
  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMobileNav();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileNavOpen, closeMobileNav]);

  return (
    <div
      className="flex flex-col h-dvh bg-paper text-ink"
      style={{
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      <TopBar showNavToggle={Boolean(hasJobRoute) && !isDesktop} />
      <div className="flex flex-1 overflow-hidden min-h-0">
        {isDesktop && hasJobRoute && <JobRail mode="sidebar" />}

        <main className="flex-1 overflow-hidden bg-paper min-w-0 min-h-0">
          {hasJobRoute ? (
            <Outlet />
          ) : (
            <JobGrid loadFailed={loadFailed} onOpenModal={openModal} />
          )}
        </main>
      </div>

      {!isDesktop && mobileNavOpen && hasJobRoute && (
        <div className="fixed inset-0 z-40 flex" id="applications-drawer">
          <button
            type="button"
            className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]"
            aria-label="Dismiss applications"
            onClick={closeMobileNav}
          />
          <div
            className="relative z-10 h-full pt-[env(safe-area-inset-top)] pl-[env(safe-area-inset-left)] shadow-[8px_0_32px_rgba(28,27,25,0.18)]"
            role="dialog"
            aria-modal="true"
            aria-label="Applications"
          >
            <JobRail mode="drawer" onNavigate={closeMobileNav} />
          </div>
        </div>
      )}

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
