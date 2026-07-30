// Bracket canvas: renders a FULLY RESOLVED bracket (every match's a/b
// populated) plus its live-narrowed `resolved` results as a desktop tree
// (RoundHeaders + connectors + competitor slots laid out in full-bracket
// geometry) and a mobile tree (the same RoundHeaders' pager + a single active
// round's slots, column-mode geometry, no connectors). Driven by playback:
// `dimmed`/`activeMatchId`/`advancingMatchId` reflect the current timeline
// step, connectors draw in as `resolved` gains entries, and a FLIP traveller
// animates the winner of `advancingMatchId` into its destination slot.

import { useEffect, useMemo, useState } from 'react';
import type { Bracket, Match, MatchResult } from '../../lib/ab/types';
import { bracketGeometry, type Rect, type SlotGeometry } from '../../lib/ab/layout';
import { CompetitorSlot, type CompetitorSlotSide } from './CompetitorSlot';
import { BracketConnectors, type ConnectorState } from './BracketConnectors';
import { RoundHeaders, type RoundInfo } from './RoundHeaders';

interface Props {
  bracket: Bracket; // FULLY RESOLVED - every match.a/match.b non-null
  resolved: Record<string, MatchResult>; // matchId -> MatchResult, for every "done" match
  activeRound: number; // mobile-mode: which round the pager currently shows
  onActiveRoundChange: (round: number) => void;
  dimmed?: boolean; // spotlight-mode wrapper opacity flag
  activeMatchId?: string | null; // the match currently in match-focus/match-score/match-verdict
  advancingMatchId?: string | null; // the match currently in match-advance - triggers the traveller
  reducedMotion?: boolean; // when true, never mount the traveller
}

/** 1-indexed seed of a competitor id (index 0 in `bracket.competitors` === seed 1). */
function seedOf(bracket: Bracket, competitorId: string | null): number | undefined {
  if (competitorId === null) return undefined;
  const index = bracket.competitors.findIndex((c) => c.id === competitorId);
  return index === -1 ? undefined : index + 1;
}

function labelOf(bracket: Bracket, competitorId: string | null): string | undefined {
  if (competitorId === null) return undefined;
  return bracket.competitors.find((c) => c.id === competitorId)?.label;
}

/** Builds the top (side `a`) and bottom (side `b`) slot sides for one match. */
function sidesForMatch(
  bracket: Bracket,
  match: Match,
  result: MatchResult | undefined,
  isActive: boolean,
): {
  top: CompetitorSlotSide;
  bottom: CompetitorSlotSide;
} {
  const topState: CompetitorSlotSide['state'] = result
    ? result.winnerId === match.a
      ? 'won'
      : 'lost'
    : match.a === null
      ? 'pending'
      : isActive
        ? 'active'
        : 'idle';
  const bottomState: CompetitorSlotSide['state'] = result
    ? result.winnerId === match.b
      ? 'won'
      : 'lost'
    : match.b === null
      ? 'pending'
      : isActive
        ? 'active'
        : 'idle';

  return {
    top: {
      seed: seedOf(bracket, match.a),
      label: labelOf(bracket, match.a),
      score: result?.scoreA.total,
      state: topState,
    },
    bottom: {
      seed: seedOf(bracket, match.b),
      label: labelOf(bracket, match.b),
      score: result?.scoreB.total,
      state: bottomState,
    },
  };
}

function matchForSlot(bracket: Bracket, slot: SlotGeometry): Match {
  const matchId = bracket.rounds[slot.round].matchIds[slot.index];
  return bracket.matches[matchId];
}

function findSlotRect(slots: SlotGeometry[], round: number, index: number): Rect | undefined {
  return slots.find((s) => s.round === round && s.index === index)?.rect;
}

interface TravellerData {
  fromRect: Rect;
  toRect: Rect;
  seed?: number;
  label?: string;
  score?: number;
}

/**
 * Derives the FLIP travel card for the currently-advancing match: the
 * resolved winner's own row (top or bottom of its origin slot) flying to
 * whichever row of the destination slot `match.next.slot` designates. `null`
 * whenever there's nothing to animate (no advancing match, reduced motion,
 * missing geometry, or the match's result hasn't landed yet).
 */
