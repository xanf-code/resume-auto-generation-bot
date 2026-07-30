// Domain + timeline types for the A/B testing résumé tournament. No runtime code.

export type JudgeId = 'ats' | 'hiring_manager' | 'technical' | 'skeptic' | 'peer';
export type BracketSize = 4 | 8 | 16;

/** A résumé in the tournament - lifted from a real job, or invented by the fixture roster. */
export interface Competitor {
  id: string;
  label: string;
  origin: 'job' | 'fixture'; // never let a fixture masquerade as the user's data
  baseScore: number; // 0-100 prior; JobSlice.aggregateScore when available
  traits: Partial<Record<JudgeId, number>>;
  note?: string;
}

export interface JudgeVerdict {
  judge: JudgeId;
  score: number;
}

export interface MatchScore {
  competitorId: string;
  total: number; // weighted composite of verdicts, 0-100, 1dp
  verdicts: JudgeVerdict[];
  upset: boolean;
}

export interface Match {
  id: string; // `r{round}-m{index}` - stable across seeds, safe React key
  round: number;
  index: number;
  side: 'left' | 'right';
  a: string | null; // null until feeders resolve
  b: string | null;
  next: { matchId: string; slot: 'a' | 'b' } | null; // null for the final only
}

export interface Round {
  index: number;
  name: string;
  matchIds: string[];
}

export interface Bracket {
  size: BracketSize;
  competitors: Competitor[]; // index 0 is the 1-seed
  rounds: Round[];
  matches: Record<string, Match>;
  finalMatchId: string;
}

export interface MatchResult {
  matchId: string;
  round: number;
  aId: string;
  bId: string;
  scoreA: MatchScore;
  scoreB: MatchScore;
  winnerId: string;
  loserId: string;
  margin: number; // margin >= 0
}

export interface TournamentResult {
  seed: string;
  bracket: Bracket;
  config: AbConfig;
  results: MatchResult[]; // first round -> final
  championId: string;
  runnerUpId: string;
}

export type TargetRole = 'backend' | 'frontend' | 'ml' | 'platform' | 'generalist';

export interface AbConfig {
  judges: JudgeId[]; // min 2
  judgeWeights: Record<JudgeId, number>; // selected judges normalise to 1.0
  upsetFactor: number; // 0 = chalk, 1 = near coin-flip
  bestOf: 1 | 3 | 5;
  targetRole: TargetRole;
  strictness: number; // 0-100
  blindJudging: boolean; // UI only
}

// --- Timeline types (phase 2) -------------------------------------------------

export type StepKind =
  | 'tournament-intro' // title card; bracket fades in seeded
  | 'round-intro' // round name sweeps in
  | 'match-focus' // bracket dims, spotlight opens on the pair
  | 'match-score' // bars race, numbers count up
  | 'match-verdict' // winner flash, loser fades
  | 'match-advance' // winner travels to its next slot, connector draws
  | 'round-outro' // spotlight closes, bracket un-dims
  | 'champion';

export interface TimelineStep {
  id: string; // `${kind}:${matchId ?? round}` - unique, readable in assertions
  kind: StepKind;
  durationMs: number; // at 1x; never 0 - a zero-length step cannot be seeked to
  startMs: number; // cumulative at 1x - makes seeking a binary search, not a replay
  round: number;
  matchId?: string;
  result?: MatchResult; // denormalised so render never does a lookup
}

export interface Timeline {
  steps: TimelineStep[];
  totalMs: number;
}
