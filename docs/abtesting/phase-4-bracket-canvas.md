# Phase 4 - Bracket Geometry & Canvas

**Goal:** Draw the bracket. Analytic geometry produces every slot rect and connector path as a pure function; the canvas positions slots absolutely and overlays one SVG for the elbows. At the end of this phase a fully-resolved bracket renders correctly for 4/8/16 at phone, tablet and desktop widths - static, no animation yet.

**Prereq:** Phase 3. **Blocks:** Phase 5.

## Modules (each <500 lines)

- `frontend/src/lib/ab/layout.ts` - `bracketGeometry(size, opts)` -> slot rects, connector `{ d, length }`, canvas box. Pure, no DOM.
- `frontend/src/components/abtest/BracketCanvas.tsx` - positions slots from geometry, owns the dim wrapper, hosts the traveller mount point (used in phase 5).
- `frontend/src/components/abtest/CompetitorSlot.tsx` - one match cell (two rows: seed, label, score, state). `React.memo`.
- `frontend/src/components/abtest/BracketConnectors.tsx` - single absolutely-positioned `<svg>`; elbow paths.
- `frontend/src/components/abtest/RoundHeaders.tsx` - column headers on desktop, round pager on mobile.

## Positioning: analytic absolute positioning

Three candidates were considered:

1. **CSS grid** - zero JS, but you never learn the *y* of a slot, so connectors become impossible without measurement, which lands you back at option 3.
2. **Absolute positioning from a pure geometry function.** Slot width/height become fixed constants rather than content-driven.
3. **Measured refs + `ResizeObserver`** - maximum flexibility, forced layout reads on every resize, and a `ResizeObserver` problem in jsdom.

**Take option 2.** A bracket is a perfectly regular binary tree, so every rect is closed-form. This buys: connectors become trivial strings; the phase-5 winner-advance becomes a delta between two known points (FLIP *without ever measuring*); resize handling collapses to "re-run a pure function when `size` or `mode` changes"; and the whole thing unit-tests with zero DOM. The cost - fixed slot width and truncated labels - is already the house pattern (`JobCard` and `JobRailItem` both truncate).

### Constants

```
ROW_H = 26, MATCH_H = 54 (two rows + divider), GAP_Y = 16, pitch0 = 70
size 16: SLOT_W = 120, COL_GAP = 40
size 8:  SLOT_W = 168, COL_GAP = 72
size 4:  SLOT_W = 168, COL_GAP = 72
```

### Converging split layout

Columns = `2 * (rounds - 1) + 1` where `rounds = log2(size)`. The final gets its own centre column and the two halves mirror inward.

| size | rounds | columns | canvas W | canvas H |
|---|---|---|---|---|
| 4 | 2 | 3 | 648 | 70 |
| 8 | 3 | 5 | 1128 | 140 |
| 16 | 4 | 7 | 1080 | 280 |

Within a half, round *r* has `size / 2^(r+2)` matches and:

```
pitch(r)      = pitch0 * 2^r
yCenter(r, m) = pitch(r) * (m + 0.5)
```