function buildTravellerData(
  bracket: Bracket,
  resolved: Record<string, MatchResult>,
  desktopSlots: SlotGeometry[],
  advancingMatchId: string | null | undefined,
  reducedMotion: boolean | undefined,
): TravellerData | null {
  if (!advancingMatchId || reducedMotion) return null;
  const match = bracket.matches[advancingMatchId];
  if (!match || !match.next) return null;
  const toMatch = bracket.matches[match.next.matchId];
  if (!toMatch) return null;

  const fromSlotRect = findSlotRect(desktopSlots, match.round, match.index);
  const toSlotRect = findSlotRect(desktopSlots, toMatch.round, toMatch.index);
  if (!fromSlotRect || !toSlotRect) return null;

  const result = resolved[advancingMatchId];
  if (!result) return null;

  const fromRowOffset = result.winnerId === match.a ? 0 : 28;
  const toRowOffset = match.next.slot === 'a' ? 0 : 28;

  return {
    fromRect: {
      x: fromSlotRect.x,
      y: fromSlotRect.y + fromRowOffset,
      width: fromSlotRect.width,
      height: 26,
    },
    toRect: { x: toSlotRect.x, y: toSlotRect.y + toRowOffset, width: toSlotRect.width, height: 26 },
    seed: seedOf(bracket, result.winnerId),
    label: labelOf(bracket, result.winnerId),
    score: result.winnerId === match.a ? result.scoreA.total : result.scoreB.total,
  };
}

/**
 * Classic FLIP: paints at `fromRect` on first mount (plain positioning, no
 * transition yet), then - after an rAF confirms the browser has registered
 * that initial paint - nudges to `toRect` via a `transform` transition only
 * (never `left`/`top`/`width` mid-transition). Key this on `advancingMatchId`
 * from the caller so a new advancing match always remounts fresh.
 */
