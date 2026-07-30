# A/B Testing - Résumé Tournament Bracket

**Goal:** A new frontend page where the user picks N résumés, sets a few judging knobs, and watches a single-elimination bracket play out live - round by round, scores racing up - until one résumé is crowned champion.

**Scope constraint: NO BACKEND. Zero new API calls.** Every number is generated client-side by a seeded PRNG. This is not a placeholder for a future backend - the dummy simulation is the deliverable.

Numbering restarts at 1 in this directory. The flat `docs/phase-1..10-*.md` series is the backend pipeline and is unrelated.

## Phases

| Phase | Doc | Ships |
|---|---|---|
| 1 | [phase-1-domain-and-sim.md](phase-1-domain-and-sim.md) | Types, PRNG, roster, config, bracket, scoring, simulate. No UI. |
| 2 | [phase-2-timeline-and-playback.md](phase-2-timeline-and-playback.md) | Timeline builder + rAF playback controller. No UI. |
| 3 | [phase-3-route-and-setup.md](phase-3-route-and-setup.md) | Route, nav, page shell, setup modal, roster picker, config panel. |
| 4 | [phase-4-bracket-canvas.md](phase-4-bracket-canvas.md) | Analytic geometry, bracket canvas, slots, SVG connectors, mobile mode. |
| 5 | [phase-5-spotlight-and-motion.md](phase-5-spotlight-and-motion.md) | Spotlight HUD, traveller advance, connector draw-in, champion, playback bar. |

Phases 1-2 ship zero UI on purpose: the whole simulation is provably correct before a pixel is drawn.

## Locked product decisions

- **Roster** - real jobs from the Zustand store, padded with a hardcoded fixture roster so the page always demos. `origin: 'job' | 'fixture'` is surfaced on every card; a fixture must never masquerade as the user's data.
- **Bracket size** - selectable 4 / 8 / 16. Powers of two only, so there are no byes to render.
- **Match reveal** - spotlight HUD. The bracket stays on screen dimmed to 40%; the active match pops forward in a centred head-to-head panel; scores race; the winner advances into its next-round slot while the connector draws itself.
- **Playback** - speed 1x/2x/4x, pause/resume, skip-to-result, replay with a new seed.

## Architecture: precompute, then play back

The load-bearing decision. The entire tournament is simulated deterministically up front into a `TournamentResult`. A second pure pass turns that into a `Timeline` - an ordered list of steps with absolute `startMs` offsets. Playback is then only ever answering "what step are we on at virtual time T?"

Every control falls out for free:

| Control | Implementation |
|---|---|
| Speed 1x/2x/4x | multiplier on `dt` - applies mid-flight, no recompute |
| Pause / resume | stop accumulating into `virtualMs` |
| Skip to result | `virtualMs = totalMs` |
| Replay (new seed) | re-run `simulate` + `buildTimeline`, new `timeline` identity |

The alternative - a `setTimeout` chain that decides winners as it goes - makes every one of those a special case, accumulates scheduling drift across ~30 steps, and leaks timers on unmount. Rejected.

**Corollary rule, applies to all five phases: motion never drives state.** The timeline is the only source of truth; CSS only decorates. Specifically, **never advance playback from `onTransitionEnd`** - `src/index.css:94-103` collapses every transition to `0.01ms !important` under `prefers-reduced-motion`, so that event fires instantly or not at all and the run desyncs permanently.

## House constraints (inherited)

- Vite + React 18 + React Router 7 SPA, Zustand, Tailwind v4. **No animation library** - CSS transitions only. Do not add a dependency.
- Design tokens live in the `@theme` block of `src/index.css` ("Manuscript": paper/ink/accent, Fraunces / Inter / JetBrains Mono, `rounded-[2px]`). This feature needs no new tokens.
- Tailwind v4 scans for *complete* class strings, so a computed value must go through the `style` prop - never `` `w-[${pct}%]` ``. Follow the existing idiom in `ActivityLog.tsx`, `PipelineLoader.tsx`, `AggregateGauge.tsx`.
- Files under 500 lines, many small focused files, immutable updates, explicit prop interfaces, no `any`, no `console.log`.
- Tests in `frontend/src/__tests__/`, Vitest + Testing Library. `setup.ts` polyfills `matchMedia` to `matches: false`, i.e. **mobile by default** - desktop-layout tests must override it.

## Full verification (after phase 5)

```bash
cd frontend
npm run lint
npx vitest run                     # full suite - existing 23 files stay green
npm run build                      # tsc must pass
npm run dev
```

1. `/` -> click **A/B Testing** in the top bar.
2. **Create A/B test** -> size 8 -> select 8 résumés. Start is disabled at 7, enabled at 8.
3. Set upset factor to 0, note the seed, Start -> **the 1-seed wins the whole thing** (chalk).
4. Replay with the *same* seed -> identical scores in every match. New seed -> different.
5. Mid-run: pause, resume, 1x -> 4x. No jump, no stutter. Skip to result. Replay.
6. Size 16 at 1440px -> full bracket, no horizontal scroll. Resize to 375px -> round-at-a-time pager.
7. DevTools Performance on a 16-run: >=55fps, no forced reflow, no layer explosion.
8. OS Reduce Motion **on**, rerun: the tournament still completes, every score is shown, a champion is crowned - just without tweening.
9. Network tab: zero requests to any `/api/ab*` endpoint.
