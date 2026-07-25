export interface UiState {
  activeJobId: string | null;
  newJobModalOpen: boolean;
  /** Applications rail collapsed — editor/proof reclaim the width (Overleaf-style). */
  jobRailCollapsed: boolean;
  /** Skills sidebar collapsed — editor/proof reclaim the width. */
  skillsSidebarCollapsed: boolean;
}

export interface UiActions {
  setActiveJobId: (id: string | null) => void;
  openNewJobModal: () => void;
  closeNewJobModal: () => void;
  toggleJobRail: () => void;
  toggleSkillsSidebar: () => void;
}

const UI_STORAGE_KEY = 'resume-desk:panel-collapse';

export function loadPanelCollapse(): Pick<
  UiState,
  'jobRailCollapsed' | 'skillsSidebarCollapsed'
> {
  try {
    const raw = localStorage.getItem(UI_STORAGE_KEY);
    if (!raw) return { jobRailCollapsed: false, skillsSidebarCollapsed: false };
    const parsed = JSON.parse(raw) as Partial<{
      jobRailCollapsed: boolean;
      skillsSidebarCollapsed: boolean;
    }>;
    return {
      jobRailCollapsed: Boolean(parsed.jobRailCollapsed),
      skillsSidebarCollapsed: Boolean(parsed.skillsSidebarCollapsed),
    };
  } catch {
    return { jobRailCollapsed: false, skillsSidebarCollapsed: false };
  }
}

export function persistPanelCollapse(
  state: Pick<UiState, 'jobRailCollapsed' | 'skillsSidebarCollapsed'>,
): void {
  try {
    localStorage.setItem(UI_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* private mode / quota — collapse still works in-session */
  }
}
