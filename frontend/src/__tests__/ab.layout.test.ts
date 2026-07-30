import { describe, it, expect } from 'vitest';
import { bracketGeometry, type Rect } from '../lib/ab/layout';
import type { BracketSize } from '../lib/ab/types';

const SIZES: BracketSize[] = [4, 8, 16];
const EXPECTED_COLUMNS: Record<BracketSize, number> = { 4: 3, 8: 5, 16: 7 };

describe('bracketGeometry - bracket mode structure', () => {
  it.each(SIZES)('columns === 2*(rounds-1)+1 for size %s', (size) => {
    const rounds = Math.log2(size);
    const expectedColumns = 2 * (rounds - 1) + 1;
    expect(expectedColumns).toBe(EXPECTED_COLUMNS[size]);

    const geo = bracketGeometry(size);
    const distinctX = new Set(geo.slots.map((s) => s.rect.x));
    expect(distinctX.size).toBe(expectedColumns);
  });

  it.each(SIZES)('total slot count equals size - 1 (summed per round) for size %s', (size) => {
    const rounds = Math.log2(size);
    let expectedTotal = 0;
    for (let r = 0; r < rounds; r++) {
      expectedTotal += size / 2 ** (r + 1);
    }
    expect(expectedTotal).toBe(size - 1);

    const geo = bracketGeometry(size);
    expect(geo.slots).toHaveLength(expectedTotal);
  });

  it.each(SIZES)('no two same-column rects overlap vertically for size %s', (size) => {
    const geo = bracketGeometry(size);
    const byX = new Map<number, Rect[]>();
    for (const slot of geo.slots) {
      const existing = byX.get(slot.rect.x) ?? [];
      byX.set(slot.rect.x, [...existing, slot.rect]);
    }
    for (const rects of byX.values()) {
      const sorted = [...rects].sort((a, b) => a.y - b.y);
      for (let i = 1; i < sorted.length; i++) {
        const prev = sorted[i - 1];
        const curr = sorted[i];
        expect(curr.y).toBeGreaterThanOrEqual(prev.y + prev.height);
      }
    }
  });

  it.each(SIZES)("the final's rect is horizontally centered within 1px for size %s", (size) => {
    const rounds = Math.log2(size);
    const geo = bracketGeometry(size);
    const final = geo.slots.find((s) => s.round === rounds - 1);
    expect(final).toBeDefined();
    const centerX = final!.rect.x + final!.rect.width / 2;
    expect(Math.abs(centerX - geo.canvasWidth / 2)).toBeLessThanOrEqual(1);
  });

  it.each(SIZES)(
    'left-half and right-half slots are both non-empty and the final is neither, for size %s',
    (size) => {
      const rounds = Math.log2(size);
      const geo = bracketGeometry(size);
      const mid = geo.canvasWidth / 2;
      const centerXOf = (r: Rect): number => r.x + r.width / 2;

      const left = geo.slots.filter((s) => centerXOf(s.rect) < mid);
      const right = geo.slots.filter((s) => centerXOf(s.rect) > mid);
      const atCenter = geo.slots.filter((s) => Math.abs(centerXOf(s.rect) - mid) < 1e-9);

      expect(left.length).toBeGreaterThan(0);
      expect(right.length).toBeGreaterThan(0);
      expect(atCenter).toHaveLength(1);
      expect(atCenter[0].round).toBe(rounds - 1);
    },
  );

  it.each(SIZES)('has exactly size - 2 connectors (one per non-final match) for size %s', (size) => {
    const geo = bracketGeometry(size);
    expect(geo.connectors).toHaveLength(size - 2);
  });

  it('canvasWidth/canvasHeight are positive for all sizes, and canvasHeight is non-decreasing (70 <= 140 <= 280)', () => {
    const results = SIZES.map((size) => bracketGeometry(size));
    for (const geo of results) {
      expect(geo.canvasWidth).toBeGreaterThan(0);
      expect(geo.canvasHeight).toBeGreaterThan(0);
    }
    // Symmetric bracket: both halves share the full-height y-centers (they are
    // NOT stacked top/bottom), so the canvas is exactly the round-0 column's
    // span: PITCH0 * (size / 4).
    expect(results.map((g) => g.canvasHeight)).toEqual([70, 140, 280]);
  });

  it.each(SIZES)(
    'left-half and right-half slots of the same round share the same y-centers (mirrored, not stacked) for size %s',
    (size) => {
      const rounds = Math.log2(size);
      const geo = bracketGeometry(size);
      const mid = geo.canvasWidth / 2;
      const centerYOf = (r: Rect): number => r.y + r.height / 2;
      const centerXOf = (r: Rect): number => r.x + r.width / 2;

      for (let round = 0; round <= rounds - 2; round++) {
        const inRound = geo.slots.filter((s) => s.round === round);
        const leftYs = inRound
          .filter((s) => centerXOf(s.rect) < mid)
          .map((s) => centerYOf(s.rect))
          .sort((a, b) => a - b);
        const rightYs = inRound
          .filter((s) => centerXOf(s.rect) > mid)
          .map((s) => centerYOf(s.rect))
          .sort((a, b) => a - b);
        expect(rightYs).toEqual(leftYs);
      }
    },
  );

  it.each(SIZES)('the final is vertically centered within 1px for size %s', (size) => {
    const rounds = Math.log2(size);
    const geo = bracketGeometry(size);
    const final = geo.slots.find((s) => s.round === rounds - 1);
    expect(final).toBeDefined();
    const centerY = final!.rect.y + final!.rect.height / 2;
    expect(Math.abs(centerY - geo.canvasHeight / 2)).toBeLessThanOrEqual(1);
  });
});

