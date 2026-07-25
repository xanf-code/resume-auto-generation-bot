import { BULLET_SHAPES, toggleShape, type BulletShape } from '../../lib/bulletShapes';
import { HelpTip } from './HelpTip';

interface Props {
  shapes: BulletShape[];
  onChange: (shapes: BulletShape[]) => void;
}

export function BulletShapeControls({ shapes, onChange }: Props) {
  return (
    <div data-testid="bullet-shape-controls" className="flex flex-col gap-2.5">
      <span className="eyebrow">Bullet shapes</span>
      <p className="text-[12px] text-ink-soft leading-snug">
        Leave all unchecked to rotate shapes automatically.
      </p>
      {BULLET_SHAPES.map((shape) => (
        <label
          key={shape.name}
          className="flex items-center gap-2 text-[13px] text-ink-soft cursor-pointer select-none"
        >
          <input
            type="checkbox"
            checked={shapes.includes(shape.name)}
            onChange={() => onChange(toggleShape(shapes, shape.name))}
            className="accent-[#c0362c] w-4 h-4 shrink-0"
          />
          <span>{shape.label}</span>
          <HelpTip text={shape.help} label={shape.label} />
        </label>
      ))}
    </div>
  );
}
