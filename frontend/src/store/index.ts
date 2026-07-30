import { create } from 'zustand';
import {
  applyEvent as applyEventFn,
  reconcileJob as reconcileJobFn,
  makeEmptyJob,
  type JobSlice,
  type JobsState,
  type JobsActions,
  type JobsMap,
} from './jobsSlice';
import {
  loadPanelCollapse,
  persistPanelCollapse,
  type UiState,
  type UiActions,
} from './uiSlice';
import type { ProgressEvent, JobDetail } from '../api/types';

type StoreState = JobsState & UiState;
type StoreActions = JobsActions & UiActions;

export type AppStore = StoreState & StoreActions;

export const useStore = create<AppStore>((set) => ({
  // --- Jobs ---
  jobs: {} as JobsMap,

  addJob: (job) =>
    set((state) => ({
      jobs: {
        ...state.jobs,
        [job.job_id]: makeEmptyJob(job.job_id, job.label),
      },
    })),

  applyEvent: (event: ProgressEvent) =>
    set((state) => ({
      jobs: applyEventFn(state.jobs, event),
    })),

  syncJob: (detail: JobDetail) =>
    set((state) => ({
      jobs: reconcileJobFn(state.jobs, detail),
    })),

  setJobs: (jobList: JobSlice[]) =>
    set(() => {
      const jobs: JobsMap = {};
      for (const j of jobList) {
        jobs[j.job_id] = j;
      }
      return { jobs };
    }),

  renameJob: (jobId, label) =>
    set((state) => {
      const job = state.jobs[jobId];
      if (!job) return {};
      return {
        jobs: {
          ...state.jobs,
          [jobId]: { ...job, label },
        },
      };
    }),

  removeJob: (jobId) =>
    set((state) => {
      const { [jobId]: _removed, ...rest } = state.jobs;
      return {
        jobs: rest,
        activeJobId: state.activeJobId === jobId ? null : state.activeJobId,
      };
    }),

  // --- UI ---
  activeJobId: null,
  ...loadPanelCollapse(),
  mobileNavOpen: false,

  setActiveJobId: (id) => set({ activeJobId: id }),

  newJobModalOpen: false,

  openNewJobModal: () => set({ newJobModalOpen: true }),

  closeNewJobModal: () => set({ newJobModalOpen: false }),

  toggleJobRail: () =>
    set((state) => {
      const next = { jobRailCollapsed: !state.jobRailCollapsed };
      persistPanelCollapse({
        jobRailCollapsed: next.jobRailCollapsed,
        skillsSidebarCollapsed: state.skillsSidebarCollapsed,
        scoresSidebarCollapsed: state.scoresSidebarCollapsed,
      });
      return next;
    }),

  toggleSkillsSidebar: () =>
    set((state) => {
      const next = { skillsSidebarCollapsed: !state.skillsSidebarCollapsed };
      persistPanelCollapse({
        jobRailCollapsed: state.jobRailCollapsed,
        skillsSidebarCollapsed: next.skillsSidebarCollapsed,
        scoresSidebarCollapsed: state.scoresSidebarCollapsed,
      });
      return next;
    }),

  toggleScoresSidebar: () =>
    set((state) => {
      const next = { scoresSidebarCollapsed: !state.scoresSidebarCollapsed };
      persistPanelCollapse({
        jobRailCollapsed: state.jobRailCollapsed,
        skillsSidebarCollapsed: state.skillsSidebarCollapsed,
        scoresSidebarCollapsed: next.scoresSidebarCollapsed,
      });
      return next;
    }),

  openMobileNav: () => set({ mobileNavOpen: true }),

  closeMobileNav: () => set({ mobileNavOpen: false }),

  toggleMobileNav: () =>
    set((state) => ({ mobileNavOpen: !state.mobileNavOpen })),
}));
