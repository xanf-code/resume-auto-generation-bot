import { AggregateGauge } from '../loader/AggregateGauge';
import type { Competitor } from '../../lib/ab/types';

interface Props {
  champion: Competitor;
  runnerUp: Competitor;
  finalScore?: number; // champion's final total, 0-100, from the final MatchResult's winning side
}

/** Climactic reveal panel shown once the bracket resolves: the champion's name in
 * oversized display type, its aggregate gauge, and a note on who it beat in the
 * final. Fixture champions carry the same origin tag `RosterPicker` uses so an
 * invented résumé can never be mistaken for one of the user's own. */
export function ChampionBanner({ champion, runnerUp, finalScore }: Props) {
  return (
    <div className="flex flex-col items-center gap-5 py-12 px-6 text-center">
      <span className="eyebrow">Champion</span>

      <div className="flex flex-col items-center gap-2">
        {champion.origin === 'fixture' && (
          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">
            fixture
          </span>
        )}
        <h2 className="max-w-2xl font-serif text-[40px] leading-tight text-ink break-words sm:text-[56px]">
          {champion.label}
        </h2>
      </div>

      <AggregateGauge score={finalScore} />

      <p className="text-[14px] text-ink-soft">
        Defeated <span className="text-ink">{runnerUp.label}</span> in the final
      </p>
    </div>
  );
}
