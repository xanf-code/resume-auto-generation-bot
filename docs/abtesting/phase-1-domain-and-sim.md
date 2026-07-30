# Phase 1 - Domain Model & Deterministic Simulation

**Goal:** Stand up the pure (no React, no DOM, no timers) core of `frontend/src/lib/ab/`: domain types, a replayable PRNG, the roster builder, the config knobs, bracket construction, the dummy scoring math, and the tournament simulator. At the end of this phase a full tournament can be computed and asserted in a test - with nothing on screen.

**Prereq:** none. **Blocks:** Phases 2-5.

## Modules (each <500 lines)

- `frontend/src/lib/ab/types.ts` - domain + timeline types. No runtime code.
- `frontend/src/lib/ab/prng.ts` - `mulberry32(seed: number)`, `hashSeed(s: string): number` (FNV-1a), `newSeedToken(): string`.
- `frontend/src/lib/ab/roster.ts` - `FIXTURE_ROSTER` (16 invented resumes), `competitorsFromJobs(jobs)`, `buildRoster(jobs, size)`.
- `frontend/src/lib/ab/config.ts` - `AbConfig`, `DEFAULT_AB_CONFIG`, `JUDGES` metadata, `ROLE_AFFINITY`, `rebalanceJudgeWeights`.
- `frontend/src/lib/ab/bracket.ts` - `seedOrder(size)`, `buildBracket(competitors, size)`.
- `frontend/src/lib/ab/scoring.ts` - `scoreSide(competitor, ctx): MatchScore`. The only place the dummy math lives.
- `frontend/src/lib/ab/simulate.ts` - `simulateTournament(bracket, seed, config): TournamentResult`.

**Hard rule: zero React imports anywhere under `src/lib/ab/`.** This is an acceptance check, not a style preference - it is what keeps the engine testable without a DOM.

## Type contract

```ts
export type JudgeId = 'ats' | 'hiring_manager' | 'technical' | 'skeptic' | 'peer';
export type BracketSize = 4 | 8 | 16;

/** A resume in the tournament - lifted from a real job, or invented by the fixture roster. */
export interface Competitor {
  id: string;
  label: string;
  origin: 'job' | 'fixture';   // never let a fixture masquerade as the user's data
  baseScore: number;           // 0-100 prior; JobSlice.aggregateScore when available
  traits: Partial<Record<JudgeId, number>>;
  note?: string;
}

export interface JudgeVerdict { judge: JudgeId; score: number }

export interface MatchScore {
  competitorId: string;
  total: number;               // weighted composite of verdicts, 0-100, 1dp
  verdicts: JudgeVerdict[];
  upset: boolean;
}

export interface Match {
  id: string;                  // `r{round}-m{index}` - stable across seeds, safe React key
  round: number;
  index: number;
  side: 'left' | 'right';
  a: string | null;            // null until feeders resolve
  b: string | null;
  next: { matchId: string; slot: 'a' | 'b' } | null;   // null for the final only
}

export interface Round { index: number; name: string; matchIds: string[] }

export interface Bracket {
  size: BracketSize;
  competitors: Competitor[];   // index 0 is the 1-seed
  rounds: Round[];
  matches: Record<string, Match>;
  finalMatchId: string;
}

export interface MatchResult {
  matchId: string; round: number; aId: string; bId: string;
  scoreA: MatchScore; scoreB: MatchScore;
  winnerId: string; loserId: string; margin: number;   // margin >= 0
}

export interface TournamentResult {
  seed: string; bracket: Bracket; config: AbConfig;
  results: MatchResult[];      // first round -> final
  championId: string; runnerUpId: string;
}
```

`AbConfig`, in `config.ts`:

```ts
export type TargetRole = 'backend' | 'frontend' | 'ml' | 'platform' | 'generalist';

export interface AbConfig {
  judges: JudgeId[];                          // min 2
  judgeWeights: Record<JudgeId, number>;      // selected judges normalise to 1.0
  upsetFactor: number;                        // 0 = chalk, 1 = near coin-flip
  bestOf: 1 | 3 | 5;
  targetRole: TargetRole;
  strictness: number;                         // 0-100
  blindJudging: boolean;                      // UI only
}
```

## Seeding

Standard recursive slot order. No byes; guarantees the 1-seed and 2-seed can only meet in the final.

```
seedOrder(2)  = [1, 2]
seedOrder(2n) = seedOrder(n).flatMap(s => [s, 2n + 1 - s])

seedOrder(4)  = [1,4,2,3]
seedOrder(8)  = [1,8,4,5,2,7,3,6]
seedOrder(16) = [1,16,8,9,4,13,5,12,2,15,7,10,3,14,6,11]
```

Seeds are assigned by sorting the selected competitors descending on `baseScore`, ties broken by `id`. Fully deterministic - consumes no randomness.

Round-0 matches with `index < size/4` get `side: 'left'`, the rest `'right'`. Later rounds inherit the side of their feeders. The final is rendered centred.

Round names by distance from the final: `Final`, `Semifinals`, `Quarterfinals`, `Round of 16`.

## Randomness - per-key derived streams

`Math.random` cannot be replayed, so it is **banned everywhere except `newSeedToken()`**. Everything downstream draws from mulberry32, seeded from a user-visible string token (e.g. `mercer-7f31`) through `hashSeed`.

```ts
export function mulberry32(a: number): () => number {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
```

