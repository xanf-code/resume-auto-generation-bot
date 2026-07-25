// Roster construction for the A/B tournament: turns real jobs (and, when there
// aren't enough of them, hand-authored fixtures) into a fixed-size bracket of
// Competitors. No React, no DOM, no Math.random - everything derived from a job
// is deterministic so a tournament seed can always be replayed.

import { mulberry32, hashSeed } from './prng';
import { personaAverage } from '../scoring';
import type { Competitor, JudgeId, BracketSize } from './types';
import type { JobSlice } from '../../store/jobsSlice';

const JUDGE_IDS: readonly JudgeId[] = ['ats', 'hiring_manager', 'technical', 'skeptic', 'peer'];

// Pseudo-score range used when a job has no aggregateScore yet. Deliberately
// modest (45-85) so an unscored job never looks like a guaranteed top seed.
const PSEUDO_SCORE_MIN = 45;
const PSEUDO_SCORE_SPAN = 40;

/** Hand-authored fixture roster: invented candidates used to pad a bracket
 * when there aren't yet enough real jobs to fill it. Deterministic - no
 * randomness - so snapshots and tests never flake. */
export const FIXTURE_ROSTER: Competitor[] = [
  {
    id: 'fixture-1',
    label: 'Priya Anand — Staff Backend Engineer',
    origin: 'fixture',
    baseScore: 92,
    traits: { ats: 88, hiring_manager: 90, technical: 95, skeptic: 85, peer: 91 },
  },
  {
    id: 'fixture-2',
    label: 'Marcus Webb — Senior Platform Engineer',
    origin: 'fixture',
    baseScore: 88,
    traits: { ats: 84, hiring_manager: 86, technical: 92, skeptic: 80, peer: 87 },
  },
  {
    id: 'fixture-3',
    label: 'Elena Fischer — ML Research Engineer',
    origin: 'fixture',
    baseScore: 85,
    traits: { ats: 79, hiring_manager: 83, technical: 94, skeptic: 76, peer: 82 },
  },
  {
    id: 'fixture-4',
    label: 'Jordan Lee — Full-Stack Developer',
    origin: 'fixture',
    baseScore: 80,
    traits: { ats: 82, hiring_manager: 78, technical: 81, skeptic: 74, peer: 79 },
  },
  {
    id: 'fixture-5',
    label: 'Sofia Ramirez — Frontend Engineer',
    origin: 'fixture',
    baseScore: 78,
    traits: { ats: 80, hiring_manager: 76, technical: 75, skeptic: 70, peer: 81 },
  },
  {
    id: 'fixture-6',
    label: 'Kenji Sato — DevOps / SRE Lead',
    origin: 'fixture',
    baseScore: 76,
    traits: { ats: 74, hiring_manager: 77, technical: 83, skeptic: 68, peer: 75 },
  },
  {
    id: 'fixture-7',
    label: 'Amara Okafor — Data Engineer',
    origin: 'fixture',
    baseScore: 74,
    traits: { ats: 77, hiring_manager: 72, technical: 79, skeptic: 65, peer: 73 },
  },
  {
    id: 'fixture-8',
    label: 'Liam O’Brien — Junior Backend Developer',
    origin: 'fixture',
    baseScore: 70,
    traits: { ats: 71, hiring_manager: 68, technical: 66, skeptic: 60, peer: 69 },
  },
  {
    id: 'fixture-9',
    label: 'Ingrid Larsen — Mobile Engineer (iOS)',
    origin: 'fixture',
    baseScore: 68,
    traits: { ats: 66, hiring_manager: 70, technical: 71, skeptic: 62, peer: 67 },
  },
  {
    id: 'fixture-10',
    label: 'Diego Morales — QA / Test Automation Engineer',
    origin: 'fixture',
    baseScore: 65,
    traits: { ats: 69, hiring_manager: 63, technical: 60, skeptic: 58, peer: 64 },
  },
  {
    id: 'fixture-11',
    label: 'Hannah Kim — Product-Minded Frontend Dev',
    origin: 'fixture',
    baseScore: 62,
    traits: { ats: 60, hiring_manager: 65, technical: 58, skeptic: 55, peer: 63 },
  },
  {
    id: 'fixture-12',
    label: 'Tomás Silva — Cloud Infrastructure Engineer',
    origin: 'fixture',
    baseScore: 60,
    traits: { ats: 63, hiring_manager: 58, technical: 66, skeptic: 52, peer: 59 },
  },
  {
    id: 'fixture-13',
    label: 'Nadia Petrova — Security Engineer',
    origin: 'fixture',
    baseScore: 57,
    traits: { ats: 55, hiring_manager: 59, technical: 62, skeptic: 50, peer: 56 },
  },
  {
    id: 'fixture-14',
    label: 'Owen Bennett — Recent Bootcamp Grad',
    origin: 'fixture',
    baseScore: 52,
    traits: { ats: 58, hiring_manager: 50, technical: 45, skeptic: 40, peer: 53 },
  },
  {
    id: 'fixture-15',
    label: 'Chidi Eze — Career-Changer, Ex-Teacher',
    origin: 'fixture',
    baseScore: 48,
    traits: { ats: 50, hiring_manager: 47, technical: 40, skeptic: 38, peer: 49 },
  },
  {
    id: 'fixture-16',
    label: 'Freya Nilsson — Generalist Applicant',
    origin: 'fixture',
    baseScore: 43,
    traits: { ats: 45, hiring_manager: 42, technical: 38, skeptic: 35, peer: 44 },
    note: 'Untargeted résumé, sent to every role verbatim.',
  },
];

