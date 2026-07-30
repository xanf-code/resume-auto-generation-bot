import { memo } from 'react';
import type { ConnectorGeometry } from '../../lib/ab/layout';

export interface ConnectorState {
  round: number;
  index: number;
  drawn: boolean; // this phase: always effectively true for every resolved match; a later phase wires this to playback.
}

interface Props {
  canvasWidth: number;
  canvasHeight: number;
  connectors: ConnectorGeometry[];
  drawnStates?: ConnectorState[];
}

/**
 * Renders the bracket's elbow connectors as a single absolutely-positioned
 * SVG overlay, sized to the exact canvas box. Uses explicit numeric
 * width/height + a matching viewBox (never width="100%") so the SVG never
 * scales independently of the absolutely-positioned HTML slots elsewhere in
 * the canvas - fractional-width scaling would drift the elbows off the cards.
 *
 * This phase only renders fully-drawn paths; `drawnStates` is accepted for
 * a later playback phase but defaults every connector to drawn.
 */
function BracketConnectorsImpl({ canvasWidth, canvasHeight, connectors, drawnStates }: Props) {
  return (
    <svg
      width={canvasWidth}
      height={canvasHeight}
      viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
      className="absolute inset-0 pointer-events-none"
      shapeRendering="geometricPrecision"
      aria-hidden="true"
    >
      {connectors.map((c) => {
        const drawn =
          drawnStates?.find((s) => s.round === c.round && s.index === c.index)?.drawn ?? true;
        return (
          <path
            key={`r${c.round}-m${c.index}`}
            d={c.d}
            strokeDasharray={c.length}
            strokeDashoffset={drawn ? 0 : c.length}
            stroke="var(--color-rule)"
            fill="none"
            strokeWidth={1.5}
            style={{ transition: 'stroke-dashoffset 620ms ease-out' }}
          />
        );
      })}
    </svg>
  );
}

export const BracketConnectors = memo(BracketConnectorsImpl);
