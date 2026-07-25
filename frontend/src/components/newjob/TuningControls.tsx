import {
  RUBRIC_FIELDS,
  SCALAR_FIELDS,
  rebalanceWeights,
  weightsSum,
  type RubricKey,
  type ScalarKey,
  type Tuning,
} from '../../lib/tuning';
import { SliderRow } from './SliderRow';

interface Props {
  tuning: Tuning;
  onChange: (tuning: Tuning) => void;
}

const pct = (v: number): string => `${Math.round(v * 100)}%`;

/**
 * Always-visible pipeline tuning panel for the New Application playground
 * config column: scalar knobs plus live-balanced rubric weights (sum to 100%).
 */
export function TuningControls({ tuning, onChange }: Props) {
  const setScalar = (key: ScalarKey, value: number) =>
    onChange({ ...tuning, [key]: value });

  const setWeight = (key: RubricKey, value: number) =>
    onChange({
      ...tuning,
      rubric_weights: rebalanceWeights(tuning.rubric_weights, key, value),
    });

  const sum = weightsSum(tuning.rubric_weights);

  return (
    <div className="flex flex-col gap-4">
      <span className="eyebrow">Loop & thresholds</span>
      <div className="grid grid-cols-1 gap-y-4">
        {SCALAR_FIELDS.map((f) => (
          <SliderRow
            key={f.key}
            label={f.label}
            help={f.help}
            min={f.min}
            max={f.max}
            step={f.step}
            value={tuning[f.key]}
            onChange={(v) => setScalar(f.key, v)}
            valueLabel={String(tuning[f.key])}
          />
        ))}
      </div>

      <div className="flex flex-col gap-3 border border-rule rounded-[3px] p-3.5 bg-paper-raised">
        <div className="flex items-center justify-between">
          <span className="eyebrow">Rubric weights</span>
          <span className="font-mono text-[12px] text-ink-soft tabular-nums">
            Σ {pct(sum)}
          </span>
        </div>
        <div className="grid grid-cols-1 gap-y-4">
          {RUBRIC_FIELDS.map((f) => (
            <SliderRow
              key={f.key}
              label={f.label}
              help={f.help}
              min={0}
              max={1}
              step={0.01}
              value={tuning.rubric_weights[f.key]}
              onChange={(v) => setWeight(f.key, v)}
              valueLabel={pct(tuning.rubric_weights[f.key])}
            />
          ))}
        </div>
        <p className="text-[11px] text-ink-faint leading-snug">
          Moving one weight rebalances the rest so the five always total 100%.
        </p>
      </div>
    </div>
  );
}
