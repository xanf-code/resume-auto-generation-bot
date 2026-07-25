import { StageStepper } from './StageStepper';
import { IterationCounter } from './IterationCounter';
import { RecruiterPanel } from './RecruiterPanel';
import type { JobSlice } from '../../store/jobsSlice';

interface Props {
  job: JobSlice;
}

export function PipelineLoader({ job }: Props) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="flex flex-col gap-8 px-8 py-10">
        <div className="flex flex-col gap-2">
          <span className="eyebrow">On the press</span>
          <h2 className="font-serif text-[28px] leading-tight text-ink">
            {job.humanLabel ?? 'Setting the type…'}
          </h2>
        </div>

        <StageStepper currentStage={job.stage ?? 'init'} iteration={job.iteration} />

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-4">
            <div className="flex-1 h-[3px] bg-rule rounded-full overflow-hidden">
              <div
                className="h-full bg-accent transition-all duration-500 ease-out"
                style={{ width: `${job.pct}%` }}
              />
            </div>
            <span className="font-mono text-[12px] text-ink-faint tabular-nums w-10 text-right">
              {job.pct}%
            </span>
          </div>
          <IterationCounter iteration={job.iteration} />
        </div>

        <RecruiterPanel
          personaScores={job.personaScores}
          aggregateScore={job.aggregateScore}
          passed={job.passed}
        />
      </div>
    </div>
  );
}
