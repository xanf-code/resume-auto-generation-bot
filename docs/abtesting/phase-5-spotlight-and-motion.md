# Phase 5 - Spotlight HUD & Motion

**Goal:** Bring the bracket to life. Wire playback to the canvas, add the centred head-to-head spotlight, the racing score bars, the traveller card that carries a winner into its next slot, the self-drawing connectors, the champion reveal, and the playback bar. At the end of this phase the feature is complete.

**Prereq:** Phase 4. **Blocks:** none.

## Modules (each <500 lines)

- `frontend/src/components/abtest/TournamentArena.tsx` - running view: round banner + `BracketCanvas` + `SpotlightHud` + `PlaybackBar` + `ChampionBanner`.
- `frontend/src/components/abtest/SpotlightHud.tsx` - centred head-to-head overlay panel.
- `frontend/src/components/abtest/HeadToHeadScore.tsx` - one side's racing bar + count-up total + per-judge verdict rows.
- `frontend/src/components/abtest/PlaybackBar.tsx` - pause/resume, 1x/2x/4x, skip-to-result, replay, imperative progress line.
- `frontend/src/components/abtest/ChampionBanner.tsx` - final winner reveal; reuses `AggregateGauge` verbatim.
- `BracketCanvas.tsx`, `CompetitorSlot.tsx`, `BracketConnectors.tsx` *(modified)* - traveller mount, dim orchestration, `drawn` wired to playback.

## Spotlight reveal (the locked interaction)

The bracket stays on screen dimmed to 40%; the active match pops forward in a centred head-to-head panel; score bars race up with count-up totals; the winner flashes; then the winner travels into its next-round slot while the connector draws itself.

Each `TimelineStep` kind maps to exactly one visual state:

| Step | Canvas | HUD |
|---|---|---|
| `tournament-intro` | slots fade in staggered | closed |
| `round-intro` | idle | closed, round banner sweeps in |
| `match-focus` | dims to 0.4 | opens on the pair |
| `match-score` | dimmed | bars race, numbers count up |
| `match-verdict` | dimmed | winner flash, loser fades to 0.35 |
| `match-advance` | traveller flies, connector draws | closing |
| `round-outro` | un-dims to 1.0 | closed |
| `champion` | idle | champion banner |

## Winner advance: traveller card

Because both rects are already known analytically from phase 4, **FLIP's measure phase is unnecessary.** During a `match-advance` step, `BracketCanvas` mounts one absolutely-positioned "traveller" clone at the source rect and animates `transform: translate3d(dx, dy, 0)` to the destination delta over 620ms `cubic-bezier(0.22, 1, 0.36, 1)`. Transform-only means compositor-only, which means 60fps is guaranteed. On landing, the destination `CompetitorSlot` fades in over 200ms and the traveller unmounts.

**Tradeoff:** a plain fade-in at the destination is five lines and zero risk; the traveller is ~40 lines plus one extra positioned node and a `will-change: transform`. The "very smooth" requirement and the "slides into the next-round slot" requirement both point at the traveller, and the analytic geometry has already removed its main cost. **Take the traveller.** Under reduced motion it is never mounted and the destination slot simply appears.

## Animation spec

| Element | Property | Duration | Easing | Delay / stagger |
|---|---|---|---|---|
| Bracket initial reveal | `opacity` + `translateY(6px->0)` | 400 | ease-out | 30ms x slot index, cap 480 |
| Bracket dim (spotlight on) | `opacity` 1->0.4 on the **wrapper** | 300 | ease-out | 0 |
| Bracket un-dim | `opacity` 0.4->1 | 300 | ease-out | 0 |
| HUD backdrop | `background-color` -> `bg-ink/25`, `backdrop-blur-[2px]` | 300 | ease-out | 0 |
| HUD panel enter | `opacity` 0->1, `scale(0.96->1)` | 320 | `cubic-bezier(.22,1,.36,1)` | 60 |
| HUD panel exit | `opacity` 1->0, `scale(1->0.98)` | 200 | ease-in | 0 |
| **Score bar race** | **`transform: scaleX(0->p)`**, origin left | 900 | `cubic-bezier(.16,1,.3,1)` | side A 0, side B 90 |
| Score total count-up | rAF interpolation, easeOutCubic | 900 | - | tracks its own bar |
| Judge verdict rows | `opacity` 0->1 | 200 | ease-out | 120 per row (<=5) |
| Winner flash | `opacity` 0->1->0 on an absolute `bg-accent-wash` overlay | 260 in / 300 out | ease-out | at verdict start |
| Loser fade | `opacity` 1->0.35 | 400 | ease-out | 120 |
| Winner traveller | `transform: translate3d()` | 620 | `cubic-bezier(.22,1,.36,1)` | 0 |
| Connector draw | `stroke-dashoffset` L->0 | 620 | ease-out | 60 |
| Destination slot fill | `opacity` 0->1 | 200 | ease-out | 560 |
| Round banner in / out | `opacity` + `translateX(-8px->0)` | 500 / 300 | ease-out | 0 |
| Champion banner | `opacity` + `scale(0.94->1)` | 600 | `cubic-bezier(.22,1,.36,1)` | 0 |
| Champion gauge arc | `stroke-dashoffset` | 400 | ease | 200 - reuses `AggregateGauge` verbatim |
| Playback progress line | `transform: scaleX()` | none (rAF-driven) | linear | imperative write, **no transition** |
| Buttons / chevrons | `color`, `border-color`, `rotate` | 200 | ease-out | matches `PanelCollapseButton` |

