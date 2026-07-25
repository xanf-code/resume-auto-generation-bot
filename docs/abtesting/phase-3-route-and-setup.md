# Phase 3 - Route, Navigation & Setup Flow

**Goal:** Make the feature reachable and configurable. Add the `/ab-testing` route, a nav entry, the page shell with its empty state, and the setup modal (roster picker + bracket size + config knobs). At the end of this phase, pressing Start produces a real `TournamentResult` - rendered as a plain `<pre>` placeholder.

**Prereq:** Phase 2. **Blocks:** Phases 4-5.

## Modules (each <500 lines)

### New - `frontend/src/components/abtest/`
- `AbTestingPage.tsx` - route root. Owns phase (`idle` | `setup` | `running`), roster, config, seed, result, timeline.
- `AbEmptyState.tsx` - eyebrow, serif headline, "Create A/B test" CTA, roster-provenance line.
- `AbSetupModal.tsx` - modal shell mirroring `NewJobModal` (backdrop, focus trap, Esc, 2-col desktop / segmented mobile).
- `RosterPicker.tsx` - selectable résumé list with origin tags, "N of M" counter, "Select top N".
- `BracketSizeSelector.tsx` - 4 / 8 / 16 segmented control.
- `AbConfigPanel.tsx` - the config knobs.

### Modified
- `frontend/src/App.tsx`
- `frontend/src/components/layout/CommandDeck.tsx`
- `frontend/src/components/layout/TopBar.tsx`

## Route registration

`App.tsx` - one nested route:

```tsx
<Route element={<CommandDeck />}>
  <Route index element={null} />
  <Route path="ab-testing" element={<AbTestingPage />} />
  <Route path="jobs/:jobId" element={<JobDetailRoute />} />
</Route>
```

## CommandDeck - split the route flag

The only non-trivial edit in this phase. `CommandDeck.tsx:19` computes `hasJobRoute` and then uses it for *two different decisions*: whether to show the `JobRail` (lines 66, 68, 79) and whether to render `<Outlet/>` vs `<JobGrid/>` (line 71). Separate them:

```tsx
const hasJobRoute = useMatch('/jobs/:jobId');
// exact match - must become '/ab-testing/*' if sub-routes are ever added,
// or the page silently falls through to JobGrid
const hasAbRoute  = useMatch('/ab-testing');
const showOutlet  = Boolean(hasJobRoute) || Boolean(hasAbRoute);

// line 71:
{showOutlet ? <Outlet /> : <JobGrid loadFailed={loadFailed} onOpenModal={openModal} />}

// lines 66 / 68 / 79 keep hasJobRoute - the applications rail stays job-only
```

**Nest, don't sibling.** `TopBar` (brand, health dot, "+ New résumé"), `NewJobModal`, `Toaster`, and the `h-dvh` / safe-area shell are app chrome that a sibling top-level route would have to duplicate. The one job-centric piece we don't want - `JobRail` - is already gated on `hasJobRoute` alone, so nesting gives exactly the right chrome with a two-line diff. Bonus: the existing `listJobs()` fetch at `CommandDeck.tsx:24` already populates the store the A/B roster reads from, so the roster is warm with no extra request.

## TopBar - nav entry

A `<nav>` between the logo (line 83) and the health-dot cluster (line 93). Import `NavLink` alongside the existing `Link`.

```tsx
<nav className="hidden sm:flex items-center gap-4 ml-2">
  <NavLink
    to="/ab-testing"
    className={({ isActive }) =>
      `eyebrow hover:text-ink transition-colors ${
        isActive ? 'text-ink border-b-2 border-accent pb-0.5' : ''
      }`
    }
  >
    A/B Testing
  </NavLink>
</nav>
```

Plus an icon-only variant inside the existing mobile cluster. Reuses the `.eyebrow` class from `index.css:55` and the `border-b-2 border-accent` active treatment already used by the `ThreePane` tabs.

## Setup flow

`AbEmptyState` -> "Create A/B test" -> `AbSetupModal`. The modal carries three things:

1. **`RosterPicker`** - `buildRoster(jobs, 16)` gives the candidate pool; the user selects exactly `size` of them. Every row shows an origin tag (`job` / `fixture`) so a fixture never masquerades as the user's data, plus `baseScore` right-aligned in `font-mono tabular-nums`. A "Select top N" affordance fills the selection in score order.
2. **`BracketSizeSelector`** - 4 / 8 / 16 segmented control. Changing size re-derives the pool and clamps the selection.
3. **`AbConfigPanel`** - the knobs below.

Start is disabled until `selected.length === size`, with the reason in a `title` attribute - the same `canSubmit` + `title` idiom `NewJobModal` already uses.

### Config knobs

