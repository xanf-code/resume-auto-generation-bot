// Pure bracket-geometry calculator for the A/B résumé tournament bracket
// visual. No React, no DOM - takes only a `size` (the shape of a bracket is
// fully determined by its size, independent of which competitors fill it).
//
// `round`/`index` on every returned SlotGeometry/ConnectorGeometry line up
// exactly with a real `Bracket`'s `Match.round`/`Match.index` (as produced by
// `bracket.ts`'s `buildBracket`), so a caller zips this geometry against a
// real bracket's `matches` (keyed by `r${round}-m${index}`) to render it.

import type { BracketSize } from './types';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SlotGeometry {
  round: number;
  index: number;
  rect: Rect;
}

export interface ConnectorGeometry {
  round: number;
  index: number;
  d: string;
  length: number;
}

export interface BracketGeometry {
  canvasWidth: number;
  canvasHeight: number;
  slots: SlotGeometry[];
  connectors: ConnectorGeometry[];
}

export interface BracketGeometryOptions {
  mode?: 'bracket' | 'column';
  activeRound?: number;
}

// Reserved for the rendering layer (two competitor-name rows stack inside a
// MATCH_H-tall slot: 54 = 26 + 26 + 2px divider) - not used in this module's
// own geometry math, which only needs MATCH_H/GAP_Y/PITCH0.
const ROW_H = 26;
const MATCH_H = 54;
const GAP_Y = 16;
const PITCH0 = 70; // === MATCH_H + GAP_Y, verified: round-0 matches spaced
// pitch0 apart center-to-center leave exactly GAP_Y of clear space between rects.

interface SizeConstants {
  slotW: number;
  colGap: number;
}

function constantsForSize(size: BracketSize): SizeConstants {
  if (size === 16) return { slotW: 120, colGap: 40 };
  return { slotW: 168, colGap: 72 }; // sizes 4 and 8 share these
}

function matchesPerHalf(size: BracketSize, round: number): number {
  return size / 2 ** (round + 2);
}

function pitchForRound(round: number): number {
  return PITCH0 * 2 ** round;
}

function yCenterInHalf(round: number, matchIndexInHalf: number): number {
  return pitchForRound(round) * (matchIndexInHalf + 0.5);
}

export function bracketGeometry(
  size: BracketSize,
  opts?: BracketGeometryOptions,
): BracketGeometry {
  const mode = opts?.mode ?? 'bracket';
  if (mode === 'column') {
    return columnModeGeometry(size, opts?.activeRound);
  }
  return bracketModeGeometry(size);
}

function bracketModeGeometry(size: BracketSize): BracketGeometry {
  const { slotW, colGap } = constantsForSize(size);
  const rounds = Math.log2(size);
  const columns = 2 * (rounds - 1) + 1;
  const canvasWidth = columns * slotW + (columns - 1) * colGap;
  // Symmetric bracket: the two halves are mirrored horizontally but share the
  // SAME vertical y-centers (they are NOT stacked top/bottom). The canvas is
  // therefore exactly as tall as the round-0 column - size/4 matches spaced
  // PITCH0 apart - which keeps left semis, the final, and right semis level.
  const canvasHeight = (PITCH0 * size) / 4;
  const colX = (column: number): number => column * (slotW + colGap);

  const slots: SlotGeometry[] = [];
  const rectByKey = new Map<string, Rect>();
  const setSlot = (round: number, index: number, rect: Rect): void => {
    slots.push({ round, index, rect });
    rectByKey.set(`${round}-${index}`, rect);
  };

  // Left half (columns 0..rounds-2, column c holds round c) and right half
  // (columns rounds..columns-1, mirrored inward) for every non-final round.
  // Both halves use the same `yCenterInHalf` centers so the same round sits at
  // the same height on both sides - the standard converging-bracket shape.
  for (let round = 0; round <= rounds - 2; round++) {
    const half = matchesPerHalf(size, round);
    const leftColumn = round;
    const rightColumn = columns - 1 - round;

    for (let m = 0; m < half; m++) {
      const y = yCenterInHalf(round, m);
      setSlot(round, m, { x: colX(leftColumn), y: y - MATCH_H / 2, width: slotW, height: MATCH_H });
    }
    for (let m = 0; m < half; m++) {
      const y = yCenterInHalf(round, m);
      setSlot(round, half + m, {
        x: colX(rightColumn),
        y: y - MATCH_H / 2,
        width: slotW,
        height: MATCH_H,
      });
    }
  }

  // The final: vertically centered, in the center column.
  const finalRound = rounds - 1;
  const finalColumn = rounds - 1;
  setSlot(finalRound, 0, {
    x: colX(finalColumn),
    y: canvasHeight / 2 - MATCH_H / 2,
    width: slotW,
    height: MATCH_H,
  });

  const connectors = buildConnectors(size, rounds, rectByKey);

  return { canvasWidth, canvasHeight, slots, connectors };
}

