export interface UiState {
  activeJobId: string | null;
  newJobModalOpen: boolean;
  /** Applications rail collapsed — editor/proof reclaim the width (Overleaf-style). */
  jobRailCollapsed: boolean;
  /** Skills sidebar collapsed — editor/proof reclaim the width. */
  skillsSidebarCollapsed: boolean;
  /** Scores sidebar collapsed — defaults collapsed so the wide split isn't crowded. */
  scoresSidebarCollapsed: boolean;
  /** Phone/tablet: applications drawer open over the workspace. */
  mobileNavOpen: boolean;
}

export interface UiActions {
  setActiveJobId: (id: string | null) => void;
  openNewJobModal: () => void;
  closeNewJobModal: () => void;
  toggleJobRail: () => void;
  toggleSkillsSidebar: () => void;
  toggleScoresSidebar: () => void;
  openMobileNav: () => void;
  closeMobileNav: () => void;
  toggleMobileNav: () => void;
}

const UI_STORAGE_KEY = 'resume-desk:panel-collapse';

type PanelCollapseState = Pick<
  UiState,
  'jobRailCollapsed' | 'skillsSidebarCollapsed' | 'scoresSidebarCollapsed'
>;

// The scores aside is a review surface that would otherwise crowd the wide
// three-pane split, so it starts collapsed unless the user has opened it before.
const DEFAULT_COLLAPSE: PanelCollapseState = {
  jobRailCollapsed: false,
  skillsSidebarCollapsed: false,
  scoresSidebarCollapsed: true,
};

export function loadPanelCollapse(): PanelCollapseState {
  try {
    const raw = localStorage.getItem(UI_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_COLLAPSE };
    const parsed = JSON.parse(raw) as Partial<PanelCollapseState>;
    return {
      jobRailCollapsed: Boolean(parsed.jobRailCollapsed),
      skillsSidebarCollapsed: Boolean(parsed.skillsSidebarCollapsed),
      scoresSidebarCollapsed:
        parsed.scoresSidebarCollapsed ?? DEFAULT_COLLAPSE.scoresSidebarCollapsed,
    };
  } catch {
    return { ...DEFAULT_COLLAPSE };
  }
}

export function persistPanelCollapse(state: PanelCollapseState): void {
  try {
    localStorage.setItem(UI_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* private mode / quota — collapse still works in-session */
  }
}
