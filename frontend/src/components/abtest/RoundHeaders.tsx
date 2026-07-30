/**
 * Round name headers for the bracket canvas: a desktop column-header row that
 * sits above the bracket (one label per column a round occupies - two for
 * every round except the final, which converges to a single center column),
 * plus a mobile round PAGER (tablist) for the narrow single-column bracket
 * view. Parent decides layout; this component renders both variants and lets
 * Tailwind's `lg:` breakpoint pick the one that's visible.
 */
export interface RoundInfo {
  index: number;
  name: string;
  columnXs: number[]; // one x-position per column this round occupies on desktop (1 for the final, 2 otherwise)
  columnWidth: number; // SLOT_W for this bracket size, sizes each label to line up with the column below it
}

interface Props {
  canvasWidth: number; // desktop: header row spans this width, matching the bracket canvas below it
  rounds: RoundInfo[]; // desktop variant data
  activeRound: number; // mobile: which round the pager currently shows
  onActiveRoundChange: (round: number) => void; // mobile: pager tab click
  roundNames: string[]; // mobile: e.g. ['Quarterfinals', 'Semifinals', 'Final']
}

/** Desktop: absolutely-positioned eyebrow labels, one per column, above the canvas. */
function DesktopRoundHeaders({ canvasWidth, rounds }: Pick<Props, 'canvasWidth' | 'rounds'>) {
  return (
    <div className="hidden lg:block relative h-5 mx-auto" style={{ width: canvasWidth }}>
      {rounds.flatMap((round) =>
        round.columnXs.map((x, i) => (
          <span
            key={`${round.index}-${i}`}
            className="eyebrow absolute top-0 text-center"
            style={{ left: x, width: round.columnWidth }}
          >
            {round.name}
          </span>
        )),
      )}
    </div>
  );
}

/** Mobile: a round pager, mirroring NewJobModal's mobile pane-switcher tablist. */
function MobileRoundPager({
  activeRound,
  onActiveRoundChange,
  roundNames,
}: Pick<Props, 'activeRound' | 'onActiveRoundChange' | 'roundNames'>) {
  return (
    <div
      className="lg:hidden flex overflow-x-auto border-b border-rule"
      role="tablist"
      aria-label="Bracket rounds"
    >
      {roundNames.map((name, i) => (
        <button
          key={name}
          type="button"
          role="tab"
          aria-selected={i === activeRound}
          onClick={() => onActiveRoundChange(i)}
          className={`flex-1 min-w-[92px] text-[13px] py-2.5 whitespace-nowrap transition-colors ${
            i === activeRound ? 'text-ink border-b-2 border-accent font-medium' : 'text-ink-soft'
          }`}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

export function RoundHeaders({
  canvasWidth,
  rounds,
  activeRound,
  onActiveRoundChange,
  roundNames,
}: Props) {
  return (
    <>
      <DesktopRoundHeaders canvasWidth={canvasWidth} rounds={rounds} />
      <MobileRoundPager
        activeRound={activeRound}
        onActiveRoundChange={onActiveRoundChange}
        roundNames={roundNames}
      />
    </>
  );
}
