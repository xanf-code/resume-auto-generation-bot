import { STAGE_ORDER, stageIndex } from '../../lib/stages';

interface Props {
  currentStage: string;
  iteration: number;
}

type StageStatus = 'done' | 'current' | 'pending';

const MARKER: Record<StageStatus, string> = {
  done: '✓',
  current: '●',
  pending: '○',
};

const COLOR: Record<StageStatus, string> = {
  done: 'text-ink-soft',
  current: 'text-accent',
  pending: 'text-ink-faint',
};

export function StageStepper({ currentStage, iteration }: Props) {
  const currentIdx = stageIndex(currentStage);

  return (
    <ol className="flex flex-wrap gap-x-4 gap-y-2 items-center">
      {STAGE_ORDER.map((stage, idx) => {
        const status: StageStatus =
          idx < currentIdx ? 'done' : stage === currentStage ? 'current' : 'pending';

        return (
          <li key={stage} data-status={status} className="flex items-center gap-1.5">
            <span
              className={`flex items-center gap-1.5 text-[13px] ${COLOR[status]} ${
                status === 'current' ? 'animate-pulse' : ''
              }`}
            >
              <span className="text-[10px] leading-none">{MARKER[status]}</span>
              <span className="capitalize font-sans tracking-wide">{stage}</span>
            </span>
            {stage === 'writer' && status === 'current' && iteration > 0 && (
              <span
                data-testid="iteration-badge"
                className="font-mono text-[10px] text-accent border border-accent/40 px-1.5 py-0.5 rounded-[2px]"
              >
                iter {iteration}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
