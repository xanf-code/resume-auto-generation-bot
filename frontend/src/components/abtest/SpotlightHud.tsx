import type { Competitor, MatchScore } from '../../lib/ab/types';
import { HeadToHeadScore } from './HeadToHeadScore';

interface SpotlightOutcome {
  winnerId: string;
  loserId: string;
}

interface Props {
  open: boolean; // whether the HUD is currently shown (match-focus through match-verdict steps)
  a: Competitor; // side A (top slot)
  b: Competitor; // side B (bottom slot)
  scoreA?: MatchScore;
  scoreB?: MatchScore;
  outcome?: SpotlightOutcome; // undefined until the verdict lands
  animate: boolean; // false under reduced motion / skip-to-end
  blindJudging: boolean; // from AbConfig.blindJudging
  seedA?: number; // bracket seed for side A, positional in Bracket.competitors - not part of Competitor itself
  seedB?: number; // bracket seed for side B
}

function sideOutcome(
  outcome: SpotlightOutcome | undefined,
  competitorId: string,
): 'won' | 'lost' | undefined {
  if (!outcome) return undefined;
  return outcome.winnerId === competitorId ? 'won' : 'lost';
}

/**
 * Full-bleed spotlight overlay shown while a single bracket match is in
 * focus (`match-focus` through `match-verdict` timeline steps). Dims the
 * bracket behind a blurred scrim and surfaces both competitors' live scores
 * side by side via two `HeadToHeadScore` panels.
 *
 * Mounting is fully owned by the caller through `open` - this component does
 * not orchestrate its own enter/exit beyond the opacity fade driven by
 * `animate` (reduced motion / skip-to-end already collapse transitions
 * globally, see index.css:94-103). It is a non-interactive spectator
 * overlay - not a form modal - so it carries `aria-live="polite"` on the
 * panel (announcing label/score reveals as they land) rather than
 * `role="dialog"`, which would imply a focus-trapped, user-dismissable
 * modal that this is not.
 */
export function SpotlightHud({
  open,
  a,
  b,
  scoreA,
  scoreB,
  outcome,
  animate,
  blindJudging,
  seedA,
  seedB,
}: Props) {
  if (!open) return null;

  return (
    <div
      data-testid="spotlight-hud"
      className="fixed inset-0 z-40 flex items-center justify-center pointer-events-none"
      style={{ transition: animate ? 'opacity 240ms ease-out' : 'none' }}
    >
      <div className="absolute inset-0 bg-ink/25 backdrop-blur-[2px]" aria-hidden="true" />

      <div
        aria-live="polite"
        data-testid="spotlight-hud-panel"
        className="relative bg-paper border border-rule rounded-[3px] w-full max-w-md mx-4 px-6 py-6 flex flex-col gap-5"
      >
        <HeadToHeadScore
          label={a.label}
          seed={seedA}
          score={scoreA}
          outcome={sideOutcome(outcome, a.id)}
          animate={animate}
          masked={blindJudging}
        />

        <div className="border-t border-rule" aria-hidden="true" />

        <HeadToHeadScore
          label={b.label}
          seed={seedB}
          score={scoreB}
          outcome={sideOutcome(outcome, b.id)}
          animate={animate}
          masked={blindJudging}
        />
      </div>
    </div>
  );
}