function Traveller({ fromRect, toRect, seed, label, score }: TravellerData) {
  const [moved, setMoved] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setMoved(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  const dx = toRect.x - fromRect.x;
  const dy = toRect.y - fromRect.y;

  return (
    <div
      data-testid="bracket-traveller"
      className="absolute z-10 flex items-center gap-1.5 overflow-hidden border border-accent/60 bg-paper-raised rounded-[2px] font-serif text-[13px] px-2"
      style={{
        left: fromRect.x,
        top: fromRect.y,
        width: fromRect.width,
        height: fromRect.height,
        transform: moved ? `translate3d(${dx}px, ${dy}px, 0)` : 'translate3d(0, 0, 0)',
        transition: 'transform 620ms cubic-bezier(0.22,1,0.36,1)',
        willChange: 'transform',
      }}
    >
      <span className="font-mono text-[10px] text-ink-faint shrink-0 w-3 text-right">
        {seed ?? ''}
      </span>
      <span className="truncate flex-1">{label ?? ''}</span>
      <span className="font-mono text-[12px] tabular-nums shrink-0">
        {score === undefined ? '—' : score}
      </span>
    </div>
  );
}

/** Derives `RoundInfo[]` for `RoundHeaders` from the bracket + desktop geometry. */
function buildRoundInfos(bracket: Bracket, desktopSlots: SlotGeometry[]): RoundInfo[] {
  return bracket.rounds.map((round) => {
    const slotsForRound = desktopSlots.filter((s) => s.round === round.index);
    const columnXs = [...new Set(slotsForRound.map((s) => s.rect.x))].sort((a, b) => a - b);
    const columnWidth = slotsForRound[0]?.rect.width ?? 0;
    return { index: round.index, name: round.name, columnXs, columnWidth };
  });
}

/** Slim "advances" chip shown next to the winning side of a decided match, mobile-only. */
function AdvancesChip() {
  return <span className="font-mono text-[10px] text-ink-faint">advances →</span>;
}

function MobileMatchGroup({
  bracket,
  slot,
  result,
  isFinalRound,
  activeMatchId,
}: {
  bracket: Bracket;
  slot: SlotGeometry;
  result: MatchResult | undefined;
  isFinalRound: boolean;
  activeMatchId?: string | null;
}) {
  const match = matchForSlot(bracket, slot);
  const { top, bottom } = sidesForMatch(bracket, match, result, match.id === activeMatchId);
  const showChip = Boolean(result) && !isFinalRound;

  return (
    <div className="relative" style={{ top: slot.rect.y, height: slot.rect.height }}>
      <CompetitorSlot rect={{ ...slot.rect, y: 0 }} top={top} bottom={bottom} dataMatchId={match.id} />
      {showChip && (
        <div
          className="absolute flex items-center h-[26px]"
          style={{ left: slot.rect.width + 8, top: top.state === 'won' ? 0 : slot.rect.height / 2 }}
        >
          <AdvancesChip />
        </div>
      )}
    </div>
  );
}

export function BracketCanvas({
  bracket,
  resolved,
  activeRound,
  onActiveRoundChange,
  dimmed,
  activeMatchId = null,
  advancingMatchId = null,
  reducedMotion,
}: Props) {
  const desktopGeometry = useMemo(() => bracketGeometry(bracket.size), [bracket.size]);
  const mobileGeometry = useMemo(
    () => bracketGeometry(bracket.size, { mode: 'column', activeRound }),
    [bracket.size, activeRound],
  );

  const roundInfos = useMemo(
    () => buildRoundInfos(bracket, desktopGeometry.slots),
    [bracket, desktopGeometry.slots],
  );
  const roundNames = useMemo(() => bracket.rounds.map((r) => r.name), [bracket.rounds]);
  const finalRoundIndex = bracket.rounds.length - 1;

  // A connector is "drawn" the instant its match has landed a result -
  // BracketConnectors' own `stroke-dashoffset` transition animates it in from there.
  const drawnStates = useMemo<ConnectorState[]>(
    () =>
      desktopGeometry.connectors.map((c) => {
        const matchId = bracket.rounds[c.round].matchIds[c.index];
        return { round: c.round, index: c.index, drawn: resolved[matchId] !== undefined };
      }),
    [desktopGeometry.connectors, bracket.rounds, resolved],
  );

  const travellerData = useMemo(
    () => buildTravellerData(bracket, resolved, desktopGeometry.slots, advancingMatchId, reducedMotion),
    [bracket, resolved, desktopGeometry.slots, advancingMatchId, reducedMotion],
  );

  return (
    <>
      <div data-testid="bracket-desktop" className="hidden lg:block">
        <RoundHeaders
          canvasWidth={desktopGeometry.canvasWidth}
          rounds={roundInfos}
          activeRound={activeRound}
          onActiveRoundChange={onActiveRoundChange}
          roundNames={roundNames}
        />
        <div
          className="relative mx-auto"
          style={{
            width: desktopGeometry.canvasWidth,
            height: desktopGeometry.canvasHeight,
            opacity: dimmed ? 0.4 : 1,
          }}
          data-dimmed={String(Boolean(dimmed))}
        >
          <BracketConnectors
            canvasWidth={desktopGeometry.canvasWidth}
            canvasHeight={desktopGeometry.canvasHeight}
            connectors={desktopGeometry.connectors}
            drawnStates={drawnStates}
          />
          {desktopGeometry.slots.map((slot) => {
            const match = matchForSlot(bracket, slot);
            const result = resolved[match.id];
            const { top, bottom } = sidesForMatch(bracket, match, result, match.id === activeMatchId);
            return (
              <CompetitorSlot
                key={match.id}
                rect={slot.rect}
                top={top}
                bottom={bottom}
                dataMatchId={match.id}
              />
            );
          })}
          {travellerData && <Traveller key={advancingMatchId} {...travellerData} />}
        </div>
      </div>

      <div data-testid="bracket-mobile" className="lg:hidden">
        <RoundHeaders
          canvasWidth={desktopGeometry.canvasWidth}
          rounds={roundInfos}
          activeRound={activeRound}
          onActiveRoundChange={onActiveRoundChange}
          roundNames={roundNames}
        />
        <div
          className="relative"
          style={{ width: mobileGeometry.canvasWidth, height: mobileGeometry.canvasHeight }}
        >
          {mobileGeometry.slots.map((slot) => (
            <MobileMatchGroup
              key={`${slot.round}-${slot.index}`}
              bracket={bracket}
              slot={slot}
              result={resolved[matchForSlot(bracket, slot).id]}
              isFinalRound={activeRound === finalRoundIndex}
              activeMatchId={activeMatchId}
            />
          ))}
        </div>
      </div>
    </>
  );
}
