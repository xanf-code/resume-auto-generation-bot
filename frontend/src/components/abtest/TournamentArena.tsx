// Live playback wiring: drives `useTournamentPlayback` off a precomputed
// `TournamentResult` + `Timeline` and maps the current `TimelineStep` onto
// the bracket canvas (dimmed/active/advancing), the spotlight HUD (open/
// scores/outcome), a round-intro banner, the champion reveal, and the
// playback transport bar. No simulation logic lives here - this component
// only interprets already-computed data for rendering.

import { useEffect, useState } from 'react';
import type { Competitor, JudgeId, StepKind, Timeline, TournamentResult } from '../../lib/ab/types';
import { useTournamentPlayback } from '../../hooks/useTournamentPlayback';
import { BracketCanvas } from './BracketCanvas';
import { SpotlightHud } from './SpotlightHud';
import {
  DEFAULT_MATCH_DURATION_SEC,
  PlaybackBar,
  speedFromMatchSeconds,
  type MatchDurationSec,
} from './PlaybackBar';
import { ChampionBanner } from './ChampionBanner';

interface Props {
  result: TournamentResult;
  timeline: Timeline;
  blindJudging: boolean;
  judges: JudgeId[];
  reducedMotion: boolean;
  onReplay: () => void;
}

const DIMMED_KINDS: StepKind[] = ['match-focus', 'match-score', 'match-verdict', 'match-advance'];
const HUD_OPEN_KINDS: StepKind[] = ['match-focus', 'match-score', 'match-verdict'];

/** Looks up a competitor by id, throwing (rather than silently rendering
 * nothing) if the tournament's own data is somehow inconsistent - this
 * should never happen for ids drawn from the tournament's own bracket/results. */
function findCompetitor(result: TournamentResult, id: string): Competitor {
  const competitor = result.bracket.competitors.find((c) => c.id === id);
  if (!competitor) {
    throw new Error(`TournamentArena: no competitor found for id "${id}"`);
  }
  return competitor;
}

/** 1-indexed seed of a competitor id (index 0 in `bracket.competitors` === seed 1). */
function seedOf(result: TournamentResult, id: string | null): number | undefined {
  if (id === null) return undefined;
  const index = result.bracket.competitors.findIndex((c) => c.id === id);
  return index === -1 ? undefined : index + 1;
}

/** A fully-resolved bracket's match.a/match.b are never actually null - this
 * just narrows the nullable domain type for callers that need the id. */
function requireCompetitorId(id: string | null, context: string): string {
  if (id === null) {
    throw new Error(`TournamentArena: expected a resolved competitor id for ${context}`);
  }
  return id;
}

