import { useCountUp } from '../../hooks/useCountUp';
import { JUDGES } from '../../lib/ab/config';
import type { MatchScore } from '../../lib/ab/types';

interface Props {
  label?: string; // competitor label; undefined if masked (blind judging pre-verdict)
  seed?: number;
  score?: MatchScore; // undefined until this side's score has landed
  outcome?: 'won' | 'lost'; // undefined while the match is still in progress
  animate: boolean; // false under reduced motion or when skipped-to
  masked?: boolean; // blind judging: hide `label` until `outcome` is set
}

const BAR_TRANSITION = 'transform 900ms cubic-bezier(.16,1,.3,1)';

const SIDE_TONE: Record<'won' | 'lost' | 'pending', string> = {
  won: 'text-ink',
  lost: 'text-ink-faint opacity-60',
  pending: 'text-ink-soft',
};

function judgeLabel(judgeId: string): string {
  return JUDGES.find((j) => j.id === judgeId)?.label ?? judgeId;
}

/** One side of a head-to-head match panel: identity, the racing score bar and
 * total count-up, and the per-judge verdict breakdown. Owns the bar-race
 * animation (`transform: scaleX`, never `width`, so it stays compositor-only)
 * and keeps the numeric readout as a sibling so scaling the bar never
 * squashes the label. */
export function HeadToHeadScore({ label, seed, score, outcome, animate, masked }: Props) {
  const revealed = outcome !== undefined;
  const showPlaceholder = masked === true && !revealed;
  const displayLabel = showPlaceholder ? 'Candidate' : (label ?? '');

  const total = useCountUp(score?.total ?? 0, 900, { enabled: animate });
  const fraction = Math.max(0, Math.min((score?.total ?? 0) / 100, 1));

  const tone = SIDE_TONE[outcome ?? 'pending'];

  return (
    <div className={`flex flex-col gap-2 ${tone}`} data-outcome={outcome ?? 'pending'}>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-[11px] text-ink-faint shrink-0">{seed ?? ''}</span>
        <span className="font-serif text-[15px] truncate">{displayLabel}</span>
      </div>

      <span
        className={`font-mono tabular-nums text-[20px] ${outcome === 'won' ? 'text-accent' : ''}`}
      >
        {total.toFixed(1)}
      </span>

      <div className="h-2 bg-paper-raised border border-rule rounded-[2px] overflow-hidden">
        <div
          className="h-full bg-accent"
          style={{
            transform: `scaleX(${fraction})`,
            transformOrigin: 'left',
            transition: animate ? BAR_TRANSITION : 'none',
          }}
        />
      </div>

      {score && (
        <ul className="flex flex-col gap-1">
          {score.verdicts.map((verdict) => (
            <li key={verdict.judge} className="flex items-center justify-between text-[12px]">
              <span className="text-ink-soft">{judgeLabel(verdict.judge)}</span>
              <span className="font-mono tabular-nums">{verdict.score}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
