import { useEffect, useState, type ReactNode } from 'react';
import { PanelCollapseButton } from '../layout/PanelCollapseButton';
import { useStore } from '../../store';
import { WIDE_MQ, useMediaQuery } from '../../hooks/useMediaQuery';

interface Props {
  /** Largest column: live pipeline while running, LaTeX editor when done. */
  main: ReactNode;
  /** Middle column: the compiled PDF proof. */
  proof: ReactNode;
  /** Collapsible column: the recruiter panel's per-persona scores. */
  scores: ReactNode;
  /** Narrow column: the copy-paste skills dump. */
  skills: ReactNode;
}

type PaneId = 'main' | 'proof' | 'scores' | 'skills';

const TABS: { id: PaneId; label: string }[] = [
  { id: 'main', label: 'Editor' },
  { id: 'proof', label: 'Proof' },
  { id: 'scores', label: 'Scores' },
  { id: 'skills', label: 'Skills' },
];

/**
 * Wide desktops keep the three-pane split. Below that, panes become a
 * segmented control — phones and tablets can't usefully show LaTeX + PDF +
 * skills side by side.
 */
export function ThreePane({ main, proof, scores, skills }: Props) {
  const skillsCollapsed = useStore((s) => s.skillsSidebarCollapsed);
  const toggleSkills = useStore((s) => s.toggleSkillsSidebar);
  const scoresCollapsed = useStore((s) => s.scoresSidebarCollapsed);
  const toggleScores = useStore((s) => s.toggleScoresSidebar);
  const isWide = useMediaQuery(WIDE_MQ);
  const [pane, setPane] = useState<PaneId>('main');

  // Prefer editor pane when crossing back below the wide breakpoint.
  useEffect(() => {
    if (!isWide) setPane('main');
  }, [isWide]);

  if (!isWide) {
    return (
      <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
        <div
          role="tablist"
          aria-label="Workspace panes"
          className="flex shrink-0 border-b border-rule bg-paper px-2 sm:px-3 gap-0.5"
        >
          {TABS.map((tab) => {
            const selected = pane === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={selected}
                id={`pane-tab-${tab.id}`}
                aria-controls={`pane-panel-${tab.id}`}
                onClick={() => setPane(tab.id)}
                className={`relative flex-1 sm:flex-none min-h-11 px-3 sm:px-4 text-[13px] font-medium transition-colors ${
                  selected
                    ? 'text-ink'
                    : 'text-ink-faint hover:text-ink-soft'
                }`}
              >
                {tab.label}
                {selected && (
                  <span
                    className="absolute left-2 right-2 bottom-0 h-[2px] bg-accent"
                    aria-hidden
                  />
                )}
              </button>
            );
          })}
        </div>
        {/* Keep all panes mounted so editor/PDF/skills state survives tab switches. */}
        {(
          [
            ['main', main],
            ['proof', proof],
            ['scores', scores],
            ['skills', skills],
          ] as const
        ).map(([id, node]) => (
          <div
            key={id}
            role="tabpanel"
            id={`pane-panel-${id}`}
            aria-labelledby={`pane-tab-${id}`}
            hidden={pane !== id}
            className={
              pane === id
                ? 'flex flex-1 min-h-0 flex-col overflow-hidden bg-paper-raised'
                : 'hidden'
            }
          >
            {node}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <section className="flex-1 min-w-[280px] border-r border-rule flex flex-col min-h-0 bg-paper-raised">
        {main}
      </section>
      <section className="flex-1 min-w-[260px] border-r border-rule flex flex-col min-h-0 bg-paper-sunk">
        {proof}
      </section>
      <aside
        className={`shrink-0 flex flex-col min-h-0 bg-paper border-r border-rule overflow-hidden transition-[width] duration-200 ease-out ${
          scoresCollapsed ? 'w-9' : 'w-[264px]'
        }`}
        aria-label="Recruiter scores"
      >
        {scoresCollapsed && (
          <div className="flex flex-col items-center pt-3 gap-3 h-full">
            <PanelCollapseButton
              direction="right"
              collapsed
              onToggle={toggleScores}
              label="Expand scores"
            />
            <span
              className="eyebrow text-[10px] select-none"
              style={{ writingMode: 'vertical-rl' }}
            >
              Scores
            </span>
          </div>
        )}
        {/* Keep mounted while collapsed so scores don't flash on expand. */}
        <div
          className={scoresCollapsed ? 'hidden' : 'flex flex-col flex-1 min-h-0'}
          aria-hidden={scoresCollapsed}
        >
          {scores}
        </div>
      </aside>
      <aside
        className={`shrink-0 flex flex-col min-h-0 bg-paper overflow-hidden transition-[width] duration-200 ease-out ${
          skillsCollapsed ? 'w-9' : 'w-[264px]'
        }`}
        aria-label="Skills"
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