/**
 * One connector per non-final match, linking it to its round+1 target. The
 * standard bracket-building convention (mirrored by `bracket.ts`) makes this
 * uniform across both halves: target round is `round + 1`, target index is
 * `Math.floor(index / 2)`, regardless of which half the source is in.
 */
function buildConnectors(
  size: BracketSize,
  rounds: number,
  rectByKey: Map<string, Rect>,
): ConnectorGeometry[] {
  const connectors: ConnectorGeometry[] = [];

  for (let round = 0; round <= rounds - 2; round++) {
    const half = matchesPerHalf(size, round);
    const totalInRound = half * 2;

    for (let index = 0; index < totalInRound; index++) {
      const isLeft = index < half;
      const targetRound = round + 1;
      const targetIndex = Math.floor(index / 2);

      const rect = rectByKey.get(`${round}-${index}`);
      const targetRect = rectByKey.get(`${targetRound}-${targetIndex}`);
      if (!rect || !targetRect) {
        throw new Error(
          `bracketGeometry: missing rect for connector r${round}-m${index} -> r${targetRound}-m${targetIndex}`,
        );
      }

      // Left-half matches converge rightward (their right edge faces the
      // target's left edge); right-half matches converge leftward (mirrored).
      const x1 = isLeft ? rect.x + rect.width : rect.x;
      const x2 = isLeft ? targetRect.x : targetRect.x + targetRect.width;
      const y1 = rect.y + MATCH_H / 2;
      const y2 = targetRect.y + MATCH_H / 2;
      const xm = (x1 + x2) / 2;

      const d = `M ${x1} ${y1} H ${xm} V ${y2} H ${x2}`;
      const length = Math.abs(xm - x1) + Math.abs(y2 - y1) + Math.abs(x2 - xm);

      connectors.push({ round, index, d, length });
    }
  }

  return connectors;
}

function columnModeGeometry(size: BracketSize, activeRound: number | undefined): BracketGeometry {
  const rounds = Math.log2(size);
  if (activeRound === undefined || activeRound < 0 || activeRound >= rounds) {
    throw new Error(
      `bracketGeometry: opts.activeRound (${String(activeRound)}) must be a valid round index (0..${rounds - 1}) for size ${size} in 'column' mode`,
    );
  }

  const { slotW } = constantsForSize(size);
  const matchesInRound = size / 2 ** (activeRound + 1);

  const slots: SlotGeometry[] = Array.from({ length: matchesInRound }, (_, index) => ({
    round: activeRound,
    index,
    rect: { x: 0, y: index * (MATCH_H + GAP_Y), width: slotW, height: MATCH_H },
  }));

  const canvasWidth = slotW;
  const canvasHeight = matchesInRound * MATCH_H + (matchesInRound - 1) * GAP_Y;

  return { canvasWidth, canvasHeight, slots, connectors: [] };
}
