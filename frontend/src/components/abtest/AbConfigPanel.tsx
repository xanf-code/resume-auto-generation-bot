import { useId } from 'react';
import type { AbConfig, JudgeId, TargetRole } from '../../lib/ab/types';
import { JUDGES, rebalanceJudgeWeights } from '../../lib/ab/config';
import { SliderRow } from '../newjob/SliderRow';
import { HelpTip } from '../newjob/HelpTip';

interface Props {
  config: AbConfig;
  onChange: (config: AbConfig) => void;
  seed: string;
  onSeedChange: (seed: string) => void;
}

const MIN_JUDGES = 2;
const BEST_OF_OPTIONS: readonly (1 | 3 | 5)[] = [1, 3, 5];

const ROLE_LABELS: Record<TargetRole, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  ml: 'ML',
  platform: 'Platform',
  generalist: 'Generalist',
};

const TARGET_ROLES: readonly TargetRole[] = [
  'backend',
  'frontend',
  'ml',
  'platform',
  'generalist',
];

const selectClass =
  'w-full bg-paper-raised border border-rule text-ink text-[13px] px-2.5 py-2 rounded-[3px] focus:outline-none focus:border-accent/60';

const pct = (v: number): string => `${Math.round(v * 100)}%`;

/**
 * Toggle a judge on/off the panel, keeping `judgeWeights` normalised to 1.0
 * across whichever judges remain selected. Never drops below MIN_JUDGES -
 * callers should also disable the checkbox so the UI explains why.
 *
 * Adding a judge pins its starting share at an even 1/n and rebalances the
 * rest proportionally (via `rebalanceJudgeWeights`); removing one pins an
 * arbitrary remaining judge at its current weight and lets the rest absorb
 * the freed-up share proportionally to their existing ratios.
 */
function toggleJudge(config: AbConfig, judgeId: JudgeId): AbConfig {
  const isSelected = config.judges.includes(judgeId);

  if (isSelected) {
    if (config.judges.length <= MIN_JUDGES) return config;
    const judges = config.judges.filter((j) => j !== judgeId);
    const anchor = judges[0];
    const judgeWeights = rebalanceJudgeWeights(
      config.judgeWeights,
      judges,
      anchor,
      config.judgeWeights[anchor],
    );
    return { ...config, judges, judgeWeights };
  }

  const judges = [...config.judges, judgeId];
  const judgeWeights = rebalanceJudgeWeights(
    config.judgeWeights,
    judges,
    judgeId,
    1 / judges.length,
  );
  return { ...config, judges, judgeWeights };
}

/**
 * Full tournament configuration panel: judging panel, live-rebalanced
 * per-judge weights, the headline chalk/chaos dial, match format, target
 * role, strictness, blind judging, and the run seed. Every knob mutates
 * `config` immutably via `onChange({ ...config, ... })`.
 */
export function AbConfigPanel({ config, onChange, seed, onSeedChange }: Props) {
  const targetRoleId = useId();
  const seedId = useId();

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2.5">
        <span className="eyebrow">Judging panel</span>
        {JUDGES.map((judge) => {
          const checked = config.judges.includes(judge.id);
          const disabled = checked && config.judges.length <= MIN_JUDGES;
          return (
            <label
              key={judge.id}
              className={`flex items-center gap-2 text-[13px] select-none ${
                disabled ? 'opacity-50 cursor-not-allowed text-ink-faint' : 'cursor-pointer text-ink-soft'
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={() => onChange(toggleJudge(config, judge.id))}
                className="accent-[#c0362c] w-4 h-4 shrink-0"
              />
              <span>{judge.label}</span>
              <HelpTip text={judge.description} label={judge.label} />
            </label>
          );
        })}
      </div>

      <div className="flex flex-col gap-3">
        <span className="eyebrow">Panel weights</span>
        <div className="grid grid-cols-1 gap-y-4">
          {config.judges.map((judgeId) => {
            const meta = JUDGES.find((j) => j.id === judgeId);
            const label = meta?.label ?? judgeId;
            const value = config.judgeWeights[judgeId];
            return (
              <SliderRow
                key={judgeId}
                label={label}
                help={meta?.description ?? ''}
                min={0}
                max={1}
                step={0.01}
                value={value}
                valueLabel={pct(value)}
                onChange={(v) =>
                  onChange({
                    ...config,
                    judgeWeights: rebalanceJudgeWeights(
                      config.judgeWeights,
                      config.judges,
                      judgeId,
                      v,
                    ),
                  })
                }
              />
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-3 border border-rule rounded-[3px] p-3.5 bg-paper-raised">
        <span className="eyebrow">Upset factor</span>
        <SliderRow
          label="Chalk ↔ Chaos"
          help="0 = chalk, favorites always win. 1 = near coin-flip, upsets everywhere."
          min={0}
          max={1}
          step={0.01}
          value={config.upsetFactor}
          valueLabel={pct(config.upsetFactor)}
          onChange={(v) => onChange({ ...config, upsetFactor: v })}
        />
      </div>

      <div className="flex flex-col gap-2">
        <span className="eyebrow">Reads per match</span>
        <div
          className="flex border-b border-rule"
          role="radiogroup"
          aria-label="Best of"
        >
          {BEST_OF_OPTIONS.map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={config.bestOf === n}
              onClick={() => onChange({ ...config, bestOf: n })}
              className={`flex-1 text-[13px] py-2.5 transition-colors ${
                config.bestOf === n
                  ? 'text-ink border-b-2 border-accent font-medium'
                  : 'text-ink-soft'
              }`}
            >
              Best of {n}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="eyebrow" htmlFor={targetRoleId}>
          Target role
        </label>
        <select
          id={targetRoleId}
          className={selectClass}
          value={config.targetRole}
          onChange={(e) =>
            onChange({ ...config, targetRole: e.target.value as TargetRole })
          }
        >
          {TARGET_ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-3">
        <span className="eyebrow">Scoring</span>
        <SliderRow
          label="Panel strictness"
          help="How harshly judges penalize weak or generic bullets. Higher reads stricter."
          min={0}
          max={100}
          step={1}
          value={config.strictness}
          valueLabel={String(config.strictness)}
          onChange={(v) => onChange({ ...config, strictness: v })}
        />
        <label className="flex items-center gap-2.5 text-[13px] text-ink-soft cursor-pointer select-none">
          <input
            type="checkbox"
            checked={config.blindJudging}
            onChange={(e) => onChange({ ...config, blindJudging: e.target.checked })}
            className="accent-[#c0362c] w-4 h-4"
          />
          Blind judging
        </label>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="eyebrow" htmlFor={seedId}>
          Seed
        </label>
        <input
          id={seedId}
          type="text"
          value={seed}
          onChange={(e) => onSeedChange(e.target.value)}
          placeholder="e.g. 2024-summer-run"
          className="font-mono bg-paper-raised border border-rule text-ink text-[13px] px-3 py-2.5 rounded-[3px] focus:outline-none focus:border-accent/60 placeholder:text-ink-faint"
        />
        <p className="text-[11px] text-ink-faint leading-snug">
          This seed determines every draw for the run - same seed, same bracket.
        </p>
      </div>
    </div>
  );
}
