import React from 'react';
import type { Rect } from '../../lib/ab/layout';

export type CompetitorSlotState = 'pending' | 'idle' | 'active' | 'won' | 'lost';

export interface CompetitorSlotSide {
  seed?: number;
  label?: string;
  score?: number;
  state: CompetitorSlotState; // per-side: which side is winning/lost/pending
}

interface Props {
  rect: Rect; // absolute position within the canvas, from bracketGeometry
  top: CompetitorSlotSide;
  bottom: CompetitorSlotSide;
  dataMatchId?: string; // for test/debug querying, e.g. `data-match-id`
}

const STATE_CLASS: Record<CompetitorSlotState, string> = {
  won: 'text-ink',
  lost: 'text-ink-faint opacity-60',
  active: 'text-ink-soft',
  idle: 'text-ink-soft',
  pending: 'text-ink-soft',
};

/** One row of a match cell: seed, label (or TBD placeholder), score. */
function CompetitorRow({ side }: { side: CompetitorSlotSide }) {
  const { seed, label, score, state } = side;
  const unresolved = label === undefined;

  return (
    <div
      className={`flex items-center gap-1.5 h-[26px] px-2 ${STATE_CLASS[state]}`}
      data-state={state}
    >
      <span className="font-mono text-[10px] text-ink-faint shrink-0 w-3 text-right">
        {seed ?? ''}
      </span>
      <span className={`font-serif text-[13px] truncate flex-1 ${unresolved ? 'text-ink-faint' : ''}`}>
        {unresolved ? 'TBD' : label}
      </span>
      <span className="font-mono text-[12px] tabular-nums shrink-0">
        {score === undefined ? '—' : score}
      </span>
    </div>
  );
}

function CompetitorSlotImpl({ rect, top, bottom, dataMatchId }: Props) {
  return (
    <div
      className="absolute bg-paper-raised border border-rule rounded-[2px] overflow-hidden"
      style={{ left: rect.x, top: rect.y, width: rect.width, height: rect.height }}
      data-match-id={dataMatchId}
    >
      <CompetitorRow side={top} />
      <div className="border-t border-rule" />
      <CompetitorRow side={bottom} />
    </div>
  );
}

export const CompetitorSlot = React.memo(CompetitorSlotImpl);