Both halves share the **same** `yCenter`s - they mirror horizontally, not vertically - so the same round sits at the same height on the left and the right and the final centres between them (`canvas H = pitch0 * size / 4`, the round-0 column's span). Stacking the right half into a lower band instead produces a broken descending staircase.

All three sizes fit a 1280px viewport without horizontal scroll - that is exactly why the final gets a centre column rather than a full extra column pair.

## Connectors: one SVG overlay, analytic path lengths

**One absolutely-positioned `<svg>`** sized to the exact canvas box (explicit `width` / `height` attributes *and* a matching `viewBox`, `pointer-events-none`, `shape-rendering="geometricPrecision"`), rendering one `<path>` per non-final match. Each path is an elbow, mirrored for the right half by sign flips:

```
M x1 y1 H xm V y2 H x2
```

Per-match pseudo-element borders were the alternative. Rejected: they can only draw fixed-size right-angle stubs, they cannot be animated as a *draw*, they cannot express the right-half mirror cleanly, and 30 pseudo-elements are 30 paint layers versus one.

### Path length must be analytic

For the phase-5 draw-in we need each path's length. Two options:

- `ref.getTotalLength()` on mount, then set `strokeDasharray` / `strokeDashoffset`. Costs a layout read per path, forces a second render, and **is unimplemented in jsdom**, which would break every component test that touches the canvas.
- **Return the length analytically from `bracketGeometry`.** We synthesised the path, so we know it: an elbow's length is `|xm - x1| + |y2 - y1| + |x2 - xm|`.

**Take the analytic length.** No DOM read, no second render, no jsdom problem, and it is an assertable value in `ab.layout.test.ts`.

```tsx
<path
  d={c.d}
  strokeDasharray={c.length}
  strokeDashoffset={drawn ? 0 : c.length}
  stroke="var(--color-rule)"
  fill="none"
  strokeWidth={1.5}
  style={{ transition: 'stroke-dashoffset 620ms ease-out' }}
/>
```

In this phase `drawn` is simply `true` for every resolved match; phase 5 wires it to playback.

### Sizing gotcha

Do **not** use `width="100%"` + `preserveAspectRatio`. At fractional container widths the SVG scales while the absolutely-positioned HTML slots do not, and the elbows drift a pixel or two off the cards - which reads as broken. If a fit-to-width `transform: scale()` wrapper is ever added, every path needs `vectorEffect="non-scaling-stroke"` or the 1.5px hairlines go fuzzy.

Because the geometry is analytic, there is no `ResizeObserver` anywhere. Resize handling reduces to "re-run `bracketGeometry` when `size` or `mode` changes" - both are React state. That is the whole payoff of choosing analytic geometry over measured refs.

## Responsive: round-at-a-time on mobile

- **>= 1024px (`DESKTOP_MQ`)** - full converging bracket, centred. Size 16 gets `overflow-x-auto` only below ~1200px of available width.
- **< 1024px** - `bracketGeometry(size, { mode: 'column', activeRound })` returns rects for only the active round, stacked full-width in a single column. Connectors are suppressed (meaningless without an adjacent column) and replaced by a slim "advances ->" chip on the winner row. `RoundHeaders` becomes a pager showing which round is live.

**Rationale:** horizontal scroll during an autoplaying animation is hostile - the user has to chase the action with their thumb. Round-at-a-time follows playback automatically. It also matches the codebase's existing mobile posture: `NewJobModal` goes full-screen with segmented panes rather than shrinking the desktop layout, and `CommandDeck` swaps the rail for a drawer.

One geometry function, two modes, identical return shape - `BracketCanvas` stays dumb.

## Styling

Slots use existing tokens only: `bg-paper-raised`, `border border-rule`, `rounded-[2px]`, `font-serif` for the label, `font-mono tabular-nums` for the score, `text-ink-faint` for the seed number. Pending slots render at `text-ink-faint` with an em-dash. No new `@theme` tokens.

## TDD

### RED

- `frontend/src/__tests__/ab.layout.test.ts`: column count `=== 2 * (rounds - 1) + 1` for 4/8/16; one rect per match and no two rects in a column overlap vertically; the final's rect is horizontally centred in the canvas (±1px); left-half rects have `x < centre` and right-half `x > centre`; one connector per non-final match; `length` equals the hand-computed manhattan sum for a named edge; `mode: 'column'` -> all rects share the same `x`; canvas `width` / `height` positive and height non-decreasing in `size`.
- `frontend/src/__tests__/BracketCanvas.test.tsx`: renders `size` competitor labels and `size - 1` match groups; one `<path>` per connector; `data-dimmed="true"` when the spotlight flag is set; pending slots render the em-dash placeholder; `mode: 'column'` renders only the active round's matches.

Assert `data-*` attributes, not CSS - mirroring `StageStepper.test.tsx`. Remember `setup.ts` gives `matchMedia -> false` (mobile), so the desktop-bracket test must override it explicitly.

### GREEN

Implement `layout.ts` and the four components. Drive `BracketCanvas` with a **statically resolved** bracket (call `skipToEnd` on mount) so the phase is verifiable without any animation wiring.

## Acceptance

```bash
cd frontend
npx vitest run src/__tests__/ab.layout src/__tests__/BracketCanvas
npx vitest run                  # full suite still green
npm run lint && npm run build
npm run dev
```

Then, with `skipToEnd` on mount, visually confirm a correct fully-resolved bracket for sizes 4, 8 and 16 at **375px, 1024px and 1440px** - elbows meeting their cards exactly, no horizontal scroll at 1440px, round-at-a-time pager at 375px.

## Files

`frontend/src/lib/ab/layout.ts`,
`frontend/src/components/abtest/{BracketCanvas,CompetitorSlot,BracketConnectors,RoundHeaders}.tsx`,
`frontend/src/__tests__/{ab.layout.test.ts,BracketCanvas.test.tsx}`.