Five of seven genuinely drive the math. Do not let this drift into decoration - the simulation should feel alive.

| Knob | Control | Effect |
|---|---|---|
| **Judging panel** | checkbox group, 5 personas, min 2 | **Real** - each selected judge adds a verdict row in the HUD and a term in the composite |
| **Panel weights** | one `SliderRow` per selected judge, live-rebalanced to 1.0 | **Real** - reuses the `rebalanceWeights` algorithm from `src/lib/tuning.ts:157`, re-keyed by `JudgeId` |
| **Upset factor** | slider 0-100%, labelled "Chalk <-> Chaos" | **Real, and the headline knob** - scales noise ±8 -> ±42. At 0 the noise is zeroed and the top seed always wins. Put it front and centre. |
| **Reads per match** | segmented 1 / 3 / 5, labelled "Best of" | **Real** - averages N independent reads per judge; variance shrinks by sqrt(N), measurably suppressing upsets. Interacts with the upset factor in a way you can feel. |
| **Target role** | select x5 | **Real** - ±6 per-judge affinity from `ROLE_AFFINITY`, genuinely reorders the field. Also drives the page subtitle copy. |
| **Panel strictness** | slider 0-100 | **Semi-decorative, honestly** - a uniform penalty. Cannot change *who* wins, but moves numbers across the pass/fail threshold so the `passColor` colouring (`src/lib/scoring.ts:9`) means something. |
| **Blind judging** | toggle | **UI only** - masks competitor names in the HUD until the verdict lands. Cheap drama, zero math. |
| **Seed** | mono text input, defaults to a generated token (`mercer-7f31`) | **Real** - the determinism story. "Replay with new seed" rerolls it. |

## Page state

`AbTestingPage` owns everything and derives downward:

```ts
const jobs = useStore((s) => Object.values(s.jobs));
const [phase, setPhase] = useState<'idle' | 'setup' | 'running'>('idle');
const [seed, setSeed] = useState(newSeedToken);
const [config, setConfig] = useState(DEFAULT_AB_CONFIG);
const [size, setSize] = useState<BracketSize>(8);
const [selectedIds, setSelectedIds] = useState<string[]>([]);

const result = useMemo(
  () => (phase === 'running' ? simulateTournament(buildBracket(chosen, size), seed, config) : null),
  [phase, chosen, size, seed, config],
);
const timeline = useMemo(
  () => (result ? buildTimeline(result, { reducedMotion }) : null),
  [result, reducedMotion],
);
```

Replay-with-new-seed is just `setSeed(newSeedToken())` - a new `result`, a new `timeline` identity, and the phase-2 hook restarts itself.

## TDD

### RED

- `frontend/src/__tests__/AbTestingPage.test.tsx`: empty state renders a "Create A/B test" button; clicking it opens a `role="dialog"`; Escape closes it; the page mounts without a `JobRail` in the tree.
- `frontend/src/__tests__/AbSetupModal.test.tsx`: Start disabled until exactly N selected (assert disabled at N-1, enabled at N, and blocked at N+1); switching size to 4 updates the "0 of 4" counter and clamps an oversized selection; unchecking below 2 judges is prevented; `onStart` fires with the assembled `{ selectedIds, size, config, seed }`.
- `frontend/src/__tests__/RosterPicker.test.tsx`: all competitors listed with origin tags; toggling a row updates the count; "Select top 8" selects exactly 8 in descending score order.

Assert `data-*` attributes and accessible roles, **not CSS classes** - this mirrors `StageStepper.test.tsx`, which asserts `data-status`. Note `src/__tests__/setup.ts` polyfills `matchMedia` to `matches: false` (mobile), so any desktop-layout assertion must override it.

### GREEN

Implement the six new components and the three edits to pass. Render the `TournamentResult` in a plain `<pre>{JSON.stringify(result, null, 2)}</pre>` placeholder - the bracket arrives in phase 4.

## Acceptance

```bash
cd frontend
npx vitest run                  # existing 23 test files must stay green
npm run lint && npm run build
npm run dev
```

Then in the browser: `/` -> **A/B Testing** in the top bar -> **Create A/B test** -> size 8 -> select 8 -> Start -> the `<pre>` shows a full tournament with a `championId`. Navigating back to `/` still shows `JobGrid`; `/jobs/:jobId` still shows the rail.

## Files

`frontend/src/components/abtest/{AbTestingPage,AbEmptyState,AbSetupModal,RosterPicker,BracketSizeSelector,AbConfigPanel}.tsx`,
`frontend/src/{App.tsx,components/layout/CommandDeck.tsx,components/layout/TopBar.tsx}` *(modified)*,
`frontend/src/__tests__/{AbTestingPage,AbSetupModal,RosterPicker}.test.tsx`.