Values land on 200 / 300 / 400 / 500 / 620 / 900, consistent with the existing 200/400/500 vocabulary in `PanelCollapseButton`, `AggregateGauge`, `ActivityLog`, `PipelineLoader`. The two off-scale values (620, 900) go through inline `style={{ transition: ... }}` - the same escape hatch `AggregateGauge.tsx` already uses.

**Tailwind v4 reminder:** the compiler scans for *complete* class strings, so a computed value must go through the `style` prop. `` `translate-x-[${dx}px]` `` silently produces nothing. Follow `ActivityLog.tsx` (`transform: translateY(...)`) and `PipelineLoader.tsx` (`width: ...%`).

## 60fps rules

- Animate only `transform` and `opacity` on anything repeated. **Never `width`** for the score bars - use `scaleX` with `transform-origin: left`, and put the numeric label in a *sibling* so it is not squashed.
- `will-change: transform` on the traveller and the HUD panel **only**, and only while mounted. Sixteen cards with persistent `will-change` would allocate sixteen GPU layers.
- The dim is **one** `opacity` on the canvas wrapper, not 16 per-card opacities.
- **No `filter: blur()`** on the dimmed bracket - that is a full-layer repaint of a 1080x560 surface on every frame of the HUD's scale animation. Plain `opacity` is compositor-only.
- `CompetitorSlot` stays `React.memo` with a primitives-only prop shape (`label`, `seed`, `score?`, `state`) so a step change re-renders 2-3 slots rather than 16. `BracketConnectors` memoizes on `(size, mode, drawnCount)`.

## Playback bar

Pause/resume, 1x/2x/4x segmented, skip-to-result, replay-with-new-seed. Replay calls back up to `AbTestingPage` (`setSeed(newSeedToken())`), which produces a new `timeline` identity - the hook restarts itself. It is deliberately not a control on the hook.

The progress line is the one element needing per-frame continuity. It runs its own tiny rAF, reads `progressRef.current` from `PlaybackState`, and writes `el.style.transform = scaleX(p)` imperatively. **No render, no reconciliation, no CSS transition** (a transition here would fight the rAF and produce lag).

## Reduced motion

`src/index.css:94-103` already sets `transition-duration: 0.01ms !important` on `*`, `*::before`, `*::after`. Every CSS-driven part of this design therefore silently no-ops under reduce: bars snap, connectors appear whole, the traveller teleports. That is acceptable - but it imposes two hard rules:

1. **No information may be carried by motion alone.** Every score, verdict and winner must be readable from a static frame.
2. **Never advance playback state from `onTransitionEnd`.** Under reduce the event fires in 0.01ms, or not at all if the property did not actually change, and the timeline desyncs permanently. The timeline is the single source of truth; CSS only decorates.

The design handles reduce explicitly rather than accidentally: `buildTimeline(result, { reducedMotion: true })` (phase 2) drops the three pure-motion step kinds and flattens the rest to a uniform 900ms, turning the run into a legible slideshow of focus -> score -> verdict; `useCountUp` jumps to target; connectors render at `strokeDashoffset={0}`; the traveller never mounts. **The tournament still completes, still shows every score, and still crowns a champion.**

Read the preference via `useMediaQuery(REDUCED_MOTION_MQ)` (added in phase 2).

## TDD

### RED

- `frontend/src/__tests__/SpotlightHud.test.tsx`: both labels shown; one verdict row per configured judge; with `blindJudging` the labels are masked pre-verdict and revealed post-verdict; the winner carries `data-outcome="won"` and the loser `data-outcome="lost"`.
- `frontend/src/__tests__/PlaybackBar.test.tsx`: pause toggles `aria-pressed` and its accessible name; the three speed buttons call `setSpeed(1|2|4)` and the active one has `aria-pressed="true"`; "Skip to result" calls `skipToEnd`; "Replay" calls the replay handler.

**Not tested, by design:** actual CSS transition timings, `will-change`, and visual smoothness. jsdom does not run transitions. The suite asserts *state* through `data-*` attributes and leaves CSS to CSS, consistent with how the existing tests treat `StageStepper` and `ActivityLog`. Smoothness is a manual DevTools check, below.

### GREEN

Implement the five new components and the three canvas modifications to pass.

## Acceptance

```bash
cd frontend
npx vitest run                  # full suite green, including all phase 1-4 files
npm run lint && npm run build
npm run dev
```

Manual, end to end:

1. `/` -> **A/B Testing** -> **Create A/B test** -> size 8 -> select 8. Start disabled at 7, enabled at 8.
2. Set upset factor to 0, note the seed, Start -> **the 1-seed wins the whole thing** (chalk).
3. Replay with the *same* seed -> identical scores in every match. New seed -> different.
4. Mid-run: pause, resume, switch 1x -> 4x. No jump, no stutter. Skip to result. Replay.
5. Size 16 at 1440px -> full bracket, no horizontal scroll. Resize to 375px -> round-at-a-time pager.
6. DevTools Performance on a 16-competitor run: **>=55fps, no forced reflow, no layer explosion.**
7. OS Reduce Motion **on**, rerun: the tournament completes, every score is shown, a champion is crowned - just without tweening.
8. Network tab: **zero requests to any `/api/ab*` endpoint.**

## Files

`frontend/src/components/abtest/{TournamentArena,SpotlightHud,HeadToHeadScore,PlaybackBar,ChampionBanner}.tsx`,
`frontend/src/components/abtest/{BracketCanvas,CompetitorSlot,BracketConnectors}.tsx` *(modified)*,
`frontend/src/__tests__/{SpotlightHud,PlaybackBar}.test.tsx`.
