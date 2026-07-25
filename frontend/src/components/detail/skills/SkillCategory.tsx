import { CopyButton } from './CopyButton';

interface Props {
  name: string;
  skills: string[];
}

export function SkillCategory({ name, skills }: Props) {
  // The extractor can surface the same skill twice (or under two categories);
  // dedupe so React keys stay unique and the copied string doesn't repeat.
  // Order-preserving.
  const unique = Array.from(new Set(skills));
  const joined = unique.join(', ');

  if (unique.length === 0) return null;

  return (
    <div className="mb-4 pb-4 border-b border-rule last:border-b-0">
      <div className="flex items-center justify-between mb-2">
        <span className="font-serif text-[14px] text-ink">{name}</span>
        <CopyButton text={joined} />
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {unique.map((skill) => (
          <li
            key={skill}
            className="text-[11px] font-mono text-ink-soft bg-paper-raised border border-rule px-2 py-0.5 rounded-[2px]"
          >
            {skill}
          </li>
        ))}
      </ul>
    </div>
  );
}