export function TournamentArena({
  result,
  timeline,
  blindJudging,
  judges,
  reducedMotion,
  onReplay,
}: Props) {
  const [matchSeconds, setMatchSeconds] = useState<MatchDurationSec>(DEFAULT_MATCH_DURATION_SEC);
  const [hudVisible, setHudVisible] = useState(true);
  const [state, controls] = useTournamentPlayback(timeline, {
    reducedMotion,
    initialSpeed: speedFromMatchSeconds(DEFAULT_MATCH_DURATION_SEC),
  });

  // A skip never tries to tween the final frame.
  const [justSkipped, setJustSkipped] = useState(false);
  useEffect(() => {
    setJustSkipped(false);
  }, [timeline]);

  // Dismissing the champion card only hides it - the bracket underneath (all
  // rounds, all fixtures) stays exactly as it was. Resets on replay/new timeline.
  const [championDismissed, setChampionDismissed] = useState(false);
  useEffect(() => {
    setChampionDismissed(false);
  }, [timeline]);

  const handleSkip = (): void => {
    setJustSkipped(true);
    controls.skipToEnd();
  };

  const handleSetMatchSeconds = (sec: MatchDurationSec): void => {
    setMatchSeconds(sec);
    controls.setSpeed(speedFromMatchSeconds(sec));
  };

  const animate = !reducedMotion && !justSkipped;
  const step = state.step;

  const dimmed = step ? DIMMED_KINDS.includes(step.kind) : false;
  const hudOpen = step ? HUD_OPEN_KINDS.includes(step.kind) : false;
  const activeMatchId = step?.matchId ?? null;
  const advancingMatchId = step?.kind === 'match-advance' ? (step.matchId ?? null) : null;
  const showRoundBanner = step?.kind === 'round-intro';
  const showChampion = step?.kind === 'champion';

  // Round-following mobile pager, still user-overridable via BracketCanvas'
  // own onActiveRoundChange. `tournament-intro` carries the sentinel
  // `round: -1` (it precedes every round), which is not a valid pager index -
  // ignore it and let the pager land on round 0 once real rounds start.
  const [activeRound, setActiveRound] = useState(0);
  useEffect(() => {
    if (step && step.round >= 0) setActiveRound(step.round);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step?.round]);

  const activeMatch = activeMatchId ? result.bracket.matches[activeMatchId] : null;
  // The ALWAYS-available precomputed result for the match currently in focus
  // - NOT gated by `state.resolved` (that's the canvas's own, playback-narrowed view).
  const trueResult = activeMatchId
    ? result.results.find((r) => r.matchId === activeMatchId)
    : undefined;

  const showScore = step?.kind === 'match-score' || step?.kind === 'match-verdict';
  const showOutcome = step?.kind === 'match-verdict';

  const spotlightA = activeMatch
    ? findCompetitor(result, requireCompetitorId(activeMatch.a, `match ${activeMatch.id} side a`))
    : null;
  const spotlightB = activeMatch
    ? findCompetitor(result, requireCompetitorId(activeMatch.b, `match ${activeMatch.id} side b`))
    : null;

  const finalResult = showChampion
    ? result.results.find((r) => r.matchId === result.bracket.finalMatchId)
    : undefined;
  const championFinalScore = finalResult
    ? finalResult.winnerId === finalResult.aId
      ? finalResult.scoreA.total
      : finalResult.scoreB.total
    : undefined;

  return (
    <div className="relative flex h-full flex-col gap-4">
      {showRoundBanner && step && (
        <div
          key={step.id}
          className="eyebrow px-1"
          style={{ transition: 'opacity 500ms ease-out, transform 500ms ease-out' }}
        >
          {result.bracket.rounds[step.round].name}
        </div>
      )}

      <div className="relative flex-1 overflow-auto flex flex-col lg:justify-center">
        <BracketCanvas
          bracket={result.bracket}
          resolved={state.resolved}
          activeRound={activeRound}
          onActiveRoundChange={setActiveRound}
          dimmed={dimmed}
          activeMatchId={activeMatchId}
          advancingMatchId={advancingMatchId}
          reducedMotion={reducedMotion}
        />

        {spotlightA && spotlightB && (
          <SpotlightHud
            open={hudOpen}
            a={spotlightA}
            b={spotlightB}
            scoreA={showScore ? trueResult?.scoreA : undefined}
            scoreB={showScore ? trueResult?.scoreB : undefined}
            outcome={
              showOutcome && trueResult
                ? { winnerId: trueResult.winnerId, loserId: trueResult.loserId }
                : undefined
            }
            animate={animate}
            blindJudging={blindJudging}
            judges={judges}
            seedA={seedOf(result, activeMatch?.a ?? null)}
            seedB={seedOf(result, activeMatch?.b ?? null)}
          />
        )}

        {showChampion && !championDismissed && (
          <div
            data-testid="champion-overlay"
            className="fixed inset-0 z-40 flex items-center justify-center pointer-events-none"
          >
            <div className="absolute inset-0 bg-ink/25 backdrop-blur-[2px]" aria-hidden="true" />
            <div className="relative mx-4 w-full max-w-md rounded-[3px] border border-rule bg-paper pointer-events-auto">
              <button
                type="button"
                onClick={() => setChampionDismissed(true)}
                aria-label="Close champion card"
                title="Close - browse other fixtures"
                className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-[2px] text-ink-soft hover:text-ink border border-transparent hover:border-rule transition-colors duration-200"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                  <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" />
                </svg>
              </button>
              <ChampionBanner
                champion={findCompetitor(result, result.championId)}
                runnerUp={findCompetitor(result, result.runnerUpId)}
                finalScore={championFinalScore}
              />
            </div>
          </div>
        )}
      </div>

      {/* Absolute to the arena (not viewport) so it clears the TopBar "New résumé" CTA. */}
      {showChampion && championDismissed && (
        <button
          type="button"
          data-testid="show-champion-button"
          onClick={() => setChampionDismissed(false)}
          aria-label="Show champion card"
          title="Show champion card"
          className="absolute right-4 top-4 z-40 font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink border border-rule hover:border-ink-faint bg-paper px-2.5 py-1 rounded-[2px] transition-colors duration-200"
        >
          Show champion
        </button>
      )}

      {/* z-50 keeps transport above fixed spotlight/champion overlays (z-40). */}
      <div className="relative z-50 shrink-0 bg-paper pt-2 pb-1">
        {hudVisible ? (
          <PlaybackBar
            status={state.status}
            matchSeconds={matchSeconds}
            progressRef={state.progressRef}
            onTogglePlay={controls.toggle}
            onSetMatchSeconds={handleSetMatchSeconds}
            onSkipToEnd={handleSkip}
            onReplay={onReplay}
            onHideHud={() => setHudVisible(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setHudVisible(true)}
            aria-label="Show HUD"
            title="Show HUD"
            className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft hover:text-ink border border-rule hover:border-ink-faint px-2.5 py-1 rounded-[2px] transition-colors duration-200"
          >
            Show HUD
          </button>
        )}
      </div>
    </div>
  );
}
