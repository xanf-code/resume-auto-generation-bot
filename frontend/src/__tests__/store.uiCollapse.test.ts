import { describe, it, expect, beforeEach } from 'vitest';
import { useStore } from '../store';

describe('scores sidebar collapse', () => {
  beforeEach(() => {
    useStore.setState({ scoresSidebarCollapsed: true });
  });

  it('toggleScoresSidebar flips the collapsed flag', () => {
    expect(useStore.getState().scoresSidebarCollapsed).toBe(true);
    useStore.getState().toggleScoresSidebar();
    expect(useStore.getState().scoresSidebarCollapsed).toBe(false);
    useStore.getState().toggleScoresSidebar();
    expect(useStore.getState().scoresSidebarCollapsed).toBe(true);
  });

  it('leaves the skills sidebar flag untouched', () => {
    useStore.setState({ skillsSidebarCollapsed: false });
    useStore.getState().toggleScoresSidebar();
    expect(useStore.getState().skillsSidebarCollapsed).toBe(false);
  });
});