/** Deterministic 45-85 pseudo-score derived from the job id, used only when a
 * job has no aggregateScore yet (e.g. still running). Never NaN. */
function pseudoScoreFromId(jobId: string): number {
  const rand = mulberry32(hashSeed(jobId));
  return PSEUDO_SCORE_MIN + rand() * PSEUDO_SCORE_SPAN;
}

function traitsFromPersonaScores(job: JobSlice): Partial<Record<JudgeId, number>> {
  const traits: Partial<Record<JudgeId, number>> = {};
  for (const judgeId of JUDGE_IDS) {
    const entry = job.personaScores[judgeId];
    if (entry) {
      traits[judgeId] = personaAverage(entry);
    }
  }
  return traits;
}

/** Maps live jobs to tournament Competitors. Always origin 'job', always a
 * finite baseScore even when the job hasn't produced an aggregateScore yet. */
export function competitorsFromJobs(jobs: JobSlice[]): Competitor[] {
  return jobs.map((job) => ({
    id: job.job_id,
    label: job.label,
    origin: 'job',
    baseScore: job.aggregateScore ?? pseudoScoreFromId(job.job_id),
    traits: traitsFromPersonaScores(job),
  }));
}

function byBaseScoreDescThenIdAsc(a: Competitor, b: Competitor): number {
  if (b.baseScore !== a.baseScore) return b.baseScore - a.baseScore;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

/** Builds an exact-size bracket roster: top jobs by baseScore, padded from
 * FIXTURE_ROSTER (skipping id collisions) when there aren't enough jobs. */
export function buildRoster(jobs: JobSlice[], size: BracketSize): Competitor[] {
  const fromJobs = competitorsFromJobs(jobs).sort(byBaseScoreDescThenIdAsc);
  const selected = fromJobs.slice(0, size);

  if (selected.length >= size) {
    return selected;
  }

  const usedIds = new Set(selected.map((c) => c.id));
  const padded = [...selected];
  for (const fixture of FIXTURE_ROSTER) {
    if (padded.length >= size) break;
    if (usedIds.has(fixture.id)) continue;
    padded.push(fixture);
    usedIds.add(fixture.id);
  }

  return padded;
}
