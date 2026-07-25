# Phase 2 - Per-application tuning (frontend)

## Goal
In the "New application" modal, expose the Phase-1 knobs as sliders, defaulted to
the current backend values, each with a hover/focus `?` help tip, and send the
chosen values with the job. Rubric weights are **live-balanced** (moving one
slider redistributes the rest so the five always sum to 1.0).

## Design (Manuscript editorial system - warm paper/serif, never terminal)
1. **`src/lib/tuning.ts`** - `Tuning` / `RubricWeights` types (snake_case to match
   the wire), `DEFAULT_TUNING`, `RUBRIC_KEYS`, field metadata (label, min, max,
   step, help text), and `rebalanceWeights(weights, key, newValue)`:
   - clamp `newValue` to [0,1];
   - distribute `1 - newValue` across the other four proportionally to their
     current values; if the others sum to 0, split equally;
   - result always sums to 1.0 (within float tolerance).
2. **`components/newjob/HelpTip.tsx`** - a `?` button; tooltip shown on hover AND
   focus, `role="tooltip"` + `aria-describedby`, dismissable, keyboard reachable.
3. **`components/newjob/SliderRow.tsx`** - eyebrow label + `HelpTip` + `range`
   input + right-aligned value; accent-colored track; editorial styling.
4. **`components/newjob/TuningControls.tsx`** - collapsible "Advanced tuning"
   disclosure (default collapsed, one click to reveal - keeps the modal calm but
   still "shows" the sliders). Six scalar `SliderRow`s + a "Rubric weights"
   subgroup of five live-balanced rows displaying `%` with a live "Σ 100%" readout.
5. **`components/newjob/NewJobModal.tsx`** - hold `tuning` state (init
   `DEFAULT_TUNING`), render `<TuningControls>`, pass `tuning` to `createJob`.
6. **`api/types.ts`** - `CreateJobRequest.tuning?: Tuning`.

## Accessibility
- Every slider has an associated `<label>`; value announced via `aria-valuetext`
  where a `%`/unit helps.
- HelpTip works with keyboard (focus reveals) and honours reduced-motion.

## Tests (write first, vitest)
- `src/__tests__/tuning.test.ts`: `rebalanceWeights` keeps Σ=1.0, proportional
  split, clamp, equal-fallback when others are 0.
- `src/__tests__/TuningControls.test.tsx`: renders six scalar sliders defaulted;
  help tips exposed; changing a rubric slider rebalances (Σ stays 100%).
- `src/__tests__/NewJobModal.test.tsx` (extend): reveals tuning; `createJob`
  receives the `tuning` payload with defaults.
</content>