**Do not use one sequential stream.** Derive a generator per read:

```ts
const rng = mulberry32(hashSeed(`${seed}|${matchId}|${competitorId}|${judge}|${read}`));
```

With a single sequential stream, adding a judge or bumping `bestOf` shifts every downstream draw and scrambles unrelated matches. Per-key derivation makes the simulation order-independent and lets a single match be reproduced in isolation in a test.

## Scoring math - per judge, per read

```
prior   = competitor.traits[judge] ?? competitor.baseScore
roleAdj = ROLE_AFFINITY[config.targetRole][judge]           // -6 .. +6
noise   = (rng() * 2 - 1) * (8 + 34 * config.upsetFactor)   // ±8 .. ±42
form    = round * 0.75
raw     = prior + roleAdj + noise + form - config.strictness * 0.12
read    = clamp(raw, 0, 100)
```

- `verdict.score` = mean of `bestOf` reads. Variance shrinks by sqrt(N), so best-of is real math, not decoration.
- `total` = sum of `verdict.score * normalisedWeight[judge]`, rounded to 1dp.
- Higher `total` wins. On an exact tie the better seed wins - deterministic, consumes no extra draw.
- `upset = winner.baseScore < loser.baseScore`.
- **Special-case `upsetFactor === 0` to zero the noise entirely.** At the default amplitude ±8 would still allow upsets; zeroing gives a crisp assertable property: **chalk mode means the top seed always wins.**

`strictness` is a uniform penalty - it cannot change *who* wins, but it moves scores across the pass/fail threshold so `passColor` (`src/lib/scoring.ts:9`) means something.

## Roster

`buildRoster(jobs, size)`:
- Map store jobs -> `Competitor` with `origin: 'job'`, `baseScore = aggregateScore ?? derived-from-seeded-default`, `traits` seeded from `personaScores` where present.
- Sort descending by `baseScore`; take the top `size`.
- If fewer than `size`, pad from `FIXTURE_ROSTER` with `origin: 'fixture'`, skipping any id collision.
- Always returns exactly `size` competitors with unique ids.

`buildBracket` **throws** on a length mismatch rather than silently slicing. The UI enforces `selected.length === size`, so a mismatch is a bug, not a user state.

## TDD

### RED

- `frontend/src/__tests__/ab.prng.test.ts`: `mulberry32(1)` yields three known fixed values (locks the constants against refactor); same seed -> identical sequence, different seed -> different; `hashSeed` stable for the same string and differs on a one-character change; every output in `[0, 1)`.
- `frontend/src/__tests__/ab.bracket.test.ts`: `seedOrder(4)` === `[1,4,2,3]`; `seedOrder(8)` === `[1,8,4,5,2,7,3,6]`; `seedOrder(16).slice(0,4)` === `[1,16,8,9]`; every seed `1..size` appears exactly once; `log2(size)` rounds and round *r* has `size / 2^(r+1)` matches; every non-final `next` points at an existing match; exactly one match has `next === null` and it equals `finalMatchId`; each round-*r+1* match is the target of exactly two feeders, once in slot `a` and once in slot `b`; round-0 splits evenly left/right; round names for size 4 are `['Semifinals','Final']` and for size 16 start at `'Round of 16'`; throws when `competitors.length !== size`.
- `frontend/src/__tests__/ab.roster.test.ts`: fewer jobs than `size` -> padded from fixture, length === `size`, no duplicate ids; more jobs than `size` -> top `size` by `aggregateScore`; a job with `aggregateScore: undefined` still yields a finite `baseScore`; `FIXTURE_ROSTER` has >=16 entries with unique ids; `origin` is `'job'` for store-derived and `'fixture'` for padding.
- `frontend/src/__tests__/ab.simulate.test.ts`: **determinism** - same `(bracket, seed, config)` `toEqual` across two calls; different seed -> different `results`; `results.length === size - 1`, ordered by round ascending; every match's `aId`/`bId` are the winners of its two feeders; `championId` is the winner of `finalMatchId`; **chalk** - `upsetFactor: 0` with distinct `baseScore`s means the 1-seed wins every match it plays; **best-of reduces variance** - over 50 *fixed* seeds at a mid upset factor, upset count at `bestOf: 5` < at `bestOf: 1` (statistical in spirit, fully deterministic in fact, cannot flake); `judges: ['ats']` -> one verdict per side and `total === verdict.score`; every `total` within `[0, 100]`; `upset` true iff `winner.baseScore < loser.baseScore`; changing `targetRole` changes at least one `total`.

### GREEN

Implement the seven modules to pass. `simulateTournament` is a fold over the bracket - it must not mutate its input; the `bracket` on the returned `TournamentResult` is a fresh object with `a`/`b` populated.

## Acceptance

```bash
cd frontend
npx vitest run src/__tests__/ab.prng src/__tests__/ab.bracket src/__tests__/ab.roster src/__tests__/ab.simulate
npm run lint
grep -rn "from 'react'" src/lib/ab/ && echo "FAIL: React import in lib/ab" || echo "OK"
```

All green, files each <500 lines, zero React imports under `src/lib/ab/`.

## Files

`frontend/src/lib/ab/{types,prng,roster,config,bracket,scoring,simulate}.ts`,
`frontend/src/__tests__/{ab.prng,ab.bracket,ab.roster,ab.simulate}.test.ts`.
