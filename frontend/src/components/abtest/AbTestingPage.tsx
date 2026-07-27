import { useMemo, useState } from 'react';
import { AbEmptyState } from './AbEmptyState';
import { AbSetupModal } from './AbSetupModal';
import { TournamentArena } from './TournamentArena';
import { buildRoster } from '../../lib/ab/roster';
import { buildBracket } from '../../lib/ab/bracket';
import { simulateTournament } from '../../lib/ab/simulate';
import { buildTimeline } from '../../lib/ab/timeline';
import { DEFAULT_AB_CONFIG } from '../../lib/ab/config';
import { newSeedToken } from '../../lib/ab/prng';
import { useMediaQuery, REDUCED_MOTION_MQ } from '../../hooks/useMediaQuery';
import { useStore } from '../../store';
import type { AbConfig, BracketSize, Competitor } from '../../lib/ab/types';

type Phase = 'idle' | 'setup' | 'running';

/** A/B testing route root: owns setup flow state and hands the simulated
 * result + timeline off to `TournamentArena` for live playback. */
export function AbTestingPage() {
  const jobsMap = useStore((s) => s.jobs);
  const jobs = Object.values(jobsMap);
  const [phase, setPhase] = useState<Phase>('idle');
  const [seed, setSeed] = useState(newSeedToken);
  const [config, setConfig] = useState<AbConfig>(DEFAULT_AB_CONFIG);
  const [size, setSize] = useState<BracketSize>(8);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const reducedMotion = useMediaQuery(REDUCED_MOTION_MQ);

  const pool = useMemo(() => buildRoster(jobs, 16), [jobs]);
  const chosen = useMemo(
    () =>
      selectedIds
        .map((id) => pool.find((c) => c.id === id))
        .filter((c): c is Competitor => Boolean(c)),
    [selectedIds, pool],
  );
  const result = useMemo(
    () =>
      phase === 'running' && chosen.length === size
        ? simulateTournament(buildBracket(chosen, size), seed, config)
        : null,
    [phase, chosen, size, seed, config],
  );
  const timeline = useMemo(
    () => (result ? buildTimeline(result, { reducedMotion }) : null),
    [result, reducedMotion],
  );

  const handleStart = (payload: {
    selectedIds: string[];
    size: BracketSize;
    config: AbConfig;
    seed: string;
  }): void => {
    setSelectedIds(payload.selectedIds);
    setSize(payload.size);
    setConfig(payload.config);
    setSeed(payload.seed);
    setPhase('running');
  };

  return (
    <div className="h-full">
      {phase !== 'running' && (
        <AbEmptyState jobCount={jobs.length} onOpenModal={() => setPhase('setup')} />
      )}

      {phase === 'setup' && (
        <AbSetupModal pool={pool} onClose={() => setPhase('idle')} onStart={handleStart} />
      )}

      {phase === 'running' && result && timeline && (
        <TournamentArena
          result={result}
          timeline={timeline}
          blindJudging={config.blindJudging}
          judges={config.judges}
          reducedMotion={reducedMotion}
          onReplay={() => setSeed(newSeedToken())}
        />
      )}
    </div>
  );
}
