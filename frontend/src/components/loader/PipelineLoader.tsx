import { StageStepper } from './StageStepper';
import { ActivityLog } from './ActivityLog';
import { IterationCounter } from './IterationCounter';
import { RecruiterPanel } from './RecruiterPanel';
import type { JobSlice } from '../../store/jobsSlice';

interface Props {
  job: JobSlice;
  onAbort: () => void;
  aborting: boolean;
}

export function PipelineLoader({ job, onAbort, aborting }: Props) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="flex flex-col gap-6 sm:gap-8 px-4 sm:px-8 py-6 sm:py-10">
        <div className="flex items-start justify-between gap-3 sm:gap-4">
          <div className="flex flex-col gap-2 min-w-0">
            <span className="eyebrow">Generating</span>
            <h2 className="font-serif text-[22px] sm:text-[28px] leading-tight text-ink">
              {job.humanLabel ?? 'Getting started…'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onAbort}
            disabled={aborting}
            className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint hover:text-fail border border-rule hover:border-fail/40 px-2.5 min-h-9 inline-flex items-center rounded-[2px] transition-colors disabled:opacity-50"
            title="Abort this run"
          >
            {aborting ? 'Stopping…' : 'Stop'}
          </button>
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

        <ActivityLog entries={job.activityLog} />

        <RecruiterPanel
          personaScores={job.personaScores}
          aggregateScore={job.aggregateScore}
          passed={job.passed}
        />
      </div>
    </div>
  );
}
