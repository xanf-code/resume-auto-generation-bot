import type { ReactNode } from 'react';
import { PanelCollapseButton } from '../layout/PanelCollapseButton';
import { useStore } from '../../store';

interface Props {
  /** Largest column: live pipeline while running, LaTeX editor when done. */
  main: ReactNode;
  /** Middle column: the compiled PDF proof. */
  proof: ReactNode;
  /** Narrow column: the copy-paste skills dump. */
  skills: ReactNode;
}

/**
 * The persistent three-pane split. Both the running and finished states share
 * this layout so the panes fill in as artifacts arrive, rather than swapping
 * the whole view. Collapsing the skills rail lets the manuscript and proof
 * share the reclaimed width (Overleaf-style).
 */
export function ThreePane({ main, proof, skills }: Props) {
  const skillsCollapsed = useStore((s) => s.skillsSidebarCollapsed);
  const toggleSkills = useStore((s) => s.toggleSkillsSidebar);

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <section className="flex-1 min-w-[280px] border-r border-rule flex flex-col min-h-0 bg-paper-raised">
        {main}
      </section>
      <section className="flex-1 min-w-[260px] border-r border-rule flex flex-col min-h-0 bg-paper-sunk">
        {proof}
      </section>
      <aside
        className={`shrink-0 flex flex-col min-h-0 bg-paper overflow-hidden transition-[width] duration-200 ease-out ${
          skillsCollapsed ? 'w-9' : 'w-[264px]'
        }`}
        aria-label="Skills to dump"
      >
        {skillsCollapsed && (
          <div className="flex flex-col items-center pt-3 gap-3 h-full">
            <PanelCollapseButton
              direction="right"
              collapsed
              onToggle={toggleSkills}
              label="Expand skills"
            />
            <span
              className="eyebrow text-[10px] select-none"
              style={{ writingMode: 'vertical-rl' }}
            >
              Skills
            </span>
          </div>
        )}
        {/* Keep mounted while collapsed so skills don't refetch on expand. */}
        <div
          className={
            skillsCollapsed ? 'hidden' : 'flex flex-col flex-1 min-h-0'
          }
          aria-hidden={skillsCollapsed}
        >
          {skills}
        </div>
      </aside>
    </div>
  );
}
