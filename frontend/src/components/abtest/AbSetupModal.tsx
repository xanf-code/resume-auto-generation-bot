import { useEffect, useRef, useState } from 'react';
import { RosterPicker } from './RosterPicker';
import { BracketSizeSelector } from './BracketSizeSelector';
import { AbConfigPanel } from './AbConfigPanel';
import { DEFAULT_AB_CONFIG } from '../../lib/ab/config';
import { newSeedToken } from '../../lib/ab/prng';
import type { AbConfig, BracketSize, Competitor } from '../../lib/ab/types';

export interface StartPayload {
  selectedIds: string[];
  size: BracketSize;
  config: AbConfig;
  seed: string;
}

interface Props {
  /** Full candidate roster pool (jobs + fixture padding), already built upstream. */
  pool: Competitor[];
  onClose: () => void;
  onStart: (payload: StartPayload) => void;
}

type MobilePane = 'roster' | 'config';

/**
 * Setup modal for a new resume A/B tournament: pick a bracket size, select
 * exactly that many resumes from the pool, and tune the judging panel /
 * match config before starting. Mirrors NewJobModal's shell conventions
 * (backdrop, focus trap, Escape-to-close, two-pane desktop / segmented
 * mobile layout).
 */
export function AbSetupModal({ pool, onClose, onStart }: Props) {
  const [size, setSize] = useState<BracketSize>(8);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [config, setConfig] = useState<AbConfig>(DEFAULT_AB_CONFIG);
  const [seed, setSeed] = useState<string>(newSeedToken);
  const [mobilePane, setMobilePane] = useState<MobilePane>('roster');
  const panelRef = useRef<HTMLDivElement>(null);

  const canSubmit = selectedIds.length === size;

  const handleSizeChange = (nextSize: BracketSize): void => {
    setSize(nextSize);
    setSelectedIds((prev) => (prev.length > nextSize ? prev.slice(0, nextSize) : prev));
  };

  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    return () => restoreTo?.focus?.();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleStart = (): void => {
    if (!canSubmit) return;
    onStart({ selectedIds, size, config, seed });
  };

  return (
    <div
      className="fixed inset-0 bg-ink/40 backdrop-blur-[2px] flex items-stretch sm:items-center justify-center z-50 sm:p-4"
      style={{
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ab-setup-title"
        tabIndex={-1}
        className="bg-paper border-rule w-full sm:max-w-6xl sm:rounded-[4px] sm:border sm:shadow-[0_24px_60px_rgba(28,27,25,0.25)] h-dvh sm:h-[min(90vh,880px)] overflow-hidden flex flex-col focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-5 sm:px-7 pt-5 sm:pt-6 pb-4 border-b border-rule shrink-0">
          <div>
            <span className="eyebrow">New A/B test</span>
            <h2
              id="ab-setup-title"
              className="font-serif text-[22px] sm:text-[26px] leading-tight text-ink mt-1"
            >
              Set the bracket
            </h2>
            <p className="text-[13px] text-ink-soft mt-1.5 max-w-md leading-snug">
              Pick a bracket size, choose your resumes, and tune the judging panel.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-ink-faint hover:text-ink text-lg leading-none inline-flex items-center justify-center min-w-11 min-h-11 -mr-2"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Mobile pane switcher */}
        <div
          className="md:hidden flex border-b border-rule shrink-0"
          role="tablist"
          aria-label="Setup panes"
        >
          {(
            [
              ['roster', 'Roster'],
              ['config', 'Configuration'],
            ] as const
          ).map(([id, labelText]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mobilePane === id}
              onClick={() => setMobilePane(id)}
              className={`flex-1 text-[13px] py-2.5 transition-colors ${
                mobilePane === id
                  ? 'text-ink border-b-2 border-accent font-medium'
                  : 'text-ink-soft'
              }`}
            >
              {labelText}
            </button>
          ))}
        </div>

        <div className="flex-1 min-h-0 grid md:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
          <div
            data-testid="ab-setup-roster"
            className={`flex-col gap-4 px-5 sm:px-7 py-5 overflow-y-auto min-h-0 ${
              mobilePane === 'roster' ? 'flex' : 'hidden md:flex'
            }`}
          >
            <BracketSizeSelector value={size} onChange={handleSizeChange} />
            <RosterPicker
              pool={pool}
              size={size}
              selectedIds={selectedIds}
              onChange={setSelectedIds}
            />
          </div>

          <aside
            data-testid="ab-setup-config"
            className={`flex-col gap-5 px-5 sm:px-6 py-5 overflow-y-auto min-h-0 border-t md:border-t-0 md:border-l border-rule bg-paper-sunk/40 ${
              mobilePane === 'config' ? 'flex' : 'hidden md:flex'
            }`}
          >
            <AbConfigPanel
              config={config}
              onChange={setConfig}
              seed={seed}
              onSeedChange={setSeed}
            />
          </aside>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end px-5 sm:px-7 py-4 border-t border-rule shrink-0 bg-paper pb-[max(0.5rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            onClick={onClose}
            className="text-[13px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleStart}
            disabled={!canSubmit}
            title={canSubmit ? undefined : `Select exactly ${size} resumes to start`}
            className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-5 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors disabled:opacity-50"
          >
            Start
          </button>
        </div>
      </div>
    </div>
  );
}
