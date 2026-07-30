interface Props {
  /** Which way the panel collapses - chevron points toward the remaining space. */
  direction: 'left' | 'right';
  collapsed: boolean;
  onToggle: () => void;
  label: string;
}

/**
 * Slim edge control for Overleaf-style panel collapse. Chevron points inward
 * when expanded (collapse this panel) and outward when collapsed (restore it).
 */
export function PanelCollapseButton({
  direction,
  collapsed,
  onToggle,
  label,
}: Props) {
  // Expanded left rail: chevron points left (collapse away). Collapsed: points right.
  // Expanded right rail: chevron points right. Collapsed: points left.
  const pointsLeft =
    direction === 'left' ? !collapsed : collapsed;

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={!collapsed}
      aria-label={label}
      title={label}
      className="inline-flex items-center justify-center w-7 h-7 rounded-[2px] text-ink-faint hover:text-ink hover:bg-paper-sunk border border-transparent hover:border-rule transition-colors focus:outline-none focus-visible:border-accent/60"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 14 14"
        fill="none"
        aria-hidden
        className={`transition-transform duration-200 ease-out ${pointsLeft ? '' : 'rotate-180'}`}
      >
        <path
          d="M8.5 3.25 5 7l3.5 3.75"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