describe('bracketGeometry - connector geometry (hand-computed)', () => {
  it('size 8 round-0 index-0 connector matches a hand-computed manhattan path/length', () => {
    // Hand-derived from the spec's formulas (SLOT_W=168, COL_GAP=72, pitch0=70, MATCH_H=54):
    //   colX(c) = c * (168 + 72) = c * 240
    //   round 0 (left half) matchesPerHalf = 8/4 = 2; pitch(0) = 70
    //   yCenterInHalf(0, 0) = 70 * 0.5 = 35 -> source rect: x=0, y=35-27=8, w=168, h=54
    //   round 1 (left half, target) matchesPerHalf = 8/8 = 1; pitch(1) = 140
    //   yCenterInHalf(1, 0) = 140 * 0.5 = 70 -> target rect: x=240, y=70-27=43, w=168, h=54
    const geo = bracketGeometry(8);

    const source = geo.slots.find((s) => s.round === 0 && s.index === 0);
    const target = geo.slots.find((s) => s.round === 1 && s.index === 0);
    expect(source?.rect).toEqual({ x: 0, y: 8, width: 168, height: 54 });
    expect(target?.rect).toEqual({ x: 240, y: 43, width: 168, height: 54 });

    const x1 = 0 + 168; // source's right edge (left-half match converges rightward)
    const y1 = 8 + 27; // source's vertical center
    const x2 = 240; // target's left edge (facing back at the source)
    const y2 = 43 + 27; // target's vertical center
    const xm = (x1 + x2) / 2;
    const expectedLength = Math.abs(xm - x1) + Math.abs(y2 - y1) + Math.abs(x2 - xm);
    expect(expectedLength).toBe(107);

    const connector = geo.connectors.find((c) => c.round === 0 && c.index === 0);
    expect(connector).toBeDefined();
    expect(connector!.length).toBe(expectedLength);
    expect(connector!.d).toBe(`M ${x1} ${y1} H ${xm} V ${y2} H ${x2}`);
  });
});

describe('bracketGeometry - column mode', () => {
  it.each(SIZES)(
    'every slot shares x, slot count matches the round size, and there are no connectors, for size %s',
    (size) => {
      const rounds = Math.log2(size);
      for (let activeRound = 0; activeRound < rounds; activeRound++) {
        const geo = bracketGeometry(size, { mode: 'column', activeRound });
        const matchesInRound = size / 2 ** (activeRound + 1);

        expect(geo.slots).toHaveLength(matchesInRound);
        const distinctX = new Set(geo.slots.map((s) => s.rect.x));
        expect(distinctX.size).toBe(1);
        expect(geo.connectors).toHaveLength(0);
      }
    },
  );
});
